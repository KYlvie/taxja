"""Document schemas for API validation"""
from datetime import date, datetime, timedelta, timezone
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from app.models.document import DocumentType


_PROCESSING_PIPELINE_STATES = {
    "processing_phase_1",
    "first_result_available",
    "finalizing",
}
_STALE_PROCESSING_TIMEOUT = timedelta(minutes=5)
_FINAL_IMPORT_STATUSES = {"confirmed", "auto_created"}
_FINAL_TRANSACTION_SUGGESTION_STATUSES = {"confirmed", "dismissed"}
_CONFIDENT_TRANSACTION_THRESHOLD = 0.90


def _parse_pipeline_timestamp(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    if not isinstance(value, str) or not value.strip():
        return None

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None

    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _get_pipeline_last_activity(ocr_result: Any, uploaded_at: Optional[datetime]) -> Optional[datetime]:
    if not isinstance(ocr_result, dict):
        return uploaded_at

    pipeline = ocr_result.get("_pipeline")
    if not isinstance(pipeline, dict):
        return uploaded_at

    checkpoints = pipeline.get("phase_checkpoints")
    if isinstance(checkpoints, list):
        for checkpoint in reversed(checkpoints):
            if not isinstance(checkpoint, dict):
                continue
            for key in ("completed_at", "started_at"):
                parsed = _parse_pipeline_timestamp(checkpoint.get(key))
                if parsed is not None:
                    return parsed

    for key in ("failed_at", "reprocess_requested_at"):
        parsed = _parse_pipeline_timestamp(pipeline.get(key))
        if parsed is not None:
            return parsed

    return uploaded_at


def derive_document_ocr_status(obj: Any) -> str:
    processed_at = getattr(obj, "processed_at", None)
    if processed_at:
        return "completed"

    ocr_result = getattr(obj, "ocr_result", None)
    pipeline = ocr_result.get("_pipeline") if isinstance(ocr_result, dict) else {}
    current_state = pipeline.get("current_state") if isinstance(pipeline, dict) else None

    if current_state == "phase_2_failed":
        return "failed"

    if current_state in _PROCESSING_PIPELINE_STATES:
        last_activity = _get_pipeline_last_activity(
            ocr_result,
            getattr(obj, "uploaded_at", None),
        )
        if last_activity and datetime.utcnow() - last_activity > _STALE_PROCESSING_TIMEOUT:
            return "failed"
        return "processing"

    if getattr(obj, "raw_text", None) or ocr_result:
        return "completed" if processed_at else "processing"

    return "processing"


def _has_final_transaction_suggestion_outcome(ocr_result: Any) -> bool:
    if not isinstance(ocr_result, dict):
        return False

    suggestions: list[dict[str, Any]] = []
    stored = ocr_result.get("transaction_suggestion")
    if isinstance(stored, dict):
        suggestions.append(stored)

    tax_analysis = ocr_result.get("tax_analysis")
    items = tax_analysis.get("items") if isinstance(tax_analysis, dict) else None
    if isinstance(items, list):
        suggestions.extend(item for item in items if isinstance(item, dict))

    for suggestion in suggestions:
        if suggestion.get("_stale"):
            continue

        status = suggestion.get("status")
        if status in _FINAL_TRANSACTION_SUGGESTION_STATUSES:
            return True

        if suggestion.get("reviewed") is True or suggestion.get("needs_review") is False:
            return True

    return False


def _has_final_document_outcome(
    *,
    ocr_result: Any,
    confidence_score: Any,
    transaction_id: Any,
    linked_transaction_count: Any,
) -> bool:
    if isinstance(ocr_result, dict) and ocr_result.get("confirmed") is True:
        return True

    if isinstance(ocr_result, dict):
        import_suggestion = ocr_result.get("import_suggestion")
        if isinstance(import_suggestion, dict) and import_suggestion.get("status") in _FINAL_IMPORT_STATUSES:
            return True

        asset_outcome = ocr_result.get("asset_outcome")
        if isinstance(asset_outcome, dict) and asset_outcome.get("status") in _FINAL_IMPORT_STATUSES:
            return True

        if _has_final_transaction_suggestion_outcome(ocr_result):
            return True

    try:
        confidence = float(confidence_score or 0)
    except (TypeError, ValueError):
        confidence = 0.0

    has_linked_transaction = bool(transaction_id) or bool(linked_transaction_count)
    return has_linked_transaction and confidence >= _CONFIDENT_TRANSACTION_THRESHOLD


class DocumentBase(BaseModel):
    """Base document schema"""
    document_type: Optional[DocumentType] = None


class DocumentUploadResponse(BaseModel):
    """Response after document upload"""
    id: int
    file_name: str
    file_size: int
    mime_type: str
    document_type: Optional[DocumentType] = None
    uploaded_at: datetime
    message: str = "Document uploaded successfully"
    deduplicated: bool = False
    duplicate_of_document_id: Optional[int] = None

    class Config:
        from_attributes = True


class DocumentDetail(BaseModel):
    """Detailed document information"""
    id: int
    user_id: int
    document_type: DocumentType
    file_name: str
    file_size: int
    mime_type: str
    file_path: str
    ocr_result: Optional[Dict[str, Any]] = None
    ocr_status: Optional[str] = None
    raw_text: Optional[str] = None
    confidence_score: Optional[float] = None
    needs_review: bool = False
    transaction_id: Optional[int] = None
    linked_transaction_count: int = 0
    uploaded_at: datetime
    processed_at: Optional[datetime] = None
    document_date: Optional[date] = None
    document_year: Optional[int] = None
    year_basis: Optional[str] = None
    year_confidence: Optional[float] = None

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(cls, obj):
        """Override to compute needs_review from confidence_score and OCR confirmation"""
        instance = super().from_orm(obj)
        instance.ocr_status = derive_document_ocr_status(obj)
        is_processed = getattr(obj, 'processed_at', None) is not None
        ocr_result = getattr(obj, 'ocr_result', None) or {}
        low_confidence = (instance.confidence_score or 0) < 0.6
        ocr_not_confirmed = bool(ocr_result and not ocr_result.get('confirmed'))
        has_final_outcome = _has_final_document_outcome(
            ocr_result=ocr_result,
            confidence_score=instance.confidence_score,
            transaction_id=getattr(obj, 'transaction_id', None),
            linked_transaction_count=getattr(obj, 'linked_transaction_count', 0),
        )
        instance.needs_review = is_processed and not has_final_outcome and (low_confidence or ocr_not_confirmed)
        return instance


class DocumentList(BaseModel):
    """List of documents with pagination"""
    documents: list[DocumentDetail]
    total: int
    page: int
    page_size: int


class DocumentSearchParams(BaseModel):
    """Search parameters for documents"""
    document_type: Optional[DocumentType] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    transaction_id: Optional[int] = None
    search_text: Optional[str] = Field(None, description="Full-text search on OCR text")
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


class BatchUploadResponse(BaseModel):
    """Response after batch document upload"""
    total_uploaded: int
    successful: list[DocumentUploadResponse]
    failed: list[Dict[str, str]]
    message: str


# =============================================================================
# AI Unified Interaction — Process Status & Follow-Up Schemas
# =============================================================================

class FollowUpQuestionSchema(BaseModel):
    """A single follow-up question for the AI chat panel."""
    id: str
    question: Dict[str, str]  # Trilingual: {"de": "...", "en": "...", "zh": "..."}
    input_type: str  # 'text' | 'number' | 'date' | 'select' | 'boolean'
    options: Optional[list] = None
    default_value: Optional[Any] = None
    required: bool = True
    field_key: str
    help_text: Optional[Dict[str, str]] = None  # Trilingual help text
    validation: Optional[Dict[str, Any]] = None


class ActionDescriptorSchema(BaseModel):
    """Self-describing action contract for frontend generic dispatch."""
    kind: str
    target_id: str
    endpoint: str
    method: str = "POST"
    payload: Optional[Dict[str, Any]] = None
    confirm_label: Optional[Dict[str, str]] = None  # Trilingual
    dismiss_label: Optional[Dict[str, str]] = None   # Trilingual
    detail_label: Optional[Dict[str, str]] = None    # Trilingual


class ProcessStatusResponse(BaseModel):
    """Response for GET /documents/{id}/process-status."""
    phase: str
    document_type: Optional[str] = None
    message: str
    ui_state: str  # 'processing' | 'needs_input' | 'ready_to_confirm' | 'confirmed' | 'dismissed' | 'error'
    suggestion: Optional[Dict[str, Any]] = None
    phase_started_at: Optional[str] = None
    phase_updated_at: Optional[str] = None
    current_phase_attempt: int = 1
    suggestion_version: Optional[int] = None
    idempotency_key: str
    action: Optional[ActionDescriptorSchema] = None
    follow_up_questions: Optional[list[FollowUpQuestionSchema]] = None


class FollowUpAnswerRequest(BaseModel):
    """Request body for POST /documents/{id}/follow-up."""
    answers: Dict[str, Any] = Field(default_factory=dict)
    use_defaults: bool = False
    suggestion_version: Optional[int] = None


class FollowUpAnswerResponse(BaseModel):
    """Response for POST /documents/{id}/follow-up."""
    status: str
    ui_state: str
    suggestion_version: int
    remaining_questions: int
    remaining_question_list: list = Field(default_factory=list)
    applied_defaults: Dict[str, Any] = Field(default_factory=dict)
