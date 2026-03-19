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
from sqlalchemy.orm.attributes import flag_modified

from app.models.document import Document, DocumentType as DBDocumentType
from app.services.document_metering_service import (
    DocumentMeteringService,
    PhaseCheckpointType,
)
from app.services.document_classifier import DocumentClassifier, DocumentType as OCRDocumentType
from app.services.ocr_engine import OCREngine, OCRResult
from app.services.processing_decision_service import (
    ProcessingAction,
    ProcessingDecisionService,
    ProcessingPhase,
)

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
    phase_checkpoints: List[Dict[str, Any]] = field(default_factory=list)
    current_state: str = "processing_phase_1"
    processing_decision: Optional[Dict[str, Any]] = None
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
            elif s.get("type") == "create_asset":
                asset_name = s.get("data", {}).get("name") or "Asset"
                parts.append(f"Anlagegut angelegt: {asset_name}")
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
            "current_state": self.current_state,
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
        result["phase_checkpoints"] = self.phase_checkpoints
        result["processing_decision"] = self.processing_decision
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
    OCRDocumentType.L1_FORM: DBDocumentType.L1_FORM,
    OCRDocumentType.L1K_BEILAGE: DBDocumentType.L1K_BEILAGE,
    OCRDocumentType.L1AB_BEILAGE: DBDocumentType.L1AB_BEILAGE,
    OCRDocumentType.E1A_BEILAGE: DBDocumentType.E1A_BEILAGE,
    OCRDocumentType.E1B_BEILAGE: DBDocumentType.E1B_BEILAGE,
    OCRDocumentType.E1KV_BEILAGE: DBDocumentType.E1KV_BEILAGE,
    OCRDocumentType.U1_FORM: DBDocumentType.U1_FORM,
    OCRDocumentType.U30_FORM: DBDocumentType.U30_FORM,
    OCRDocumentType.JAHRESABSCHLUSS: DBDocumentType.JAHRESABSCHLUSS,
    OCRDocumentType.SPENDENBESTAETIGUNG: DBDocumentType.SPENDENBESTAETIGUNG,
    OCRDocumentType.VERSICHERUNGSBESTAETIGUNG: DBDocumentType.VERSICHERUNGSBESTAETIGUNG,
    OCRDocumentType.KINDERBETREUUNGSKOSTEN: DBDocumentType.KINDERBETREUUNGSKOSTEN,
    OCRDocumentType.FORTBILDUNGSKOSTEN: DBDocumentType.FORTBILDUNGSKOSTEN,
    OCRDocumentType.PENDLERPAUSCHALE: DBDocumentType.PENDLERPAUSCHALE,
    OCRDocumentType.KIRCHENBEITRAG: DBDocumentType.KIRCHENBEITRAG,
    OCRDocumentType.GRUNDBUCHAUSZUG: DBDocumentType.GRUNDBUCHAUSZUG,
    OCRDocumentType.BETRIEBSKOSTENABRECHNUNG: DBDocumentType.BETRIEBSKOSTENABRECHNUNG,
    OCRDocumentType.GEWERBESCHEIN: DBDocumentType.GEWERBESCHEIN,
    OCRDocumentType.KONTOAUSZUG: DBDocumentType.KONTOAUSZUG,
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
AUTO_CREATE_THRESHOLD_DEFAULT = DEFAULT_AUTO_CREATE_THRESHOLD

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

    # DB document types that generate tax filing data suggestions
    TAX_FORM_DB_TYPES = {
        DBDocumentType.LOHNZETTEL,
        DBDocumentType.L1_FORM,
        DBDocumentType.L1K_BEILAGE,
        DBDocumentType.L1AB_BEILAGE,
        DBDocumentType.E1A_BEILAGE,
        DBDocumentType.E1B_BEILAGE,
        DBDocumentType.E1KV_BEILAGE,
        DBDocumentType.U1_FORM,
        DBDocumentType.U30_FORM,
        DBDocumentType.JAHRESABSCHLUSS,
        DBDocumentType.SVS_NOTICE,
        DBDocumentType.PROPERTY_TAX,
        DBDocumentType.BANK_STATEMENT,
    }

    # Map DB type to import_suggestion type string
    TAX_FORM_SUGGESTION_TYPE_MAP = {
        DBDocumentType.LOHNZETTEL: "import_lohnzettel",
        DBDocumentType.L1_FORM: "import_l1",
        DBDocumentType.L1K_BEILAGE: "import_l1k",
        DBDocumentType.L1AB_BEILAGE: "import_l1ab",
        DBDocumentType.E1A_BEILAGE: "import_e1a",
        DBDocumentType.E1B_BEILAGE: "import_e1b",
        DBDocumentType.E1KV_BEILAGE: "import_e1kv",
        DBDocumentType.U1_FORM: "import_u1",
        DBDocumentType.U30_FORM: "import_u30",
        DBDocumentType.JAHRESABSCHLUSS: "import_jahresabschluss",
        DBDocumentType.SVS_NOTICE: "import_svs",
        DBDocumentType.PROPERTY_TAX: "import_grundsteuer",
        DBDocumentType.BANK_STATEMENT: "import_bank_statement",
    }

    def __init__(self, db: Session):
        self.db = db
        self.ocr_engine = OCREngine()
        self.classifier = DocumentClassifier()
        self.processing_decision_service = ProcessingDecisionService()
        self.document_metering_service = DocumentMeteringService()

    def _get_processing_decision_service(self) -> ProcessingDecisionService:
        if not hasattr(self, "processing_decision_service") or self.processing_decision_service is None:
            self.processing_decision_service = ProcessingDecisionService()
        return self.processing_decision_service

    def _get_document_metering_service(self) -> DocumentMeteringService:
        if not hasattr(self, "document_metering_service") or self.document_metering_service is None:
            self.document_metering_service = DocumentMeteringService()
        return self.document_metering_service

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
        metering_service = self._get_document_metering_service()
        phase_1_checkpoint = metering_service.begin_phase(
            phase=ProcessingPhase.PHASE_1,
            checkpoint=PhaseCheckpointType.FIRST_RESULT,
            entry_stage=PipelineStage.CLASSIFY.value,
            metadata={"document_id": document_id},
        )
        phase_2_checkpoint = None

        try:
            # Load document
            document = self.db.query(Document).filter(Document.id == document_id).first()
            if not document:
                result.error = f"Document {document_id} not found"
                result.phase_checkpoints.append(
                    metering_service.fail_phase(
                        phase_1_checkpoint,
                        exit_stage=result.stage_reached.value,
                        error=result.error,
                    )
                )
                return result

            # Stage 1: OCR + Classification
            ocr_result = self._stage_ocr(document, result)
            if ocr_result is None:
                result.stage_reached = PipelineStage.CLASSIFY
                result.phase_checkpoints.append(
                    metering_service.fail_phase(
                        phase_1_checkpoint,
                        exit_stage=result.stage_reached.value,
                        error=result.error or "ocr_failed",
                    )
                )
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

            result.phase_checkpoints.append(
                metering_service.complete_phase(
                    phase_1_checkpoint,
                    exit_stage=PipelineStage.VALIDATE.value,
                    metadata={
                        "document_type": db_type.value,
                        "classification_method": (
                            result.classification.method if result.classification else None
                        ),
                        "extracted_field_count": len(result.extracted_data or {}),
                        "validation_error_count": validation.error_count,
                        "validation_warning_count": validation.warning_count,
                    },
                )
            )
            result.current_state = "first_result_available"
            self._persist_checkpoint_state(document, result, commit=True)

            phase_2_checkpoint = metering_service.begin_phase(
                phase=ProcessingPhase.PHASE_2,
                checkpoint=PhaseCheckpointType.FINALIZATION,
                entry_stage=PipelineStage.SUGGEST.value,
                metadata={"document_type": db_type.value},
            )
            result.phase_checkpoints.append(phase_2_checkpoint.model_dump(mode="json"))
            result.current_state = "finalizing"
            self._persist_checkpoint_state(document, result, commit=True)

            # Stage 5: Build suggestions AND auto-create
            self._stage_suggest(document, db_type, ocr_result, result)

            result.phase_checkpoints.append(
                metering_service.complete_phase(
                    phase_2_checkpoint,
                    exit_stage=PipelineStage.SUGGEST.value,
                    metadata={
                        "suggestion_count": len(result.suggestions),
                        "processing_decision": result.processing_decision,
                    },
                )
            )
            result.current_state = "completed"

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
            self.db.rollback()
            failed_checkpoint = phase_2_checkpoint or phase_1_checkpoint
            result.phase_checkpoints.append(
                metering_service.fail_phase(
                    failed_checkpoint,
                    exit_stage=result.stage_reached.value,
                    error=result.error,
                )
            )
            if phase_2_checkpoint is not None:
                result.current_state = "phase_2_failed"
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
            DBDocumentType.LOAN_CONTRACT: self._validate_kreditvertrag,
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
        purchase_contract_kind = data.get("purchase_contract_kind")

        # Missing date → today (but use the correct date field per document type)
        # Kaufvertrag uses purchase_date, Mietvertrag uses start_date, others use date
        if db_type == DBDocumentType.PURCHASE_CONTRACT:
            date_field = "purchase_date"
        elif db_type == DBDocumentType.RENTAL_CONTRACT:
            date_field = "start_date"
        else:
            date_field = "date"

        if not data.get(date_field) and date_field not in validation.corrected_fields:
            today = date.today().isoformat()
            validation.corrected_fields[date_field] = today
            validation.issues.append(ValidationIssue(
                field=date_field, issue=f"No date found, auto-set to {today}", severity="info",
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
        if db_type == DBDocumentType.PURCHASE_CONTRACT and purchase_contract_kind != "asset":
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
        if data.get("purchase_contract_kind") == "asset":
            if not data.get("purchase_price"):
                validation.issues.append(ValidationIssue(
                    field="purchase_price",
                    issue="No purchase price found",
                    severity="error",
                ))
            return

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

    def _validate_kreditvertrag(self, data: Dict[str, Any], validation: ValidationResult):
        """Validate Kreditvertrag-specific fields."""
        if not data.get("loan_amount"):
            validation.issues.append(ValidationIssue(
                field="loan_amount",
                issue="No loan amount found",
                severity="error",
            ))

        if not data.get("interest_rate"):
            validation.issues.append(ValidationIssue(
                field="interest_rate",
                issue="No interest rate found",
                severity="error",
            ))

        # Informational checks on loan_amount range
        loan_amount = data.get("loan_amount")
        if loan_amount:
            try:
                amt = float(loan_amount)
                if amt < 1000:
                    validation.issues.append(ValidationIssue(
                        field="loan_amount",
                        issue=f"Loan amount seems unusually low: €{amt:.2f}",
                        severity="info",
                    ))
                elif amt > 10_000_000:
                    validation.issues.append(ValidationIssue(
                        field="loan_amount",
                        issue=f"Loan amount seems unusually high: €{amt:.2f}",
                        severity="info",
                    ))
            except (ValueError, TypeError):
                pass

        # Informational check on interest_rate range
        interest_rate = data.get("interest_rate")
        if interest_rate:
            try:
                rate = float(interest_rate)
                if rate < 0:
                    validation.issues.append(ValidationIssue(
                        field="interest_rate",
                        issue=f"Interest rate is negative: {rate}%",
                        severity="warning",
                    ))
                elif rate > 20:
                    validation.issues.append(ValidationIssue(
                        field="interest_rate",
                        issue=f"Interest rate seems unusually high: {rate}%",
                        severity="info",
                    ))
            except (ValueError, TypeError):
                pass

    # ---- Stage 5: Auto-create ----

    def _stage_suggest(
        self, document: Document, db_type: DBDocumentType,
        ocr_result: OCRResult, result: PipelineResult,
    ):
        """Execute explicit Phase-2 actions for the classified document."""
        result.stage_reached = PipelineStage.SUGGEST
        decision = self._get_processing_decision_service().build_phase_two_decision(
            db_type,
            tax_form_types=set(self.TAX_FORM_DB_TYPES),
        )
        result.processing_decision = decision.model_dump(mode="json")

        for action in [*decision.primary_actions, *decision.secondary_actions]:
            self._execute_processing_action(
                action=action,
                document=document,
                db_type=db_type,
                ocr_result=ocr_result,
                result=result,
            )

    def _execute_processing_action(
        self,
        *,
        action: ProcessingAction,
        document: Document,
        db_type: DBDocumentType,
        ocr_result: OCRResult,
        result: PipelineResult,
    ) -> None:
        """Run a single explicit Phase-2 action and append/log any outcomes."""
        del ocr_result  # Phase-2 actions consume persisted result state via helpers.

        if action == ProcessingAction.PURCHASE_CONTRACT:
            # TODO(v1.4-followup): property persistence still bypasses the asset-path
            # quality gate. Whole-pipeline gate unification is not done yet.
            suggestion = self._build_kaufvertrag_suggestion(document, result)
            if suggestion:
                result.suggestions.append(suggestion)
                self._log_audit(result, "auto-create", "Auto-created property from Kaufvertrag")
            return

        if action == ProcessingAction.RENTAL_CONTRACT:
            # TODO(v1.4-followup): recurring-income persistence still uses its own
            # document-type-specific branch; quality-gate authority is asset-path only.
            suggestion = self._build_mietvertrag_suggestion(document, result)
            if suggestion:
                result.suggestions.append(suggestion)
                self._log_audit(result, "auto-create", "Auto-created recurring income from Mietvertrag")
            return

        if action == ProcessingAction.LOAN_CONTRACT:
            suggestion = self._build_kreditvertrag_suggestion(document, result)
            if suggestion:
                result.suggestions.append(suggestion)
                self._log_audit(result, "suggest", "Built loan suggestion from Kreditvertrag")
            return

        if action == ProcessingAction.INSURANCE_RECURRING:
            suggestion = self._build_versicherung_suggestion(document, result)
            if suggestion:
                result.suggestions.append(suggestion)
                self._log_audit(
                    result,
                    "suggest",
                    "Built insurance recurring suggestion from Versicherungsbestätigung",
                )
            return

        if action == ProcessingAction.TAX_FORM_IMPORT:
            suggestion = self._build_tax_form_suggestion(document, db_type, result)
            if suggestion:
                result.suggestions.append(suggestion)
                self._log_audit(
                    result,
                    "suggest",
                    f"Built tax data suggestion from {db_type.value}",
                )
            return

        if action == ProcessingAction.TRANSACTION_SUGGESTIONS:
            # TODO(v1.4-followup): transaction auto-create still runs outside the
            # asset-path quality gate. Whole-pipeline unification is not complete.
            transaction_suggestions = self._build_transaction_suggestions(
                document, db_type, result
            )
            result.suggestions.extend(transaction_suggestions)
            if transaction_suggestions:
                self._log_audit(
                    result,
                    "auto-create",
                    f"Auto-created {len(transaction_suggestions)} transaction(s)",
                )
            return

        if action == ProcessingAction.ASSET_SUGGESTION:
            asset_suggestion = self._build_asset_suggestion(document, result)
            if asset_suggestion:
                result.suggestions.append(asset_suggestion)
                message = (
                    "Built asset suggestion from Kaufvertrag"
                    if db_type == DBDocumentType.PURCHASE_CONTRACT
                    else "Built asset suggestion from expense document"
                )
                self._log_audit(result, "suggest", message)

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

            data = suggestion.get("data", {})

            # If no property matched, keep as pending — user needs to create/link property first
            if data.get("no_property_match"):
                suggestion["status"] = "pending"
                return suggestion

            # Auto-confirm: create the recurring income immediately
            try:
                from app.tasks.ocr_tasks import create_recurring_from_suggestion
                create_result = create_recurring_from_suggestion(
                    self.db, document, suggestion.get("data", {})
                )
                suggestion["status"] = "auto-created"
                suggestion["recurring_id"] = create_result.get("recurring_id")
                suggestion["is_partial_match"] = create_result.get("is_partial_match", False)
                suggestion["unit_percentage"] = create_result.get("unit_percentage")
            except Exception as e:
                logger.warning(f"Auto-create recurring failed, keeping as suggestion: {e}")
                suggestion["status"] = "pending"

            return suggestion
        except Exception as e:
            logger.warning(f"Mietvertrag suggestion failed: {e}")
            return None

    def _build_kreditvertrag_suggestion(
        self, document: Document, result: PipelineResult
    ) -> Optional[Dict[str, Any]]:
        """Build loan suggestion from Kreditvertrag. Does NOT auto-create — user must confirm."""
        from app.tasks.ocr_tasks import _build_kreditvertrag_suggestion

        try:
            suggestion_dict = _build_kreditvertrag_suggestion(self.db, document, result)
            suggestion = suggestion_dict.get("import_suggestion")
            if not suggestion:
                return None

            return suggestion
        except Exception as e:
            logger.warning(f"Kreditvertrag suggestion failed: {e}")
            return None

    def _build_versicherung_suggestion(
        self, document: Document, result: PipelineResult
    ) -> Optional[Dict[str, Any]]:
        """Build insurance recurring suggestion from Versicherungsbestätigung. Does NOT auto-create — user must confirm."""
        from app.tasks.ocr_tasks import _build_versicherung_suggestion

        try:
            suggestion_dict = _build_versicherung_suggestion(self.db, document, result)
            suggestion = suggestion_dict.get("import_suggestion")
            if not suggestion:
                return None
            return suggestion
        except Exception as e:
            logger.warning(f"Versicherung suggestion failed: {e}")
            return None

    def _build_asset_suggestion(
        self, document: Document, result: PipelineResult
    ) -> Optional[Dict[str, Any]]:
        """Build asset suggestion and auto-create only when confidence is high and complete."""
        from app.tasks.ocr_tasks import (
            _build_asset_outcome_payload,
            _build_asset_suggestion,
        )

        try:
            suggestion_dict = _build_asset_suggestion(self.db, document, result)
            suggestion = suggestion_dict.get("import_suggestion")
            auto_create_payload = suggestion_dict.get("auto_create_payload")

            if auto_create_payload:
                try:
                    from app.tasks.ocr_tasks import create_asset_from_suggestion

                    create_result = create_asset_from_suggestion(
                        self.db,
                        document,
                        auto_create_payload.get("data", {}),
                        trigger_source="system",
                    )
                    auto_create_payload["status"] = "auto-created"
                    auto_create_payload["asset_id"] = create_result.get("asset_id")
                    return auto_create_payload
                except Exception as e:
                    logger.warning(f"Auto-create asset failed, keeping as suggestion: {e}")
                    self.db.rollback()
                    self.db.refresh(document)
                    fallback_suggestion = {
                        **auto_create_payload,
                        "status": "pending",
                    }
                    fallback_suggestion.setdefault("data", {})
                    fallback_suggestion["data"]["decision"] = "create_asset_suggestion"
                    updated_ocr = document.ocr_result.copy() if isinstance(document.ocr_result, dict) else {}
                    updated_ocr["import_suggestion"] = fallback_suggestion
                    updated_ocr["asset_outcome"] = _build_asset_outcome_payload(
                        status="pending_confirmation",
                        decision="create_asset_suggestion",
                        source="system_fallback",
                        quality_gate_decision=auto_create_payload.get("data", {}).get(
                            "quality_gate_decision"
                        ),
                    )
                    document.ocr_result = updated_ocr
                    flag_modified(document, "ocr_result")
                    self.db.flush()
                    return fallback_suggestion

            if not suggestion:
                return None

            return suggestion
        except Exception as e:
            logger.warning(f"Asset suggestion failed: {e}")
            return None

    def _build_tax_form_suggestion(
        self, document: Document, db_type: DBDocumentType, result: PipelineResult
    ) -> Optional[Dict[str, Any]]:
        """Build import suggestion for tax form documents (L16, L1, E1a, E1b, etc.).

        Stores extracted data in import_suggestion for user confirmation via
        the confirm-tax-data endpoint.
        """
        try:
            ocr_result = document.ocr_result or {}
            extracted_data = ocr_result.get("extracted_data", {})

            if not extracted_data:
                return None

            suggestion_type = self.TAX_FORM_SUGGESTION_TYPE_MAP.get(db_type)
            if not suggestion_type:
                return None

            suggestion = {
                "type": suggestion_type,
                "status": "pending",
                "data": extracted_data,
                "confidence": ocr_result.get("confidence_score", 0.0),
            }

            # Store in document.ocr_result.import_suggestion
            import json as _json
            updated_ocr = _json.loads(_json.dumps(document.ocr_result)) if document.ocr_result else {}
            updated_ocr["import_suggestion"] = suggestion
            document.ocr_result = updated_ocr
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(document, "ocr_result")

            return suggestion

        except Exception as e:
            logger.warning(f"Tax form suggestion failed for {db_type.value}: {e}")
            return None

    def _build_transaction_suggestions(
        self, document: Document, db_type: DBDocumentType, result: PipelineResult,
    ) -> List[Dict[str, Any]]:
        """
        Build AND auto-create transactions for receipts/invoices.

        Supports multi-receipt PDFs: if _additional_receipts is present in
        extracted data, creates a transaction for each receipt.

        Creates immediately. User sees result in dashboard, can edit/delete.
        """
        try:
            from app.services.ocr_transaction_service import OCRTransactionService
            service = OCRTransactionService(self.db)

            # Check for multi-receipt data
            primary_receipt = result.extracted_data
            additional_receipts = result.extracted_data.get("_additional_receipts", [])
            receipt_count = result.extracted_data.get("_receipt_count", 1)

            if not additional_receipts:
                multiple_receipts = result.extracted_data.get("multiple_receipts", [])
                if isinstance(multiple_receipts, list) and multiple_receipts:
                    primary_receipt = multiple_receipts[0]
                    additional_receipts = multiple_receipts[1:]
                    receipt_count = result.extracted_data.get(
                        "receipt_count", len(multiple_receipts)
                    )

            if receipt_count > 1 and additional_receipts:
                logger.info(
                    f"Multi-receipt document {document.id}: creating {receipt_count} transactions"
                )
                suggestions = self._create_multi_receipt_transactions(
                    document, service, primary_receipt, additional_receipts
                )
            else:
                suggestions = service.create_split_suggestions(
                    document.id, document.user_id
                )

            # Auto-create all suggestions as transactions
            for s in suggestions:
                s["needs_review"] = False  # Don't nag the user
                try:
                    s["document_id"] = document.id
                    creation_result = service.create_transaction_from_suggestion_with_result(
                        s, document.user_id
                    )
                    s["transaction_id"] = creation_result.transaction.id
                    if creation_result.created:
                        s["status"] = "auto-created"
                    else:
                        s["status"] = "duplicate-skipped"
                        s["is_duplicate"] = True
                        s["duplicate_of_id"] = creation_result.duplicate_of_id
                        s["duplicate_confidence"] = creation_result.duplicate_confidence
                except Exception as e:
                    logger.warning(f"Auto-create transaction failed for doc {document.id}: {e}")
                    s["status"] = "pending"

            return suggestions

        except Exception as e:
            logger.warning(f"Transaction suggestion failed for doc {document.id}: {e}")
            return []

    def _create_multi_receipt_transactions(
        self, document, service, primary_data: Dict, additional_receipts: List[Dict],
    ) -> List[Dict[str, Any]]:
        """
        Build transaction suggestions for a multi-receipt document.
        Each receipt becomes its own transaction suggestion.
        """
        all_suggestions = []

        # Build suggestion for the primary (first) receipt
        all_receipts = [primary_data] + additional_receipts

        for i, receipt_data in enumerate(all_receipts):
            amount = receipt_data.get("amount")
            if amount is None:
                continue

            merchant = receipt_data.get("merchant") or receipt_data.get("supplier") or "Unknown"
            date_val = receipt_data.get("date")
            date_str = None
            if date_val:
                if hasattr(date_val, "isoformat"):
                    date_str = date_val.isoformat()
                else:
                    date_str = str(date_val)

            description = f"{merchant}"
            product = receipt_data.get("product_summary")
            if product:
                description += f" - {product}"

            suggestion = {
                "document_id": document.id,
                "document_type": str(document.document_type.value) if hasattr(document.document_type, 'value') else str(document.document_type),
                "transaction_type": "expense",
                "amount": str(amount),
                "date": date_str,
                "description": description,
                "category": "other",
                "is_deductible": False,
                "deduction_reason": None,
                "confidence": float(receipt_data.get("amount_confidence", 0.8)),
                "needs_review": False,
                "extracted_fields": {},
                "_receipt_index": i + 1,
            }
            all_suggestions.append(suggestion)

        logger.info(
            f"Created {len(all_suggestions)} suggestions from multi-receipt document {document.id}"
        )
        return all_suggestions

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

    # =========================================================================
    # Follow-Up Question Generation (Tasks 4-6)
    # =========================================================================

    def _enrich_suggestions_with_follow_ups(self, result: PipelineResult) -> None:
        """
        Enrich suggestions with follow-up questions for missing data and version tracking.

        For asset suggestions: asks about put_into_use_date, business_use_percentage, etc.
        For property suggestions: asks about building_value_ratio, building_year, etc.
        All questions are trilingual (de/en/zh) with helpText for non-obvious fields.
        """
        for suggestion in (result.suggestions or []):
            if not suggestion or not isinstance(suggestion, dict):
                continue

            # Skip auto-created/confirmed suggestions — they don't need follow-ups
            if suggestion.get("status") in ("auto-created", "confirmed", "dismissed"):
                continue

            # Add version tracking for optimistic concurrency
            if "version" not in suggestion:
                suggestion["version"] = 0

            suggestion_type = suggestion.get("type", "")
            data = suggestion.get("data", {})

            follow_up_questions = []

            if suggestion_type == "create_asset":
                follow_up_questions = self._build_asset_follow_up_questions(data)
            elif suggestion_type == "create_property":
                follow_up_questions = self._build_property_follow_up_questions(data)

            if follow_up_questions:
                suggestion["follow_up_questions"] = follow_up_questions
                # If there are required follow-up questions, set status to needs_input
                has_required = any(q.get("required") for q in follow_up_questions)
                if has_required and suggestion.get("status") == "pending":
                    suggestion["status"] = "pending"  # Keep pending, frontend derives needs_input from presence of questions

    def _build_asset_follow_up_questions(self, data: Dict[str, Any]) -> list:
        """Build follow-up questions for asset suggestions with missing required fields."""
        questions = []

        # Required: put_into_use_date
        if not data.get("put_into_use_date"):
            questions.append({
                "id": "put_into_use_date",
                "question": {
                    "de": "Wann haben Sie diesen Gegenstand betrieblich in Nutzung genommen?",
                    "en": "When did you start using this item for business?",
                    "zh": "您何时开始将此物品用于业务？",
                },
                "input_type": "date",
                "required": True,
                "field_key": "put_into_use_date",
                "default_value": None,
                "help_text": {
                    "de": "Das Datum, an dem Sie den Gegenstand betrieblich nutzen, nicht das Kaufdatum.",
                    "en": "The date you started using this for business, not the purchase date.",
                    "zh": "您开始将此物品用于业务的日期，不是购买日期。",
                },
            })

        # Required: business_use_percentage
        if not data.get("business_use_percentage"):
            questions.append({
                "id": "business_use_pct",
                "question": {
                    "de": "Wie hoch ist der betriebliche Nutzungsanteil in Prozent?",
                    "en": "What percentage of use is for business?",
                    "zh": "业务使用比例是多少？",
                },
                "input_type": "number",
                "required": True,
                "field_key": "business_use_percentage",
                "default_value": 100,
                "validation": {"min": 1, "max": 100},
                "help_text": {
                    "de": "100% wenn ausschließlich betrieblich genutzt. Bei gemischter Nutzung den betrieblichen Anteil angeben.",
                    "en": "100% if used exclusively for business. For mixed use, enter the business portion.",
                    "zh": "如果完全用于业务则填100%。混合使用时填写业务占比。",
                },
            })

        # Conditional: is_used_asset (for vehicles)
        asset_category = data.get("asset_category", "").lower()
        is_vehicle = any(kw in asset_category for kw in ("fahrzeug", "vehicle", "auto", "pkw", "kfz", "car"))
        if is_vehicle and data.get("is_used_asset") is None:
            questions.append({
                "id": "is_used_asset",
                "question": {
                    "de": "Ist dies ein Gebrauchtfahrzeug?",
                    "en": "Is this a used vehicle?",
                    "zh": "这是二手车辆吗？",
                },
                "input_type": "boolean",
                "required": False,
                "field_key": "is_used_asset",
                "default_value": False,
                "help_text": {
                    "de": "Gebrauchtfahrzeuge haben eine verkürzte Nutzungsdauer für die AfA.",
                    "en": "Used vehicles have a shorter useful life for depreciation purposes.",
                    "zh": "二手车辆的折旧年限较短。",
                },
            })

        # Optional: depreciation_method
        if not data.get("depreciation_method"):
            questions.append({
                "id": "depreciation_method",
                "question": {
                    "de": "Welche Abschreibungsmethode möchten Sie verwenden?",
                    "en": "Which depreciation method would you like to use?",
                    "zh": "您希望使用哪种折旧方法？",
                },
                "input_type": "select",
                "required": False,
                "field_key": "depreciation_method",
                "default_value": "linear",
                "options": [
                    {"value": "linear", "label": {"de": "Linear (Standard)", "en": "Linear (Standard)", "zh": "直线法（标准）"}},
                    {"value": "degressive", "label": {"de": "Degressiv", "en": "Degressive", "zh": "递减法"}},
                ],
                "help_text": {
                    "de": "Linear ist der Standard. Degressive AfA ist nur in bestimmten Fällen möglich.",
                    "en": "Linear is the default. Degressive depreciation is only available in certain cases.",
                    "zh": "直线法是默认方式。递减法仅在特定情况下可用。",
                },
            })

        return questions

    def _build_property_follow_up_questions(self, data: Dict[str, Any]) -> list:
        """Build follow-up questions for property suggestions with missing fields."""
        questions = []

        # Required: building_value_ratio
        if not data.get("building_value_ratio"):
            questions.append({
                "id": "building_ratio",
                "question": {
                    "de": "Wie ist das Gebäude-zu-Grund-Verhältnis?",
                    "en": "What is the building-to-land value ratio?",
                    "zh": "建筑与土地的价值比例是多少？",
                },
                "input_type": "select",
                "required": True,
                "field_key": "building_value_ratio",
                "default_value": "0.7",
                "options": [
                    {"value": "0.7", "label": "70/30 (Standard)"},
                    {"value": "0.6", "label": "60/40"},
                    {"value": "0.8", "label": "80/20"},
                    {"value": "custom", "label": {"de": "Eigener Wert...", "en": "Custom value...", "zh": "自定义..."}},
                ],
                "help_text": {
                    "de": "Standard ist 70% Gebäude / 30% Grund. Verwenden Sie Ihr Liegenschaftsgutachten falls vorhanden.",
                    "en": "Standard is 70% building / 30% land. Use your Liegenschaftsgutachten if available.",
                    "zh": "标准比例为70%建筑/30%土地。如有物业评估报告请使用实际数据。",
                },
            })

        # Optional: building_year
        if not data.get("building_year"):
            questions.append({
                "id": "building_year",
                "question": {
                    "de": "Wann wurde das Gebäude errichtet?",
                    "en": "When was the building constructed?",
                    "zh": "建筑何时建成？",
                },
                "input_type": "number",
                "required": False,
                "field_key": "building_year",
                "default_value": None,
                "validation": {"min": 1800, "max": 2030},
                "help_text": {
                    "de": "Das Baujahr beeinflusst den AfA-Satz (1,5% oder 2% p.a.).",
                    "en": "The construction year affects the depreciation rate (1.5% or 2% p.a.).",
                    "zh": "建造年份影响折旧率（每年1.5%或2%）。",
                },
            })

        # Optional: intended_use
        if not data.get("intended_use"):
            questions.append({
                "id": "intended_use",
                "question": {
                    "de": "Wie wird die Immobilie genutzt?",
                    "en": "How is the property used?",
                    "zh": "房产如何使用？",
                },
                "input_type": "select",
                "required": False,
                "field_key": "intended_use",
                "default_value": "rental",
                "options": [
                    {"value": "rental", "label": {"de": "Vermietung", "en": "Rental", "zh": "出租"}},
                    {"value": "own_use", "label": {"de": "Eigennutzung", "en": "Own use", "zh": "自用"}},
                    {"value": "mixed", "label": {"de": "Gemischt", "en": "Mixed", "zh": "混合使用"}},
                ],
                "help_text": {
                    "de": "Nur bei Vermietung oder betrieblicher Nutzung können Kosten steuerlich abgesetzt werden.",
                    "en": "Only rental or business use allows tax deductions on costs.",
                    "zh": "仅出租或业务使用的费用可以税前扣除。",
                },
            })

        return questions

    def _build_validation_payload(self, result: PipelineResult) -> Optional[Dict[str, Any]]:
        if not result.validation or not result.validation.issues:
            return None
        return {
            "is_valid": result.validation.is_valid,
            "issues": [
                {"field": i.field, "issue": i.issue, "severity": i.severity}
                for i in result.validation.issues
            ],
        }

    def _persist_checkpoint_state(
        self,
        document: Document,
        result: PipelineResult,
        *,
        commit: bool,
    ) -> None:
        """Persist visible checkpoint state without overwriting existing OCR contracts."""
        ocr_result = (
            self._make_json_safe(dict(document.ocr_result))
            if isinstance(document.ocr_result, dict)
            else {}
        )
        if result.extracted_data:
            ocr_result.update(self._make_json_safe(result.extracted_data))

        validation_payload = self._build_validation_payload(result)
        if validation_payload:
            ocr_result["_validation"] = validation_payload

        ocr_result["_pipeline"] = self._get_document_metering_service().build_pipeline_metadata(
            result=result
        )

        document.ocr_result = self._make_json_safe(ocr_result)
        if result.raw_text:
            document.raw_text = result.raw_text
        if result.classification:
            document.confidence_score = result.classification.confidence
        try:
            flag_modified(document, "ocr_result")
        except Exception:
            pass

        if commit:
            self.db.commit()
            self.db.refresh(document)
        else:
            self.db.flush()

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
            # Merge into the latest persisted OCR result so terminal asset state
            # and other checkpoint contracts survive finalization.
            ocr_result = (
                self._make_json_safe(dict(document.ocr_result))
                if isinstance(document.ocr_result, dict)
                else {}
            )
            if result.extracted_data:
                ocr_result.update(self._make_json_safe(result.extracted_data))
            if result.raw_text:
                document.raw_text = result.raw_text
            if result.classification:
                document.confidence_score = result.classification.confidence
            elif result.error:
                # Pipeline failed before/during classification — mark as 0.0
                # so the frontend doesn't keep polling (Requirement 6.5)
                document.confidence_score = 0.0

            if result.current_state == "completed":
                document.processed_at = datetime.utcnow()

            # Store pipeline metadata in ocr_result
            ocr_result["_pipeline"] = self._get_document_metering_service().build_pipeline_metadata(
                result=result
            )

            # Store validation issues
            validation_payload = self._build_validation_payload(result)
            if validation_payload:
                ocr_result["_validation"] = validation_payload

            # Enrich suggestions with follow-up questions and version before storing
            self._enrich_suggestions_with_follow_ups(result)

            # Store suggestions
            if result.suggestions:
                import_suggestion_types = {
                    "create_property",
                    "create_recurring_income",
                    "create_loan",
                    "create_loan_repayment",
                    "create_recurring_expense",
                    "create_insurance_recurring",
                }

                for s in result.suggestions:
                    if not s:
                        continue

                    if s.get("type") == "create_asset":
                        status = s.get("status")
                        if status == "pending":
                            ocr_result["import_suggestion"] = s
                            if not ocr_result.get("asset_outcome"):
                                ocr_result["asset_outcome"] = {
                                    "contract_version": "v1",
                                    "type": "create_asset",
                                    "status": "pending_confirmation",
                                    "decision": s.get("data", {}).get(
                                        "decision", "create_asset_suggestion"
                                    ),
                                    "asset_id": None,
                                    "source": "quality_gate",
                                    "quality_gate_decision": s.get("data", {}).get(
                                        "quality_gate_decision"
                                    ),
                                }
                        else:
                            existing_suggestion = ocr_result.get("import_suggestion")
                            if (
                                isinstance(existing_suggestion, dict)
                                and existing_suggestion.get("type") == "create_asset"
                            ):
                                ocr_result.pop("import_suggestion", None)
                            if status == "auto-created" and not ocr_result.get("asset_outcome"):
                                ocr_result["asset_outcome"] = {
                                    "contract_version": "v1",
                                    "type": "create_asset",
                                    "status": "auto_created",
                                    "decision": s.get("data", {}).get(
                                        "decision", "create_asset_auto"
                                    ),
                                    "asset_id": s.get("asset_id"),
                                    "source": "quality_gate",
                                    "quality_gate_decision": s.get("data", {}).get(
                                        "quality_gate_decision"
                                    ),
                                }
                        continue

                    if s.get("type") in import_suggestion_types:
                        ocr_result["import_suggestion"] = s
                    else:
                        # Transaction suggestions
                        ocr_result["transaction_suggestion"] = s

                # Store tax_analysis for transaction suggestions
                tx_suggestions = [
                    s for s in result.suggestions
                    if s and s.get("type") not in (import_suggestion_types | {"create_asset"})
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
            try:
                flag_modified(document, "ocr_result")
            except Exception:
                pass
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
                creation_result = service.create_transaction_from_suggestion_with_result(
                    suggestion, user_id
                )
                if creation_result.created:
                    created_ids.append(creation_result.transaction.id)
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
