"""Pydantic schemas for recurring transactions"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field, field_validator
from app.models.recurring_transaction import RecurrenceFrequency, RecurringTransactionType


class RecurringTransactionBase(BaseModel):
    """Base schema for recurring transaction"""
    description: str = Field(..., min_length=1, max_length=500)
    amount: Decimal = Field(..., gt=0, decimal_places=2)
    transaction_type: str = Field(..., pattern="^(income|expense)$")
    category: str = Field(..., min_length=1, max_length=100)
    frequency: RecurrenceFrequency
    start_date: date
    end_date: Optional[date] = None
    day_of_month: Optional[int] = Field(None, ge=1, le=31)
    template: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = Field(None, max_length=1000)
    
    @field_validator('end_date')
    @classmethod
    def validate_end_date(cls, v, info):
        if v and info.data.get('start_date') and v < info.data['start_date']:
            raise ValueError('end_date must be after start_date')
        return v


class RecurringTransactionCreate(RecurringTransactionBase):
    """Schema for creating a recurring transaction"""
    recurring_type: RecurringTransactionType
    property_id: Optional[str] = None
    loan_id: Optional[int] = None


class RecurringTransactionUpdate(BaseModel):
    """Schema for updating a recurring transaction"""
    description: Optional[str] = Field(None, min_length=1, max_length=500)
    amount: Optional[Decimal] = Field(None, gt=0, decimal_places=2)
    frequency: Optional[RecurrenceFrequency] = None
    end_date: Optional[date] = None
    day_of_month: Optional[int] = Field(None, ge=1, le=31)
    notes: Optional[str] = Field(None, max_length=1000)
    is_active: Optional[bool] = None


class RecurringTransactionResponse(RecurringTransactionBase):
    """Schema for recurring transaction response"""
    id: int
    user_id: int
    recurring_type: RecurringTransactionType
    property_id: Optional[str] = None
    loan_id: Optional[int] = None
    template: Optional[str] = None
    is_active: bool
    paused_at: Optional[datetime] = None
    last_generated_date: Optional[date] = None
    next_generation_date: Optional[date] = None
    created_at: datetime
    updated_at: datetime

    @field_validator("property_id", mode="before")
    @classmethod
    def coerce_uuid_to_str(cls, v):
        """Convert UUID to string if needed"""
        return str(v) if v is not None else None

    class Config:
        from_attributes = True


class RentalIncomeRecurringCreate(BaseModel):
    """Schema for creating rental income recurring transaction"""
    property_id: str
    monthly_rent: Decimal = Field(..., gt=0, decimal_places=2)
    start_date: date
    end_date: Optional[date] = None
    day_of_month: int = Field(1, ge=1, le=31)


class LoanInterestRecurringCreate(BaseModel):
    """Schema for creating loan interest recurring transaction"""
    loan_id: int
    monthly_interest: Decimal = Field(..., gt=0, decimal_places=2)
    start_date: date
    end_date: Optional[date] = None
    day_of_month: int = Field(1, ge=1, le=31)


class RecurringTransactionListResponse(BaseModel):
    """Schema for list of recurring transactions"""
    items: list[RecurringTransactionResponse]
    total: int
    active_count: int
    paused_count: int

    class Config:
        from_attributes = True



class TemplateRecurringCreate(BaseModel):
    """Schema for creating recurring transaction from template"""
    template_id: str
    amount: Decimal = Field(..., gt=0, decimal_places=2)
    start_date: date
    end_date: Optional[date] = None
    day_of_month: Optional[int] = Field(None, ge=1, le=31)
    notes: Optional[str] = Field(None, max_length=1000)


class RecurringTemplateResponse(BaseModel):
    """Schema for template information"""
    id: str
    name_de: str
    name_en: str
    name_zh: str
    description_de: str
    description_en: str
    description_zh: str
    transaction_type: str
    category: str
    frequency: str
    default_day_of_month: int
    icon: str
    priority: int
