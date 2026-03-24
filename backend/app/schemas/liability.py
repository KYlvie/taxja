"""Schemas for unified liability management."""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.models.liability import LiabilityReportCategory, LiabilitySourceType, LiabilityType


class LiabilityRelatedTransaction(BaseModel):
    id: int
    type: str
    amount: Decimal
    transaction_date: date
    description: Optional[str] = None


class LiabilityRelatedRecurring(BaseModel):
    id: int
    recurring_type: str
    description: str
    amount: Decimal
    frequency: str
    is_active: bool
    next_generation_date: Optional[date] = None


class LiabilityBase(BaseModel):
    liability_type: LiabilityType
    display_name: str = Field(..., min_length=1, max_length=255)
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    lender_name: str = Field(..., min_length=1, max_length=255)
    principal_amount: Decimal = Field(..., gt=0)
    outstanding_balance: Decimal = Field(..., gt=0)
    interest_rate: Optional[Decimal] = Field(None, ge=0)
    start_date: date
    end_date: Optional[date] = None
    monthly_payment: Optional[Decimal] = Field(None, gt=0)
    tax_relevant: bool = False
    tax_relevance_reason: Optional[str] = Field(None, max_length=500)
    report_category: Optional[LiabilityReportCategory] = None
    linked_property_id: Optional[str] = None
    source_document_id: Optional[int] = None
    notes: Optional[str] = Field(None, max_length=1000)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


class LiabilityCreate(LiabilityBase):
    create_recurring_plan: bool = False
    recurring_day_of_month: Optional[int] = Field(None, ge=1, le=31)


class LiabilityUpdate(BaseModel):
    display_name: Optional[str] = Field(None, min_length=1, max_length=255)
    currency: Optional[str] = Field(None, min_length=3, max_length=3)
    lender_name: Optional[str] = Field(None, min_length=1, max_length=255)
    principal_amount: Optional[Decimal] = Field(None, gt=0)
    outstanding_balance: Optional[Decimal] = Field(None, ge=0)
    interest_rate: Optional[Decimal] = Field(None, ge=0)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    monthly_payment: Optional[Decimal] = Field(None, gt=0)
    tax_relevant: Optional[bool] = None
    tax_relevance_reason: Optional[str] = Field(None, max_length=500)
    report_category: Optional[LiabilityReportCategory] = None
    linked_property_id: Optional[str] = None
    source_document_id: Optional[int] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = Field(None, max_length=1000)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: Optional[str]) -> Optional[str]:
        return value.upper() if value else value


class LiabilityResponse(LiabilityBase):
    id: int
    user_id: int
    source_type: LiabilitySourceType
    report_category: LiabilityReportCategory
    linked_loan_id: Optional[int] = None
    is_active: bool
    can_edit_directly: bool
    can_deactivate_directly: bool
    edit_via_document: bool
    requires_supporting_document: bool
    recommended_document_type: str
    created_at: datetime
    updated_at: datetime

    @field_validator("linked_property_id", mode="before")
    @classmethod
    def coerce_property_id(cls, value):
        return str(value) if value is not None else None

    class Config:
        from_attributes = True


class LiabilityDetailResponse(LiabilityResponse):
    related_transactions: list[LiabilityRelatedTransaction] = []
    related_recurring_transactions: list[LiabilityRelatedRecurring] = []


class LiabilityListResponse(BaseModel):
    items: list[LiabilityResponse]
    total: int
    active_count: int


class LiabilitySummaryResponse(BaseModel):
    total_assets: Decimal
    total_liabilities: Decimal
    net_worth: Decimal
    active_liability_count: int
    monthly_debt_service: Decimal
    annual_deductible_interest: Decimal
