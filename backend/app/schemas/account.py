"""Account cancellation schemas for request/response validation"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class DeactivateAccountRequest(BaseModel):
    """Schema for account deactivation (cancellation) request"""
    password: str = Field(..., min_length=1, description="Current password for identity verification")
    reason: Optional[str] = Field(None, max_length=500, description="Optional cancellation reason")
    two_factor_code: Optional[str] = Field(
        None, max_length=10, description="2FA code if two-factor authentication is enabled"
    )
    confirmation_word: str = Field(..., description='Must be "DELETE" to confirm account cancellation')

    @field_validator("confirmation_word")
    @classmethod
    def validate_confirmation_word(cls, v: str) -> str:
        """Validate that confirmation word is exactly 'DELETE'"""
        if v != "DELETE":
            raise ValueError('Confirmation word must be exactly "DELETE"')
        return v


class CancellationImpactResponse(BaseModel):
    """Schema for cancellation impact summary response"""
    transaction_count: int = Field(..., ge=0, description="Number of transactions to be deleted")
    document_count: int = Field(..., ge=0, description="Number of documents to be deleted")
    tax_report_count: int = Field(..., ge=0, description="Number of tax reports to be deleted")
    property_count: int = Field(..., ge=0, description="Number of properties to be deleted")
    has_active_subscription: bool = Field(..., description="Whether user has an active subscription")
    subscription_days_remaining: Optional[int] = Field(
        None, ge=0, description="Days remaining on active subscription"
    )
    cooling_off_days: int = Field(default=30, description="Cooling-off period in days before permanent deletion")


class DataExportRequest(BaseModel):
    """Schema for GDPR data export request"""
    encryption_password: str = Field(
        ..., min_length=8, description="Password for AES-256 encryption of the data package"
    )


class DataExportStatusResponse(BaseModel):
    """Schema for data export task status response"""
    status: str = Field(..., description="Export status: pending, processing, ready, or failed")
    download_url: Optional[str] = Field(None, description="Pre-signed download URL (available when ready)")
    expires_at: Optional[datetime] = Field(None, description="Download URL expiration time")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Validate export status is one of the allowed values"""
        allowed = {"pending", "processing", "ready", "failed"}
        if v not in allowed:
            raise ValueError(f"Status must be one of: {', '.join(sorted(allowed))}")
        return v


class ReactivateAccountResponse(BaseModel):
    """Schema for account reactivation response"""
    message: str = Field(..., description="Reactivation result message")
    account_status: str = Field(..., description="Current account status after reactivation")


class AdminCancellationStatsResponse(BaseModel):
    """Schema for admin cancellation statistics response"""
    monthly_cancellations: int = Field(..., ge=0, description="Number of cancellations this month")
    cancellation_reasons: dict = Field(
        default_factory=dict, description="Distribution of cancellation reasons"
    )
    reactivation_rate: float = Field(..., ge=0, le=1, description="Rate of reactivations during cooling-off period")
    average_user_lifetime_days: float = Field(..., ge=0, description="Average user account lifetime in days")
