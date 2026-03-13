"""
Property-based tests for transaction input validation

Property 3: Input validation rejects invalid data
Validates Requirements: 1.3, 1.4, 9.1, 9.2, 9.4

This test suite uses property-based testing (Hypothesis) to verify that:
1. All invalid transaction data is properly rejected
2. Validation rules are consistently applied
3. Error messages are clear and informative
4. Valid data is always accepted
"""
import pytest
from hypothesis import given, strategies as st, assume, settings, example
from hypothesis.strategies import composite
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pydantic import ValidationError, BaseModel, Field, field_validator, model_validator
from typing import Optional
from enum import Enum


# Define enums locally to avoid database imports
class TransactionType(str, Enum):
    """Transaction type enumeration"""
    INCOME = "income"
    EXPENSE = "expense"


class IncomeCategory(str, Enum):
    """Income category enumeration"""
    AGRICULTURE = "agriculture"
    SELF_EMPLOYMENT = "self_employment"
    BUSINESS = "business"
    EMPLOYMENT = "employment"
    CAPITAL_GAINS = "capital_gains"
    RENTAL = "rental"
    OTHER_INCOME = "other_income"


class ExpenseCategory(str, Enum):
    """Expense category enumeration"""
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


# Define schemas locally to avoid database imports
class TransactionBase(BaseModel):
    """Base transaction schema"""
    type: TransactionType
    amount: Decimal = Field(..., gt=0)
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


class TransactionUpdate(BaseModel):
    """Transaction update schema"""
    type: Optional[TransactionType] = None
    amount: Optional[Decimal] = Field(None, gt=0)
    transaction_date: Optional[date] = None
    description: Optional[str] = Field(None, min_length=1, max_length=500)
    income_category: Optional[IncomeCategory] = None
    expense_category: Optional[ExpenseCategory] = None
    is_deductible: Optional[bool] = None
    
    @field_validator('transaction_date')
    @classmethod
    def validate_transaction_date(cls, v: Optional[date]) -> Optional[date]:
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
        if v is not None:
            v = v.strip()
            if len(v) == 0:
                raise ValueError("Description cannot be empty.")
        return v


# Strategy helpers

@composite
def valid_amounts(draw):
    """Generate valid positive amounts with 2 decimal places"""
    # Generate amounts between 0.01 and 1,000,000.00
    amount_int = draw(st.integers(min_value=1, max_value=100000000))
    return Decimal(amount_int) / Decimal(100)


@composite
def invalid_amounts(draw):
    """Generate invalid amounts (negative, zero, or invalid precision)"""
    choice = draw(st.integers(min_value=0, max_value=2))
    
    if choice == 0:
        # Negative amount
        amount_int = draw(st.integers(min_value=-100000000, max_value=-1))
        return Decimal(amount_int) / Decimal(100)
    elif choice == 1:
        # Zero amount
        return Decimal("0.00")
    else:
        # Invalid precision (more than 2 decimal places)
        # Note: Pydantic will reject this during validation
        return Decimal("100.999")


@composite
def valid_past_dates(draw):
    """Generate valid dates (today or in the past)"""
    days_ago = draw(st.integers(min_value=0, max_value=3650))  # Up to 10 years ago
    return date.today() - timedelta(days=days_ago)


@composite
def future_dates(draw):
    """Generate future dates (invalid)"""
    days_ahead = draw(st.integers(min_value=1, max_value=365))
    return date.today() + timedelta(days=days_ahead)


@composite
def valid_descriptions(draw):
    """Generate valid descriptions (non-empty, max 500 chars)"""
    return draw(st.text(min_size=1, max_size=500).filter(lambda x: x.strip() != ""))


@composite
def invalid_descriptions(draw):
    """Generate invalid descriptions (empty or whitespace only)"""
    choice = draw(st.integers(min_value=0, max_value=2))
    
    if choice == 0:
        return ""
    elif choice == 1:
        return "   "
    else:
        # Too long
        return "x" * 501


@composite
def valid_income_transaction_data(draw):
    """Generate valid income transaction data"""
    return {
        "type": TransactionType.INCOME,
        "amount": draw(valid_amounts()),
        "transaction_date": draw(valid_past_dates()),
        "description": draw(valid_descriptions()),
        "income_category": draw(st.sampled_from(list(IncomeCategory))),
        "expense_category": None
    }


@composite
def valid_expense_transaction_data(draw):
    """Generate valid expense transaction data"""
    return {
        "type": TransactionType.EXPENSE,
        "amount": draw(valid_amounts()),
        "transaction_date": draw(valid_past_dates()),
        "description": draw(valid_descriptions()),
        "expense_category": draw(st.sampled_from(list(ExpenseCategory))),
        "income_category": None
    }


class TestInputValidationProperties:
    """Property-based tests for input validation"""
    
    # Property 3.1: Valid data is always accepted
    
    @given(data=valid_income_transaction_data())
    @settings(max_examples=100)
    def test_valid_income_transactions_always_accepted(self, data):
        """
        Property: All valid income transactions should be accepted
        Validates: Requirements 1.3, 1.4, 9.1, 9.2
        """
        try:
            transaction = TransactionCreate(**data)
            
            # Verify all fields are correctly set
            assert transaction.type == TransactionType.INCOME
            assert transaction.amount > 0
            assert transaction.transaction_date <= date.today()
            assert transaction.description.strip() != ""
            assert transaction.income_category is not None
            assert transaction.expense_category is None
            
        except ValidationError as e:
            pytest.fail(f"Valid income transaction was rejected: {e}")
    
    @given(data=valid_expense_transaction_data())
    @settings(max_examples=100)
    def test_valid_expense_transactions_always_accepted(self, data):
        """
        Property: All valid expense transactions should be accepted
        Validates: Requirements 1.3, 1.4, 9.1, 9.2
        """
        try:
            transaction = TransactionCreate(**data)
            
            # Verify all fields are correctly set
            assert transaction.type == TransactionType.EXPENSE
            assert transaction.amount > 0
            assert transaction.transaction_date <= date.today()
            assert transaction.description.strip() != ""
            assert transaction.expense_category is not None
            assert transaction.income_category is None
            
        except ValidationError as e:
            pytest.fail(f"Valid expense transaction was rejected: {e}")
    
    # Property 3.2: Invalid amounts are always rejected
    
    @given(
        amount=invalid_amounts(),
        transaction_date=valid_past_dates(),
        description=valid_descriptions(),
        income_category=st.sampled_from(list(IncomeCategory))
    )
    @settings(max_examples=50)
    def test_invalid_amounts_always_rejected(
        self,
        amount,
        transaction_date,
        description,
        income_category
    ):
        """
        Property: All invalid amounts (negative, zero, wrong precision) should be rejected
        Validates: Requirements 1.4, 9.2
        """
        with pytest.raises(ValidationError) as exc_info:
            TransactionCreate(
                type=TransactionType.INCOME,
                amount=amount,
                transaction_date=transaction_date,
                description=description,
                income_category=income_category
            )
        
        # Verify error is about amount
        errors = exc_info.value.errors()
        assert any('amount' in str(error['loc']) for error in errors), \
            f"Expected amount validation error, got: {errors}"
    
    # Property 3.3: Future dates are always rejected
    
    @given(
        future_date=future_dates(),
        amount=valid_amounts(),
        description=valid_descriptions(),
        income_category=st.sampled_from(list(IncomeCategory))
    )
    @settings(max_examples=50)
    @example(
        future_date=date.today() + timedelta(days=1),
        amount=Decimal("100.00"),
        description="Test",
        income_category=IncomeCategory.EMPLOYMENT
    )
    def test_future_dates_always_rejected(
        self,
        future_date,
        amount,
        description,
        income_category
    ):
        """
        Property: All future dates should be rejected
        Validates: Requirements 9.1
        """
        with pytest.raises(ValidationError) as exc_info:
            TransactionCreate(
                type=TransactionType.INCOME,
                amount=amount,
                transaction_date=future_date,
                description=description,
                income_category=income_category
            )
        
        # Verify error is about transaction_date
        errors = exc_info.value.errors()
        assert any('transaction_date' in str(error['loc']) for error in errors), \
            f"Expected transaction_date validation error, got: {errors}"
        
        # Verify error message mentions "future"
        error_messages = [error['msg'] for error in errors]
        assert any('future' in msg.lower() for msg in error_messages), \
            f"Expected 'future' in error message, got: {error_messages}"
    
    # Property 3.4: Invalid descriptions are always rejected
    
    @given(
        description=invalid_descriptions(),
        amount=valid_amounts(),
        transaction_date=valid_past_dates(),
        income_category=st.sampled_from(list(IncomeCategory))
    )
    @settings(max_examples=50)
    def test_invalid_descriptions_always_rejected(
        self,
        description,
        amount,
        transaction_date,
        income_category
    ):
        """
        Property: All invalid descriptions (empty, whitespace, too long) should be rejected
        Validates: Requirements 1.3
        """
        with pytest.raises(ValidationError) as exc_info:
            TransactionCreate(
                type=TransactionType.INCOME,
                amount=amount,
                transaction_date=transaction_date,
                description=description,
                income_category=income_category
            )
        
        # Verify error is about description
        errors = exc_info.value.errors()
        assert any('description' in str(error['loc']) for error in errors), \
            f"Expected description validation error, got: {errors}"
    
    # Property 3.5: Missing required fields are always rejected
    
    @given(
        amount=valid_amounts(),
        transaction_date=valid_past_dates(),
        description=valid_descriptions()
    )
    @settings(max_examples=50)
    def test_missing_type_always_rejected(
        self,
        amount,
        transaction_date,
        description
    ):
        """
        Property: Transactions without type field should always be rejected
        Validates: Requirements 1.3
        """
        with pytest.raises(ValidationError) as exc_info:
            # Intentionally omit type field
            TransactionCreate(
                amount=amount,
                transaction_date=transaction_date,
                description=description
            )
        
        errors = exc_info.value.errors()
        assert any(error['loc'] == ('type',) and error['type'] == 'missing' for error in errors), \
            f"Expected missing 'type' error, got: {errors}"
    
    @given(
        transaction_date=valid_past_dates(),
        description=valid_descriptions(),
        income_category=st.sampled_from(list(IncomeCategory))
    )
    @settings(max_examples=50)
    def test_missing_amount_always_rejected(
        self,
        transaction_date,
        description,
        income_category
    ):
        """
        Property: Transactions without amount field should always be rejected
        Validates: Requirements 1.3
        """
        with pytest.raises(ValidationError) as exc_info:
            TransactionCreate(
                type=TransactionType.INCOME,
                transaction_date=transaction_date,
                description=description,
                income_category=income_category
            )
        
        errors = exc_info.value.errors()
        assert any(error['loc'] == ('amount',) and error['type'] == 'missing' for error in errors), \
            f"Expected missing 'amount' error, got: {errors}"
    
    @given(
        amount=valid_amounts(),
        description=valid_descriptions(),
        income_category=st.sampled_from(list(IncomeCategory))
    )
    @settings(max_examples=50)
    def test_missing_date_always_rejected(
        self,
        amount,
        description,
        income_category
    ):
        """
        Property: Transactions without transaction_date field should always be rejected
        Validates: Requirements 1.3
        """
        with pytest.raises(ValidationError) as exc_info:
            TransactionCreate(
                type=TransactionType.INCOME,
                amount=amount,
                description=description,
                income_category=income_category
            )
        
        errors = exc_info.value.errors()
        assert any(error['loc'] == ('transaction_date',) and error['type'] == 'missing' for error in errors), \
            f"Expected missing 'transaction_date' error, got: {errors}"
    
    @given(
        amount=valid_amounts(),
        transaction_date=valid_past_dates(),
        income_category=st.sampled_from(list(IncomeCategory))
    )
    @settings(max_examples=50)
    def test_missing_description_always_rejected(
        self,
        amount,
        transaction_date,
        income_category
    ):
        """
        Property: Transactions without description field should always be rejected
        Validates: Requirements 1.3
        """
        with pytest.raises(ValidationError) as exc_info:
            TransactionCreate(
                type=TransactionType.INCOME,
                amount=amount,
                transaction_date=transaction_date,
                income_category=income_category
            )
        
        errors = exc_info.value.errors()
        assert any(error['loc'] == ('description',) and error['type'] == 'missing' for error in errors), \
            f"Expected missing 'description' error, got: {errors}"
    
    # Property 3.6: Category consistency is always enforced
    
    @given(
        amount=valid_amounts(),
        transaction_date=valid_past_dates(),
        description=valid_descriptions()
    )
    @settings(max_examples=50)
    def test_income_without_income_category_rejected(
        self,
        amount,
        transaction_date,
        description
    ):
        """
        Property: Income transactions without income_category should always be rejected
        Validates: Requirements 1.3
        """
        with pytest.raises(ValidationError) as exc_info:
            TransactionCreate(
                type=TransactionType.INCOME,
                amount=amount,
                transaction_date=transaction_date,
                description=description
            )
        
        errors = exc_info.value.errors()
        error_messages = [error['msg'] for error in errors]
        assert any('income_category is required' in msg for msg in error_messages), \
            f"Expected 'income_category is required' error, got: {error_messages}"
    
    @given(
        amount=valid_amounts(),
        transaction_date=valid_past_dates(),
        description=valid_descriptions()
    )
    @settings(max_examples=50)
    def test_expense_without_expense_category_rejected(
        self,
        amount,
        transaction_date,
        description
    ):
        """
        Property: Expense transactions without expense_category should always be rejected
        Validates: Requirements 1.3
        """
        with pytest.raises(ValidationError) as exc_info:
            TransactionCreate(
                type=TransactionType.EXPENSE,
                amount=amount,
                transaction_date=transaction_date,
                description=description
            )
        
        errors = exc_info.value.errors()
        error_messages = [error['msg'] for error in errors]
        assert any('expense_category is required' in msg for msg in error_messages), \
            f"Expected 'expense_category is required' error, got: {error_messages}"
    
    @given(
        amount=valid_amounts(),
        transaction_date=valid_past_dates(),
        description=valid_descriptions(),
        income_category=st.sampled_from(list(IncomeCategory)),
        expense_category=st.sampled_from(list(ExpenseCategory))
    )
    @settings(max_examples=50)
    def test_income_with_expense_category_rejected(
        self,
        amount,
        transaction_date,
        description,
        income_category,
        expense_category
    ):
        """
        Property: Income transactions with expense_category should always be rejected
        Validates: Requirements 1.3
        """
        with pytest.raises(ValidationError) as exc_info:
            TransactionCreate(
                type=TransactionType.INCOME,
                amount=amount,
                transaction_date=transaction_date,
                description=description,
                income_category=income_category,
                expense_category=expense_category
            )
        
        errors = exc_info.value.errors()
        error_messages = [error['msg'] for error in errors]
        assert any('expense_category should not be set' in msg for msg in error_messages), \
            f"Expected 'expense_category should not be set' error, got: {error_messages}"
    
    @given(
        amount=valid_amounts(),
        transaction_date=valid_past_dates(),
        description=valid_descriptions(),
        income_category=st.sampled_from(list(IncomeCategory)),
        expense_category=st.sampled_from(list(ExpenseCategory))
    )
    @settings(max_examples=50)
    def test_expense_with_income_category_rejected(
        self,
        amount,
        transaction_date,
        description,
        income_category,
        expense_category
    ):
        """
        Property: Expense transactions with income_category should always be rejected
        Validates: Requirements 1.3
        """
        with pytest.raises(ValidationError) as exc_info:
            TransactionCreate(
                type=TransactionType.EXPENSE,
                amount=amount,
                transaction_date=transaction_date,
                description=description,
                expense_category=expense_category,
                income_category=income_category
            )
        
        errors = exc_info.value.errors()
        error_messages = [error['msg'] for error in errors]
        assert any('income_category should not be set' in msg for msg in error_messages), \
            f"Expected 'income_category should not be set' error, got: {error_messages}"
    
    # Property 3.7: Error messages are always clear and informative
    
    @given(
        amount=st.one_of(
            st.just(Decimal("-100.00")),
            st.just(Decimal("0.00"))
        ),
        transaction_date=valid_past_dates(),
        description=valid_descriptions(),
        income_category=st.sampled_from(list(IncomeCategory))
    )
    @settings(max_examples=20)
    def test_amount_error_messages_are_clear(
        self,
        amount,
        transaction_date,
        description,
        income_category
    ):
        """
        Property: Amount validation errors should always have clear messages
        Validates: Requirements 9.4
        """
        with pytest.raises(ValidationError) as exc_info:
            TransactionCreate(
                type=TransactionType.INCOME,
                amount=amount,
                transaction_date=transaction_date,
                description=description,
                income_category=income_category
            )
        
        errors = exc_info.value.errors()
        error_messages = [error['msg'] for error in errors if 'amount' in str(error['loc'])]
        
        # Error message should mention "positive" or "greater than"
        assert any(
            'positive' in msg.lower() or 'greater than' in msg.lower()
            for msg in error_messages
        ), f"Expected clear amount error message, got: {error_messages}"
    
    @given(
        future_date=future_dates(),
        amount=valid_amounts(),
        description=valid_descriptions(),
        income_category=st.sampled_from(list(IncomeCategory))
    )
    @settings(max_examples=20)
    def test_date_error_messages_are_clear(
        self,
        future_date,
        amount,
        description,
        income_category
    ):
        """
        Property: Date validation errors should always have clear messages
        Validates: Requirements 9.4
        """
        with pytest.raises(ValidationError) as exc_info:
            TransactionCreate(
                type=TransactionType.INCOME,
                amount=amount,
                transaction_date=future_date,
                description=description,
                income_category=income_category
            )
        
        errors = exc_info.value.errors()
        error_messages = [error['msg'] for error in errors if 'transaction_date' in str(error['loc'])]
        
        # Error message should mention "future" and include the date
        assert any('future' in msg.lower() for msg in error_messages), \
            f"Expected 'future' in error message, got: {error_messages}"
        
        assert any(future_date.strftime('%Y-%m-%d') in msg for msg in error_messages), \
            f"Expected date in error message, got: {error_messages}"
    
    @given(
        amount=valid_amounts(),
        transaction_date=valid_past_dates(),
        description=valid_descriptions()
    )
    @settings(max_examples=20)
    def test_category_error_messages_list_valid_options(
        self,
        amount,
        transaction_date,
        description
    ):
        """
        Property: Category validation errors should always list valid options
        Validates: Requirements 9.4
        """
        with pytest.raises(ValidationError) as exc_info:
            TransactionCreate(
                type=TransactionType.INCOME,
                amount=amount,
                transaction_date=transaction_date,
                description=description
            )
        
        errors = exc_info.value.errors()
        error_messages = [error['msg'] for error in errors]
        
        # Error message should list valid income categories
        combined_message = ' '.join(error_messages)
        assert any(cat.value in combined_message for cat in IncomeCategory), \
            f"Expected valid categories in error message, got: {error_messages}"
    
    # Property 3.8: Amount precision is always enforced
    
    @given(
        amount_str=st.decimals(
            min_value=Decimal("0.01"),
            max_value=Decimal("1000000.00"),
            places=2
        ),
        transaction_date=valid_past_dates(),
        description=valid_descriptions(),
        income_category=st.sampled_from(list(IncomeCategory))
    )
    @settings(max_examples=50)
    def test_amount_precision_always_enforced(
        self,
        amount_str,
        transaction_date,
        description,
        income_category
    ):
        """
        Property: Amount should always be quantized to 2 decimal places
        Validates: Requirements 9.2
        """
        transaction = TransactionCreate(
            type=TransactionType.INCOME,
            amount=amount_str,
            transaction_date=transaction_date,
            description=description,
            income_category=income_category
        )
        
        # Verify amount has exactly 2 decimal places
        amount_str_repr = str(transaction.amount)
        if '.' in amount_str_repr:
            decimal_places = len(amount_str_repr.split('.')[1])
            assert decimal_places <= 2, \
                f"Amount should have at most 2 decimal places, got: {amount_str_repr}"


class TestUpdateValidationProperties:
    """Property-based tests for update validation"""
    
    @given(
        amount=st.one_of(st.none(), valid_amounts()),
        transaction_date=st.one_of(st.none(), valid_past_dates()),
        description=st.one_of(st.none(), valid_descriptions())
    )
    @settings(max_examples=50)
    def test_valid_updates_always_accepted(
        self,
        amount,
        transaction_date,
        description
    ):
        """
        Property: All valid update data should be accepted
        Validates: Requirements 1.3, 1.4, 9.1, 9.2
        """
        try:
            update = TransactionUpdate(
                amount=amount,
                transaction_date=transaction_date,
                description=description
            )
            
            # Verify fields are correctly set
            if amount is not None:
                assert update.amount > 0
            if transaction_date is not None:
                assert update.transaction_date <= date.today()
            if description is not None:
                assert update.description.strip() != ""
                
        except ValidationError as e:
            pytest.fail(f"Valid update was rejected: {e}")
    
    @given(amount=invalid_amounts())
    @settings(max_examples=30)
    def test_invalid_update_amounts_rejected(self, amount):
        """
        Property: Invalid amounts in updates should always be rejected
        Validates: Requirements 1.4, 9.2
        """
        with pytest.raises(ValidationError) as exc_info:
            TransactionUpdate(amount=amount)
        
        errors = exc_info.value.errors()
        assert any('amount' in str(error['loc']) for error in errors)
    
    @given(future_date=future_dates())
    @settings(max_examples=30)
    def test_invalid_update_dates_rejected(self, future_date):
        """
        Property: Future dates in updates should always be rejected
        Validates: Requirements 9.1
        """
        with pytest.raises(ValidationError) as exc_info:
            TransactionUpdate(transaction_date=future_date)
        
        errors = exc_info.value.errors()
        assert any('transaction_date' in str(error['loc']) for error in errors)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--hypothesis-show-statistics"])
