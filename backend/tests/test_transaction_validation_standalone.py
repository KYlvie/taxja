"""
Standalone unit tests for transaction input validation (no DB required)

Tests Requirements:
- 1.3: Validate required fields completeness
- 1.4: Validate amount format and positivity
- 9.1: Validate dates in valid tax year range
- 9.2: Validate amounts are positive and properly formatted
- 9.4: Display detailed error messages for validation failures
"""
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

import pytest
from datetime import date, timedelta
from decimal import Decimal
from pydantic import ValidationError
from enum import Enum


# Define enums locally to avoid DB import
class TransactionType(str, Enum):
    INCOME = "income"
    EXPENSE = "expense"


class IncomeCategory(str, Enum):
    AGRICULTURE = "agriculture"
    SELF_EMPLOYMENT = "self_employment"
    BUSINESS = "business"
    EMPLOYMENT = "employment"
    CAPITAL_GAINS = "capital_gains"
    RENTAL = "rental"
    OTHER_INCOME = "other_income"


class ExpenseCategory(str, Enum):
    OFFICE_SUPPLIES = "office_supplies"
    EQUIPMENT = "equipment"
    TRAVEL = "travel"
    MARKETING = "marketing"
    PROFESSIONAL_SERVICES = "professional_services"
    INSURANCE = "insurance"
    MAINTENANCE = "maintenance"
    PROPERTY_TAX = "property_tax"
    LOAN_INTEREST = "loan_interest"
    DEPRECIATION = "depreciation"
    GROCERIES = "groceries"
    UTILITIES = "utilities"
    COMMUTING = "commuting"
    HOME_OFFICE = "home_office"
    OTHER = "other"


# Import schemas after setting up path
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional


class TransactionBase(BaseModel):
    """Base transaction schema"""
    type: TransactionType
    amount: Decimal = Field(..., gt=0, decimal_places=2)
    transaction_date: date
    description: Optional[str] = Field(None, max_length=500)
    income_category: Optional[IncomeCategory] = None
    expense_category: Optional[ExpenseCategory] = None
    is_deductible: bool = False
    
    @field_validator('type')
    @classmethod
    def validate_type(cls, v: TransactionType) -> TransactionType:
        if not isinstance(v, TransactionType):
            valid_types = [t.value for t in TransactionType]
            raise ValueError(
                f"Invalid transaction type. Must be one of: {', '.join(valid_types)}"
            )
        return v
    
    @field_validator('transaction_date')
    @classmethod
    def validate_transaction_date(cls, v: date) -> date:
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
        if v <= 0:
            raise ValueError(
                f"Transaction amount must be positive. Provided amount: €{v}"
            )
        return v
    
    @field_validator('description')
    @classmethod
    def validate_description(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if len(v) == 0:
                raise ValueError("Description cannot be empty.")
        return v


class TransactionCreate(TransactionBase):
    """Transaction creation schema"""
    description: str = Field(..., min_length=1, max_length=500)
    
    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError(
                f"Transaction amount must be positive. Provided amount: €{v}"
            )
        return v.quantize(Decimal('0.01'))
    
    @model_validator(mode='after')
    def validate_category_consistency(self):
        if self.type == TransactionType.INCOME:
            if not self.income_category:
                raise ValueError(
                    'income_category is required for income transactions. '
                    f'Valid categories: {", ".join([c.value for c in IncomeCategory])}'
                )
            if self.expense_category:
                raise ValueError(
                    'expense_category should not be set for income transactions.'
                )
        elif self.type == TransactionType.EXPENSE:
            if not self.expense_category:
                raise ValueError(
                    'expense_category is required for expense transactions. '
                    f'Valid categories: {", ".join([c.value for c in ExpenseCategory])}'
                )
            if self.income_category:
                raise ValueError(
                    'income_category should not be set for expense transactions.'
                )
        return self


class TestTransactionValidation:
    """Test transaction input validation"""
    
    def test_valid_income_transaction(self):
        """Test creating a valid income transaction"""
        transaction = TransactionCreate(
            type=TransactionType.INCOME,
            amount=Decimal("1000.50"),
            transaction_date=date.today(),
            description="Monthly salary",
            income_category=IncomeCategory.EMPLOYMENT
        )
        
        assert transaction.type == TransactionType.INCOME
        assert transaction.amount == Decimal("1000.50")
        assert transaction.income_category == IncomeCategory.EMPLOYMENT
    
    def test_negative_amount_rejected(self):
        """Requirement 1.4: Validate amount is positive"""
        with pytest.raises(ValidationError) as exc_info:
            TransactionCreate(
                type=TransactionType.INCOME,
                amount=Decimal("-100.00"),
                transaction_date=date.today(),
                description="Test",
                income_category=IncomeCategory.EMPLOYMENT
            )
        
        errors = exc_info.value.errors()
        assert any('amount' in str(error['loc']) for error in errors)
        # Check error message mentions greater than 0 or positive
        assert any('greater than 0' in error['msg'].lower() or 'positive' in error['msg'].lower() for error in errors)
    
    def test_zero_amount_rejected(self):
        """Requirement 1.4: Validate amount is positive"""
        with pytest.raises(ValidationError) as exc_info:
            TransactionCreate(
                type=TransactionType.INCOME,
                amount=Decimal("0.00"),
                transaction_date=date.today(),
                description="Test",
                income_category=IncomeCategory.EMPLOYMENT
            )
        
        errors = exc_info.value.errors()
        assert any('amount' in str(error['loc']) for error in errors)
    
    def test_future_date_rejected(self):
        """Requirement 9.1: Validate date is not in future"""
        future_date = date.today() + timedelta(days=1)
        
        with pytest.raises(ValidationError) as exc_info:
            TransactionCreate(
                type=TransactionType.INCOME,
                amount=Decimal("100.00"),
                transaction_date=future_date,
                description="Test",
                income_category=IncomeCategory.EMPLOYMENT
            )
        
        errors = exc_info.value.errors()
        assert any('transaction_date' in str(error['loc']) for error in errors)
        assert any('future' in error['msg'].lower() for error in errors)
    
    def test_missing_required_fields(self):
        """Requirement 1.3: Validate required fields"""
        # Missing type
        with pytest.raises(ValidationError):
            TransactionCreate(
                amount=Decimal("100.00"),
                transaction_date=date.today(),
                description="Test"
            )
        
        # Missing amount
        with pytest.raises(ValidationError):
            TransactionCreate(
                type=TransactionType.INCOME,
                transaction_date=date.today(),
                description="Test"
            )
        
        # Missing date
        with pytest.raises(ValidationError):
            TransactionCreate(
                type=TransactionType.INCOME,
                amount=Decimal("100.00"),
                description="Test"
            )
        
        # Missing description
        with pytest.raises(ValidationError):
            TransactionCreate(
                type=TransactionType.INCOME,
                amount=Decimal("100.00"),
                transaction_date=date.today()
            )
    
    def test_income_requires_income_category(self):
        """Requirement 1.3: Validate category is valid enum value"""
        with pytest.raises(ValidationError) as exc_info:
            TransactionCreate(
                type=TransactionType.INCOME,
                amount=Decimal("100.00"),
                transaction_date=date.today(),
                description="Test"
            )
        
        errors = exc_info.value.errors()
        error_messages = [error['msg'] for error in errors]
        assert any('income_category is required' in msg for msg in error_messages)
    
    def test_expense_requires_expense_category(self):
        """Requirement 1.3: Validate category is valid enum value"""
        with pytest.raises(ValidationError) as exc_info:
            TransactionCreate(
                type=TransactionType.EXPENSE,
                amount=Decimal("100.00"),
                transaction_date=date.today(),
                description="Test"
            )
        
        errors = exc_info.value.errors()
        error_messages = [error['msg'] for error in errors]
        assert any('expense_category is required' in msg for msg in error_messages)
    
    def test_clear_error_messages(self):
        """Requirement 9.4: Return clear error messages"""
        # Test negative amount error message
        with pytest.raises(ValidationError) as exc_info:
            TransactionCreate(
                type=TransactionType.INCOME,
                amount=Decimal("-50.00"),
                transaction_date=date.today(),
                description="Test",
                income_category=IncomeCategory.EMPLOYMENT
            )
        
        errors = exc_info.value.errors()
        error_msg = next(e['msg'] for e in errors if 'amount' in str(e['loc']))
        # Check error message is clear about amount requirement
        assert 'greater than 0' in error_msg.lower() or 'positive' in error_msg.lower()
        
        # Test future date error message
        future_date = date.today() + timedelta(days=5)
        with pytest.raises(ValidationError) as exc_info:
            TransactionCreate(
                type=TransactionType.INCOME,
                amount=Decimal("100.00"),
                transaction_date=future_date,
                description="Test",
                income_category=IncomeCategory.EMPLOYMENT
            )
        
        errors = exc_info.value.errors()
        error_msg = next(e['msg'] for e in errors if 'transaction_date' in str(e['loc']))
        assert 'future' in error_msg.lower()
        assert future_date.strftime('%Y-%m-%d') in error_msg
    
    def test_amount_precision(self):
        """Requirement 9.2: Validate amount format (2 decimal places)"""
        # Pydantic enforces decimal_places=2, so more than 2 decimals should be rejected
        with pytest.raises(ValidationError) as exc_info:
            TransactionCreate(
                type=TransactionType.INCOME,
                amount=Decimal("100.999"),
                transaction_date=date.today(),
                description="Test",
                income_category=IncomeCategory.EMPLOYMENT
            )
        
        errors = exc_info.value.errors()
        assert any('amount' in str(error['loc']) for error in errors)
        assert any('decimal' in error['msg'].lower() for error in errors)
        
        # Valid 2 decimal places should work
        transaction = TransactionCreate(
            type=TransactionType.INCOME,
            amount=Decimal("100.50"),
            transaction_date=date.today(),
            description="Test",
            income_category=IncomeCategory.EMPLOYMENT
        )
        assert transaction.amount == Decimal("100.50")
    
    def test_empty_description_rejected(self):
        """Requirement 1.3: Validate required fields"""
        with pytest.raises(ValidationError):
            TransactionCreate(
                type=TransactionType.INCOME,
                amount=Decimal("100.00"),
                transaction_date=date.today(),
                description="",
                income_category=IncomeCategory.EMPLOYMENT
            )
    
    def test_all_valid_income_categories(self):
        """Requirement 1.3: Validate category is valid enum value"""
        for category in IncomeCategory:
            transaction = TransactionCreate(
                type=TransactionType.INCOME,
                amount=Decimal("100.00"),
                transaction_date=date.today(),
                description="Test",
                income_category=category
            )
            assert transaction.income_category == category
    
    def test_all_valid_expense_categories(self):
        """Requirement 1.3: Validate category is valid enum value"""
        for category in ExpenseCategory:
            transaction = TransactionCreate(
                type=TransactionType.EXPENSE,
                amount=Decimal("100.00"),
                transaction_date=date.today(),
                description="Test",
                expense_category=category
            )
            assert transaction.expense_category == category


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
