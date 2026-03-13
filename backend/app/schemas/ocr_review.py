"""OCR review and correction schemas"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from decimal import Decimal
from pydantic import BaseModel, Field, validator
from app.models.document import DocumentType


class OCRReviewData(BaseModel):
    """OCR review data with extracted fields"""
    document_id: int
    document_type: DocumentType
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    raw_text: str
    extracted_data: Dict[str, Any]
    needs_review: bool
    suggestions: Optional[List[str]] = None
    warnings: Optional[List[str]] = None
    
    class Config:
        from_attributes = True


class OCRFieldConfidence(BaseModel):
    """Confidence score for individual OCR fields"""
    field_name: str
    value: Any
    confidence: float = Field(..., ge=0.0, le=1.0)
    needs_review: bool


class OCRReviewResponse(BaseModel):
    """Response for OCR review endpoint"""
    document_id: int
    document_type: DocumentType
    file_name: str
    uploaded_at: datetime
    processed_at: Optional[datetime]
    overall_confidence: float = Field(..., ge=0.0, le=1.0)
    needs_review: bool
    raw_text: str
    extracted_fields: List[OCRFieldConfidence]
    suggestions: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    quality_feedback: Optional[str] = None


class OCRCorrectionRequest(BaseModel):
    """Request to correct OCR extracted data"""
    corrected_data: Dict[str, Any] = Field(
        ...,
        description="Corrected field values (e.g., {'date': '2026-01-15', 'amount': '123.45'})"
    )
    document_type: Optional[DocumentType] = Field(
        None,
        description="Corrected document type if classification was wrong"
    )
    notes: Optional[str] = Field(
        None,
        max_length=500,
        description="Optional notes about the correction"
    )
    
    @validator('corrected_data')
    def validate_corrected_data(cls, v):
        """Validate that corrected data is not empty"""
        if not v:
            raise ValueError("corrected_data cannot be empty")
        return v


class OCRCorrectionResponse(BaseModel):
    """Response after OCR correction"""
    document_id: int
    message: str
    updated_fields: List[str]
    previous_confidence: float
    new_confidence: float
    correction_recorded: bool


class OCRConfirmRequest(BaseModel):
    """Request to confirm OCR data is correct"""
    confirmed: bool = Field(True, description="Confirmation flag")
    notes: Optional[str] = Field(
        None,
        max_length=500,
        description="Optional notes about the confirmation"
    )


class OCRConfirmResponse(BaseModel):
    """Response after OCR confirmation"""
    document_id: int
    message: str
    confirmed_at: datetime
    can_create_transaction: bool


class OCRQualityFeedback(BaseModel):
    """Quality feedback for OCR results"""
    overall_quality: str = Field(
        ...,
        description="Overall quality assessment: excellent, good, fair, poor"
    )
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    issues: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
    retake_recommended: bool = False
    manual_input_recommended: bool = False


class OCRRetakeGuidance(BaseModel):
    """Guidance for retaking document photo"""
    reason: str
    tips: List[str]
    example_image_url: Optional[str] = None


class OCRErrorResponse(BaseModel):
    """Error response for OCR failures"""
    document_id: int
    error_type: str = Field(
        ...,
        description="Error type: low_confidence, no_text_found, invalid_format, processing_failed"
    )
    error_message: str
    suggestions: List[str] = Field(default_factory=list)
    retake_guidance: Optional[OCRRetakeGuidance] = None
    can_retry: bool = True
