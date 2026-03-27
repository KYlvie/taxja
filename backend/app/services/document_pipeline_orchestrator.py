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
import hashlib
import json
import logging
import time
from collections import OrderedDict
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
from app.services.document_transaction_suggestion_store import (
    copy_transaction_suggestions,
    store_transaction_suggestions,
)
from app.services.final_transaction_type_service import (
    materialize_final_transaction_type,
)
from app.services.document_classifier import DocumentClassifier, DocumentType as OCRDocumentType
from app.services.field_normalization import (
    normalize_amount,
    normalize_date,
    normalize_vat_rate,
)
from app.services.ocr_engine import OCREngine, OCRResult
from app.services.processing_decision_service import (
    ProcessingAction,
    ProcessingDecisionService,
    ProcessingPhase,
)

logger = logging.getLogger(__name__)

_LLM_CLASSIFICATION_CACHE_VERSION = "orchestrator-llm-classify-v1"
_LLM_CLASSIFICATION_CACHE_TTL_SECONDS = 24 * 60 * 60
_LLM_CLASSIFICATION_CACHE_MAX_SIZE = 512
_LLM_CLASSIFICATION_TEXT_WINDOW = 4000

_DEDUP_MATCH_FIELDS = (
    "amount",
    "merchant",
    "date",
    "description",
    "address",
    "property_address",
    "monthly_rent",
    "purchase_price",
    "insurer_name",
    "praemie",
    "polizze",
    "versicherungsart",
    "insurance_type",
    "lender_name",
    "loan_amount",
    "employer",
    "employer_name",
    "gross_income",
)

_REVERSE_CHARGE_VAT_HINTS = (
    "reverse charge",
    "steuerschuldnerschaft des leistungsempfängers",
    "steuerschuldnerschaft des leistungsempfaengers",
    "tax to be accounted for by the recipient",
    "vat to be accounted for by the recipient",
    "recipient owes the vat",
    "recipient is liable for vat",
    "intra-community",
    "innergemeinschaft",
    "eu b2b",
)


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
    provider_used: Optional[str] = None
    ocr_confidence_score: Optional[float] = None
    reprocess_mode: Optional[str] = None
    reprocess_requested_at: Optional[str] = None
    ocr_provider_override: Optional[str] = None
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
    OCRDocumentType.LOAN_CONTRACT: DBDocumentType.LOAN_CONTRACT,
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
    }
    BANK_STATEMENT_SUGGESTION_TYPE = "import_bank_statement"

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

    def _build_phase_two_decision(self, db_type: DBDocumentType):
        return self._get_processing_decision_service().build_phase_two_decision(
            db_type,
            tax_form_types=set(self.TAX_FORM_DB_TYPES),
        )

    def _decision_has_transaction_suggestions(self, decision) -> bool:
        transaction_action = ProcessingAction.TRANSACTION_SUGGESTIONS
        actions = [*decision.primary_actions, *decision.secondary_actions]
        return any(
            action == transaction_action or action == transaction_action.value
            for action in actions
        )

    def _get_llm_classification_cache(self) -> "OrderedDict[str, Tuple[float, str]]":
        cache = getattr(self.__class__, "_llm_classification_cache", None)
        if cache is None:
            cache = OrderedDict()
            setattr(self.__class__, "_llm_classification_cache", cache)
        return cache

    def _get_llm_classification_provider_fingerprint(self, extractor) -> str:
        try:
            llm = extractor.llm
        except Exception:
            return "llm-unavailable"

        model_parts = []
        for attr_name in ("model", "anthropic_model", "groq_model", "gpt_oss_model"):
            attr_value = getattr(llm, attr_name, None)
            if attr_value:
                model_parts.append(f"{attr_name}={attr_value}")
        return "|".join(model_parts) or "default-provider-chain"

    def _build_llm_classification_cache_key(self, raw_text: str, extractor) -> str:
        normalized_text = " ".join(
            raw_text[:_LLM_CLASSIFICATION_TEXT_WINDOW].lower().split()
        )
        text_hash = hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()
        provider_fingerprint = self._get_llm_classification_provider_fingerprint(extractor)
        return (
            f"{_LLM_CLASSIFICATION_CACHE_VERSION}:"
            f"{provider_fingerprint}:{text_hash}"
        )

    def _get_cached_llm_classification(
        self, cache_key: str
    ) -> Optional[DBDocumentType]:
        cache = self._get_llm_classification_cache()
        self._last_llm_classification_cache_hit = False

        cached_entry = cache.get(cache_key)
        if not cached_entry:
            return None

        expires_at, cached_value = cached_entry
        if expires_at <= time.time():
            cache.pop(cache_key, None)
            return None

        cache.move_to_end(cache_key)
        self._last_llm_classification_cache_hit = True
        try:
            return DBDocumentType(cached_value)
        except ValueError:
            cache.pop(cache_key, None)
            return None

    def _set_cached_llm_classification(
        self, cache_key: str, db_type: DBDocumentType
    ) -> None:
        cache = self._get_llm_classification_cache()
        cache[cache_key] = (
            time.time() + _LLM_CLASSIFICATION_CACHE_TTL_SECONDS,
            db_type.value,
        )
        cache.move_to_end(cache_key)

        while len(cache) > _LLM_CLASSIFICATION_CACHE_MAX_SIZE:
            cache.popitem(last=False)

    def _get_llm_arbitration_threshold(
        self, db_type: DBDocumentType, method: str
    ) -> float:
        if db_type in {DBDocumentType.RECEIPT, DBDocumentType.INVOICE}:
            return 0.62 if method == "regex" else 0.72

        if db_type in {
            DBDocumentType.PURCHASE_CONTRACT,
            DBDocumentType.RENTAL_CONTRACT,
            DBDocumentType.LOAN_CONTRACT,
            DBDocumentType.BANK_STATEMENT,
            DBDocumentType.KONTOAUSZUG,
            DBDocumentType.LOHNZETTEL,
            DBDocumentType.EINKOMMENSTEUERBESCHEID,
            DBDocumentType.SVS_NOTICE,
            DBDocumentType.VERSICHERUNGSBESTAETIGUNG,
        } or db_type in self.TAX_FORM_DB_TYPES:
            return 0.75

        return 0.70

    def _build_dedup_extracted_summary(
        self, extracted: Dict[str, Any], db_type: DBDocumentType
    ) -> Dict[str, Any]:
        extracted_summary = {
            key: value
            for key, value in extracted.items()
            if key in _DEDUP_MATCH_FIELDS and value is not None
        }
        extracted_summary["document_type"] = (
            db_type.value if hasattr(db_type, "value") else str(db_type)
        )
        return extracted_summary

    def _should_run_duplicate_entity_check(
        self,
        db_type: DBDocumentType,
        result: "PipelineResult",
        decision=None,
    ) -> Tuple[bool, str]:
        extracted = result.extracted_data or {}
        if not extracted:
            return False, "no_extracted_data"

        if db_type in {DBDocumentType.BANK_STATEMENT, DBDocumentType.KONTOAUSZUG}:
            return False, "bank_statement_import"

        decision = decision or self._build_phase_two_decision(db_type)
        if not self._decision_has_transaction_suggestions(decision):
            return False, "non_transaction_document"

        extracted_summary = self._build_dedup_extracted_summary(extracted, db_type)
        summary_fields = [
            key for key in extracted_summary.keys()
            if key != "document_type"
        ]
        if len(summary_fields) < 2:
            return False, "insufficient_match_fields"

        return True, "eligible"

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

            decision = self._build_phase_two_decision(db_type)
            result.processing_decision = decision.model_dump(mode="json")

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
                        "processing_decision": result.processing_decision,
                    },
                )
            )
            result.current_state = "first_result_available"
            self._persist_checkpoint_state(document, result, commit=True)

            phase_2_checkpoint = metering_service.begin_phase(
                phase=ProcessingPhase.PHASE_2,
                checkpoint=PhaseCheckpointType.FINALIZATION,
                entry_stage=PipelineStage.SUGGEST.value,
                metadata={
                    "document_type": db_type.value,
                    "processing_decision": result.processing_decision,
                },
            )
            result.phase_checkpoints.append(phase_2_checkpoint.model_dump(mode="json"))
            result.current_state = "finalizing"
            self._persist_checkpoint_state(document, result, commit=True)

            # Stage 4.5: AI-driven duplicate entity check
            self._check_duplicate_entity(document, db_type, result, decision=decision)

            # Stage 5: Build suggestions AND auto-create
            self._stage_suggest(document, db_type, ocr_result, result, decision=decision)

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
            # Guarantee: every document gets at least one suggestion/feedback
            self._ensure_suggestion_exists(document, db_type, result)

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

        pipeline_state = {}
        if isinstance(document.ocr_result, dict):
            pipeline_state = document.ocr_result.get("_pipeline") or {}
        vision_provider_preference = pipeline_state.get("ocr_provider_override")
        reprocess_mode = pipeline_state.get("reprocess_mode")
        # When reprocessing or when the document has no meaningful type yet,
        # do NOT lock the classification with the old document_type.
        # The previous type may be wrong (e.g. SVS misclassified as INVOICE
        # because only page-1 text was available during initial classification).
        # Also skip hint for OTHER (upload default) — let the classifier decide.
        _skip_hint = (
            reprocess_mode
            or document.document_type is None
            or document.document_type == DBDocumentType.OTHER
        )
        doc_type_hint = None if _skip_hint else document.document_type

        # Build user identity string for VLM direction detection
        user_identity = None
        try:
            from app.models.user import User as _User
            _user = self.db.query(_User).filter(_User.id == document.user_id).first()
            if _user:
                parts = []
                if _user.name:
                    parts.append(_user.name)
                if getattr(_user, "business_name", None):
                    parts.append(_user.business_name)
                if parts:
                    user_identity = " / ".join(parts)
        except Exception:
            pass

        ocr_result = self.ocr_engine.process_document(
            image_bytes,
            mime_type=document.mime_type,
            vision_provider_preference=vision_provider_preference,
            reprocess_mode=reprocess_mode,
            document_type_hint=doc_type_hint,
            user_identity=user_identity,
        )
        result.provider_used = ocr_result.provider_used
        result.ocr_confidence_score = ocr_result.confidence_score
        result.reprocess_mode = reprocess_mode
        result.reprocess_requested_at = pipeline_state.get("reprocess_requested_at")
        result.ocr_provider_override = vision_provider_preference
        self._log_audit(
            result, "ocr",
            f"OCR completed: confidence={ocr_result.confidence_score:.2f}, "
            f"type={ocr_result.document_type.value}"
        )
        return ocr_result

    # ---- Stage 2: Classification arbitration ----

    # Types that can be directly trusted from unified VLM classification
    # (first-batch types only — not tax forms, contracts, bank statements)
    _VLM_DIRECT_PASSTHROUGH_TYPES = {
        DBDocumentType.RECEIPT,
        DBDocumentType.INVOICE,
        DBDocumentType.SVS_NOTICE,
        DBDocumentType.OTHER,
        DBDocumentType.SPENDENBESTAETIGUNG,
        DBDocumentType.KIRCHENBEITRAG,
        DBDocumentType.VERSICHERUNGSBESTAETIGUNG,
        DBDocumentType.BETRIEBSKOSTENABRECHNUNG,
    }

    def _stage_classify(
        self, document: Document, ocr_result: OCRResult, result: PipelineResult
    ) -> DBDocumentType:
        """
        Classify document type with multi-signal arbitration.

        Priority:
          0. VLM direct pass-through (unified_vision with high confidence)
          1. OCR engine classification (regex patterns)
          2. Filename hints (if OCR confidence is low)
          3. LLM classification (if still ambiguous and LLM available)
        """
        ocr_type = ocr_result.document_type
        ocr_confidence = ocr_result.confidence_score

        # -- VLM direct pass-through --
        # When the unified VLM already classified with high confidence AND
        # the type is in our first-batch allowlist, trust it and skip arbitration.
        classification_source = getattr(ocr_result, "classification_source", None)
        if (
            classification_source == "unified_vision"
            and ocr_confidence >= 0.85
        ):
            if ocr_type in OCR_TO_DB_TYPE_MAP:
                db_type = OCR_TO_DB_TYPE_MAP[ocr_type]
            else:
                try:
                    db_type = DBDocumentType[ocr_type.name]
                except KeyError:
                    db_type = DBDocumentType.OTHER

            if db_type in self._VLM_DIRECT_PASSTHROUGH_TYPES:
                classification = ClassificationResult(
                    document_type=db_type.value,
                    confidence=ocr_confidence,
                    method="vlm_direct",
                )
                document.document_type = db_type
                result.classification = classification
                result.stage_reached = PipelineStage.CLASSIFY
                self._log_audit(
                    result, "classify",
                    f"VLM direct pass-through: {db_type.value} "
                    f"(confidence {ocr_confidence:.2f})"
                )
                return db_type

        # -- Standard multi-signal arbitration --
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

        filename_type = self._classify_by_filename(document.file_name)

        # Signal 2: Filename boost when OCR classification is weak
        if db_type == DBDocumentType.OTHER or ocr_confidence < 0.5:
            if filename_type and filename_type != DBDocumentType.OTHER:
                self._log_audit(
                    result, "classify",
                    f"Filename override: {db_type.value} → {filename_type.value} "
                    f"(OCR confidence was {ocr_confidence:.2f})"
                )
                db_type = filename_type
                classification.method = "filename"
                classification.confidence = max(ocr_confidence, 0.6)

        # Signal 2.5: Keyword boost for known sensitive document families.
        if db_type == DBDocumentType.OTHER or classification.confidence < 0.5:
            keyword_type = self._classify_by_keyword_hints(ocr_result.raw_text)
            if keyword_type and keyword_type != DBDocumentType.OTHER:
                self._log_audit(
                    result, "classify",
                    f"Keyword override: {db_type.value} → {keyword_type.value} "
                    f"(OCR confidence was {ocr_confidence:.2f})"
                )
                db_type = keyword_type
                classification.method = "keyword"
                classification.confidence = max(classification.confidence, 0.62)

        # Signal 3: LLM arbitration for ambiguous results.
        # Keep stricter thresholds for route-sensitive families than for routine receipts/invoices.
        llm_threshold = self._get_llm_arbitration_threshold(
            db_type, classification.method
        )
        should_try_llm = (
            ocr_result.raw_text
            and len(ocr_result.raw_text.strip()) > 50
            and (
                db_type == DBDocumentType.OTHER
                or classification.confidence < llm_threshold
            )
        )
        if should_try_llm:
            llm_type = self._try_llm_classification(ocr_result.raw_text)
            cache_hint = ""
            if getattr(self, "_last_llm_classification_cache_hit", False):
                cache_hint = " (cache hit)"
            if llm_type and llm_type != DBDocumentType.OTHER:
                if db_type == DBDocumentType.OTHER:
                    # LLM found a type when regex couldn't — use it
                    self._log_audit(
                        result, "classify",
                        f"LLM classification{cache_hint} (regex failed): "
                        f"OTHER → {llm_type.value}"
                    )
                    db_type = llm_type
                    classification.method = "llm"
                    classification.confidence = 0.65
                elif llm_type != db_type:
                    # LLM disagrees with regex — LLM wins when regex confidence is low
                    self._log_audit(
                        result, "classify",
                        f"LLM override{cache_hint} "
                        f"(low confidence {classification.confidence:.2f}, "
                        f"threshold {llm_threshold:.2f}): "
                        f"{db_type.value} → {llm_type.value}"
                    )
                    db_type = llm_type
                    classification.method = "llm_override"
                    classification.confidence = 0.70
                else:
                    # LLM agrees with regex — boost confidence
                    self._log_audit(
                        result, "classify",
                        f"LLM confirmed regex classification{cache_hint}: "
                        f"{db_type.value} (confidence boosted)"
                    )
                    classification.method = "regex+llm"
                    classification.confidence = min(classification.confidence + 0.15, 0.95)
                classification.needs_llm_arbitration = True

        # Detect unsupported document types for suggestion guarantee
        if db_type == DBDocumentType.OTHER and ocr_result.raw_text:
            _text_low = ocr_result.raw_text.lower()[:2000]
            _unsupported = None
            if "dienstzettel" in _text_low or "pflichten aus dem arbeitsvertrag" in _text_low:
                _unsupported = "dienstzettel"
            elif any(m in _text_low for m in ["übergabeprotokoll", "uebergabeprotokoll",
                                               "wohnungsübergabe", "wohnungsuebergabe"]):
                _unsupported = "handover_protocol"
            elif any(m in _text_low for m in ["körperschaftsteuer", "koerperschaftsteuer",
                                               "k1-pdf", "k 1-pdf"]):
                _unsupported = "k1_form"
            if _unsupported:
                ocr_json = document.ocr_result if isinstance(document.ocr_result, dict) else {}
                ocr_json["_unsupported_type"] = _unsupported
                document.ocr_result = ocr_json
                self._log_audit(result, "classify", f"Unsupported type detected: {_unsupported}")

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
        loan_markers = ("kreditvertrag", "zinsbescheinigung", "darlehen", "wohnbaukredit")
        if any(marker in fname_lower for marker in loan_markers):
            return DBDocumentType.LOAN_CONTRACT
        if "kredit" in fname_lower and any(marker in fname_lower for marker in ("zins", "tilgung", "annuit", "wohnbau")):
            return DBDocumentType.LOAN_CONTRACT

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

    def _classify_by_keyword_hints(self, raw_text: Optional[str]) -> Optional[DBDocumentType]:
        """Classify ambiguous documents using lightweight keyword bundles."""
        if not raw_text:
            return None

        text_low = raw_text.lower()

        loan_keywords = (
            "kreditnehmer",
            "darlehensnehmer",
            "kreditkonto",
            "wohnbaukredit",
            "zinsbescheinigung",
            "zinsaufwand",
            "tilgung",
            "annuitaet",
            "annuität",
            "hypothekendarlehen",
        )
        loan_hits = sum(1 for keyword in loan_keywords if keyword in text_low)
        if loan_hits >= 2:
            return DBDocumentType.LOAN_CONTRACT

        return None

    def _try_llm_classification(self, raw_text: str) -> Optional[DBDocumentType]:
        """Use LLM as fallback for document classification."""
        try:
            from app.services.llm_extractor import get_llm_extractor
            extractor = get_llm_extractor()
            self._last_llm_classification_cache_hit = False
            if not extractor.is_available:
                return None

            cache_key = self._build_llm_classification_cache_key(raw_text, extractor)
            cached_type = self._get_cached_llm_classification(cache_key)
            if cached_type is not None:
                return cached_type

            llm_type_str = extractor.classify_document(raw_text)
            if not llm_type_str:
                return None

            # Map LLM response to DB type — comprehensive mapping
            llm_type_map = {
                "invoice": DBDocumentType.INVOICE,
                "receipt": DBDocumentType.RECEIPT,
                "mietvertrag": DBDocumentType.RENTAL_CONTRACT,
                "rental_contract": DBDocumentType.RENTAL_CONTRACT,
                "kaufvertrag": DBDocumentType.PURCHASE_CONTRACT,
                "purchase_contract": DBDocumentType.PURCHASE_CONTRACT,
                "purchase_contract_vehicle": DBDocumentType.PURCHASE_CONTRACT,
                "e1_form": DBDocumentType.E1_FORM,
                "e1a_beilage": DBDocumentType.E1A_BEILAGE,
                "e1b_beilage": DBDocumentType.E1B_BEILAGE,
                "e1kv_beilage": DBDocumentType.E1KV_BEILAGE,
                "l1_form": DBDocumentType.L1_FORM,
                "l1k_beilage": DBDocumentType.L1K_BEILAGE,
                "l1ab_beilage": DBDocumentType.L1AB_BEILAGE,
                "u1_form": DBDocumentType.U1_FORM,
                "u30_form": DBDocumentType.U30_FORM,
                "lohnzettel": DBDocumentType.LOHNZETTEL,
                "lohnzettel_l16": DBDocumentType.LOHNZETTEL,
                "payslip": DBDocumentType.LOHNZETTEL,
                "einkommensteuerbescheid": DBDocumentType.EINKOMMENSTEUERBESCHEID,
                "jahresabschluss": DBDocumentType.JAHRESABSCHLUSS,
                "bank_statement": DBDocumentType.BANK_STATEMENT,
                "kontoauszug": DBDocumentType.KONTOAUSZUG,
                "svs_notice": DBDocumentType.SVS_NOTICE,
                "betriebskostenabrechnung": DBDocumentType.BETRIEBSKOSTENABRECHNUNG,
                "versicherungsbestaetigung": DBDocumentType.VERSICHERUNGSBESTAETIGUNG,
                "spendenbestaetigung": DBDocumentType.SPENDENBESTAETIGUNG,
                "kirchenbeitrag": DBDocumentType.KIRCHENBEITRAG,
                "kreditvertrag": DBDocumentType.LOAN_CONTRACT,
                "loan_contract": DBDocumentType.LOAN_CONTRACT,
                # Unsupported types → map to OTHER
                "k1_unsupported": DBDocumentType.OTHER,
                "k1_form": DBDocumentType.OTHER,
                "dienstzettel_not_payslip": DBDocumentType.OTHER,
                "dienstzettel": DBDocumentType.OTHER,
                "handover_protocol": DBDocumentType.OTHER,
                "other": DBDocumentType.OTHER,
            }
            # Case-insensitive lookup
            resolved_type = llm_type_map.get(llm_type_str.lower().strip())
            if resolved_type is not None:
                self._set_cached_llm_classification(cache_key, resolved_type)
            return resolved_type

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
        # SVS: build date from quarter + tax_year before generic date autofix
        if db_type == DBDocumentType.SVS_NOTICE:
            self._autofix_svs_date(extracted_data, validation)
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
            amount = normalize_amount(value)
            if amount is None:
                # Can't parse at all — this IS an error, can't auto-fix
                validation.issues.append(ValidationIssue(
                    field=field_name,
                    issue=f"Invalid amount value: {value}",
                    severity="error",
                ))
                continue

            normalized = float(amount)
            if str(value) != str(normalized):
                validation.corrected_fields[field_name] = normalized

            if normalized < 0:
                # Auto-fix: take absolute value
                fixed = abs(normalized)
                validation.corrected_fields[field_name] = fixed
                validation.issues.append(ValidationIssue(
                    field=field_name,
                    issue=f"Auto-corrected negative amount {normalized} → {fixed}",
                    severity="info",
                ))
            # Zero is OK — might be a free item or zero-cost document

    def _autofix_svs_date(self, data: Dict[str, Any], validation: ValidationResult):
        """Build SVS date from quarter + tax_year if date is missing/unparseable.

        SVS quarterly notices often don't have a clear invoice date, but they
        have quarter (1-4) and tax_year fields. Use the quarter end date
        so each quarter gets a unique date and dedup doesn't merge them.
        """
        existing_date = data.get("date")
        if existing_date:
            parsed = normalize_date(existing_date)
            if parsed and parsed.year >= 2000 and parsed.year <= 2100:
                return  # Date already valid, no fix needed

        quarter = data.get("quarter")
        tax_year = data.get("tax_year")
        if not quarter or not tax_year:
            return

        try:
            q = int(quarter)
            y = int(tax_year)
            if q < 1 or q > 4 or y < 2000:
                return
            # Use quarter end date: Q1→03-31, Q2→06-30, Q3→09-30, Q4→12-31
            quarter_end = {1: "03-31", 2: "06-30", 3: "09-30", 4: "12-31"}
            svs_date = f"{y}-{quarter_end[q]}"
            data["date"] = svs_date
            validation.corrected_fields["date"] = svs_date
            validation.issues.append(ValidationIssue(
                field="date",
                issue=f"SVS date built from Q{q}/{y}: {svs_date}",
                severity="info",
            ))
        except (ValueError, TypeError):
            pass

    def _autofix_date(self, data: Dict[str, Any], validation: ValidationResult):
        """Auto-fix date fields: unparseable→today, future→today."""
        for field_name in ("date", "purchase_date", "start_date"):
            value = data.get(field_name)
            if value is None:
                continue

            parsed_date = normalize_date(value)
            if parsed_date and isinstance(value, str):
                normalized = parsed_date.isoformat()
                if value != normalized:
                    validation.corrected_fields[field_name] = normalized

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
            # Sync from the generic 'date' field — VLM returns 'date' for all doc types,
            # but contracts use purchase_date/start_date internally.
            generic_date = data.get("date") if date_field != "date" else None
            if generic_date:
                parsed = normalize_date(generic_date)
                if parsed:
                    data[date_field] = parsed.isoformat()
                    validation.issues.append(ValidationIssue(
                        field=date_field,
                        issue=f"Synced from document date: {parsed}",
                        severity="info",
                    ))
                    # done — no need to default to today
                else:
                    today = date.today().isoformat()
                    validation.corrected_fields[date_field] = today
                    validation.issues.append(ValidationIssue(
                        field=date_field, issue=f"No date found, auto-set to {today}", severity="info",
                    ))
            else:
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
        reverse_charge_detected = self._invoice_looks_reverse_charge(data)
        normalized_amount = normalize_amount(amount)
        normalized_vat_amount = normalize_amount(vat_amount)
        normalized_vat_rate = normalize_vat_rate(vat_rate)

        if normalized_amount is not None and amount is not None:
            normalized_float = float(normalized_amount)
            if str(amount) != str(normalized_float):
                validation.corrected_fields["amount"] = normalized_float

        if normalized_vat_amount is not None and vat_amount is not None:
            normalized_float = float(normalized_vat_amount)
            if str(vat_amount) != str(normalized_float):
                validation.corrected_fields["vat_amount"] = normalized_float

        if normalized_vat_rate is not None and vat_rate is not None:
            normalized_float = float(normalized_vat_rate)
            if str(vat_rate) != str(normalized_float):
                validation.corrected_fields["vat_rate"] = normalized_float

        # If VAT rate is known but VAT amount is missing, calculate it
        if normalized_amount is not None and normalized_vat_rate is not None and normalized_vat_amount is None:
            amt = float(normalized_amount)
            rate = float(normalized_vat_rate) / 100.0
            calculated_vat = round(amt * rate / (1 + rate), 2)
            validation.corrected_fields["vat_amount"] = calculated_vat
            validation.issues.append(ValidationIssue(
                field="vat_amount",
                issue=f"Auto-calculated VAT: €{calculated_vat:.2f} ({float(normalized_vat_rate):g}%)",
                severity="info",
            ))
        elif normalized_amount is not None and normalized_vat_amount is not None and normalized_vat_rate is not None:
            # Check consistency
            amt = float(normalized_amount)
            vat = float(normalized_vat_amount)
            rate = float(normalized_vat_rate) / 100.0
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

        # If no VAT rate, only default to Austrian standard 20% for plain domestic invoices.
        if normalized_amount is not None and normalized_vat_rate is None and reverse_charge_detected:
            validation.issues.append(ValidationIssue(
                field="vat_rate",
                issue="No VAT rate found; reverse-charge indicators detected, skipped Austrian 20% fallback",
                severity="info",
            ))
        elif normalized_amount is not None and normalized_vat_rate is None:
            validation.corrected_fields["vat_rate"] = 20
            amt = float(normalized_amount)
            calculated_vat = round(amt * 0.2 / 1.2, 2)
            if normalized_vat_amount is None:
                validation.corrected_fields["vat_amount"] = calculated_vat
            validation.issues.append(ValidationIssue(
                field="vat_rate",
                issue="No VAT rate found, auto-set to 20% (Austrian standard)",
                severity="info",
            ))

    def _invoice_looks_reverse_charge(self, data: Dict[str, Any]) -> bool:
        """Return True when invoice text strongly suggests reverse-charge VAT treatment."""
        text_fragments: list[str] = []

        for key in (
            "raw_text",
            "description",
            "merchant",
            "supplier",
            "tax_note",
            "notes",
            "invoice_text",
        ):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                text_fragments.append(value)

        for list_key in ("line_items", "items"):
            raw_items = data.get(list_key)
            if not isinstance(raw_items, list):
                continue
            for item in raw_items:
                if not isinstance(item, dict):
                    continue
                for item_key in ("name", "description", "vat_indicator", "notes"):
                    value = item.get(item_key)
                    if isinstance(value, str) and value.strip():
                        text_fragments.append(value)

        if not text_fragments:
            return False

        haystack = " ".join(text_fragments).lower()
        return any(hint in haystack for hint in _REVERSE_CHARGE_VAT_HINTS)

    def _validate_receipt(self, data: Dict[str, Any], validation: ValidationResult):
        """Validate receipt-specific fields."""
        if not data.get("amount"):
            # Try to compute from line items
            line_items = data.get("line_items", [])
            if line_items:
                normalized_items = [
                    normalize_amount(item.get("amount") or item.get("price"))
                    for item in line_items
                ]
                numeric_items = [item for item in normalized_items if item is not None]
                items_total = float(sum(numeric_items, Decimal("0"))) if numeric_items else 0.0
                if items_total > 0:
                    validation.corrected_fields["amount"] = round(items_total, 2)
                    validation.issues.append(ValidationIssue(
                        field="amount",
                        issue=f"No total found, auto-calculated from line items: €{items_total:.2f}",
                        severity="info",
                    ))
                    return

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
            normalized_items = [
                normalize_amount(item.get("amount") or item.get("price"))
                for item in line_items
            ]
            numeric_items = [item for item in normalized_items if item is not None]
            total_amount = normalize_amount(data["amount"])
            if numeric_items and total_amount is not None:
                items_total = float(sum(numeric_items, Decimal("0")))
                total = float(total_amount)
                diff = abs(items_total - total)
                if items_total > 0 and diff > 2.0:
                    validation.issues.append(ValidationIssue(
                        field="line_items",
                        issue=f"Line items sum ({items_total:.2f}) differs from "
                              f"total ({total:.2f}) by {diff:.2f}",
                        severity="info",
                    ))

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
        ocr_result: OCRResult, result: PipelineResult, decision=None,
    ):
        """Execute explicit Phase-2 actions for the classified document."""
        result.stage_reached = PipelineStage.SUGGEST

        decision = decision or self._build_phase_two_decision(db_type)
        result.processing_decision = decision.model_dump(mode="json")

        # Check if AI dedup found a match — if so, create link_to_existing suggestion
        # instead of normal transaction-create suggestions.
        ocr_json = document.ocr_result if isinstance(document.ocr_result, dict) else {}
        matched = ocr_json.get("matched_existing")
        has_transaction_action = self._decision_has_transaction_suggestions(decision)
        allow_link_to_existing = db_type in {
            DBDocumentType.BANK_STATEMENT,
            DBDocumentType.KONTOAUSZUG,
        }
        if (
            allow_link_to_existing
            and matched
            and matched.get("type") != "none"
            and has_transaction_action
        ):
            result.suggestions.append({
                "type": "link_to_existing",
                "status": "pending",
                "data": {
                    "matched_type": matched["type"],
                    "matched_id": matched.get("id"),
                    "reason": matched.get("reason", ""),
                    "extracted_data": result.extracted_data or {},
                },
                "document_id": document.id,
                "user_id": document.user_id,
                "confidence": 0.8,
            })
            self._log_audit(
                result, "suggest",
                f"Link-to-existing suggestion: {matched['type']} #{matched.get('id')} — {matched.get('reason')}"
            )
            # Skip normal suggestion building — user must confirm or reject the link first
            return

        for action in [*decision.primary_actions, *decision.secondary_actions]:
            self._execute_processing_action(
                action=action,
                document=document,
                db_type=db_type,
                ocr_result=ocr_result,
                result=result,
            )

    # ---- AI-Driven Duplicate Entity Check ----

    def _check_duplicate_entity(
        self,
        document: Document,
        db_type: DBDocumentType,
        result: "PipelineResult",
        decision=None,
    ):
        """DB-only duplicate entity check (no LLM call).

        Matches extracted data against user's existing entities using
        deterministic rules. Only serves matched_existing / link_to_existing
        suggestions — does NOT participate in transaction creation gating
        or asset recognition blocking.

        If a match is found, stores it in ocr_result["matched_existing"] so
        suggestion builders can change behavior (link instead of create).
        """
        try:
            should_run, skip_reason = self._should_run_duplicate_entity_check(
                db_type, result, decision=decision
            )
            if not should_run:
                self._log_audit(
                    result,
                    "dedup",
                    f"Skipping dedup check: {skip_reason}",
                )
                return

            extracted = result.extracted_data or {}
            user_id = document.user_id

            match = self._db_match_entity(user_id, db_type, extracted)

            if match:
                ocr_json = document.ocr_result if isinstance(document.ocr_result, dict) else {}
                ocr_json["matched_existing"] = {
                    "type": match["type"],
                    "id": match.get("id"),
                    "reason": match.get("reason", ""),
                    "user_confirmed": None,
                }
                document.ocr_result = ocr_json

                self._log_audit(
                    result, "dedup",
                    f"DB match found: {match['type']} #{match.get('id')} — {match.get('reason')}"
                )
            else:
                self._log_audit(result, "dedup", "No duplicate entity match (DB-only)")

        except Exception as e:
            logger.warning(f"Dedup check failed (non-critical): {e}")
            self._log_audit(result, "dedup", f"Dedup check error (skipped): {e}")

    def _db_match_entity(
        self,
        user_id: int,
        db_type: DBDocumentType,
        extracted: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Deterministic DB matching for duplicate entity detection.

        Only serves matched_existing / link_to_existing suggestions.
        Returns match dict or None.
        """
        # Extract matching signals from VLM dedup_hints or standard fields
        dedup_hints = extracted.get("dedup_hints", {})
        if isinstance(dedup_hints, str):
            dedup_hints = {}
        entity_name = (
            dedup_hints.get("entity_name")
            or extracted.get("merchant")
            or extracted.get("issuer")
            or ""
        ).strip().lower()
        entity_address = (
            dedup_hints.get("entity_address")
            or extracted.get("property_address")
            or ""
        ).strip().lower()
        amount = None
        for amt_key in ("amount", "purchase_price", "monthly_rent", "praemie", "beitrag_gesamt"):
            raw = extracted.get(amt_key)
            if raw is not None:
                try:
                    amount = float(raw)
                    break
                except (ValueError, TypeError):
                    continue

        doc_date = extracted.get("date")

        if not entity_name and not entity_address and amount is None:
            return None

        # 1. Match properties by address
        if entity_address and len(entity_address) > 5:
            try:
                from app.models.property import Property, PropertyStatus
                properties = self.db.query(Property).filter(
                    Property.user_id == user_id,
                    Property.status == PropertyStatus.ACTIVE,
                ).limit(10).all()
                for p in properties:
                    addr = (getattr(p, "address", "") or "").strip().lower()
                    if addr and len(addr) > 5:
                        # Substring match (normalized)
                        if addr in entity_address or entity_address in addr:
                            return {
                                "type": "property",
                                "id": p.id,
                                "reason": f"Adresse stimmt überein: {addr[:50]}",
                            }
            except Exception:
                pass

        # 2. Match recurring transactions by merchant + amount (±5%)
        if entity_name and amount is not None:
            try:
                from app.models.recurring_transaction import RecurringTransaction
                recurrings = self.db.query(RecurringTransaction).filter(
                    RecurringTransaction.user_id == user_id,
                    RecurringTransaction.is_active == True,
                ).limit(20).all()
                for r in recurrings:
                    r_desc = (r.description or "").strip().lower()
                    r_amount = float(r.amount) if r.amount else None
                    if r_desc and r_amount is not None:
                        name_match = entity_name in r_desc or r_desc in entity_name
                        amount_match = (
                            abs(amount - r_amount) / max(abs(r_amount), 1.0) <= 0.05
                        )
                        if name_match and amount_match:
                            return {
                                "type": "recurring",
                                "id": r.id,
                                "reason": f"Wiederkehrend: {r_desc[:40]} €{r_amount}",
                            }
            except Exception:
                pass

        # 3. Match recent transactions by merchant + amount + date (±7 days)
        if entity_name and amount is not None:
            try:
                from app.models.transaction import Transaction
                from datetime import timedelta
                cutoff = datetime.utcnow() - timedelta(days=90)
                recent = self.db.query(Transaction).filter(
                    Transaction.user_id == user_id,
                    Transaction.transaction_date >= cutoff,
                ).order_by(Transaction.transaction_date.desc()).limit(30).all()
                for t in recent:
                    t_desc = (t.description or "").strip().lower()
                    t_amount = float(t.amount) if t.amount else None
                    if t_desc and t_amount is not None:
                        name_match = entity_name in t_desc or t_desc in entity_name
                        amount_match = (
                            abs(amount - t_amount) / max(abs(t_amount), 1.0) <= 0.05
                        )
                        date_match = True
                        if doc_date and t.transaction_date:
                            try:
                                from datetime import datetime as dt_cls
                                if isinstance(doc_date, str):
                                    doc_dt = dt_cls.strptime(doc_date[:10], "%Y-%m-%d").date()
                                else:
                                    doc_dt = doc_date
                                t_dt = t.transaction_date
                                if hasattr(t_dt, "date"):
                                    t_dt = t_dt.date()
                                date_match = abs((doc_dt - t_dt).days) <= 7
                            except Exception:
                                date_match = True  # Can't parse → don't block match

                        if name_match and amount_match and date_match:
                            return {
                                "type": "transaction",
                                "id": t.id,
                                "reason": f"Ähnliche Transaktion: {t_desc[:40]} €{t_amount}",
                            }
            except Exception:
                pass

        return None

    def _build_entity_summaries(self, user_id: int) -> str:
        """Build compact text summaries of user's existing entities for LLM context."""
        parts = []

        try:
            # Properties
            from app.models.property import Property, PropertyStatus
            properties = self.db.query(Property).filter(
                Property.user_id == user_id,
                Property.status == PropertyStatus.ACTIVE,
            ).all()
            if properties:
                prop_lines = []
                for p in properties[:10]:  # Cap at 10
                    addr = getattr(p, 'address', '') or ''
                    price = getattr(p, 'purchase_price', '') or ''
                    prop_lines.append(f"  ID={p.id}: {addr} (Kaufpreis: {price})")
                parts.append("Immobilien:\n" + "\n".join(prop_lines))

            # Recurring transactions
            from app.models.recurring_transaction import RecurringTransaction
            recurrings = self.db.query(RecurringTransaction).filter(
                RecurringTransaction.user_id == user_id,
                RecurringTransaction.is_active == True,
            ).all()
            if recurrings:
                rec_lines = []
                for r in recurrings[:20]:  # Cap at 20
                    rec_lines.append(
                        f"  ID={r.id}: {r.description} — €{r.amount}/{r.frequency}"
                    )
                parts.append("Wiederkehrende Ausgaben/Einnahmen:\n" + "\n".join(rec_lines))

            # Loans
            try:
                from app.models.property_loan import PropertyLoan
                loans = self.db.query(PropertyLoan).filter(
                    PropertyLoan.user_id == user_id,
                ).all()
                if loans:
                    loan_lines = []
                    for l in loans[:5]:
                        loan_lines.append(
                            f"  ID={l.id}: {getattr(l, 'lender_name', 'Unbekannt')} — €{getattr(l, 'loan_amount', '?')}"
                        )
                    parts.append("Kredite:\n" + "\n".join(loan_lines))
            except Exception:
                pass  # Loan model may not exist

            # Assets
            try:
                from app.models.asset import Asset
                assets = self.db.query(Asset).filter(
                    Asset.user_id == user_id,
                ).all()
                if assets:
                    asset_lines = []
                    for a in assets[:15]:
                        asset_lines.append(
                            f"  ID={a.id}: {getattr(a, 'name', '')} — €{getattr(a, 'purchase_price', '?')}"
                        )
                    parts.append("Vermögenswerte:\n" + "\n".join(asset_lines))
            except Exception:
                pass

            # Recent transactions (90 days)
            from app.models.transaction import Transaction
            from datetime import datetime, timedelta
            cutoff = datetime.utcnow() - timedelta(days=90)
            recent = self.db.query(Transaction).filter(
                Transaction.user_id == user_id,
                Transaction.transaction_date >= cutoff,
            ).order_by(Transaction.transaction_date.desc()).limit(30).all()
            if recent:
                txn_lines = []
                for t in recent:
                    txn_lines.append(
                        f"  ID={t.id}: {t.transaction_date} {t.description} €{t.amount}"
                    )
                parts.append("Letzte Transaktionen (90 Tage):\n" + "\n".join(txn_lines))

        except Exception as e:
            self.db.rollback()
            logger.warning(f"Failed to build entity summaries: {e}")

        return "\n\n".join(parts) if parts else ""

    # ---- Suggestion Guarantee ----

    # Tax form types that should generate import suggestions
    TAX_FORM_SUGGESTION_TYPES = {
        DBDocumentType.E1_FORM, DBDocumentType.E1A_BEILAGE, DBDocumentType.E1B_BEILAGE,
        DBDocumentType.E1KV_BEILAGE, DBDocumentType.L1_FORM, DBDocumentType.L1K_BEILAGE,
        DBDocumentType.L1AB_BEILAGE, DBDocumentType.U1_FORM, DBDocumentType.U30_FORM,
        DBDocumentType.LOHNZETTEL, DBDocumentType.SVS_NOTICE,
        DBDocumentType.EINKOMMENSTEUERBESCHEID, DBDocumentType.JAHRESABSCHLUSS,
    }

    def _ensure_suggestion_exists(
        self, document: Document, db_type: DBDocumentType, result: "PipelineResult"
    ):
        """Guarantee: every completed document has at least one suggestion.

        If Phase 2 didn't produce any suggestions (due to extraction failure,
        missing data, or unsupported type), generate a fallback suggestion
        so the user always gets feedback.
        """
        if result.suggestions:
            return  # Already has suggestions — nothing to do

        # Check if this was detected as an unsupported type
        classification = result.classification
        unsupported_type = None
        if classification and hasattr(classification, 'document_type'):
            # Check if the original OCR result had _unsupported_type metadata
            ocr_result_data = document.ocr_result or {}
            unsupported_type = ocr_result_data.get("_unsupported_type")

        if unsupported_type:
            # Unsupported document type (K1, Dienstzettel, Übergabeprotokoll)
            messages = {
                "k1_form": "K1 (Körperschaftsteuererklärung) — Taxja unterstützt derzeit keine GmbH-Steuererklärungen.",
                "dienstzettel": "Dienstzettel — kein steuerlich relevantes Dokument. Archiviert.",
                "handover_protocol": "Übergabeprotokoll — kein steuerlich relevantes Dokument. Archiviert.",
            }
            result.suggestions.append({
                "type": "not_supported",
                "status": "dismissed",
                "data": {"unsupported_type": unsupported_type},
                "review_reason": messages.get(unsupported_type, f"Unsupported document type: {unsupported_type}"),
                "confidence": 0,
            })
            self._log_audit(result, "suggest", f"Unsupported type fallback: {unsupported_type}")
            return

        # Tax form with no KZ data extracted
        if db_type in self.TAX_FORM_SUGGESTION_TYPES:
            type_name = db_type.value.lower()
            result.suggestions.append({
                "type": f"import_{type_name}",
                "status": "needs_review",
                "data": result.extracted_data or {},
                "review_reason": "Die strukturierten Steuerdaten konnten nicht vollständig extrahiert werden. Bitte überprüfen Sie das Dokument manuell.",
                "confidence": classification.confidence if classification else 0,
                "document_id": document.id,
                "user_id": document.user_id,
            })
            self._log_audit(result, "suggest", f"Tax form fallback suggestion: import_{type_name} (needs_review)")
            return

        # SVS notice with non-transaction subtype — show specific guidance
        if db_type == DBDocumentType.SVS_NOTICE:
            # Read subtype from document.ocr_result (set by _extract_from_svs_notice)
            # or from result.extracted_data (set by VLM)
            doc_ocr = document.ocr_result if isinstance(document.ocr_result, dict) else {}
            ed = result.extracted_data or {}
            svs_sub = doc_ocr.get("_svs_subtype") or ed.get("_svs_subtype") or ed.get("svs_subtype", "")
            _SVS_SUBTYPE_MESSAGES = {
                "kontoauszug": (
                    "SVS Beitragskontoauszug erkannt. "
                    "Bitte prüfen Sie die Soll/Haben-Summe gegen Ihre SVS-Transaktionen. "
                    "Ein Kontostand ≠ 0 zum 31.12. deutet auf offene Beiträge oder Überzahlungen hin."
                ),
                "herabsetzung": (
                    "SVS Herabsetzungsbescheid erkannt. "
                    "Ihre SVS-Beitragsgrundlage wurde geändert. "
                    "Bitte überprüfen Sie Ihre wiederkehrenden SVS-Zahlungen und passen Sie den Betrag an."
                ),
                "versicherungspflicht": (
                    "SVS Versicherungspflicht-Mitteilung erkannt. "
                    "Diese bestätigt Ihren Versicherungsbeginn und die Beitragsgruppe. "
                    "Bitte überprüfen Sie Ihr Steuerprofil."
                ),
                "mindestbeitrag": (
                    "SVS Mindestbeitragsgrundlage-Bescheid (Neugründer) erkannt. "
                    "Dies ist ein Referenzdokument für die ersten Geschäftsjahre."
                ),
                "zahlungserinnerung": (
                    "SVS Zahlungserinnerung erkannt. "
                    "Wenn Sie bereits bezahlt haben, ist keine weitere Aktion nötig. "
                    "Andernfalls bitte umgehend zahlen, um Säumniszuschläge zu vermeiden."
                ),
                "befreiung": (
                    "SVS Befreiungsbescheid erkannt. "
                    "Ihre KV/PV-Beiträge entfallen für den angegebenen Zeitraum. "
                    "Ihre SVS-Zahlungen reduzieren sich auf UV + Selbständigenvorsorge. "
                    "Hinweis: Die Befreiung muss jährlich neu beantragt werden."
                ),
                "kontobestaetigung": (
                    "SVS Kontobestätigung erkannt. "
                    "Dies ist eine Bestätigung Ihrer Beitragszahlungen — es wird keine Transaktion erstellt."
                ),
                "ratenzahlung": (
                    "SVS Ratenzahlungsvereinbarung erkannt. "
                    "Bitte überprüfen Sie die Ratenanzahl und den monatlichen Betrag. "
                    "Falls die automatische Erstellung nicht möglich war, erstellen Sie bitte "
                    "die wiederkehrende Zahlung manuell unter 'Wiederkehrende Transaktionen'."
                ),
                "saeumniszuschlag": (
                    "SVS Säumniszuschlag-Bescheid erkannt. "
                    "Der genaue Zuschlagsbetrag konnte nicht automatisch extrahiert werden. "
                    "Bitte geben Sie den Säumniszuschlag manuell ein. "
                    "Wichtig: Säumniszuschläge sind NICHT als Betriebsausgabe absetzbar."
                ),
            }
            msg = _SVS_SUBTYPE_MESSAGES.get(svs_sub)
            if msg:
                result.suggestions.append({
                    "type": "svs_info",
                    "status": "needs_review" if svs_sub in ("saeumniszuschlag", "ratenzahlung") else "dismissed",
                    "data": result.extracted_data or {},
                    "review_reason": msg,
                    "confidence": classification.confidence if classification else 0,
                    "document_id": document.id,
                    "user_id": document.user_id,
                })
                self._log_audit(result, "suggest", f"SVS subtype guidance: {svs_sub}")
                return

            # SVS without recognized subtype → manual review
            if not svs_sub or svs_sub not in ("vorschreibung", "nachforderung", "gutschrift", "saeumniszuschlag"):
                result.suggestions.append({
                    "type": "manual_review",
                    "status": "needs_review",
                    "data": result.extracted_data or {},
                    "review_reason": "SVS-Dokument erkannt, aber der genaue Typ konnte nicht bestimmt werden. Bitte manuell prüfen.",
                    "confidence": classification.confidence if classification else 0,
                    "document_id": document.id,
                    "user_id": document.user_id,
                })
                self._log_audit(result, "suggest", "SVS unknown subtype fallback")
                return

        # Invoice/Receipt with no transaction created
        if db_type in (DBDocumentType.INVOICE, DBDocumentType.RECEIPT):
            result.suggestions.append({
                "type": "create_transaction",
                "status": "needs_review",
                "data": result.extracted_data or {},
                "review_reason": "Betrag oder Empfänger konnte nicht extrahiert werden. Bitte überprüfen Sie die Daten.",
                "confidence": classification.confidence if classification else 0,
                "document_id": document.id,
                "user_id": document.user_id,
            })
            self._log_audit(result, "suggest", "Transaction fallback suggestion (needs_review)")
            return

        # Kinderbetreuungskosten — since 2019, no longer separately deductible
        # (replaced by Familienbonus Plus)
        if db_type == DBDocumentType.KINDERBETREUUNGSKOSTEN:
            result.suggestions.append({
                "type": "manual_review",
                "status": "needs_review",
                "data": result.extracted_data or {},
                "review_reason": (
                    "Kinderbetreuungskosten-Bestätigung erkannt. "
                    "Seit 2019 werden Kinderbetreuungskosten nicht mehr separat abgesetzt, "
                    "sondern über den Familienbonus Plus berücksichtigt. "
                    "Bitte prüfen Sie, ob der Familienbonus Plus bereits beantragt wurde."
                ),
                "confidence": classification.confidence if classification else 0,
                "document_id": document.id,
                "user_id": document.user_id,
            })
            self._log_audit(result, "suggest", "Kinderbetreuungskosten: Familienbonus Plus hint")
            return

        # Betriebskostenabrechnung — complex, needs property context
        if db_type == DBDocumentType.BETRIEBSKOSTENABRECHNUNG:
            result.suggestions.append({
                "type": "manual_review",
                "status": "needs_review",
                "data": result.extracted_data or {},
                "review_reason": (
                    "Betriebskostenabrechnung erkannt. "
                    "Bitte bestätigen Sie Ihre Rolle: Als Vermieter kann ein Teil der Kosten "
                    "als Werbungskosten geltend gemacht werden (nicht umlagefähiger Anteil). "
                    "Als Mieter ist die Abrechnung in der Regel steuerlich nicht relevant. "
                    "Bitte überprüfen Sie Nachzahlung/Gutschrift und die einzelnen Positionen."
                ),
                "confidence": classification.confidence if classification else 0,
                "document_id": document.id,
                "user_id": document.user_id,
            })
            self._log_audit(result, "suggest", "Betriebskosten: role clarification needed")
            return

        # Generic fallback — any other type
        result.suggestions.append({
            "type": "manual_review",
            "status": "needs_review",
            "data": result.extracted_data or {},
            "review_reason": f"Dokument als {db_type.value} klassifiziert, aber keine automatische Aktion verfügbar.",
            "confidence": classification.confidence if classification else 0,
            "document_id": document.id,
            "user_id": document.user_id,
        })
        self._log_audit(result, "suggest", f"Generic fallback suggestion for {db_type.value}")

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

        if action == ProcessingAction.BANK_STATEMENT_IMPORT:
            suggestion = self._build_bank_statement_import_suggestion(document, result)
            if suggestion:
                result.suggestions.append(suggestion)
                self._log_audit(
                    result,
                    "suggest",
                    "Built bank statement import suggestion",
                )
            return

        if action == ProcessingAction.TAX_FORM_IMPORT:
            # SVS: override suggestion status based on subtype
            if db_type == DBDocumentType.SVS_NOTICE:
                doc_ocr = document.ocr_result if isinstance(document.ocr_result, dict) else {}
                ed = result.extracted_data or {}
                svs_sub = doc_ocr.get("_svs_subtype") or ed.get("_svs_subtype") or ed.get("svs_subtype", "")

                # Reference-only subtypes: mark as dismissed, no review needed
                _SVS_DISMISSED_SUBTYPES = {
                    "kontoauszug", "herabsetzung", "versicherungspflicht",
                    "mindestbeitrag", "zahlungserinnerung", "kontobestaetigung",
                    "befreiung",
                }
                if svs_sub in _SVS_DISMISSED_SUBTYPES:
                    suggestion = self._build_tax_form_suggestion(document, db_type, result)
                    if suggestion:
                        suggestion["status"] = "dismissed"
                        result.suggestions.append(suggestion)
                        self._log_audit(result, "suggest", f"SVS {svs_sub}: reference document, dismissed")
                    return

                # Ratenzahlung: build import_suggestion so user can confirm → create recurring
                if svs_sub == "ratenzahlung":
                    ed = result.extracted_data or {}
                    nachzahlung = ed.get("nachzahlung") or ed.get("amount")
                    ratenanzahl = ed.get("ratenanzahl") or 0
                    ratenbetrag = ed.get("ratenbetrag") or 0

                    # Try to extract from raw_text if VLM didn't provide
                    import re as _re
                    raw = str(ed.get("raw_text") or "")
                    if not ratenanzahl:
                        m = _re.search(r'(\d+)\s*(?:Monats)?rate[n]?', raw, _re.IGNORECASE)
                        if m:
                            ratenanzahl = int(m.group(1))
                    if not ratenbetrag:
                        m = _re.search(r'(?:EUR|€)\s*(\d[\d.,]*)\s*(?:pro\s*Monat|monatlich)', raw, _re.IGNORECASE)
                        if m:
                            ratenbetrag = float(m.group(1).replace('.', '').replace(',', '.'))
                    if not ratenanzahl:
                        ratenanzahl = 6  # Common default
                    if not ratenbetrag and nachzahlung:
                        try:
                            ratenbetrag = round(float(nachzahlung) / int(ratenanzahl), 2)
                        except (ValueError, TypeError, ZeroDivisionError):
                            pass

                    import_sugg = {
                        "type": "create_recurring_expense",
                        "status": "pending",
                        "data": {
                            "amount": ratenbetrag,
                            "description": f"SVS Ratenzahlung ({ratenanzahl}x €{ratenbetrag:.2f})" if ratenbetrag else "SVS Ratenzahlung",
                            "category": "insurance",
                            "transaction_type": "expense",
                            "frequency": "monthly",
                            "start_date": ed.get("date"),
                            "ratenanzahl": ratenanzahl,
                            "is_deductible": True,
                            "deduction_reason": "SVS Nachbemessung Ratenzahlung — Betriebsausgabe im Zahlungsjahr",
                        },
                    }
                    # Store in ocr_result for the confirm-recurring-expense endpoint
                    ocr_json = document.ocr_result if isinstance(document.ocr_result, dict) else {}
                    ocr_json["import_suggestion"] = import_sugg
                    document.ocr_result = ocr_json
                    from sqlalchemy.orm.attributes import flag_modified
                    flag_modified(document, "ocr_result")
                    self.db.flush()

                    result.suggestions.append({
                        "type": "svs_ratenzahlung",
                        "status": "needs_review",
                        "data": import_sugg["data"],
                        "review_reason": (
                            f"SVS Ratenzahlungsvereinbarung: {ratenanzahl} Monatsraten à €{ratenbetrag:.2f}. "
                            "Bitte bestätigen Sie die Daten, um die wiederkehrende Zahlung zu erstellen."
                        ) if ratenbetrag else "SVS Ratenzahlungsvereinbarung erkannt. Bitte Ratendetails prüfen.",
                        "confidence": 0.95,
                        "document_id": document.id,
                        "user_id": document.user_id,
                    })
                    self._log_audit(result, "suggest", f"SVS Ratenzahlung: {ratenanzahl}x €{ratenbetrag}")
                    return

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
            # SVS_NOTICE: map SVS-specific fields to generic transaction fields
            # so the transaction suggestion builder can find amount/description.
            if db_type == DBDocumentType.SVS_NOTICE and result.extracted_data:
                ed = result.extracted_data
                if not ed.get("amount"):
                    for svs_amount_key in ("total_contribution", "gesamtbeitrag", "beitrag_gesamt"):
                        val = ed.get(svs_amount_key)
                        if val is not None and val != "" and val != 0:
                            ed["amount"] = val
                            break
                if not ed.get("description"):
                    ed["description"] = "SVS Beitragsvorschreibung"

            # TODO(v1.4-followup): transaction auto-create still runs outside the
            # asset-path quality gate. Whole-pipeline unification is not complete.
            transaction_suggestions = self._build_transaction_suggestions(
                document, db_type, result
            )
            result.suggestions.extend(transaction_suggestions)

            # Write detected direction back to extracted_data so frontend can read it
            if transaction_suggestions:
                first_suggestion = transaction_suggestions[0]
                detected_type = first_suggestion.get("transaction_type", "expense")
                if result.extracted_data is None:
                    result.extracted_data = {}
                result.extracted_data["_transaction_type"] = detected_type
                result.extracted_data["final_transaction_type"] = detected_type
                result.extracted_data["final_transaction_type_source"] = "transaction_suggestion"
                direction_source = (first_suggestion.get("extracted_fields") or {}).get("direction_source", "default")
                if direction_source != "default":
                    result.extracted_data["document_transaction_direction"] = detected_type
                    result.extracted_data["document_transaction_direction_source"] = direction_source

                # Persist commercial semantics and reversal flag from direction
                # resolution so the frontend can display the correct label.
                for meta_key in ("commercial_document_semantics", "is_reversal", "document_transaction_direction", "transaction_direction_resolution"):
                    if meta_key in first_suggestion and first_suggestion[meta_key] is not None:
                        result.extracted_data[meta_key] = first_suggestion[meta_key]

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

    def _extract_structured_import_data(self, ocr_result: Dict[str, Any]) -> Dict[str, Any]:
        """Collect persisted structured fields for import suggestions."""
        extracted_data = ocr_result.get("extracted_data", {})

        # Fallback: some OCR extractors store fields at top level of ocr_result
        # instead of nesting under "extracted_data". Collect non-internal fields.
        if not extracted_data:
            _internal_keys = {
                "_pipeline",
                "_validation",
                "confidence",
                "document_year",
                "year_basis",
                "year_confidence",
                "matched_existing",
                "import_suggestion",
                "asset_outcome",
                "transaction_suggestion",
                "tax_analysis",
                "_additional_receipts",
                "document_transaction_direction",
                "document_transaction_direction_source",
                "document_transaction_direction_confidence",
                "transaction_direction_resolution",
                "commercial_document_semantics",
                "is_reversal",
            }
            extracted_data = {
                k: v for k, v in ocr_result.items() if k not in _internal_keys and not k.startswith("_")
            }

        return extracted_data or {}

    def _build_bank_statement_import_suggestion(
        self, document: Document, result: PipelineResult
    ) -> Optional[Dict[str, Any]]:
        """Build import suggestion for bank statements without tax-form routing semantics."""
        try:
            ocr_result = document.ocr_result or {}
            extracted_data = self._extract_structured_import_data(ocr_result)
            if not extracted_data:
                return None

            suggestion = {
                "type": self.BANK_STATEMENT_SUGGESTION_TYPE,
                "status": "pending",
                "data": extracted_data,
                "confidence": ocr_result.get("confidence_score", 0.0),
            }

            import json as _json
            updated_ocr = _json.loads(_json.dumps(document.ocr_result)) if document.ocr_result else {}
            updated_ocr.update(
                self._build_bank_statement_direction_metadata(
                    document=document,
                    ocr_data=updated_ocr,
                    raw_text=result.raw_text,
                )
            )
            updated_ocr["import_suggestion"] = suggestion
            document.ocr_result = updated_ocr
            from sqlalchemy.orm.attributes import flag_modified

            flag_modified(document, "ocr_result")
            return suggestion
        except Exception as e:
            logger.warning(f"Bank statement import suggestion failed: {e}")
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
            extracted_data = self._extract_structured_import_data(ocr_result)
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

    def _build_bank_statement_direction_metadata(
        self,
        *,
        document: Document,
        ocr_data: dict[str, Any] | None,
        raw_text: str | None = None,
    ) -> dict[str, Any]:
        from app.services.contract_role_service import ContractRoleService, load_sensitive_user_context

        user = load_sensitive_user_context(self.db, document.user_id)
        if not user:
            return {}

        resolution = ContractRoleService(language=getattr(user, "language", None)).resolve_transaction_direction(
            user,
            DBDocumentType.BANK_STATEMENT,
            ocr_data or {},
            raw_text=raw_text or document.raw_text,
        )
        return {
            "document_transaction_direction": resolution.candidate,
            "document_transaction_direction_source": resolution.source,
            "document_transaction_direction_confidence": round(
                float(resolution.confidence),
                4,
            ),
            "transaction_direction_resolution": resolution.to_payload(),
            "commercial_document_semantics": resolution.semantics,
            "is_reversal": bool(resolution.is_reversal),
        }

    def _recover_missing_invoice_transaction_fields(
        self,
        *,
        db_type: DBDocumentType,
        raw_text: str | None,
        suggestion_ocr_data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Recover missing amount/date for a single receipt or invoice suggestion.

        This intentionally reuses the existing extractor once and only consumes
        the two critical fields needed by the transaction gate.
        """
        if db_type not in (DBDocumentType.RECEIPT, DBDocumentType.INVOICE):
            return {}
        if not raw_text or not raw_text.strip():
            return {}

        missing_amount = suggestion_ocr_data.get("amount") in (None, "")
        missing_date = not suggestion_ocr_data.get("date")
        if not (missing_amount or missing_date):
            return {}

        try:
            from app.services.llm_extractor import get_llm_extractor

            extractor = get_llm_extractor()
            recovered = extractor.extract(raw_text, db_type)
            if not isinstance(recovered, dict):
                return {}

            updates: dict[str, Any] = {}
            if missing_amount:
                recovered_amount = recovered.get("amount")
                if recovered_amount not in (None, ""):
                    updates["amount"] = recovered_amount

            if missing_date:
                recovered_date = recovered.get("date")
                if recovered_date:
                    if hasattr(recovered_date, "isoformat"):
                        updates["date"] = recovered_date.isoformat()
                    else:
                        updates["date"] = str(recovered_date)

            if updates:
                logger.info(
                    "Recovered missing OCR transaction fields for %s via narrow AI pass: %s",
                    db_type.value,
                    ", ".join(sorted(updates.keys())),
                )
            return updates
        except Exception as exc:
            logger.warning(
                "Narrow AI field recovery failed for %s: %s",
                db_type.value,
                exc,
            )
            return {}

    _income_category_cache: Dict[int, str] = {}

    def _resolve_income_category(self, user_id: int) -> str:
        """Map user's business_type to an income category."""
        if user_id in self._income_category_cache:
            return self._income_category_cache[user_id]

        category = "self_employment"  # default
        try:
            from app.models.user import User as _User
            _user = self.db.query(_User).filter(_User.id == user_id).first()
            if _user and getattr(_user, "business_type", None):
                bt = _user.business_type.lower()
                # Map Austrian business types to income categories
                type_map = {
                    "freiberufler": "freelance_income",      # §22 EStG
                    "gewerblich": "business_income",         # §23 EStG
                    "neue_selbstaendige": "self_employment", # NSA
                }
                category = type_map.get(bt, "self_employment")
        except Exception:
            pass

        self._income_category_cache[user_id] = category
        return category

    def _build_transaction_suggestions(
        self, document: Document, db_type: DBDocumentType, result: PipelineResult,
    ) -> List[Dict[str, Any]]:
        """
        Build transaction suggestions for receipts/invoices, with confidence-
        gated creation.

        Supports multi-receipt PDFs: if _additional_receipts is present in
        extracted data, creates a suggestion for each receipt.

        Each suggestion is individually evaluated by the transaction gate:
        - HIGH confidence  -> auto-create transaction (needs_review=False, reviewed=True)
        - MEDIUM confidence -> auto-create transaction (needs_review=True)
        - LOW confidence   -> store suggestion only, no transaction created
        """
        try:
            from app.services.ocr_transaction_service import OCRTransactionService
            from app.services.transaction_gate_service import evaluate_transaction_gate

            service = OCRTransactionService(self.db)

            # Guard: if no extracted data at all, nothing to suggest
            if not result.extracted_data:
                logger.warning(
                    f"No extracted data for doc {document.id}, skipping transaction suggestions"
                )
                return []

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
                    f"Multi-receipt document {document.id}: creating {receipt_count} transaction suggestions"
                )
                suggestions = self._create_multi_receipt_transactions(
                    document, service, primary_receipt, additional_receipts
                )
            else:
                suggestions = service.create_split_suggestions(
                    document.id, document.user_id
                )

            # -- Direction override: VLM + UID matching + name matching --
            # Skip for SVS notices — SVS direction is determined by the SVS
            # extractor (_extract_from_svs_notice) which knows about Gutschrift
            # vs Nachforderung vs regular Beitragsvorschreibung.
            _skip_direction_override = db_type == DBDocumentType.SVS_NOTICE
            # Priority chain (first confirmed wins):
            #   1. VLM transaction_direction (has user identity context)
            #   2. UID match: issuer_uid/tax_id matches user's vat_number
            #   3. Name match: issuer/recipient matches user name/business_name
            # ContractRoleService already ran inside create_split_suggestions,
            # but these signals can override it when they're more reliable.
            ed = result.extracted_data or {}
            confirmed_direction = None
            override_source = None

            # Signal 1: VLM transaction_direction (highest priority — has full context)
            vlm_dir = ed.get("transaction_direction")
            if vlm_dir in ("income", "expense"):
                confirmed_direction = vlm_dir
                override_source = "vlm_direction"

            # Signal 2: UID match (deterministic — if user's ATU matches issuer_uid)
            if confirmed_direction is None or confirmed_direction == "expense":
                issuer_uid = str(ed.get("issuer_uid") or ed.get("tax_id") or "").strip().upper()
                if issuer_uid and len(issuer_uid) > 5:
                    if not hasattr(self, '_user_uids') or self._user_uids is None:
                        self._user_uids = set()
                        try:
                            from app.services.contract_role_service import load_sensitive_user_context
                            _uctx = load_sensitive_user_context(self.db, document.user_id)
                            if _uctx:
                                for uid_field in [_uctx.vat_number, _uctx.tax_number]:
                                    if uid_field:
                                        self._user_uids.add(str(uid_field).strip().upper())
                        except Exception:
                            pass
                    if self._user_uids and issuer_uid in self._user_uids:
                        confirmed_direction = "income"
                        override_source = "uid_match"
                        logger.info(
                            "UID match: issuer_uid '%s' matches user UID -> income for doc %d",
                            issuer_uid[:15], document.id,
                        )

            # Signal 3: Name match (issuer or recipient matches user name)
            if confirmed_direction is None:
                issuer = str(ed.get("issuer") or "").strip().lower()
                recipient = str(ed.get("recipient") or "").strip().lower()
                if not hasattr(self, '_user_identity_tokens_direction'):
                    self._user_identity_tokens_direction = set()
                    try:
                        from app.models.user import User as _User
                        _user = self.db.query(_User).filter(_User.id == document.user_id).first()
                        if _user:
                            for field in [_user.name, getattr(_user, "business_name", None)]:
                                if field:
                                    self._user_identity_tokens_direction.add(str(field).strip().lower())
                                    parts = str(field).strip().lower().split()
                                    if len(parts) > 1:
                                        self._user_identity_tokens_direction.add(" ".join(parts[-2:]))
                    except Exception:
                        pass
                if self._user_identity_tokens_direction:
                    for token in self._user_identity_tokens_direction:
                        if token and len(token) > 2:
                            if issuer and token in issuer:
                                confirmed_direction = "income"
                                override_source = "issuer_name_match"
                                break
                            if recipient and token in recipient:
                                confirmed_direction = "income"
                                override_source = "recipient_name_match"
                                break

            # Apply override to all suggestions (skip SVS — has its own logic)
            if confirmed_direction and not _skip_direction_override:
                for s in suggestions:
                    old_type = s.get("transaction_type")
                    if old_type != confirmed_direction:
                        s["transaction_type"] = confirmed_direction
                        s["category"] = self._resolve_income_category(document.user_id) if confirmed_direction == "income" else s.get("category", "other")
                        logger.info(
                            "Direction override (%s): %s -> %s for doc %d",
                            override_source, old_type, confirmed_direction, document.id,
                        )

            # OCR-level confidence must come from the current OCR pass, not the
            # persisted document row (which may still hold a stale earlier run
            # or later be overwritten with classification confidence).
            ocr_confidence = float(
                result.ocr_confidence_score
                if result.ocr_confidence_score is not None
                else (document.confidence_score or 0.5)
            )

            # Classification confidence comes from each suggestion individually
            # (set by the classifier in _build_single_suggestion)

            doc_type_value = (
                db_type.value if hasattr(db_type, "value") else str(db_type)
            )

            # Gate each suggestion individually
            for s in suggestions:
                s["document_id"] = document.id

                # Extract direction resolution from the suggestion itself
                # (set by _annotate_suggestion_with_direction in the service)
                direction_resolution = None
                dir_payload = s.get("transaction_direction_resolution")
                if dir_payload:
                    from app.services.contract_role_service import TransactionDirectionResolution
                    try:
                        direction_resolution = TransactionDirectionResolution(
                            candidate=dir_payload.get("candidate", "unknown"),
                            confidence=dir_payload.get("confidence", 0.3),
                            source=dir_payload.get("source", "unknown"),
                            evidence=dir_payload.get("evidence", []),
                            semantics=dir_payload.get("semantics", "unknown"),
                            is_reversal=dir_payload.get("is_reversal", False),
                            mode=dir_payload.get("mode", "shadow"),
                            gate_enabled=dir_payload.get("gate_enabled", True),
                            normalized_from=dir_payload.get("normalized_from"),
                        )
                    except Exception:
                        direction_resolution = None

                # Use the higher of suggestion confidence and OCR confidence.
                # When the classifier fallback gives 0.3 but VLM classified with 0.95,
                # the low classifier score shouldn't tank the composite.
                suggestion_confidence = float(s.get("confidence") or 0.5)
                classification_confidence = max(suggestion_confidence, ocr_confidence)

                # Determine the classifier's explicit review flag.
                # The suggestion's needs_review can be True due to either:
                #   (a) classifier confidence < 0.7, or
                #   (b) classifier's explicit requires_review flag.
                # We pass requires_review=True only when the classifier
                # explicitly flagged it (i.e. needs_review is True AND
                # confidence is high enough that it wasn't auto-set).
                classifier_requires_review = (
                    s.get("needs_review", False) and classification_confidence >= 0.7
                )

                # Build per-suggestion OCR data for the gate.
                # For multi-receipt documents, each suggestion has its own
                # amount/date from the individual receipt, NOT the top-level
                # extracted_data which belongs to the primary receipt only.
                suggestion_ocr_data: dict[str, Any] = {}
                if s.get("amount") is not None:
                    try:
                        suggestion_ocr_data["amount"] = float(s["amount"])
                    except (ValueError, TypeError):
                        suggestion_ocr_data["amount"] = s["amount"]
                if s.get("date"):
                    suggestion_ocr_data["date"] = s["date"]

                # Fall back to top-level extracted_data only if the
                # suggestion itself has no amount/date fields.
                if "amount" not in suggestion_ocr_data and "date" not in suggestion_ocr_data:
                    suggestion_ocr_data = result.extracted_data or {}

                if (
                    len(suggestions) == 1
                    and (
                        suggestion_ocr_data.get("amount") in (None, "")
                        or not suggestion_ocr_data.get("date")
                    )
                ):
                    recovered_fields = self._recover_missing_invoice_transaction_fields(
                        db_type=db_type,
                        raw_text=result.raw_text,
                        suggestion_ocr_data=suggestion_ocr_data,
                    )
                    if recovered_fields:
                        suggestion_ocr_data = {
                            **suggestion_ocr_data,
                            **recovered_fields,
                        }
                        for field_name in ("amount", "date"):
                            if s.get(field_name) in (None, "") and field_name in recovered_fields:
                                s[field_name] = recovered_fields[field_name]
                        s["field_recovery"] = {
                            "applied": True,
                            "fields": sorted(recovered_fields.keys()),
                        }

                gate_result = evaluate_transaction_gate(
                    document_type=doc_type_value,
                    ocr_confidence=ocr_confidence,
                    classification_confidence=classification_confidence,
                    direction_resolution=direction_resolution,
                    ocr_data=suggestion_ocr_data,
                    requires_review=classifier_requires_review,
                )

                # Persist gate metadata on the suggestion
                s["gate_decision"] = gate_result.decision.value
                s["gate_composite_confidence"] = gate_result.composite_confidence
                s["gate_reasons"] = gate_result.reasons

                if gate_result.should_create_transaction:
                    # HIGH or MEDIUM confidence: create real transaction
                    s["needs_review"] = gate_result.needs_review
                    s["reviewed"] = gate_result.reviewed
                    try:
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
                            # Sync metadata with the reused transaction's actual state
                            reused_tx = creation_result.transaction
                            s["needs_review"] = getattr(reused_tx, "needs_review", True)
                            s["reviewed"] = getattr(reused_tx, "reviewed", False)
                    except Exception as e:
                        logger.warning(
                            f"Auto-create transaction failed for doc {document.id}: {e}"
                        )
                        self.db.rollback()
                        s["status"] = "pending"
                        s["needs_review"] = True
                        s["reviewed"] = False
                else:
                    # LOW confidence: store suggestion only, no transaction
                    s["status"] = "manual-review-required"
                    s["needs_review"] = True
                    s["reviewed"] = False
                    logger.info(
                        f"Transaction gate blocked auto-create for doc {document.id}: "
                        f"composite={gate_result.composite_confidence:.4f} "
                        f"reasons={gate_result.reasons}"
                    )

            return suggestions

        except Exception as e:
            logger.warning(f"Transaction suggestion failed for doc {document.id}: {e}")
            self.db.rollback()
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

            # Direction detection: prefer VLM's transaction_direction, fall back to token matching
            issuer = str(receipt_data.get("issuer") or "").strip()
            recipient = str(receipt_data.get("recipient") or "").strip()
            merchant = receipt_data.get("merchant") or receipt_data.get("supplier") or issuer or recipient or "Unknown"
            detected_direction = "expense"  # default
            direction_confirmed = False

            # Priority 1: VLM already determined direction (unified vision path)
            vlm_direction = receipt_data.get("transaction_direction")
            if vlm_direction in ("income", "expense"):
                detected_direction = vlm_direction
                direction_confirmed = True
                if vlm_direction == "income":
                    merchant = recipient or merchant  # counterparty is the customer
                logger.info(
                    "Direction from VLM: %s for doc %d (issuer='%s', recipient='%s')",
                    vlm_direction, document.id, issuer[:50], recipient[:50],
                )

            # Priority 2: Fall back to token matching if VLM didn't determine direction
            if not direction_confirmed:
                if not hasattr(self, '_user_identity_tokens'):
                    self._user_identity_tokens = set()
                    try:
                        from app.models.user import User as _User
                        _user = self.db.query(_User).filter(_User.id == document.user_id).first()
                        if _user:
                            for field in [_user.name, getattr(_user, "business_name", None)]:
                                if field:
                                    self._user_identity_tokens.add(str(field).strip().lower())
                                    parts = str(field).strip().lower().split()
                                    if len(parts) > 1:
                                        self._user_identity_tokens.add(" ".join(parts[-2:]))
                    except Exception:
                        pass

                if issuer and self._user_identity_tokens:
                    issuer_lower = issuer.lower()
                    for token in self._user_identity_tokens:
                        if token and len(token) > 2 and token in issuer_lower:
                            detected_direction = "income"
                            direction_confirmed = True
                            merchant = recipient or merchant
                            logger.info(
                                "Direction token match: issuer '%s' matches '%s' -> income for doc %d",
                                issuer[:50], token, document.id,
                            )
                            break

                if not direction_confirmed and recipient and self._user_identity_tokens:
                    recipient_lower = recipient.lower()
                    for token in self._user_identity_tokens:
                        if token and len(token) > 2 and token in recipient_lower:
                            detected_direction = "income"
                            direction_confirmed = True
                            merchant = issuer or merchant
                            logger.info(
                                "Direction swap: user in recipient '%s' -> income for doc %d",
                                recipient[:50], document.id,
                            )
                            break

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
                "transaction_type": detected_direction,
                "amount": str(amount),
                "date": date_str,
                "description": description,
                "category": self._resolve_income_category(document.user_id) if detected_direction == "income" else "other",
                "is_deductible": False if detected_direction == "income" else False,
                "deduction_reason": None,
                "confidence": float(receipt_data.get("amount_confidence", 0.8)),
                "needs_review": False,
                "extracted_fields": {
                    "issuer": issuer or None,
                    "recipient": recipient or None,
                    "direction_source": "issuer_match" if detected_direction == "income" else "default",
                    "direction_confirmed": direction_confirmed,
                },
                "_receipt_index": i + 1,
            }

            # Apply user classification rules: override direction and category
            try:
                from app.services.user_classification_service import (
                    UserClassificationService,
                    normalize_description,
                )
                cls_svc = UserClassificationService(self.db)
                # Try multiple description formats to match rules
                lookup_descriptions = [description]
                product_desc = receipt_data.get("description") or receipt_data.get("product_summary") or ""
                if product_desc and merchant:
                    lookup_descriptions.append(f"{merchant}: {product_desc}")
                # Also try merchant alone
                if merchant and merchant != description:
                    lookup_descriptions.append(merchant)

                rule_matched = False
                for lookup_desc in lookup_descriptions:
                    if rule_matched:
                        break
                    norm_desc = normalize_description(lookup_desc)
                    if not norm_desc:
                        continue
                    for try_type in ["income", "expense"]:
                        rule = cls_svc.lookup(
                            user_id=document.user_id,
                            description=lookup_desc,
                            txn_type=try_type,
                        )
                        if rule and rule.category:
                            suggestion["transaction_type"] = rule.txn_type
                            suggestion["category"] = rule.category
                            if rule.txn_type == "income":
                                suggestion["is_deductible"] = False
                            suggestion["extracted_fields"]["direction_source"] = "user_rule"
                            suggestion["extracted_fields"]["direction_confirmed"] = True
                            suggestion["extracted_fields"]["rule_id"] = rule.id
                            cls_svc.record_hit(rule)
                            logger.info(
                                "User rule override for doc %d: '%s' -> %s/%s (rule %d)",
                                document.id, lookup_desc[:50], rule.txn_type, rule.category, rule.id,
                            )
                            rule_matched = True
                            break
            except Exception as e:
                logger.warning("User rule lookup failed for doc %d: %s", document.id, e)

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
        All questions are multilingual (de/en/zh/fr/ru) with helpText for non-obvious fields.
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
                    "fr": "Quand avez-vous commencé à utiliser cet article à des fins professionnelles ?",
                    "ru": "Когда вы начали использовать этот предмет в бизнесе?",
                    "hu": "Mikor kezdte üzleti célra használni ezt a tárgyat?",
                    "pl": "Kiedy zaczął/zaczęła Pan/Pani używać tego przedmiotu w działalności gospodarczej?",
                    "tr": "Bu esyayi is amacli kullanmaya ne zaman basladiniz?",
                    "bs": "Kada ste poceli koristiti ovu stavku u poslovne svrhe?",
                },
                "input_type": "date",
                "required": True,
                "field_key": "put_into_use_date",
                "default_value": None,
                "help_text": {
                    "de": "Das Datum, an dem Sie den Gegenstand betrieblich nutzen, nicht das Kaufdatum.",
                    "en": "The date you started using this for business, not the purchase date.",
                    "zh": "您开始将此物品用于业务的日期，不是购买日期。",
                    "fr": "La date de mise en service professionnelle, pas la date d'achat.",
                    "ru": "Дата начала использования в бизнесе, а не дата покупки.",
                    "hu": "Az üzleti használat kezdetének dátuma, nem a vásárlás dátuma.",
                    "pl": "Data rozpoczęcia użytkowania w działalności, a nie data zakupu.",
                    "tr": "Isletme amacli kullanima basladiginiz tarih, satin alma tarihi degil.",
                    "bs": "Datum kada ste poceli koristiti za posao, ne datum kupovine.",
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
                    "fr": "Quel pourcentage d'utilisation est professionnel ?",
                    "ru": "Какой процент использования приходится на бизнес?",
                    "hu": "Hány százalékban használja üzleti célra?",
                    "pl": "Jaki procent użytkowania przypada na działalność gospodarczą?",
                    "tr": "Is amacli kullanim yuzdesi nedir?",
                    "bs": "Koji postotak koristenja je u poslovne svrhe?",
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
                    "fr": "100 % si usage exclusivement professionnel. Pour un usage mixte, indiquez la part professionnelle.",
                    "ru": "100%, если используется исключительно для бизнеса. При смешанном использовании укажите долю бизнеса.",
                    "hu": "100%, ha kizárólag üzleti célra használja. Vegyes használat esetén adja meg az üzleti arányt.",
                    "pl": "100%, jeśli używany wyłącznie w działalności. W przypadku użytku mieszanego podaj udział służbowy.",
                    "tr": "Yalnizca is amacli kullanimda %100. Karisik kullanimda is payini belirtin.",
                    "bs": "100% ako se koristi iskljucivo za posao. Za mjesovitu upotrebu navedite poslovni udio.",
                },
            })

        # Conditional: is_used_asset (for vehicles)
        # Bug #14 fix: Use word boundary matching to avoid "fahrzeugausruestung" false positive
        asset_category = data.get("asset_category", "").lower()
        asset_words = set(asset_category.replace("-", " ").replace("_", " ").split())
        is_vehicle = bool(asset_words & {"fahrzeug", "vehicle", "auto", "pkw", "kfz", "car"})
        if is_vehicle and data.get("is_used_asset") is None:
            questions.append({
                "id": "is_used_asset",
                "question": {
                    "de": "Ist dies ein Gebrauchtfahrzeug?",
                    "en": "Is this a used vehicle?",
                    "zh": "这是二手车辆吗？",
                    "fr": "S'agit-il d'un véhicule d'occasion ?",
                    "ru": "Это подержанный автомобиль?",
                    "hu": "Ez egy használt jármű?",
                    "pl": "Czy to pojazd używany?",
                    "tr": "Bu ikinci el bir arac mi?",
                    "bs": "Da li je ovo polovni automobil?",
                },
                "input_type": "boolean",
                "required": False,
                "field_key": "is_used_asset",
                "default_value": False,
                "help_text": {
                    "de": "Gebrauchtfahrzeuge haben eine verkürzte Nutzungsdauer für die AfA.",
                    "en": "Used vehicles have a shorter useful life for depreciation purposes.",
                    "zh": "二手车辆的折旧年限较短。",
                    "fr": "Les véhicules d'occasion ont une durée de vie utile plus courte pour l'amortissement.",
                    "ru": "Подержанные автомобили имеют более короткий срок полезного использования для амортизации.",
                    "hu": "A használt járművek rövidebb hasznos élettartammal rendelkeznek az értékcsökkenés szempontjából.",
                    "pl": "Pojazdy używane mają krótszy okres użytkowania do celów amortyzacji.",
                    "tr": "Ikinci el araclar, amortisman icin daha kisa faydali omre sahiptir.",
                    "bs": "Polovna vozila imaju kraci vijek trajanja za potrebe amortizacije.",
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
                    "fr": "Quelle méthode d'amortissement souhaitez-vous utiliser ?",
                    "ru": "Какой метод амортизации вы хотите использовать?",
                    "hu": "Milyen értékcsökkenési módszert szeretne alkalmazni?",
                    "pl": "Jaką metodę amortyzacji chciałby/chciałaby Pan/Pani zastosować?",
                    "tr": "Hangi amortisman yontemini kullanmak istersiniz?",
                    "bs": "Koju metodu amortizacije zelite koristiti?",
                },
                "input_type": "select",
                "required": False,
                "field_key": "depreciation_method",
                "default_value": "linear",
                "options": [
                    {"value": "linear", "label": {"de": "Linear (Standard)", "en": "Linear (Standard)", "zh": "直线法（标准）", "fr": "Linéaire (standard)", "ru": "Линейный (стандарт)", "hu": "Lineáris (standard)", "pl": "Liniowa (standardowa)", "tr": "Dogrusal (Standart)", "bs": "Linearna (standardna)"}},
                    {"value": "degressive", "label": {"de": "Degressiv", "en": "Degressive", "zh": "递减法", "fr": "Dégressif", "ru": "Дегрессивный", "hu": "Degresszív", "pl": "Degresywna", "tr": "Azalan bakiyeler", "bs": "Degresivna"}},
                ],
                "help_text": {
                    "de": "Linear ist der Standard. Degressive AfA ist nur in bestimmten Fällen möglich.",
                    "en": "Linear is the default. Degressive depreciation is only available in certain cases.",
                    "zh": "直线法是默认方式。递减法仅在特定情况下可用。",
                    "fr": "Le linéaire est la méthode par défaut. L'amortissement dégressif n'est disponible que dans certains cas.",
                    "ru": "Линейный метод — стандарт. Дегрессивная амортизация доступна только в определённых случаях.",
                    "hu": "A lineáris a standard módszer. A degresszív értékcsökkenés csak bizonyos esetekben alkalmazható.",
                    "pl": "Metoda liniowa jest domyślna. Amortyzacja degresywna jest dostępna tylko w określonych przypadkach.",
                    "tr": "Dogrusal yontem standarttir. Azalan bakiyeler amortismani yalnizca belirli durumlarda kullanilabilir.",
                    "bs": "Linearna metoda je standardna. Degresivna amortizacija je dostupna samo u odredenim slucajevima.",
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
                    "fr": "Quel est le rapport de valeur bâtiment/terrain ?",
                    "ru": "Каково соотношение стоимости здания и земли?",
                    "hu": "Mekkora az épület és a telek értékaránya?",
                    "pl": "Jaki jest stosunek wartości budynku do gruntu?",
                    "tr": "Bina-arsa deger orani nedir?",
                    "bs": "Koji je omjer vrijednosti zgrade i zemljista?",
                },
                "input_type": "select",
                "required": True,
                "field_key": "building_value_ratio",
                "default_value": "0.7",
                "options": [
                    {"value": "0.7", "label": "70/30 (Standard)"},
                    {"value": "0.6", "label": "60/40"},
                    {"value": "0.8", "label": "80/20"},
                    {"value": "custom", "label": {"de": "Eigener Wert...", "en": "Custom value...", "zh": "自定义...", "fr": "Valeur personnalisée...", "ru": "Своё значение...", "hu": "Egyéni érték...", "pl": "Wartość niestandardowa...", "tr": "Ozel deger...", "bs": "Prilagodena vrijednost..."}},
                ],
                "help_text": {
                    "de": "Standard ist 70% Gebäude / 30% Grund. Verwenden Sie Ihr Liegenschaftsgutachten falls vorhanden.",
                    "en": "Standard is 70% building / 30% land. Use your Liegenschaftsgutachten if available.",
                    "zh": "标准比例为70%建筑/30%土地。如有物业评估报告请使用实际数据。",
                    "fr": "Le standard est 70 % bâtiment / 30 % terrain. Utilisez votre expertise immobilière si disponible.",
                    "ru": "Стандарт — 70% здание / 30% земля. Используйте экспертизу недвижимости, если есть.",
                    "hu": "A standard 70% épület / 30% telek. Használja az ingatlanértékelést, ha rendelkezésre áll.",
                    "pl": "Standard to 70% budynek / 30% grunt. Użyj operatu szacunkowego, jeśli jest dostępny.",
                    "tr": "Standart %70 bina / %30 arsadir. Varsa gayrimenkul degerleme raporunuzu kullanin.",
                    "bs": "Standard je 70% zgrada / 30% zemljiste. Koristite procjenu nekretnine ako je dostupna.",
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
                    "fr": "Quand le bâtiment a-t-il été construit ?",
                    "ru": "Когда было построено здание?",
                    "hu": "Mikor épült az épület?",
                    "pl": "Kiedy budynek został wybudowany?",
                    "tr": "Bina ne zaman insa edildi?",
                    "bs": "Kada je zgrada izgradena?",
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
                    "fr": "L'année de construction affecte le taux d'amortissement (1,5 % ou 2 % par an).",
                    "ru": "Год постройки влияет на ставку амортизации (1,5% или 2% в год).",
                    "hu": "Az építés éve befolyásolja az értékcsökkenési rátát (évi 1,5% vagy 2%).",
                    "pl": "Rok budowy wpływa na stawkę amortyzacji (1,5% lub 2% rocznie).",
                    "tr": "Insaat yili amortisman oranini etkiler (yillik %1,5 veya %2).",
                    "bs": "Godina izgradnje utice na stopu amortizacije (1,5% ili 2% godisnje).",
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
                    "fr": "Comment le bien est-il utilisé ?",
                    "ru": "Как используется недвижимость?",
                    "hu": "Hogyan használják az ingatlant?",
                    "pl": "W jaki sposób jest używana nieruchomość?",
                    "tr": "Gayrimenkul nasil kullaniliyor?",
                    "bs": "Kako se nekretnina koristi?",
                },
                "input_type": "select",
                "required": False,
                "field_key": "intended_use",
                "default_value": "rental",
                "options": [
                    {"value": "rental", "label": {"de": "Vermietung", "en": "Rental", "zh": "出租", "fr": "Location", "ru": "Аренда", "hu": "Bérbeadás", "pl": "Wynajem", "tr": "Kiralama", "bs": "Iznajmljivanje"}},
                    {"value": "own_use", "label": {"de": "Eigennutzung", "en": "Own use", "zh": "自用", "fr": "Usage personnel", "ru": "Собственное использование", "hu": "Saját használat", "pl": "Użytek własny", "tr": "Kendi kullanimi", "bs": "Vlastita upotreba"}},
                    {"value": "mixed", "label": {"de": "Gemischt", "en": "Mixed", "zh": "混合使用", "fr": "Mixte", "ru": "Смешанное", "hu": "Vegyes", "pl": "Mieszany", "tr": "Karisik", "bs": "Mjesovito"}},
                ],
                "help_text": {
                    "de": "Nur bei Vermietung oder betrieblicher Nutzung können Kosten steuerlich abgesetzt werden.",
                    "en": "Only rental or business use allows tax deductions on costs.",
                    "zh": "仅出租或业务使用的费用可以税前扣除。",
                    "fr": "Seul l'usage locatif ou professionnel permet des déductions fiscales sur les coûts.",
                    "ru": "Только аренда или деловое использование позволяют налоговые вычеты на расходы.",
                    "hu": "Csak bérbeadás vagy üzleti használat esetén érvényesíthetők adólevonások a költségekre.",
                    "pl": "Tylko wynajem lub użytek służbowy umożliwia odliczenia podatkowe kosztów.",
                    "tr": "Yalnizca kiralama veya ticari kullanim masraflarda vergi indirimi saglar.",
                    "bs": "Samo iznajmljivanje ili poslovna upotreba omogucava porezne odbitke na troskove.",
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
                    "link_to_existing",
                    self.BANK_STATEMENT_SUGGESTION_TYPE,
                    # All import_* types (tax forms, payslips, etc.)
                    *(v for v in self.TAX_FORM_SUGGESTION_TYPE_MAP.values()),
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

                # Store tax_analysis for transaction suggestions
                tx_suggestions = [
                    s for s in result.suggestions
                    if s and s.get("type") not in (import_suggestion_types | {"create_asset"})
                ]
                store_transaction_suggestions(
                    ocr_result,
                    tx_suggestions,
                    json_safe=self._make_json_safe,
                )

            materialize_final_transaction_type(
                document=document,
                ocr_result=ocr_result,
                db=self.db,
            )

            from app.services.document_year_attribution import (
                materialize_document_temporal_metadata,
            )

            materialize_document_temporal_metadata(document, ocr_result)
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
        suggestions = [
            s for s in copy_transaction_suggestions(ocr_result)
            if not s.get("transaction_id")
        ]

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
                # User has explicitly reviewed and approved these suggestions
                suggestion["needs_review"] = False
                suggestion["reviewed"] = True
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
