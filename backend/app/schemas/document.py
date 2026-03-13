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
    transaction_id: Optional[int] = None
    uploaded_at: datetime
    processed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


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
