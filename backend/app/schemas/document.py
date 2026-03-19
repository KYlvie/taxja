"""Document schemas for API validation"""
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from app.models.document import DocumentType


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
    raw_text: Optional[str] = None
    confidence_score: Optional[float] = None
    needs_review: bool = False
    transaction_id: Optional[int] = None
    uploaded_at: datetime
    processed_at: Optional[datetime] = None

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(cls, obj):
        """Override to compute needs_review from confidence_score"""
        instance = super().from_orm(obj)
        if not hasattr(obj, 'needs_review') or obj.needs_review is None:
            instance.needs_review = (instance.confidence_score or 0) < 0.6
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
