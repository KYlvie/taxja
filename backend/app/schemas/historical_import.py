"""Historical import schemas for API validation"""
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class HistoricalImportUploadRequest(BaseModel):
    """Request schema for uploading a historical document"""

    document_type: Literal["e1_form", "bescheid", "kaufvertrag", "saldenliste"] = Field(
        ..., description="Type of historical document being uploaded"
    )
    tax_year: int = Field(..., ge=2000, le=2030, description="Tax year for the document")
    session_id: Optional[UUID] = Field(
        None, description="Optional session ID for multi-document imports"
    )

    @field_validator("tax_year")
    @classmethod
    def validate_tax_year(cls, v: int) -> int:
        """Validate tax year is not in the future and not more than 10 years old"""
        current_year = date.today().year

        if v > current_year:
            raise ValueError(
                f"Tax year cannot be in the future. "
                f"Provided year: {v}, Current year: {current_year}"
            )

        if v < current_year - 10:
            raise ValueError(
                f"Tax year is too old (maximum 10 years). "
                f"Provided year: {v}, Oldest allowed: {current_year - 10}"
            )

        return v


class HistoricalImportUploadResponse(BaseModel):
    """Response after uploading a historical document"""

    upload_id: UUID = Field(..., description="Unique identifier for this upload")
    document_id: int = Field(..., description="Database ID of the uploaded document")
    status: str = Field(..., description="Current processing status")
    task_id: Optional[str] = Field(None, description="Celery task ID for OCR processing")
    estimated_completion: Optional[datetime] = Field(
        None, description="Estimated completion time for processing"
    )
    message: str = Field(default="Document uploaded successfully", description="Status message")

    model_config = ConfigDict(from_attributes=True)


class HistoricalImportStatusResponse(BaseModel):
    """Response for checking the status of a historical import"""

    upload_id: UUID = Field(..., description="Unique identifier for this upload")
    status: Literal[
        "uploaded",
        "processing",
        "extracted",
        "review_required",
        "approved",
        "rejected",
        "failed",
    ] = Field(..., description="Current processing status")
    progress: int = Field(
        default=0, ge=0, le=100, description="Processing progress percentage"
    )
    extracted_data: Optional[Dict[str, Any]] = Field(
        None, description="Extracted structured data from the document"
    )
    confidence: Optional[Decimal] = Field(
        None, ge=0, le=1, description="Extraction confidence score (0.0 to 1.0)"
    )
    requires_review: bool = Field(
        default=False, description="Whether the extraction requires manual review"
    )
    errors: List[Dict[str, Any]] = Field(
        default_factory=list, description="List of errors encountered during processing"
    )
    created_at: datetime = Field(..., description="Upload creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")

    model_config = ConfigDict(from_attributes=True)


class HistoricalImportReviewRequest(BaseModel):
    """Request schema for reviewing and approving/rejecting an import"""

    approved: bool = Field(..., description="Whether the import is approved or rejected")
    edited_data: Optional[Dict[str, Any]] = Field(
        None, description="User-corrected extraction data (if any corrections were made)"
    )
    notes: Optional[str] = Field(
        None, max_length=1000, description="Optional notes about the review decision"
    )

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, v: Optional[str]) -> Optional[str]:
        """Validate notes are not empty if provided"""
        if v is not None:
            v = v.strip()
            if len(v) == 0:
                raise ValueError(
                    "Notes cannot be empty. Either provide notes or omit the field."
                )
        return v

    @model_validator(mode="after")
    def validate_rejection_notes(self):
        """Validate that rejection includes notes explaining the reason"""
        if not self.approved and not self.notes:
            raise ValueError(
                "Notes are required when rejecting an import. "
                "Please provide a reason for rejection."
            )
        return self


class HistoricalImportReviewResponse(BaseModel):
    """Response after reviewing an import"""

    import_id: UUID = Field(..., description="Unique identifier for the finalized import")
    status: str = Field(..., description="Final status after review")
    transactions_created: int = Field(
        default=0, ge=0, description="Number of transactions created"
    )
    properties_created: int = Field(default=0, ge=0, description="Number of properties created")
    properties_linked: int = Field(
        default=0, ge=0, description="Number of properties linked to existing records"
    )
    summary: Dict[str, Any] = Field(
        default_factory=dict, description="Detailed import summary"
    )
    message: str = Field(..., description="Result message")

    model_config = ConfigDict(from_attributes=True)


class ImportSessionRequest(BaseModel):
    """Request schema for creating a multi-document import session"""

    tax_years: List[int] = Field(
        ..., min_length=1, max_length=10, description="List of tax years to import"
    )
    document_types: List[Literal["e1_form", "bescheid", "kaufvertrag", "saldenliste"]] = Field(
        ..., min_length=1, description="List of document types expected in this session"
    )

    @field_validator("tax_years")
    @classmethod
    def validate_tax_years(cls, v: List[int]) -> List[int]:
        """Validate all tax years are valid and unique"""
        current_year = date.today().year

        # Check for duplicates
        if len(v) != len(set(v)):
            raise ValueError("Tax years must be unique. Duplicate years found in the list.")

        # Validate each year
        for year in v:
            if year < 2000 or year > 2030:
                raise ValueError(
                    f"Tax year {year} is out of valid range (2000-2030). "
                    f"All years must be between 2000 and 2030."
                )

            if year > current_year:
                raise ValueError(
                    f"Tax year {year} cannot be in the future. Current year: {current_year}"
                )

            if year < current_year - 10:
                raise ValueError(
                    f"Tax year {year} is too old (maximum 10 years). "
                    f"Oldest allowed: {current_year - 10}"
                )

        # Sort years for consistency
        return sorted(v)

    @field_validator("document_types")
    @classmethod
    def validate_document_types(cls, v: List[str]) -> List[str]:
        """Validate document types are unique"""
        if len(v) != len(set(v)):
            raise ValueError(
                "Document types must be unique. Duplicate types found in the list."
            )
        return v


class ImportSessionResponse(BaseModel):
    """Response for import session status and summary"""

    session_id: UUID = Field(..., description="Unique identifier for this import session")
    status: Literal["active", "completed", "failed"] = Field(
        ..., description="Current session status"
    )
    tax_years: List[int] = Field(..., description="Tax years included in this session")
    expected_documents: int = Field(
        ..., ge=0, description="Expected number of documents to upload"
    )
    uploaded_documents: int = Field(
        default=0, ge=0, description="Number of documents uploaded so far"
    )
    documents: List[Dict[str, Any]] = Field(
        default_factory=list, description="List of uploaded documents with their status"
    )
    summary: Dict[str, Any] = Field(
        default_factory=dict, description="Session summary with aggregated metrics"
    )
    conflicts: List[Dict[str, Any]] = Field(
        default_factory=list, description="List of detected conflicts between documents"
    )
    created_at: datetime = Field(..., description="Session creation timestamp")
    completed_at: Optional[datetime] = Field(None, description="Session completion timestamp")

    model_config = ConfigDict(from_attributes=True)


class ImportConflictResponse(BaseModel):
    """Response schema for import conflicts"""

    id: int = Field(..., description="Conflict ID")
    conflict_type: str = Field(..., description="Type of conflict detected")
    field_name: str = Field(..., description="Field name where conflict occurred")
    value_1: str = Field(..., description="First conflicting value")
    value_2: str = Field(..., description="Second conflicting value")
    upload_id_1: UUID = Field(..., description="First upload ID")
    upload_id_2: UUID = Field(..., description="Second upload ID")
    resolution: Optional[str] = Field(None, description="Resolution strategy applied")
    resolved_at: Optional[datetime] = Field(None, description="Resolution timestamp")

    model_config = ConfigDict(from_attributes=True)


class ImportMetricsResponse(BaseModel):
    """Response schema for import metrics"""

    upload_id: UUID = Field(..., description="Upload ID for these metrics")
    document_type: str = Field(..., description="Type of document")
    extraction_confidence: Decimal = Field(
        ..., ge=0, le=1, description="Overall extraction confidence"
    )
    fields_extracted: int = Field(..., ge=0, description="Number of fields successfully extracted")
    fields_total: int = Field(..., ge=0, description="Total number of expected fields")
    extraction_time_ms: int = Field(..., ge=0, description="Extraction time in milliseconds")
    fields_corrected: int = Field(
        default=0, ge=0, description="Number of fields corrected by user"
    )
    field_accuracies: Dict[str, float] = Field(
        default_factory=dict, description="Field-level accuracy scores"
    )
    corrections: List[Dict[str, Any]] = Field(
        default_factory=list, description="List of user corrections for ML training"
    )
    created_at: datetime = Field(..., description="Metrics creation timestamp")

    model_config = ConfigDict(from_attributes=True)
