"""Transaction schemas for request/response validation"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field, field_validator, model_validator
from app.models.transaction import TransactionType, IncomeCategory, ExpenseCategory


class TransactionBase(BaseModel):
    """Base transaction schema"""
    type: TransactionType
    amount: Decimal = Field(..., gt=0, description="Transaction amount (must be positive)")
    transaction_date: date = Field(..., description="Transaction date")
    description: Optional[str] = Field(None, max_length=500, description="Transaction description")
    income_category: Optional[IncomeCategory] = Field(None, description="Income category (required if type is income)")
    expense_category: Optional[ExpenseCategory] = Field(None, description="Expense category (required if type is expense)")
    is_deductible: bool = Field(default=False, description="Whether the expense is tax deductible")
    deduction_reason: Optional[str] = Field(None, max_length=500, description="Reason for deductibility")
    vat_rate: Optional[Decimal] = Field(None, ge=0, le=1, description="VAT rate (e.g., 0.20 for 20%)")
    vat_amount: Optional[Decimal] = Field(None, ge=0, description="VAT amount")
    document_id: Optional[int] = Field(None, description="Associated document ID")
    
    @field_validator('type')
    @classmethod
    def validate_type(cls, v: TransactionType) -> TransactionType:
        """Validate transaction type is a valid enum value"""
        if not isinstance(v, TransactionType):
            valid_types = [t.value for t in TransactionType]
            raise ValueError(
                f"Invalid transaction type. Must be one of: {', '.join(valid_types)}"
            )
        return v
    
    @field_validator('income_category')
    @classmethod
    def validate_income_category(cls, v: Optional[IncomeCategory]) -> Optional[IncomeCategory]:
        """Validate income category is a valid enum value if provided"""
        if v is not None and not isinstance(v, IncomeCategory):
            valid_categories = [c.value for c in IncomeCategory]
            raise ValueError(
                f"Invalid income category. Must be one of: {', '.join(valid_categories)}"
            )
        return v
    
    @field_validator('expense_category')
    @classmethod
    def validate_expense_category(cls, v: Optional[ExpenseCategory]) -> Optional[ExpenseCategory]:
        """Validate expense category is a valid enum value if provided"""
        if v is not None and not isinstance(v, ExpenseCategory):
            valid_categories = [c.value for c in ExpenseCategory]
            raise ValueError(
                f"Invalid expense category. Must be one of: {', '.join(valid_categories)}"
            )
        return v
    
    @field_validator('transaction_date')
    @classmethod
    def validate_transaction_date(cls, v: date) -> date:
        """Validate transaction date is not in the future"""
        if v > date.today():
            raise ValueError(
                f"Transaction date cannot be in the future. "
                f"Provided date: {v.strftime('%Y-%m-%d')}, "
                f"Today: {date.today().strftime('%Y-%m-%d')}"
            )
        return v
    
    @field_validator('amount')
    @classmethod
    def validate_amount_positive(cls, v: Decimal) -> Decimal:
        """Validate amount is positive with clear error message"""
        if v <= 0:
            raise ValueError(
                f"Transaction amount must be positive. Provided amount: €{v}"
            )
        return v
    
    @field_validator('description')
    @classmethod
    def validate_description(cls, v: Optional[str]) -> Optional[str]:
        """Validate description is not empty if provided"""
        if v is not None:
            v = v.strip()
            if len(v) == 0:
                raise ValueError("Description cannot be empty. Either provide a description or omit the field.")
        return v


class TransactionCreate(TransactionBase):
    """Transaction creation schema with comprehensive validation"""
    
    # Override to make description required for creation
    description: str = Field(..., min_length=1, max_length=500, description="Transaction description (required)")
    
    # Recurring fields
    is_recurring: bool = Field(default=False, description="Whether this is a recurring transaction")
    recurring_frequency: Optional[str] = Field(None, description="Frequency: monthly, quarterly, yearly, weekly")
    recurring_start_date: Optional[date] = Field(None, description="Start date for recurring")
    recurring_end_date: Optional[date] = Field(None, description="End date for recurring (optional)")
    recurring_day_of_month: Optional[int] = Field(None, ge=1, le=31, description="Day of month for generation")
    property_id: Optional[str] = Field(None, description="Associated property/asset ID")
    
    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        """Validate amount is positive and has correct precision"""
        if v <= 0:
            raise ValueError(
                f"Transaction amount must be positive. Provided amount: €{v}"
            )
        # Ensure 2 decimal places
        quantized = v.quantize(Decimal('0.01'))
        return quantized
    
    @model_validator(mode='after')
    def validate_category_consistency(self):
        """Validate category based on type after model initialization"""
        if self.type == TransactionType.INCOME:
            if not self.income_category:
                raise ValueError(
                    'income_category is required for income transactions. '
                    f'Valid categories: {", ".join([c.value for c in IncomeCategory])}'
                )
            if self.expense_category:
                raise ValueError(
                    'expense_category should not be set for income transactions. '
                    'Please remove expense_category or change type to expense.'
                )
        elif self.type == TransactionType.EXPENSE:
            if not self.expense_category:
                raise ValueError(
                    'expense_category is required for expense transactions. '
                    f'Valid categories: {", ".join([c.value for c in ExpenseCategory])}'
                )
            if self.income_category:
                raise ValueError(
                    'income_category should not be set for expense transactions. '
                    'Please remove income_category or change type to income.'
                )
        
        # Validate recurring fields
        if self.is_recurring:
            if not self.recurring_frequency:
                raise ValueError('recurring_frequency is required for recurring transactions')
            if self.recurring_frequency not in ('monthly', 'quarterly', 'yearly', 'weekly', 'daily'):
                raise ValueError('recurring_frequency must be one of: monthly, quarterly, yearly, weekly, daily')
            if not self.recurring_start_date:
                raise ValueError('recurring_start_date is required for recurring transactions')
        
        return self


class TransactionUpdate(BaseModel):
    """Transaction update schema (all fields optional)"""
    type: Optional[TransactionType] = None
    amount: Optional[Decimal] = Field(None, gt=0)
    transaction_date: Optional[date] = None
    description: Optional[str] = Field(None, min_length=1, max_length=500)
    income_category: Optional[IncomeCategory] = None
    expense_category: Optional[ExpenseCategory] = None
    is_deductible: Optional[bool] = None
    deduction_reason: Optional[str] = Field(None, max_length=500)
    vat_rate: Optional[Decimal] = Field(None, ge=0, le=1)
    vat_amount: Optional[Decimal] = Field(None, ge=0)
    document_id: Optional[int] = None
    reviewed: Optional[bool] = None
    locked: Optional[bool] = None
    
    @field_validator('type')
    @classmethod
    def validate_type(cls, v: Optional[TransactionType]) -> Optional[TransactionType]:
        """Validate transaction type is a valid enum value if provided"""
        if v is not None and not isinstance(v, TransactionType):
            valid_types = [t.value for t in TransactionType]
            raise ValueError(
                f"Invalid transaction type. Must be one of: {', '.join(valid_types)}"
            )
        return v
    
    @field_validator('income_category')
    @classmethod
    def validate_income_category(cls, v: Optional[IncomeCategory]) -> Optional[IncomeCategory]:
        """Validate income category is a valid enum value if provided"""
        if v is not None and not isinstance(v, IncomeCategory):
            valid_categories = [c.value for c in IncomeCategory]
            raise ValueError(
                f"Invalid income category. Must be one of: {', '.join(valid_categories)}"
            )
        return v
    
    @field_validator('expense_category')
    @classmethod
    def validate_expense_category(cls, v: Optional[ExpenseCategory]) -> Optional[ExpenseCategory]:
        """Validate expense category is a valid enum value if provided"""
        if v is not None and not isinstance(v, ExpenseCategory):
            valid_categories = [c.value for c in ExpenseCategory]
            raise ValueError(
                f"Invalid expense category. Must be one of: {', '.join(valid_categories)}"
            )
        return v
    
    @field_validator('transaction_date')
    @classmethod
    def validate_transaction_date(cls, v: Optional[date]) -> Optional[date]:
        """Validate transaction date is not in the future if provided"""
        if v is not None and v > date.today():
            raise ValueError(
                f"Transaction date cannot be in the future. "
                f"Provided date: {v.strftime('%Y-%m-%d')}, "
                f"Today: {date.today().strftime('%Y-%m-%d')}"
            )
        return v
    
    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Validate amount if provided"""
        if v is not None:
            if v <= 0:
                raise ValueError(
                    f"Transaction amount must be positive. Provided amount: €{v}"
                )
            return v.quantize(Decimal('0.01'))
        return v
    
    @field_validator('description')
    @classmethod
    def validate_description(cls, v: Optional[str]) -> Optional[str]:
        """Validate description is not empty if provided"""
        if v is not None:
            v = v.strip()
            if len(v) == 0:
                raise ValueError("Description cannot be empty. Either provide a description or omit the field.")
        return v


class TransactionResponse(TransactionBase):
    """Transaction response schema"""
    id: int
    user_id: int
    property_id: Optional[str] = None
    classification_confidence: Optional[Decimal] = None
    needs_review: bool = False
    import_source: Optional[str] = None
    is_recurring: bool = False
    recurring_frequency: Optional[str] = None
    recurring_start_date: Optional[date] = None
    recurring_end_date: Optional[date] = None
    recurring_day_of_month: Optional[int] = None
    recurring_is_active: bool = True
    recurring_next_date: Optional[date] = None
    recurring_last_generated: Optional[date] = None
    parent_recurring_id: Optional[int] = None
    is_system_generated: bool = False
    reviewed: bool = False
    locked: bool = False
    created_at: datetime
    updated_at: datetime

    @field_validator(
        "needs_review", "is_recurring", "recurring_is_active",
        "is_system_generated", "is_deductible", "reviewed", "locked", mode="before",
    )
    @classmethod
    def coerce_none_to_false(cls, v):
        """Coerce None to False for boolean fields that may be NULL in DB"""
        return v if v is not None else False

    class Config:
        from_attributes = True


class TransactionListResponse(BaseModel):
    """Transaction list response with pagination"""
    total: int
    transactions: list[TransactionResponse]
    page: int
    page_size: int
    total_pages: int


class TransactionFilterParams(BaseModel):
    """Transaction filter parameters"""
    type: Optional[TransactionType] = Field(None, description="Filter by transaction type")
    income_category: Optional[IncomeCategory] = Field(None, description="Filter by income category")
    expense_category: Optional[ExpenseCategory] = Field(None, description="Filter by expense category")
    is_deductible: Optional[bool] = Field(None, description="Filter by deductibility")
    date_from: Optional[date] = Field(None, description="Filter transactions from this date")
    date_to: Optional[date] = Field(None, description="Filter transactions until this date")
    min_amount: Optional[Decimal] = Field(None, ge=0, description="Minimum transaction amount")
    max_amount: Optional[Decimal] = Field(None, ge=0, description="Maximum transaction amount")
    search: Optional[str] = Field(None, max_length=100, description="Search in description")
    tax_year: Optional[int] = Field(None, ge=1900, le=2100, description="Filter by tax year (e.g., 2026)")
    
    @field_validator('date_from', 'date_to')
    @classmethod
    def validate_dates(cls, v, info):
        """Validate date range"""
        if info.field_name == 'date_to' and v:
            date_from = info.data.get('date_from')
            if date_from and v < date_from:
                raise ValueError('date_to must be after date_from')
        return v
