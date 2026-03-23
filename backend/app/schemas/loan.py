"""Schemas for property-loan summaries and installment APIs."""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class LoanInstallmentResponse(BaseModel):
    """API shape for a persisted loan installment row."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    loan_id: int
    user_id: int
    due_date: date
    actual_payment_date: Optional[date] = None
    tax_year: int
    scheduled_payment: Decimal
    principal_amount: Decimal
    interest_amount: Decimal
    remaining_balance_after: Decimal
    source: str
    status: str
    source_document_id: Optional[int] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class LoanInstallmentListResponse(BaseModel):
    """List response for a loan's installment rows."""

    loan_id: int
    total: int
    tax_year: Optional[int] = None
    installments: List[LoanInstallmentResponse]


class LoanSummaryResponse(BaseModel):
    """High-level summary derived from the loan service."""

    loan_id: int
    property_id: str
    loan_amount: float
    interest_rate: float
    monthly_payment: float
    start_date: str
    end_date: Optional[str] = None
    lender_name: str
    loan_type: Optional[str] = None
    current_balance: float
    total_payments: float
    total_interest: float
    total_principal: float
    current_year_interest: float
    number_of_payments: int
    payments_remaining: int


class AnnualInterestCertificateApplyRequest(BaseModel):
    """Payload for applying a bank-issued annual interest certificate."""

    tax_year: int = Field(..., ge=2000, le=2100)
    annual_interest_amount: Decimal = Field(..., gt=0)
    source_document_id: Optional[int] = None
    actual_payment_date: Optional[date] = None


class AnnualInterestCertificateApplyResponse(BaseModel):
    """Response after reconciling a year with a Zinsbescheinigung."""

    loan_id: int
    tax_year: int
    annual_interest_amount: Decimal
    installments_updated: int
    installments: List[LoanInstallmentResponse]

