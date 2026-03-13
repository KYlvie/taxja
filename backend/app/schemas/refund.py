"""
Pydantic schemas for employee refund calculation

Used for request/response validation in the refund API.
"""

from typing import Optional, Dict, Any
from decimal import Decimal
from pydantic import BaseModel, Field


class LohnzettelSchema(BaseModel):
    """Schema for Lohnzettel data"""

    gross_income: float = Field(..., description="Gross annual income (Brutto)", gt=0)
    withheld_tax: float = Field(
        ..., description="Withheld income tax (Lohnsteuer)", ge=0
    )
    withheld_svs: float = Field(
        default=0.0, description="Withheld social insurance contributions", ge=0
    )
    employer_name: str = Field(..., description="Employer name", min_length=1)
    tax_year: int = Field(..., description="Tax year", ge=2020, le=2030)


class AdditionalDeductionsSchema(BaseModel):
    """Schema for additional deductions"""

    donations: Optional[float] = Field(
        None, description="Charitable donations", ge=0
    )
    church_tax: Optional[float] = Field(None, description="Church tax", ge=0)
    other: Optional[float] = Field(None, description="Other deductible expenses", ge=0)


class RefundCalculationRequestSchema(BaseModel):
    """Schema for refund calculation request"""

    lohnzettel: LohnzettelSchema
    additional_deductions: Optional[AdditionalDeductionsSchema] = None


class RefundResultSchema(BaseModel):
    """Schema for refund calculation result"""

    gross_income: float = Field(..., description="Gross annual income")
    withheld_tax: float = Field(..., description="Withheld tax")
    actual_tax_liability: float = Field(..., description="Actual tax liability")
    refund_amount: float = Field(..., description="Refund amount (absolute value)")
    is_refund: bool = Field(..., description="True if refund, False if payment needed")
    deductions_applied: Dict[str, float] = Field(
        ..., description="Deductions applied"
    )
    explanation: str = Field(..., description="Human-readable explanation")
    breakdown: Dict[str, Any] = Field(..., description="Detailed breakdown")


class RefundEstimateSchema(BaseModel):
    """Schema for refund estimate"""

    estimated_refund: float = Field(..., description="Estimated refund amount")
    is_refund: bool = Field(..., description="True if refund expected")
    confidence: str = Field(..., description="Confidence level (low/medium/high/none)")
    suggestions: list[str] = Field(..., description="Suggestions to increase refund")
    message: str = Field(..., description="Message to user")
