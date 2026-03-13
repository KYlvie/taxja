"""Pydantic schemas for PropertyLoan"""
from datetime import date
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field, field_validator
from uuid import UUID


class LoanBase(BaseModel):
    """Base schema for PropertyLoan"""
    loan_amount: Decimal = Field(..., gt=0, le=100_000_000, description="Loan principal amount")
    interest_rate: Decimal = Field(..., ge=0, le=0.20, description="Annual interest rate (0-20%)")
    start_date: date = Field(..., description="Loan start date")
    end_date: Optional[date] = Field(None, description="Loan end date (optional for open-ended)")
    monthly_payment: Decimal = Field(..., gt=0, description="Monthly payment amount")
    lender_name: str = Field(..., min_length=1, max_length=255, description="Lender institution name")
    lender_account: Optional[str] = Field(None, max_length=100, description="IBAN or account number")
    loan_type: Optional[str] = Field(None, max_length=50, description="Loan type (fixed_rate, variable_rate, annuity)")
    notes: Optional[str] = Field(None, max_length=1000, description="Additional notes")
    
    @field_validator('end_date')
    @classmethod
    def validate_end_date(cls, v, info):
        """Validate that end_date is after start_date"""
        if v is not None and 'start_date' in info.data:
            start_date = info.data['start_date']
            if v < start_date:
                raise ValueError('end_date must be on or after start_date')
        return v
    
    @field_validator('interest_rate')
    @classmethod
    def validate_interest_rate(cls, v):
        """Validate interest rate is reasonable"""
        if v < 0 or v > Decimal("0.20"):
            raise ValueError('interest_rate must be between 0% and 20%')
        return v


class LoanCreate(LoanBase):
    """Schema for creating a new loan"""
    property_id: UUID = Field(..., description="Property ID to link loan to")


class LoanUpdate(BaseModel):
    """Schema for updating a loan"""
    loan_amount: Optional[Decimal] = Field(None, gt=0, le=100_000_000)
    interest_rate: Optional[Decimal] = Field(None, ge=0, le=0.20)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    monthly_payment: Optional[Decimal] = Field(None, gt=0)
    lender_name: Optional[str] = Field(None, min_length=1, max_length=255)
    lender_account: Optional[str] = Field(None, max_length=100)
    loan_type: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = Field(None, max_length=1000)


class LoanResponse(LoanBase):
    """Schema for loan API responses"""
    id: int
    property_id: UUID
    user_id: int
    created_at: date
    updated_at: date
    
    class Config:
        from_attributes = True


class LoanListItem(BaseModel):
    """Schema for loan list items"""
    id: int
    property_id: UUID
    loan_amount: Decimal
    interest_rate: Decimal
    monthly_payment: Decimal
    start_date: date
    end_date: Optional[date]
    lender_name: str
    loan_type: Optional[str]
    
    class Config:
        from_attributes = True


class AmortizationEntry(BaseModel):
    """Schema for amortization schedule entry"""
    payment_number: int
    payment_date: str  # ISO format date string
    payment_amount: float
    principal_amount: float
    interest_amount: float
    remaining_balance: float


class AmortizationSchedule(BaseModel):
    """Schema for complete amortization schedule"""
    loan_id: int
    schedule: list[AmortizationEntry]
    total_payments: float
    total_interest: float
    total_principal: float


class LoanSummary(BaseModel):
    """Schema for loan summary with calculated metrics"""
    loan_id: int
    property_id: str
    loan_amount: float
    interest_rate: float
    monthly_payment: float
    start_date: str
    end_date: Optional[str]
    lender_name: str
    loan_type: Optional[str]
    current_balance: float
    total_payments: float
    total_interest: float
    total_principal: float
    current_year_interest: float
    number_of_payments: int
    payments_remaining: int


class AnnualInterest(BaseModel):
    """Schema for annual interest calculation"""
    loan_id: int
    year: int
    interest_amount: float
