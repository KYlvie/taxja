"""
Document Pipeline Orchestrator — AI dispatch layer for document processing.

Orchestrates the full document processing pipeline:
  Upload → Classify → Extract → Validate+AutoFix → AutoCreate → Notify user

Design principles — "傻瓜操作" (zero-friction for the user):
  - User uploads a photo/PDF → system does EVERYTHING automatically
  - Auto-correct what can be fixed (negative amounts, bad dates, missing fields)
  - Auto-create transactions, properties, recurring income — all document types
  - User sees the RESULT, not questions. Can edit/undo if wrong.
  - Only flag needs_review when data is truly unusable (no amount, no OCR text)
  - All decisions logged with confidence scores for auditability
"""
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.document import Document, DocumentType as DBDocumentType
from app.services.document_classifier import DocumentClassifier, DocumentType as OCRDocumentType
from app.services.ocr_engine import OCREngine, OCRResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pipeline stage results
# ---------------------------------------------------------------------------

class PipelineStage(str, Enum):
    CLASSIFY = "classify"
    EXTRACT = "extract"
    VALIDATE = "validate"
    SUGGEST = "suggest"


class ConfidenceLevel(str, Enum):
    HIGH = "high"        # >= 0.8 — auto-proceed
    MEDIUM = "medium"    # 0.5–0.8 — proceed but flag for review
    LOW = "low"          # < 0.5 — require manual review


@dataclass
class ClassificationResult:
    """Result of document classification stage."""
    document_type: str
    confidence: float
    method: str  # "regex", "llm", "filename", "combined"
    alternatives: List[Dict[str, Any]] = field(default_factory=list)
    needs_llm_arbitration: bool = False


@dataclass
class ValidationIssue:
    """A single validation problem found in extracted data."""
    field: str
    issue: str
    severity: str  # "error", "warning", "info"
    suggestion: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of cross-field validation."""
    is_valid: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    corrected_fields: Dict[str, Any] = field(default_factory=dict)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")


@dataclass
class PipelineResult:
    """Complete result of the document processing pipeline."""
    document_id: int
    stage_reached: PipelineStage = PipelineStage.CLASSIFY
    classification: Optional[ClassificationResult] = None
    extracted_data: Optional[Dict[str, Any]] = None
    raw_text: Optional[str] = None
    validation: Optional[ValidationResult] = None
    suggestions: List[Dict[str, Any]] = field(default_factory=list)
    needs_review: bool = True
    confidence_level: ConfidenceLevel = ConfidenceLevel.LOW
    processing_time_ms: float = 0.0
    audit_log: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def user_message(self) -> str:
        """Generate a user-friendly notification message."""
        if self.error:
            return "Dokument konnte nicht verarbeitet werden. Bitte erneut hochladen."

        auto_created = [s for s in self.suggestions if s.get("status") == "auto-created"]
        if not auto_created:
            if self.needs_review:
                return "Dokument verarbeitet. Bitte überprüfen."
            return "Dokument verarbeitet."

        parts = []
        for s in auto_created:
            if s.get("type") == "create_property":
                parts.append("Immobilie angelegt")
            elif s.get("type") == "create_recurring_income":
                parts.append("Mieteinnahme angelegt")
            elif s.get("transaction_id"):
                amt = s.get("amount", "?")
                desc = s.get("description", "")
                deductible = " (absetzbar)" if s.get("is_deductible") else ""
                parts.append(f"€{amt} {desc}{deductible}")

        if parts:
            return "Automatisch erstellt: " + "; ".join(parts)
        return "Dokument verarbeitet."

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "document_id": self.document_id,
            "stage_reached": self.stage_reached.value,
            "extracted_data": self.extracted_data or {},
            "raw_text": self.raw_text or "",
            "needs_review": self.needs_review,
            "confidence_level": self.confidence_level.value,
            "processing_time_ms": self.processing_time_ms,
            "suggestions": self.suggestions,
            "error": self.error,
            "user_message": self.user_message,
        }
        if self.classification:
            result["classification"] = asdict(self.classification)
        if self.validation:
            result["validation"] = {
                "is_valid": self.validation.is_valid,
                "issues": [asdict(i) for i in self.validation.issues],
                "corrected_fields": self.validation.corrected_fields,
            }
        result["audit_log"] = self.audit_log
        return result


# ---------------------------------------------------------------------------
# Type mapping
# ---------------------------------------------------------------------------

OCR_TO_DB_TYPE_MAP = {
    OCRDocumentType.KAUFVERTRAG: DBDocumentType.PURCHASE_CONTRACT,
    OCRDocumentType.MIETVERTRAG: DBDocumentType.RENTAL_CONTRACT,
    OCRDocumentType.RENTAL_CONTRACT: DBDocumentType.RENTAL_CONTRACT,
    OCRDocumentType.E1_FORM: DBDocumentType.E1_FORM,
    OCRDocumentType.EINKOMMENSTEUERBESCHEID: DBDocumentType.EINKOMMENSTEUERBESCHEID,
    OCRDocumentType.UNKNOWN: DBDocumentType.OTHER,
}

# Auto-create confidence thresholds — below this, still create but mark needs_review
# These are intentionally LOW because the philosophy is "do it, let user fix later"
AUTO_CREATE_THRESHOLDS = {
    DBDocumentType.PURCHASE_CONTRACT: 0.4,   # Kaufvertrag: auto-create property
    DBDocumentType.RENTAL_CONTRACT: 0.4,     # Mietvertrag: auto-create recurring
    DBDocumentType.E1_FORM: 0.4,
    DBDocumentType.EINKOMMENSTEUERBESCHEID: 0.4,
    DBDocumentType.RECEIPT: 0.3,
    DBDocumentType.INVOICE: 0.3,
}
DEFAULT_AUTO_CREATE_THRESHOLD = 0.3

# Keep backward compat for tests
CONFIRMATION_REQUIRED_TYPES = set()  # Empty — nothing requires confirmation anymore
CONFIDENCE_THRESHOLDS = AUTO_CREATE_THRESHOLDS
DEFAULT_CONFIDENCE_THRESHOLD = DEFAULT_AUTO_CREATE_THRESHOLD


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class DocumentPipelineOrchestrator:
    """
    Central orchestrator for the document processing pipeline.

    Coordinates: OCR → Classification → Extraction → Validate+AutoFix → AutoCreate
    Philosophy: do everything automatically, let user edit/undo later.
    """

    def __init__(self, db: Session):
        self.db = db
        self.ocr_engine = OCREngine()
        self.classifier = DocumentClassifier()

    # ---- Main entry point ----

    def process_document(self, document_id: int) -> PipelineResult:
        """
        Process a document through the full auto pipeline.

        Steps:
          1. OCR + Classification (regex → filename → LLM)
          2. Extraction (specialized extractor or LLM)
          3. Validate + auto-fix (negative→abs, missing date→today, etc.)
          4. Auto-create records (transactions, properties, recurring income)
          5. Persist results → user sees notification, not questions

        needs_review is ONLY set when data is truly unusable.
        """
        start_time = datetime.utcnow()
        result = PipelineResult(document_id=document_id)

        try:
            # Load document
            document = self.db.query(Document).filter(Document.id == document_id).first()
            if not document:
                result.error = f"Document {document_id} not found"
                return result

            # Stage 1: OCR + Classification
            ocr_result = self._stage_ocr(document, result)
            if ocr_result is None:
                result.stage_reached = PipelineStage.CLASSIFY
                return self._finalize(result, document, start_time)

            # Stage 2: Classification arbitration
            db_type = self._stage_classify(document, ocr_result, result)

            # Stage 3: Extraction is already done by OCR engine
            result.extracted_data = ocr_result.extracted_data
            result.raw_text = ocr_result.raw_text
            result.stage_reached = PipelineStage.EXTRACT
            self._log_audit(result, "extract", f"Extracted {len(ocr_result.extracted_data)} fields")

            # Stage 4: Validate + auto-fix
            validation = self._stage_validate(db_type, ocr_result.extracted_data, result)
            if validation.corrected_fields:
                result.extracted_data.update(validation.corrected_fields)
                self._log_audit(
                    result, "autofix",
                    f"Auto-corrected {len(validation.corrected_fields)} field(s): "
                    f"{list(validation.corrected_fields.keys())}"
                )

            # Stage 5: Build suggestions AND auto-create
            self._stage_suggest(document, db_type, ocr_result, result)

            # Determine overall confidence
            result.confidence_level = self._assess_confidence(
                ocr_result.confidence_score, db_type, validation
            )

            # needs_review ONLY when data is truly unusable
            result.needs_review = (
                result.confidence_level == ConfidenceLevel.LOW
                and validation.error_count > 0
            )

            return self._finalize(result, document, start_time)

        except Exception as e:
            logger.error(f"Pipeline failed for document {document_id}: {e}", exc_info=True)
            result.error = str(e)
            result.stage_reached = PipelineStage.CLASSIFY
            return self._finalize(result, document if 'document' in dir() else None, start_time)

    # ---- Stage 1: OCR ----

    def _stage_ocr(self, document: Document, result: PipelineResult) -> Optional[OCRResult]:
        """Run OCR engine on the document."""
        from app.services.storage_service import StorageService

        storage = StorageService()
        try:
            image_bytes = storage.download_file(document.file_path)
        except Exception as e:
            result.error = f"Failed to download file: {e}"
            self._log_audit(result, "ocr", f"Download failed: {e}")
            return None

        ocr_result = self.ocr_engine.process_document(image_bytes, mime_type=document.mime_type)
        self._log_audit(
            result, "ocr",
            f"OCR completed: confidence={ocr_result.confidence_score:.2f}, "
            f"type={ocr_result.document_type.value}"
        )
        return ocr_result

    # ---- Stage 2: Classification arbitration ----

    def _stage_classify(
        self, document: Document, ocr_result: OCRResult, result: PipelineResult
    ) -> DBDocumentType:
        """
        Classify document type with multi-signal arbitration.

        Priority:
          1. OCR engine classification (regex patterns)
          2. Filename hints (if OCR confidence is low)
          3. LLM classification (if still ambiguous and LLM available)
        """
        ocr_type = ocr_result.document_type
        ocr_confidence = ocr_result.confidence_score

        classification = ClassificationResult(
            document_type=ocr_type.value,
            confidence=ocr_confidence,
            method="regex",
        )

        # Map OCR type to DB type
        if ocr_type in OCR_TO_DB_TYPE_MAP:
            db_type = OCR_TO_DB_TYPE_MAP[ocr_type]
        else:
            try:
                db_type = DBDocumentType[ocr_type.name]
            except KeyError:
                db_type = DBDocumentType.OTHER

        # Signal 2: Filename boost when OCR classification is weak
        if db_type == DBDocumentType.OTHER or ocr_confidence < 0.5:
            filename_type = self._classify_by_filename(document.file_name)
            if filename_type and filename_type != DBDocumentType.OTHER:
                self._log_audit(
                    result, "classify",
                    f"Filename override: {db_type.value} → {filename_type.value} "
                    f"(OCR confidence was {ocr_confidence:.2f})"
                )
                db_type = filename_type
                classification.method = "filename"
                classification.confidence = max(ocr_confidence, 0.6)

        # Signal 3: LLM arbitration when still uncertain
        if db_type == DBDocumentType.OTHER and ocr_result.raw_text:
            llm_type = self._try_llm_classification(ocr_result.raw_text)
            if llm_type and llm_type != DBDocumentType.OTHER:
                self._log_audit(
                    result, "classify",
                    f"LLM classification: {db_type.value} → {llm_type.value}"
                )
                db_type = llm_type
                classification.method = "llm"
                classification.needs_llm_arbitration = True
                classification.confidence = 0.65  # LLM classification is less trusted

        # Persist classification
        document.document_type = db_type
        classification.document_type = db_type.value
        result.classification = classification
        result.stage_reached = PipelineStage.CLASSIFY

        self._log_audit(
            result, "classify",
            f"Final type={db_type.value}, confidence={classification.confidence:.2f}, "
            f"method={classification.method}"
        )

        return db_type

    def _classify_by_filename(self, file_name: Optional[str]) -> Optional[DBDocumentType]:
        """Classify document type by filename hints."""
        if not file_name:
            return None

        fname_lower = file_name.lower()
        filename_hints = {
            "kaufvertrag": DBDocumentType.PURCHASE_CONTRACT,
            "mietvertrag": DBDocumentType.RENTAL_CONTRACT,
            "miete": DBDocumentType.RENTAL_CONTRACT,
            "pacht": DBDocumentType.RENTAL_CONTRACT,
            "gehalt": DBDocumentType.LOHNZETTEL,
            "lohn": DBDocumentType.LOHNZETTEL,
            "rechnung": DBDocumentType.INVOICE,
            "invoice": DBDocumentType.INVOICE,
            "beleg": DBDocumentType.RECEIPT,
            "receipt": DBDocumentType.RECEIPT,
            "bon": DBDocumentType.RECEIPT,
            "svs": DBDocumentType.SVS_NOTICE,
            "kontoauszug": DBDocumentType.BANK_STATEMENT,
            "e1": DBDocumentType.E1_FORM,
            "einkommensteuererkl": DBDocumentType.E1_FORM,
            "bescheid": DBDocumentType.EINKOMMENSTEUERBESCHEID,
        }

        for hint, doc_type in filename_hints.items():
            if hint in fname_lower:
                return doc_type
        return None

    def _try_llm_classification(self, raw_text: str) -> Optional[DBDocumentType]:
        """Use LLM as fallback for document classification."""
        try:
            from app.services.llm_extractor import get_llm_extractor
            extractor = get_llm_extractor()
            if not extractor.is_available:
                return None

            llm_type_str = extractor.classify_document(raw_text)
            if not llm_type_str:
                return None

            # Map LLM response to DB type
            llm_type_map = {
                "invoice": DBDocumentType.INVOICE,
                "receipt": DBDocumentType.RECEIPT,
                "mietvertrag": DBDocumentType.RENTAL_CONTRACT,
                "kaufvertrag": DBDocumentType.PURCHASE_CONTRACT,
                "e1_form": DBDocumentType.E1_FORM,
                "einkommensteuerbescheid": DBDocumentType.EINKOMMENSTEUERBESCHEID,
                "bank_statement": DBDocumentType.BANK_STATEMENT,
                "payslip": DBDocumentType.PAYSLIP,
                "lohnzettel": DBDocumentType.LOHNZETTEL,
            }
            return llm_type_map.get(llm_type_str)

        except Exception as e:
            logger.warning(f"LLM classification failed: {e}")
            return None

    # ---- Stage 4: Cross-field validation ----

    def _stage_validate(
        self, db_type: DBDocumentType, extracted_data: Dict[str, Any],
        result: PipelineResult,
    ) -> ValidationResult:
        """
        Validate + auto-fix extracted data.

        Philosophy: FIX what can be fixed, only ERROR when data is truly unusable.
        Auto-corrections are stored in validation.corrected_fields.
        """
        validation = ValidationResult(is_valid=True)

        if not extracted_data:
            validation.is_valid = False
            validation.issues.append(ValidationIssue(
                field="*", issue="No data extracted", severity="error"
            ))
            result.validation = validation
            return validation

        # Auto-fix + validate common fields
        self._autofix_amount(extracted_data, validation)
        self._autofix_date(extracted_data, validation)
        self._autofix_missing_fields(extracted_data, db_type, validation)

        # Type-specific validations (mostly informational now)
        validators = {
            DBDocumentType.INVOICE: self._validate_invoice,
            DBDocumentType.RECEIPT: self._validate_receipt,
            DBDocumentType.PURCHASE_CONTRACT: self._validate_kaufvertrag,
            DBDocumentType.RENTAL_CONTRACT: self._validate_mietvertrag,
        }
        validator = validators.get(db_type)
        if validator:
            validator(extracted_data, validation)

        validation.is_valid = validation.error_count == 0
        result.validation = validation
        result.stage_reached = PipelineStage.VALIDATE

        self._log_audit(
            result, "validate",
            f"Validation: valid={validation.is_valid}, "
            f"errors={validation.error_count}, warnings={validation.warning_count}, "
            f"auto-fixed={len(validation.corrected_fields)}"
        )

        return validation

    def _autofix_amount(self, data: Dict[str, Any], validation: ValidationResult):
        """Auto-fix amount fields: negative→abs, invalid→remove."""
        for field_name in ("amount", "purchase_price", "monthly_rent"):
            value = data.get(field_name)
            if value is None:
                continue
            try:
                amount = float(value)
                if amount < 0:
                    # Auto-fix: take absolute value
                    fixed = abs(amount)
                    validation.corrected_fields[field_name] = fixed
                    validation.issues.append(ValidationIssue(
                        field=field_name,
                        issue=f"Auto-corrected negative amount {amount} → {fixed}",
                        severity="info",
                    ))
                # Zero is OK — might be a free item or zero-cost document
            except (ValueError, TypeError):
                # Can't parse at all — this IS an error, can't auto-fix
                validation.issues.append(ValidationIssue(
                    field=field_name,
                    issue=f"Invalid amount value: {value}",
                    severity="error",
                ))

    def _autofix_date(self, data: Dict[str, Any], validation: ValidationResult):
        """Auto-fix date fields: unparseable→today, future→today."""
        for field_name in ("date", "purchase_date", "start_date"):
            value = data.get(field_name)
            if value is None:
                continue

            parsed_date = None
            if isinstance(value, (date, datetime)):
                parsed_date = value if isinstance(value, date) else value.date()
            elif isinstance(value, str):
                for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%Y-%m-%dT%H:%M:%S"):
                    try:
                        parsed_date = datetime.strptime(value, fmt).date()
                        break
                    except ValueError:
                        continue

            if parsed_date is None:
                # Auto-fix: use today
                today = date.today()
                validation.corrected_fields[field_name] = today.isoformat()
                validation.issues.append(ValidationIssue(
                    field=field_name,
                    issue=f"Cannot parse date '{value}', auto-set to {today}",
                    severity="info",
                ))
                continue

            # Future date → keep it (might be a contract start date)
            if parsed_date > date.today():
                validation.issues.append(ValidationIssue(
                    field=field_name,
                    issue=f"Date is in the future: {parsed_date}",
                    severity="info",
                ))

            # Very old date → keep but note
            if parsed_date.year < 2000:
                validation.issues.append(ValidationIssue(
                    field=field_name,
                    issue=f"Date seems old: {parsed_date}",
                    severity="info",
                ))

    def _autofix_missing_fields(
        self, data: Dict[str, Any], db_type: DBDocumentType,
        validation: ValidationResult,
    ):
        """Fill in smart defaults for missing fields so auto-create can proceed."""
        # Missing date → today
        if not data.get("date") and "date" not in validation.corrected_fields:
            today = date.today().isoformat()
            validation.corrected_fields["date"] = today
            validation.issues.append(ValidationIssue(
                field="date", issue=f"No date found, auto-set to {today}", severity="info",
            ))

        # Missing merchant → "Unbekannt"
        if db_type in (DBDocumentType.RECEIPT, DBDocumentType.INVOICE):
            if not data.get("merchant") and not data.get("supplier"):
                validation.corrected_fields["merchant"] = "Unbekannt"
                validation.issues.append(ValidationIssue(
                    field="merchant",
                    issue="No merchant found, auto-set to 'Unbekannt'",
                    severity="info",
                ))

        # Kaufvertrag: missing address → "Adresse nicht erkannt"
        if db_type == DBDocumentType.PURCHASE_CONTRACT:
            if not data.get("property_address"):
                validation.corrected_fields["property_address"] = "Adresse nicht erkannt"
                validation.issues.append(ValidationIssue(
                    field="property_address",
                    issue="No property address found, auto-set placeholder",
                    severity="info",
                ))

        # Mietvertrag: missing address → "Adresse nicht erkannt"
        if db_type == DBDocumentType.RENTAL_CONTRACT:
            if not data.get("property_address"):
                validation.corrected_fields["property_address"] = "Adresse nicht erkannt"
                validation.issues.append(ValidationIssue(
                    field="property_address",
                    issue="No property address found, auto-set placeholder",
                    severity="info",
                ))

    def _validate_invoice(self, data: Dict[str, Any], validation: ValidationResult):
        """Validate invoice-specific fields. Auto-fix VAT when possible."""
        amount = data.get("amount")
        vat_amount = data.get("vat_amount")
        vat_rate = data.get("vat_rate")

        # If VAT rate is known but VAT amount is missing, calculate it
        if amount and vat_rate and not vat_amount:
            try:
                amt = float(amount)
                rate = float(vat_rate) / 100.0
                calculated_vat = round(amt * rate / (1 + rate), 2)
                validation.corrected_fields["vat_amount"] = calculated_vat
                validation.issues.append(ValidationIssue(
                    field="vat_amount",
                    issue=f"Auto-calculated VAT: €{calculated_vat:.2f} ({vat_rate}%)",
                    severity="info",
                ))
            except (ValueError, TypeError):
                pass
        elif amount and vat_amount and vat_rate:
            # Check consistency
            try:
                amt = float(amount)
                vat = float(vat_amount)
                rate = float(vat_rate) / 100.0
                expected_vat = amt * rate / (1 + rate)
                diff = abs(vat - expected_vat)
                if diff > 1.0:
                    # Auto-fix: recalculate VAT from amount and rate
                    fixed_vat = round(expected_vat, 2)
                    validation.corrected_fields["vat_amount"] = fixed_vat
                    validation.issues.append(ValidationIssue(
                        field="vat_amount",
                        issue=f"VAT mismatch, auto-corrected {vat:.2f} → {fixed_vat:.2f}",
                        severity="info",
                    ))
            except (ValueError, TypeError):
                pass

        # If no VAT rate, default to Austrian standard 20%
        if amount and not vat_rate:
            validation.corrected_fields["vat_rate"] = 20
            try:
                amt = float(amount)
                calculated_vat = round(amt * 0.2 / 1.2, 2)
                if not vat_amount:
                    validation.corrected_fields["vat_amount"] = calculated_vat
                validation.issues.append(ValidationIssue(
                    field="vat_rate",
                    issue="No VAT rate found, auto-set to 20% (Austrian standard)",
                    severity="info",
                ))
            except (ValueError, TypeError):
                pass

    def _validate_receipt(self, data: Dict[str, Any], validation: ValidationResult):
        """Validate receipt-specific fields."""
        if not data.get("amount"):
            # Try to compute from line items
            line_items = data.get("line_items", [])
            if line_items:
                try:
                    items_total = sum(
                        float(item.get("amount") or item.get("price") or 0)
                        for item in line_items
                    )
                    if items_total > 0:
                        validation.corrected_fields["amount"] = round(items_total, 2)
                        validation.issues.append(ValidationIssue(
                            field="amount",
                            issue=f"No total found, auto-calculated from line items: €{items_total:.2f}",
                            severity="info",
                        ))
                        return
                except (ValueError, TypeError):
                    pass

            # No amount and no line items → genuine error
            validation.issues.append(ValidationIssue(
                field="amount",
                issue="Receipt has no total amount and no line items",
                severity="error",
            ))
            return

        # Line items sum check (informational only)
        line_items = data.get("line_items", [])
        if line_items and data.get("amount"):
            try:
                items_total = sum(
                    float(item.get("amount") or item.get("price") or 0)
                    for item in line_items
                )
                total = float(data["amount"])
                diff = abs(items_total - total)
                if items_total > 0 and diff > 2.0:
                    validation.issues.append(ValidationIssue(
                        field="line_items",
                        issue=f"Line items sum ({items_total:.2f}) differs from "
                              f"total ({total:.2f}) by {diff:.2f}",
                        severity="info",
                    ))
            except (ValueError, TypeError):
                pass

    def _validate_kaufvertrag(self, data: Dict[str, Any], validation: ValidationResult):
        """Validate Kaufvertrag-specific fields. Auto-fill where possible."""
        if not data.get("purchase_price"):
            # This is a genuine error — can't create property without price
            validation.issues.append(ValidationIssue(
                field="purchase_price",
                issue="No purchase price found",
                severity="error",
            ))

        # Building + land values: auto-calculate if one is missing
        building = data.get("building_value")
        land = data.get("land_value")
        price = data.get("purchase_price")
        if price:
            try:
                p = float(price)
                if building and not land:
                    # Auto-calculate land value
                    b = float(building)
                    calculated_land = max(0, p - b)
                    validation.corrected_fields["land_value"] = calculated_land
                    validation.issues.append(ValidationIssue(
                        field="land_value",
                        issue=f"Auto-calculated land value: €{calculated_land:.0f}",
                        severity="info",
                    ))
                elif land and not building:
                    # Auto-calculate building value
                    l = float(land)
                    calculated_building = max(0, p - l)
                    validation.corrected_fields["building_value"] = calculated_building
                    validation.issues.append(ValidationIssue(
                        field="building_value",
                        issue=f"Auto-calculated building value: €{calculated_building:.0f}",
                        severity="info",
                    ))
                elif not building and not land:
                    # Use Austrian default split: 70% building, 30% land
                    b = round(p * 0.7, 2)
                    l = round(p * 0.3, 2)
                    validation.corrected_fields["building_value"] = b
                    validation.corrected_fields["land_value"] = l
                    validation.issues.append(ValidationIssue(
                        field="building_value",
                        issue=f"No split found, auto-set 70/30: building €{b:.0f}, land €{l:.0f}",
                        severity="info",
                    ))
                elif building and land:
                    total = float(building) + float(land)
                    if p > 0 and abs(total - p) / p > 0.1:
                        validation.issues.append(ValidationIssue(
                            field="building_value",
                            issue=f"Building ({building}) + Land ({land}) = {total:.0f} "
                                  f"doesn't match purchase price ({price})",
                            severity="info",
                        ))
            except (ValueError, TypeError):
                pass

        # Grunderwerbsteuer: auto-calculate if missing
        grest = data.get("grunderwerbsteuer")
        if not grest and price:
            try:
                calculated = round(float(price) * 0.035, 2)
                validation.corrected_fields["grunderwerbsteuer"] = calculated
                validation.issues.append(ValidationIssue(
                    field="grunderwerbsteuer",
                    issue=f"Auto-calculated GrESt (3.5%): €{calculated:.0f}",
                    severity="info",
                ))
            except (ValueError, TypeError):
                pass
        elif grest and price:
            try:
                expected = float(price) * 0.035
                actual = float(grest)
                if actual > 0 and abs(actual - expected) / expected > 0.3:
                    validation.issues.append(ValidationIssue(
                        field="grunderwerbsteuer",
                        issue=f"GrESt ({actual:.0f}) differs from expected 3.5% ({expected:.0f})",
                        severity="info",
                    ))
            except (ValueError, TypeError):
                pass

    def _validate_mietvertrag(self, data: Dict[str, Any], validation: ValidationResult):
        """Validate Mietvertrag-specific fields."""
        if not data.get("monthly_rent"):
            # Genuine error — can't create recurring without amount
            validation.issues.append(ValidationIssue(
                field="monthly_rent",
                issue="No monthly rent found",
                severity="error",
            ))

        # Rent range is informational only — don't block
        rent = data.get("monthly_rent")
        if rent:
            try:
                r = float(rent)
                if r < 100:
                    validation.issues.append(ValidationIssue(
                        field="monthly_rent",
                        issue=f"Rent seems unusually low: €{r:.2f}",
                        severity="info",
                    ))
                elif r > 10000:
                    validation.issues.append(ValidationIssue(
                        field="monthly_rent",
                        issue=f"Rent seems unusually high: €{r:.2f}",
                        severity="info",
                    ))
            except (ValueError, TypeError):
                pass

    # ---- Stage 5: Auto-create ----

    def _stage_suggest(
        self, document: Document, db_type: DBDocumentType,
        ocr_result: OCRResult, result: PipelineResult,
    ):
        """
        Build suggestions AND auto-create records for ALL document types.

        Philosophy: do it now, let user edit/undo later.
        - Kaufvertrag → auto-create property
        - Mietvertrag → auto-create recurring income
        - Receipt/Invoice → auto-create transaction(s)
        """
        result.stage_reached = PipelineStage.SUGGEST

        if db_type == DBDocumentType.PURCHASE_CONTRACT:
            suggestion = self._build_kaufvertrag_suggestion(document, result)
            if suggestion:
                result.suggestions.append(suggestion)
                self._log_audit(result, "auto-create", "Auto-created property from Kaufvertrag")

        elif db_type == DBDocumentType.RENTAL_CONTRACT:
            suggestion = self._build_mietvertrag_suggestion(document, result)
            if suggestion:
                result.suggestions.append(suggestion)
                self._log_audit(result, "auto-create", "Auto-created recurring income from Mietvertrag")

        else:
            # Receipt/Invoice/Other → auto-create transaction(s)
            transaction_suggestions = self._build_transaction_suggestions(
                document, db_type, result
            )
            result.suggestions.extend(transaction_suggestions)
            if transaction_suggestions:
                self._log_audit(
                    result, "auto-create",
                    f"Auto-created {len(transaction_suggestions)} transaction(s)"
                )

    def _build_kaufvertrag_suggestion(
        self, document: Document, result: PipelineResult
    ) -> Optional[Dict[str, Any]]:
        """Build AND auto-create property from Kaufvertrag."""
        from app.tasks.ocr_tasks import _build_kaufvertrag_suggestion
        try:
            suggestion_dict = _build_kaufvertrag_suggestion(self.db, document, result)
            suggestion = suggestion_dict.get("import_suggestion")
            if not suggestion:
                return None

            # Auto-confirm: create the property immediately
            try:
                from app.tasks.ocr_tasks import create_property_from_suggestion
                create_result = create_property_from_suggestion(
                    self.db, document, suggestion.get("data", {})
                )
                suggestion["status"] = "auto-created"
                suggestion["property_id"] = create_result.get("property_id")
            except Exception as e:
                logger.warning(f"Auto-create property failed, keeping as suggestion: {e}")
                suggestion["status"] = "pending"

            return suggestion
        except Exception as e:
            logger.warning(f"Kaufvertrag suggestion failed: {e}")
            return None

    def _build_mietvertrag_suggestion(
        self, document: Document, result: PipelineResult
    ) -> Optional[Dict[str, Any]]:
        """Build AND auto-create recurring income from Mietvertrag."""
        from app.tasks.ocr_tasks import _build_mietvertrag_suggestion
        try:
            suggestion_dict = _build_mietvertrag_suggestion(self.db, document, result)
            suggestion = suggestion_dict.get("import_suggestion")
            if not suggestion:
                return None

            # Auto-confirm: create the recurring income immediately
            try:
                from app.tasks.ocr_tasks import create_recurring_from_suggestion
                create_result = create_recurring_from_suggestion(
                    self.db, document, suggestion.get("data", {})
                )
                suggestion["status"] = "auto-created"
                suggestion["recurring_id"] = create_result.get("recurring_id")
            except Exception as e:
                logger.warning(f"Auto-create recurring failed, keeping as suggestion: {e}")
                suggestion["status"] = "pending"

            return suggestion
        except Exception as e:
            logger.warning(f"Mietvertrag suggestion failed: {e}")
            return None

    def _build_transaction_suggestions(
        self, document: Document, db_type: DBDocumentType, result: PipelineResult,
    ) -> List[Dict[str, Any]]:
        """
        Build AND auto-create transactions for receipts/invoices.

        Creates immediately. User sees result in dashboard, can edit/delete.
        """
        try:
            from app.services.ocr_transaction_service import OCRTransactionService
            service = OCRTransactionService(self.db)
            suggestions = service.create_split_suggestions(
                document.id, document.user_id
            )

            # Auto-create all suggestions as transactions
            for s in suggestions:
                s["needs_review"] = False  # Don't nag the user
                try:
                    s["document_id"] = document.id
                    txn = service.create_transaction_from_suggestion(s, document.user_id)
                    s["transaction_id"] = txn.id
                    s["status"] = "auto-created"
                except Exception as e:
                    logger.warning(f"Auto-create transaction failed for doc {document.id}: {e}")
                    s["status"] = "pending"

            return suggestions

        except Exception as e:
            logger.warning(f"Transaction suggestion failed for doc {document.id}: {e}")
            return []

    # ---- Confidence assessment ----

    def _assess_confidence(
        self, ocr_confidence: float, db_type: DBDocumentType,
        validation: ValidationResult,
    ) -> ConfidenceLevel:
        """
        Determine confidence level. Lenient — only errors drop to LOW.

        Warnings and info issues are just metadata; they don't block auto-creation.
        """
        score = ocr_confidence

        # Only real errors reduce confidence significantly
        if validation.error_count > 0:
            score *= 0.4

        # Warnings are mild — auto-fix has already handled most issues
        # Don't penalize for "info" level issues (auto-corrections)

        if score >= 0.6:
            return ConfidenceLevel.HIGH
        elif score >= 0.3:
            return ConfidenceLevel.MEDIUM
        else:
            return ConfidenceLevel.LOW

    # ---- Persistence ----

    def _finalize(
        self, result: PipelineResult, document: Optional[Document],
        start_time: datetime,
    ) -> PipelineResult:
        """Persist results to the database and finalize timing."""
        result.processing_time_ms = (
            datetime.utcnow() - start_time
        ).total_seconds() * 1000

        if document is None:
            return result

        try:
            # Update document with OCR results
            if result.extracted_data:
                document.ocr_result = self._make_json_safe(result.extracted_data)
            if result.raw_text:
                document.raw_text = result.raw_text
            if result.classification:
                document.confidence_score = result.classification.confidence

            document.processed_at = datetime.utcnow()

            # Store pipeline metadata in ocr_result
            ocr_result = document.ocr_result if isinstance(document.ocr_result, dict) else {}
            ocr_result["_pipeline"] = {
                "stage_reached": result.stage_reached.value,
                "confidence_level": result.confidence_level.value,
                "needs_review": result.needs_review,
                "processing_time_ms": result.processing_time_ms,
            }

            # Store validation issues
            if result.validation and result.validation.issues:
                ocr_result["_validation"] = {
                    "is_valid": result.validation.is_valid,
                    "issues": [
                        {"field": i.field, "issue": i.issue, "severity": i.severity}
                        for i in result.validation.issues
                    ],
                }

            # Store suggestions
            if result.suggestions:
                # For Kaufvertrag/Mietvertrag, store as import_suggestion
                for s in result.suggestions:
                    if s and s.get("type") in ("create_property", "create_recurring_income"):
                        ocr_result["import_suggestion"] = s
                    elif s:
                        # Transaction suggestions
                        ocr_result["transaction_suggestion"] = s

                # Store tax_analysis for transaction suggestions
                tx_suggestions = [
                    s for s in result.suggestions
                    if s and s.get("type") not in ("create_property", "create_recurring_income")
                ]
                if tx_suggestions:
                    ocr_result["tax_analysis"] = {
                        "items": [
                            {
                                "description": s.get("description", ""),
                                "amount": s.get("amount"),
                                "category": s.get("category"),
                                "is_deductible": s.get("is_deductible", False),
                                "deduction_reason": s.get("deduction_reason", ""),
                                "confidence": s.get("confidence", 0),
                                "transaction_type": s.get("transaction_type", "expense"),
                            }
                            for s in tx_suggestions
                        ],
                        "is_split": len(tx_suggestions) > 1,
                        "total_deductible": sum(
                            float(s.get("amount", 0))
                            for s in tx_suggestions if s.get("is_deductible")
                        ),
                        "total_non_deductible": sum(
                            float(s.get("amount", 0))
                            for s in tx_suggestions if not s.get("is_deductible")
                        ),
                    }

            document.ocr_result = self._make_json_safe(ocr_result)
            self.db.commit()

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to persist pipeline results for doc {result.document_id}: {e}")

        return result

    # ---- Transaction creation (called after user confirmation) ----

    def create_transactions_from_suggestions(
        self, document_id: int, user_id: int,
        approved_suggestions: Optional[List[int]] = None,
    ) -> List[int]:
        """
        Create transactions from approved suggestions.

        This should only be called AFTER the user has reviewed and confirmed.

        Args:
            document_id: Document ID
            user_id: User ID
            approved_suggestions: Indices of approved suggestions (None = all)

        Returns:
            List of created transaction IDs
        """
        document = self.db.query(Document).filter(
            Document.id == document_id,
            Document.user_id == user_id,
        ).first()

        if not document or not document.ocr_result:
            return []

        ocr_result = document.ocr_result
        suggestions = []

        # Collect transaction suggestions
        if ocr_result.get("transaction_suggestion"):
            suggestions.append(ocr_result["transaction_suggestion"])
        if ocr_result.get("tax_analysis", {}).get("items"):
            suggestions = ocr_result["tax_analysis"]["items"]

        if not suggestions:
            return []

        # Filter to approved ones
        if approved_suggestions is not None:
            suggestions = [
                s for i, s in enumerate(suggestions)
                if i in approved_suggestions
            ]

        from app.services.ocr_transaction_service import OCRTransactionService
        service = OCRTransactionService(self.db)
        created_ids = []

        for suggestion in suggestions:
            try:
                # Ensure document_id is set
                suggestion["document_id"] = document_id
                transaction = service.create_transaction_from_suggestion(
                    suggestion, user_id
                )
                created_ids.append(transaction.id)
            except Exception as e:
                logger.warning(
                    f"Failed to create transaction from suggestion for doc {document_id}: {e}"
                )

        return created_ids

    # ---- Helpers ----

    def _log_audit(self, result: PipelineResult, stage: str, message: str):
        """Add an entry to the pipeline audit log."""
        result.audit_log.append({
            "timestamp": datetime.utcnow().isoformat(),
            "stage": stage,
            "message": message,
        })
        logger.info(f"[Pipeline doc={result.document_id}] [{stage}] {message}")

    @staticmethod
    def _make_json_safe(obj):
        """Recursively convert non-JSON-safe types."""
        if isinstance(obj, dict):
            return {k: DocumentPipelineOrchestrator._make_json_safe(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [DocumentPipelineOrchestrator._make_json_safe(v) for v in obj]
        elif isinstance(obj, (datetime, date)):
            return obj.isoformat()
        elif isinstance(obj, Decimal):
            return float(obj)
        return obj
