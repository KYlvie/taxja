"""
Unit tests for transaction input validation

Tests Requirements:
- 1.3: Validate required fields completeness
- 1.4: Validate amount format and positivity
- 9.1: Validate dates in valid tax year range
- 9.2: Validate amounts are positive and properly formatted
- 9.4: Display detailed error messages for validation failures
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal
from pydantic import ValidationError
from app.schemas.transaction import TransactionCreate, TransactionUpdate
from app.models.transaction import TransactionType, IncomeCategory, ExpenseCategory


class TestTransactionCreateValidation:
    """Test validation for transaction creation"""
    
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
        assert transaction.expense_category is None
    
    def test_valid_expense_transaction(self):
        """Test creating a valid expense transaction"""
        transaction = TransactionCreate(
            type=TransactionType.EXPENSE,
            amount=Decimal("50.99"),
            transaction_date=date.today(),
            description="Office supplies",
            expense_category=ExpenseCategory.OFFICE_SUPPLIES
        )
        
        assert transaction.type == TransactionType.EXPENSE
        assert transaction.amount == Decimal("50.99")
        assert transaction.expense_category == ExpenseCategory.OFFICE_SUPPLIES
        assert transaction.income_category is None
    
    # Test required field validation
    
    def test_missing_type_field(self):
        """Test that type field is required"""
        with pytest.raises(ValidationError) as exc_info:
            TransactionCreate(
                amount=Decimal("100.00"),
                transaction_date=date.today(),
                description="Test transaction",
                income_category=IncomeCategory.EMPLOYMENT
            )
        
        errors = exc_info.value.errors()
        assert any(error['loc'] == ('type',) and error['type'] == 'missing' for error in errors)
    
    def test_missing_amount_field(self):
        """Test that amount field is required"""
        with pytest.raises(ValidationError) as exc_info:
            TransactionCreate(
                type=TransactionType.INCOME,
                transaction_date=date.today(),
                description="Test transaction",
                income_category=IncomeCategory.EMPLOYMENT
            )
        
        errors = exc_info.value.errors()
        assert any(error['loc'] == ('amount',) and error['type'] == 'missing' for error in errors)
    
    def test_missing_transaction_date_field(self):
        """Test that transaction_date field is required"""
        with pytest.raises(ValidationError) as exc_info:
            TransactionCreate(
                type=TransactionType.INCOME,
                amount=Decimal("100.00"),
                description="Test transaction",
                income_category=IncomeCategory.EMPLOYMENT
            )
        
        errors = exc_info.value.errors()
        assert any(error['loc'] == ('transaction_date',) and error['type'] == 'missing' for error in errors)
    
    def test_missing_description_field(self):
        """Test that description field is required for creation"""
        with pytest.raises(ValidationError) as exc_info:
            TransactionCreate(
                type=TransactionType.INCOME,
                amount=Decimal("100.00"),
                transaction_date=date.today(),
                income_category=IncomeCategory.EMPLOYMENT
            )
        
        errors = exc_info.value.errors()
        assert any(error['loc'] == ('description',) and error['type'] == 'missing' for error in errors)
    
    # Test amount validation
    
    def test_negative_amount(self):
        """Test that negative amounts are rejected"""
        with pytest.raises(ValidationError) as exc_info:
            TransactionCreate(
                type=TransactionType.INCOME,
                amount=Decimal("-100.00"),
                transaction_date=date.today(),
                description="Test transaction",
                income_category=IncomeCategory.EMPLOYMENT
            )
        
        errors = exc_info.value.errors()
        assert any('amount' in str(error['loc']) for error in errors)
        # Check that error message mentions positive
        assert any('positive' in error['msg'].lower() for error in errors)
    
    def test_zero_amount(self):
        """Test that zero amounts are rejected"""
        with pytest.raises(ValidationError) as exc_info:
            TransactionCreate(
                type=TransactionType.INCOME,
                amount=Decimal("0.00"),
                transaction_date=date.today(),
                description="Test transaction",
                income_category=IncomeCategory.EMPLOYMENT
            )
        
        errors = exc_info.value.errors()
        assert any('amount' in str(error['loc']) for error in errors)
    
    def test_amount_precision(self):
        """Test that amount is quantized to 2 decimal places"""
        transaction = TransactionCreate(
            type=TransactionType.INCOME,
            amount=Decimal("100.999"),
            transaction_date=date.today(),
            description="Test transaction",
            income_category=IncomeCategory.EMPLOYMENT
        )
        
        # Should be rounded to 2 decimal places
        assert transaction.amount == Decimal("101.00")
    
    def test_amount_with_valid_precision(self):
        """Test that amount with 2 decimal places is accepted"""
        transaction = TransactionCreate(
            type=TransactionType.INCOME,
            amount=Decimal("100.50"),
            transaction_date=date.today(),
            description="Test transaction",
            income_category=IncomeCategory.EMPLOYMENT
        )
        
        assert transaction.amount == Decimal("100.50")
    
    # Test date validation
    
    def test_future_date_rejected(self):
        """Test that future dates are rejected"""
        future_date = date.today() + timedelta(days=1)
        
        with pytest.raises(ValidationError) as exc_info:
            TransactionCreate(
                type=TransactionType.INCOME,
                amount=Decimal("100.00"),
                transaction_date=future_date,
                description="Test transaction",
                income_category=IncomeCategory.EMPLOYMENT
            )
        
        errors = exc_info.value.errors()
        assert any('transaction_date' in str(error['loc']) for error in errors)
        # Check that error message mentions future
        assert any('future' in error['msg'].lower() for error in errors)
    
    def test_today_date_accepted(self):
        """Test that today's date is accepted"""
        transaction = TransactionCreate(
            type=TransactionType.INCOME,
            amount=Decimal("100.00"),
            transaction_date=date.today(),
            description="Test transaction",
            income_category=IncomeCategory.EMPLOYMENT
        )
        
        assert transaction.transaction_date == date.today()
    
    def test_past_date_accepted(self):
        """Test that past dates are accepted"""
        past_date = date.today() - timedelta(days=30)
        
        transaction = TransactionCreate(
            type=TransactionType.INCOME,
            amount=Decimal("100.00"),
            transaction_date=past_date,
            description="Test transaction",
            income_category=IncomeCategory.EMPLOYMENT
        )
        
        assert transaction.transaction_date == past_date
    
    # Test description validation
    
    def test_empty_description_rejected(self):
        """Test that empty description is rejected"""
        with pytest.raises(ValidationError) as exc_info:
            TransactionCreate(
                type=TransactionType.INCOME,
                amount=Decimal("100.00"),
                transaction_date=date.today(),
                description="",
                income_category=IncomeCategory.EMPLOYMENT
            )
        
        errors = exc_info.value.errors()
        assert any('description' in str(error['loc']) for error in errors)
    
    def test_whitespace_only_description_rejected(self):
        """Test that whitespace-only description is rejected"""
        with pytest.raises(ValidationError) as exc_info:
            TransactionCreate(
                type=TransactionType.INCOME,
                amount=Decimal("100.00"),
                transaction_date=date.today(),
                description="   ",
                income_category=IncomeCategory.EMPLOYMENT
            )
        
        errors = exc_info.value.errors()
        assert any('description' in str(error['loc']) for error in errors)
    
    def test_description_max_length(self):
        """Test that description respects max length"""
        long_description = "x" * 501
        
        with pytest.raises(ValidationError) as exc_info:
            TransactionCreate(
                type=TransactionType.INCOME,
                amount=Decimal("100.00"),
                transaction_date=date.today(),
                description=long_description,
                income_category=IncomeCategory.EMPLOYMENT
            )
        
        errors = exc_info.value.errors()
        assert any('description' in str(error['loc']) for error in errors)
    
    # Test category validation
    
    def test_income_transaction_requires_income_category(self):
        """Test that income transactions require income_category"""
        with pytest.raises(ValidationError) as exc_info:
            TransactionCreate(
                type=TransactionType.INCOME,
                amount=Decimal("100.00"),
                transaction_date=date.today(),
                description="Test transaction"
            )
        
        errors = exc_info.value.errors()
        error_messages = [error['msg'] for error in errors]
        assert any('income_category is required' in msg for msg in error_messages)
    
    def test_expense_transaction_requires_expense_category(self):
        """Test that expense transactions require expense_category"""
        with pytest.raises(ValidationError) as exc_info:
            TransactionCreate(
                type=TransactionType.EXPENSE,
                amount=Decimal("100.00"),
                transaction_date=date.today(),
                description="Test transaction"
            )
        
        errors = exc_info.value.errors()
        error_messages = [error['msg'] for error in errors]
        assert any('expense_category is required' in msg for msg in error_messages)
    
    def test_income_transaction_rejects_expense_category(self):
        """Test that income transactions reject expense_category"""
        with pytest.raises(ValidationError) as exc_info:
            TransactionCreate(
                type=TransactionType.INCOME,
                amount=Decimal("100.00"),
                transaction_date=date.today(),
                description="Test transaction",
                income_category=IncomeCategory.EMPLOYMENT,
                expense_category=ExpenseCategory.OFFICE_SUPPLIES
            )
        
        errors = exc_info.value.errors()
        error_messages = [error['msg'] for error in errors]
        assert any('expense_category should not be set' in msg for msg in error_messages)
    
    def test_expense_transaction_rejects_income_category(self):
        """Test that expense transactions reject income_category"""
        with pytest.raises(ValidationError) as exc_info:
            TransactionCreate(
                type=TransactionType.EXPENSE,
                amount=Decimal("100.00"),
                transaction_date=date.today(),
                description="Test transaction",
                expense_category=ExpenseCategory.OFFICE_SUPPLIES,
                income_category=IncomeCategory.EMPLOYMENT
            )
        
        errors = exc_info.value.errors()
        error_messages = [error['msg'] for error in errors]
        assert any('income_category should not be set' in msg for msg in error_messages)
    
    def test_invalid_income_category_value(self):
        """Test that invalid income category values are rejected"""
        with pytest.raises(ValidationError):
            TransactionCreate(
                type=TransactionType.INCOME,
                amount=Decimal("100.00"),
                transaction_date=date.today(),
                description="Test transaction",
                income_category="invalid_category"
            )
    
    def test_invalid_expense_category_value(self):
        """Test that invalid expense category values are rejected"""
        with pytest.raises(ValidationError):
            TransactionCreate(
                type=TransactionType.EXPENSE,
                amount=Decimal("100.00"),
                transaction_date=date.today(),
                description="Test transaction",
                expense_category="invalid_category"
            )
    
    def test_valid_income_categories(self):
        """Test all valid income categories"""
        for category in IncomeCategory:
            transaction = TransactionCreate(
                type=TransactionType.INCOME,
                amount=Decimal("100.00"),
                transaction_date=date.today(),
                description="Test transaction",
                income_category=category
            )
            assert transaction.income_category == category
    
    def test_valid_expense_categories(self):
        """Test all valid expense categories"""
        for category in ExpenseCategory:
            transaction = TransactionCreate(
                type=TransactionType.EXPENSE,
                amount=Decimal("100.00"),
                transaction_date=date.today(),
                description="Test transaction",
                expense_category=category
            )
            assert transaction.expense_category == category


class TestTransactionUpdateValidation:
    """Test validation for transaction updates"""
    
    def test_all_fields_optional(self):
        """Test that all fields are optional for updates"""
        # Should not raise any errors
        update = TransactionUpdate()
        assert update.type is None
        assert update.amount is None
        assert update.transaction_date is None
    
    def test_update_amount_validation(self):
        """Test that amount validation applies to updates"""
        with pytest.raises(ValidationError) as exc_info:
            TransactionUpdate(amount=Decimal("-100.00"))
        
        errors = exc_info.value.errors()
        assert any('amount' in str(error['loc']) for error in errors)
    
    def test_update_date_validation(self):
        """Test that date validation applies to updates"""
        future_date = date.today() + timedelta(days=1)
        
        with pytest.raises(ValidationError) as exc_info:
            TransactionUpdate(transaction_date=future_date)
        
        errors = exc_info.value.errors()
        assert any('transaction_date' in str(error['loc']) for error in errors)
    
    def test_update_description_validation(self):
        """Test that description validation applies to updates"""
        with pytest.raises(ValidationError) as exc_info:
            TransactionUpdate(description="")
        
        errors = exc_info.value.errors()
        assert any('description' in str(error['loc']) for error in errors)
    
    def test_update_partial_fields(self):
        """Test updating only some fields"""
        update = TransactionUpdate(
            amount=Decimal("200.00"),
            description="Updated description"
        )
        
        assert update.amount == Decimal("200.00")
        assert update.description == "Updated description"
        assert update.type is None
        assert update.transaction_date is None


class TestErrorMessages:
    """Test that error messages are clear and helpful"""
    
    def test_negative_amount_error_message(self):
        """Test that negative amount error message is clear"""
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
        assert 'positive' in error_msg.lower()
        assert '€' in error_msg or 'amount' in error_msg.lower()
    
    def test_future_date_error_message(self):
        """Test that future date error message is clear"""
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
    
    def test_missing_category_error_message(self):
        """Test that missing category error message lists valid options"""
        with pytest.raises(ValidationError) as exc_info:
            TransactionCreate(
                type=TransactionType.INCOME,
                amount=Decimal("100.00"),
                transaction_date=date.today(),
                description="Test"
            )
        
        errors = exc_info.value.errors()
        error_msg = next(e['msg'] for e in errors)
        assert 'income_category' in error_msg.lower()
        # Should mention valid categories
        assert any(cat.value in error_msg for cat in IncomeCategory)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
