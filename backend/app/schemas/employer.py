"""Schemas for employer-light monthly handling."""
from datetime import datetime, date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from app.models.employer_annual_archive import EmployerAnnualArchiveStatus
from app.models.employer_month import EmployerMonthStatus


class EmployerMonthBase(BaseModel):
    year_month: str = Field(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$")


class EmployerMonthSummaryUpdate(BaseModel):
    employee_count: Optional[int] = Field(None, ge=0, le=9999)
    gross_wages: Optional[Decimal] = Field(None, ge=0)
    net_paid: Optional[Decimal] = Field(None, ge=0)
    employer_social_cost: Optional[Decimal] = Field(None, ge=0)
    lohnsteuer: Optional[Decimal] = Field(None, ge=0)
    db_amount: Optional[Decimal] = Field(None, ge=0)
    dz_amount: Optional[Decimal] = Field(None, ge=0)
    kommunalsteuer: Optional[Decimal] = Field(None, ge=0)
    special_payments: Optional[Decimal] = Field(None, ge=0)
    notes: Optional[str] = Field(None, max_length=2000)


class EmployerMonthConfirmPayroll(EmployerMonthBase, EmployerMonthSummaryUpdate):
    document_id: Optional[int] = None
    payroll_signal: Optional[str] = Field(None, max_length=50)
    source_type: str = Field(default="manual_summary", max_length=30)
    confidence: Optional[Decimal] = Field(None, ge=0, le=1)


class EmployerMonthConfirmNoPayroll(EmployerMonthBase):
    note: Optional[str] = Field(None, max_length=1000)


class EmployerMonthDocumentLink(BaseModel):
    document_id: int
    file_name: str
    document_type: str
    relation_type: str


class EmployerMonthResponse(BaseModel):
    id: int
    year_month: str
    status: EmployerMonthStatus
    source_type: Optional[str] = None
    payroll_signal: Optional[str] = None
    confidence: Optional[Decimal] = None
    employee_count: Optional[int] = None
    gross_wages: Optional[Decimal] = None
    net_paid: Optional[Decimal] = None
    employer_social_cost: Optional[Decimal] = None
    lohnsteuer: Optional[Decimal] = None
    db_amount: Optional[Decimal] = None
    dz_amount: Optional[Decimal] = None
    kommunalsteuer: Optional[Decimal] = None
    special_payments: Optional[Decimal] = None
    notes: Optional[str] = None
    confirmed_at: Optional[datetime] = None
    last_signal_at: Optional[datetime] = None
    documents: list[EmployerMonthDocumentLink] = []


class EmployerDocumentDetectionResponse(BaseModel):
    detected: bool
    reason: Optional[str] = None
    month: Optional[EmployerMonthResponse] = None


class EmployerAnnualArchiveConfirm(BaseModel):
    tax_year: int = Field(..., ge=2000, le=2100)
    document_id: Optional[int] = None
    archive_signal: Optional[str] = Field(None, max_length=50)
    source_type: str = Field(default="manual_archive", max_length=30)
    confidence: Optional[Decimal] = Field(None, ge=0, le=1)
    employer_name: Optional[str] = Field(None, max_length=255)
    gross_income: Optional[Decimal] = Field(None, ge=0)
    withheld_tax: Optional[Decimal] = Field(None, ge=0)
    notes: Optional[str] = Field(None, max_length=2000)


class EmployerAnnualArchiveDocumentLink(BaseModel):
    document_id: int
    file_name: str
    document_type: str
    relation_type: str


class EmployerAnnualArchiveResponse(BaseModel):
    id: int
    tax_year: int
    status: EmployerAnnualArchiveStatus
    source_type: Optional[str] = None
    archive_signal: Optional[str] = None
    confidence: Optional[Decimal] = None
    employer_name: Optional[str] = None
    gross_income: Optional[Decimal] = None
    withheld_tax: Optional[Decimal] = None
    notes: Optional[str] = None
    confirmed_at: Optional[datetime] = None
    last_signal_at: Optional[datetime] = None
    documents: list[EmployerAnnualArchiveDocumentLink] = []


class EmployerAnnualArchiveDetectionResponse(BaseModel):
    detected: bool
    reason: Optional[str] = None
    archive: Optional[EmployerAnnualArchiveResponse] = None


class EmployerDocumentReviewContextResponse(BaseModel):
    supported: bool
    reason: Optional[str] = None
    document_id: int
    document_type: str
    candidate_year_month: Optional[str] = None
    candidate_tax_year: Optional[int] = None
    month: Optional[EmployerMonthResponse] = None
    annual_archive: Optional[EmployerAnnualArchiveResponse] = None


class EmployerOverviewResponse(BaseModel):
    year: int
    employer_mode: str
    total_months: int
    payroll_months: int
    missing_confirmation_months: int
    no_payroll_months: int
    unknown_months: int
    next_deadline: Optional[date] = None
    next_deadline_label: Optional[str] = None
