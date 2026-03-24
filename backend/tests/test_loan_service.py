"""Unit tests for LoanService"""
import pytest
from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.services.loan_service import LoanService
from app.models.property_loan import PropertyLoan
from app.models.property import Property, PropertyStatus, PropertyType
from app.models.user import User, UserType
from app.models.transaction import Transaction, TransactionType, ExpenseCategory


@pytest.fixture
def test_user(db):
    """Create a test user"""
    user = User(
        email="landlord@test.com",
        name="Test Landlord",
        password_hash="hashed_password",
        user_type="LANDLORD"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def test_property(db, test_user):
    """Create a test property"""
    property = Property(
        user_id=test_user.id,
        property_type=PropertyType.RENTAL,
        rental_percentage=Decimal("100.00"),
        address="Teststraße 123, 1010 Wien",
        street="Teststraße 123",
        city="Wien",
        postal_code="1010",
        purchase_date=date(2020, 6, 15),
        purchase_price=Decimal("350000.00"),
        building_value=Decimal("280000.00"),
        construction_year=1985,
        depreciation_rate=Decimal("0.02"),
        status=PropertyStatus.ACTIVE
    )
    db.add(property)
    db.commit()
    db.refresh(property)
    return property


@pytest.fixture
def test_loan(db, test_user, test_property):
    """Create a test loan"""
    loan = PropertyLoan(
        user_id=test_user.id,
        property_id=test_property.id,
        loan_amount=Decimal("280000.00"),
        interest_rate=Decimal("0.0325"),  # 3.25%
        start_date=date(2024, 1, 1),
        monthly_payment=Decimal("1200.00"),
        lender_name="Erste Bank",
        loan_type="fixed_rate"
    )
    db.add(loan)
    db.commit()
    db.refresh(loan)
    return loan


@pytest.fixture
def loan_service(db):
    """Create LoanService instance"""
    return LoanService(db)


class TestLoanServiceCRUD:
    """Test CRUD operations"""
    
    def test_create_loan(self, loan_service, test_user, test_property):
        """Test creating a loan"""
        loan = loan_service.create_loan(
            user_id=test_user.id,
            property_id=test_property.id,
            loan_amount=Decimal("280000.00"),
            interest_rate=Decimal("0.0325"),  # 3.25%
            start_date=date(2020, 6, 15),
            monthly_payment=Decimal("1200.00"),
            lender_name="Test Bank",
            end_date=date(2050, 6, 15),
            loan_type="fixed_rate"
        )
        
        assert loan.id is not None
        assert loan.user_id == test_user.id
        assert loan.property_id == test_property.id
        assert loan.loan_amount == Decimal("280000.00")
        assert loan.interest_rate == Decimal("0.0325")
        assert loan.lender_name == "Test Bank"
        assert loan.loan_type == "fixed_rate"
    
    def test_create_loan_invalid_property(self, loan_service, test_user):
        """Test creating loan with invalid property ID"""
        with pytest.raises(ValueError, match="Property not found"):
            loan_service.create_loan(
                user_id=test_user.id,
                property_id=uuid4(),  # Non-existent property
                loan_amount=Decimal("280000.00"),
                interest_rate=Decimal("0.0325"),
                start_date=date(2020, 6, 15),
                monthly_payment=Decimal("1200.00"),
                lender_name="Test Bank"
            )
    
    def test_get_loan(self, loan_service, test_user, test_property):
        """Test retrieving a loan"""
        # Create loan
        created_loan = loan_service.create_loan(
            user_id=test_user.id,
            property_id=test_property.id,
            loan_amount=Decimal("280000.00"),
            interest_rate=Decimal("0.0325"),
            start_date=date(2020, 6, 15),
            monthly_payment=Decimal("1200.00"),
            lender_name="Test Bank"
        )
        
        # Retrieve loan
        loan = loan_service.get_loan(created_loan.id, test_user.id)
        
        assert loan is not None
        assert loan.id == created_loan.id
        assert loan.loan_amount == Decimal("280000.00")
    
    def test_get_loan_wrong_user(self, loan_service, test_user, test_property, db):
        """Test retrieving loan with wrong user ID"""
        # Create loan
        loan = loan_service.create_loan(
            user_id=test_user.id,
            property_id=test_property.id,
            loan_amount=Decimal("280000.00"),
            interest_rate=Decimal("0.0325"),
            start_date=date(2020, 6, 15),
            monthly_payment=Decimal("1200.00"),
            lender_name="Test Bank"
        )
        
        # Try to retrieve with different user ID
        retrieved_loan = loan_service.get_loan(loan.id, test_user.id + 999)
        
        assert retrieved_loan is None
    
    def test_list_loans(self, loan_service, test_user, test_property):
        """Test listing loans"""
        # Create multiple loans
        loan1 = loan_service.create_loan(
            user_id=test_user.id,
            property_id=test_property.id,
            loan_amount=Decimal("280000.00"),
            interest_rate=Decimal("0.0325"),
            start_date=date(2020, 6, 15),
            monthly_payment=Decimal("1200.00"),
            lender_name="Bank A"
        )
        
        loan2 = loan_service.create_loan(
            user_id=test_user.id,
            property_id=test_property.id,
            loan_amount=Decimal("50000.00"),
            interest_rate=Decimal("0.045"),
            start_date=date(2021, 1, 1),
            monthly_payment=Decimal("500.00"),
            lender_name="Bank B"
        )
        
        # List all loans
        loans = loan_service.list_loans(test_user.id)
        
        assert len(loans) == 2
        assert loans[0].id == loan2.id  # Most recent first
        assert loans[1].id == loan1.id
    
    def test_list_loans_by_property(self, loan_service, test_user, test_property, db):
        """Test listing loans filtered by property"""
        # Create second property
        property2 = Property(
            user_id=test_user.id,
            property_type=PropertyType.RENTAL,
            rental_percentage=Decimal("100.00"),
            address="Andere Straße 456, 1020 Wien",
            street="Andere Straße 456",
            city="Wien",
            postal_code="1020",
            purchase_date=date(2021, 1, 1),
            purchase_price=Decimal("250000.00"),
            building_value=Decimal("200000.00"),
            construction_year=1990,
            depreciation_rate=Decimal("0.02"),
            status=PropertyStatus.ACTIVE
        )
        db.add(property2)
        db.commit()
        
        # Create loans for both properties
        loan1 = loan_service.create_loan(
            user_id=test_user.id,
            property_id=test_property.id,
            loan_amount=Decimal("280000.00"),
            interest_rate=Decimal("0.0325"),
            start_date=date(2020, 6, 15),
            monthly_payment=Decimal("1200.00"),
            lender_name="Bank A"
        )
        
        loan2 = loan_service.create_loan(
            user_id=test_user.id,
            property_id=property2.id,
            loan_amount=Decimal("200000.00"),
            interest_rate=Decimal("0.035"),
            start_date=date(2021, 1, 1),
            monthly_payment=Decimal("900.00"),
            lender_name="Bank B"
        )
        
        # List loans for property 1
        loans = loan_service.list_loans(test_user.id, property_id=test_property.id)
        
        assert len(loans) == 1
        assert loans[0].id == loan1.id
    
    def test_update_loan(self, loan_service, test_user, test_property):
        """Test updating a loan"""
        # Create loan
        loan = loan_service.create_loan(
            user_id=test_user.id,
            property_id=test_property.id,
            loan_amount=Decimal("280000.00"),
            interest_rate=Decimal("0.0325"),
            start_date=date(2020, 6, 15),
            monthly_payment=Decimal("1200.00"),
            lender_name="Test Bank"
        )
        
        # Update loan
        updated_loan = loan_service.update_loan(
            loan_id=loan.id,
            user_id=test_user.id,
            interest_rate=Decimal("0.0275"),  # Rate changed
            monthly_payment=Decimal("1150.00"),
            notes="Refinanced at lower rate"
        )
        
        assert updated_loan.interest_rate == Decimal("0.0275")
        assert updated_loan.monthly_payment == Decimal("1150.00")
        assert updated_loan.notes == "Refinanced at lower rate"
        assert updated_loan.loan_amount == Decimal("280000.00")  # Unchanged
    
    def test_update_loan_wrong_user(self, loan_service, test_user, test_property):
        """Test updating loan with wrong user ID"""
        # Create loan
        loan = loan_service.create_loan(
            user_id=test_user.id,
            property_id=test_property.id,
            loan_amount=Decimal("280000.00"),
            interest_rate=Decimal("0.0325"),
            start_date=date(2020, 6, 15),
            monthly_payment=Decimal("1200.00"),
            lender_name="Test Bank"
        )
        
        # Try to update with wrong user ID
        with pytest.raises(ValueError, match="Loan not found"):
            loan_service.update_loan(
                loan_id=loan.id,
                user_id=test_user.id + 999,
                interest_rate=Decimal("0.0275")
            )
    
    def test_delete_loan(self, loan_service, test_user, test_property):
        """Test deleting a loan"""
        # Create loan
        loan = loan_service.create_loan(
            user_id=test_user.id,
            property_id=test_property.id,
            loan_amount=Decimal("280000.00"),
            interest_rate=Decimal("0.0325"),
            start_date=date(2020, 6, 15),
            monthly_payment=Decimal("1200.00"),
            lender_name="Test Bank"
        )
        
        # Delete loan
        result = loan_service.delete_loan(loan.id, test_user.id)
        
        assert result is True
        
        # Verify deletion
        deleted_loan = loan_service.get_loan(loan.id, test_user.id)
        assert deleted_loan is None
    
    def test_delete_loan_wrong_user(self, loan_service, test_user, test_property):
        """Test deleting loan with wrong user ID"""
        # Create loan
        loan = loan_service.create_loan(
            user_id=test_user.id,
            property_id=test_property.id,
            loan_amount=Decimal("280000.00"),
            interest_rate=Decimal("0.0325"),
            start_date=date(2020, 6, 15),
            monthly_payment=Decimal("1200.00"),
            lender_name="Test Bank"
        )
        
        # Try to delete with wrong user ID
        result = loan_service.delete_loan(loan.id, test_user.id + 999)
        
        assert result is False


class TestAmortizationCalculations:
    """Test amortization schedule and interest calculations"""
    
    def test_generate_amortization_schedule(self, loan_service, test_user, test_property):
        """Test generating amortization schedule"""
        # Create loan
        loan = loan_service.create_loan(
            user_id=test_user.id,
            property_id=test_property.id,
            loan_amount=Decimal("100000.00"),
            interest_rate=Decimal("0.06"),  # 6% annual
            start_date=date(2024, 1, 1),
            monthly_payment=Decimal("1000.00"),
            lender_name="Test Bank"
        )
        
        # Generate schedule
        schedule = loan_service.generate_amortization_schedule(loan.id, test_user.id)
        
        assert len(schedule) > 0
        
        # Check first payment
        first_payment = schedule[0]
        assert first_payment.payment_number == 1
        assert first_payment.payment_date == date(2024, 1, 1)
        assert first_payment.payment_amount == Decimal("1000.00")
        assert first_payment.interest_amount > 0
        assert first_payment.principal_amount > 0
        assert first_payment.interest_amount + first_payment.principal_amount == Decimal("1000.00")
        
        # Check that balance decreases
        assert schedule[0].remaining_balance < Decimal("100000.00")
        assert schedule[-1].remaining_balance <= Decimal("0.01")  # Nearly paid off
    
    def test_calculate_annual_interest(self, loan_service, test_user, test_property):
        """Test calculating annual interest"""
        # Create loan
        loan = loan_service.create_loan(
            user_id=test_user.id,
            property_id=test_property.id,
            loan_amount=Decimal("100000.00"),
            interest_rate=Decimal("0.06"),  # 6% annual
            start_date=date(2024, 1, 1),
            monthly_payment=Decimal("1000.00"),
            lender_name="Test Bank"
        )
        
        # Calculate interest for 2024
        interest_2024 = loan_service.calculate_annual_interest(loan.id, test_user.id, 2024)
        
        assert interest_2024 > 0
        # First year interest should be close to 6% of average balance
        # With declining balance, should be less than 6000
        assert interest_2024 < Decimal("6000.00")
    
    def test_calculate_remaining_balance(self, loan_service, test_user, test_property):
        """Test calculating remaining balance"""
        # Create loan
        loan = loan_service.create_loan(
            user_id=test_user.id,
            property_id=test_property.id,
            loan_amount=Decimal("100000.00"),
            interest_rate=Decimal("0.06"),
            start_date=date(2024, 1, 1),
            monthly_payment=Decimal("1000.00"),
            lender_name="Test Bank"
        )
        
        # Calculate balance after 1 year
        balance_after_1_year = loan_service.calculate_remaining_balance(
            loan.id,
            test_user.id,
            date(2025, 1, 1)
        )
        
        assert balance_after_1_year < Decimal("100000.00")
        assert balance_after_1_year > Decimal("80000.00")  # Should have paid down some principal
    
    def test_get_loan_summary(self, loan_service, test_user, test_property):
        """Test getting comprehensive loan summary"""
        # Create loan
        loan = loan_service.create_loan(
            user_id=test_user.id,
            property_id=test_property.id,
            loan_amount=Decimal("100000.00"),
            interest_rate=Decimal("0.06"),
            start_date=date(2024, 1, 1),
            monthly_payment=Decimal("1000.00"),
            lender_name="Test Bank",
            loan_type="fixed_rate"
        )
        
        # Get summary
        summary = loan_service.get_loan_summary(loan.id, test_user.id)
        
        assert summary["loan_id"] == loan.id
        assert summary["loan_amount"] == 100000.00
        assert summary["interest_rate"] == 0.06
        assert summary["monthly_payment"] == 1000.00
        assert summary["lender_name"] == "Test Bank"
        assert summary["loan_type"] == "fixed_rate"
        assert summary["current_balance"] > 0
        assert summary["total_interest"] > 0
        assert summary["total_principal"] > 0
        assert summary["number_of_payments"] > 0
        assert summary["payments_remaining"] > 0


# ============================================================================
# LOAN INTEREST TRANSACTION TESTS
# ============================================================================

def test_create_interest_payment_transaction(db, test_user, test_property, test_loan):
    """Test creating a single interest payment transaction"""
    service = LoanService(db)
    
    payment_date = date(2024, 2, 1)
    interest_amount = Decimal("906.67")
    
    transaction = service.create_interest_payment_transaction(
        loan_id=test_loan.id,
        user_id=test_user.id,
        payment_date=payment_date,
        interest_amount=interest_amount,
        description="Custom interest payment"
    )
    
    assert transaction.id is not None
    assert transaction.user_id == test_user.id
    assert transaction.property_id == test_property.id
    assert transaction.type == TransactionType.EXPENSE
    assert transaction.amount == interest_amount
    assert transaction.transaction_date == payment_date
    assert transaction.expense_category == ExpenseCategory.LOAN_INTEREST
    assert transaction.is_deductible is True
    assert transaction.import_source == "loan_service"
    assert transaction.description == "Custom interest payment"


def test_create_interest_payment_transaction_auto_description(db, test_user, test_property, test_loan):
    """Test auto-generated description for interest payment"""
    service = LoanService(db)
    
    payment_date = date(2024, 2, 1)
    interest_amount = Decimal("906.67")
    
    transaction = service.create_interest_payment_transaction(
        loan_id=test_loan.id,
        user_id=test_user.id,
        payment_date=payment_date,
        interest_amount=interest_amount
    )
    
    assert "Erste Bank" in transaction.description
    assert "February 2024" in transaction.description


def test_create_interest_payment_invalid_amount(db, test_user, test_loan):
    """Test creating interest payment with invalid amount"""
    service = LoanService(db)
    
    with pytest.raises(ValueError, match="Interest amount must be greater than zero"):
        service.create_interest_payment_transaction(
            loan_id=test_loan.id,
            user_id=test_user.id,
            payment_date=date(2024, 2, 1),
            interest_amount=Decimal("0")
        )


def test_create_monthly_interest_transactions_full_year(db, test_user, test_property, test_loan):
    """Test creating interest transactions for entire year"""
    service = LoanService(db)
    
    # Create transactions for 2024
    transactions = service.create_monthly_interest_transactions(
        loan_id=test_loan.id,
        user_id=test_user.id,
        year=2024
    )
    
    # Should have 12 monthly transactions
    assert len(transactions) == 12
    
    # Verify all transactions
    for i, transaction in enumerate(transactions):
        assert transaction.user_id == test_user.id
        assert transaction.property_id == test_property.id
        assert transaction.type == TransactionType.EXPENSE
        assert transaction.expense_category == ExpenseCategory.LOAN_INTEREST
        assert transaction.is_deductible is True
        assert transaction.is_system_generated is True
        assert transaction.transaction_date.year == 2024
        assert transaction.transaction_date.month == i + 1
        assert transaction.amount > 0
    
    # Verify total interest matches annual calculation
    total_interest = sum(t.amount for t in transactions)
    expected_interest = service.calculate_annual_interest(test_loan.id, test_user.id, 2024)
    assert abs(total_interest - expected_interest) < Decimal("0.01")


def test_create_monthly_interest_transactions_uses_installment_overrides(db, test_user, test_property, test_loan):
    service = LoanService(db)

    service.generate_installment_plan(test_loan.id, test_user.id)
    service.apply_annual_interest_certificate(
        test_loan.id,
        test_user.id,
        2024,
        Decimal("7146.54"),
    )

    transactions = service.create_monthly_interest_transactions(
        loan_id=test_loan.id,
        user_id=test_user.id,
        year=2024,
    )

    assert len(transactions) == 12
    total_interest = sum(t.amount for t in transactions)
    assert total_interest == Decimal("7146.54")


def test_create_monthly_interest_transactions_single_month(db, test_user, test_property, test_loan):
    """Test creating interest transactions for single month"""
    service = LoanService(db)
    
    # Create transactions for February 2024
    transactions = service.create_monthly_interest_transactions(
        loan_id=test_loan.id,
        user_id=test_user.id,
        year=2024,
        month=2
    )
    
    # Should have 1 transaction
    assert len(transactions) == 1
    
    transaction = transactions[0]
    assert transaction.transaction_date == date(2024, 2, 1)
    assert transaction.expense_category == ExpenseCategory.LOAN_INTEREST
    assert "Payment #2" in transaction.description


def test_create_monthly_interest_transactions_duplicate_prevention(db, test_user, test_loan):
    """Test that duplicate transactions are prevented"""
    service = LoanService(db)
    
    # Create transactions for 2024
    service.create_monthly_interest_transactions(
        loan_id=test_loan.id,
        user_id=test_user.id,
        year=2024
    )
    
    # Try to create again - should fail
    with pytest.raises(ValueError, match="Interest payment transactions already exist"):
        service.create_monthly_interest_transactions(
            loan_id=test_loan.id,
            user_id=test_user.id,
            year=2024
        )


def test_create_monthly_interest_transactions_no_payments(db, test_user, test_property):
    """Test creating transactions when no payments exist for period"""
    service = LoanService(db)
    
    # Create loan starting in 2025
    loan = service.create_loan(
        user_id=test_user.id,
        property_id=test_property.id,
        loan_amount=Decimal("100000.00"),
        interest_rate=Decimal("0.03"),
        start_date=date(2025, 1, 1),
        monthly_payment=Decimal("500.00"),
        lender_name="Test Bank"
    )
    
    # Try to create transactions for 2024 (before loan starts)
    with pytest.raises(ValueError, match="No loan payments found"):
        service.create_monthly_interest_transactions(
            loan_id=loan.id,
            user_id=test_user.id,
            year=2024
        )


def test_get_interest_transactions(db, test_user, test_loan):
    """Test retrieving interest transactions"""
    service = LoanService(db)
    
    # Create transactions for 2024
    created = service.create_monthly_interest_transactions(
        loan_id=test_loan.id,
        user_id=test_user.id,
        year=2024
    )
    
    # Retrieve all transactions
    transactions = service.get_interest_transactions(
        loan_id=test_loan.id,
        user_id=test_user.id
    )
    
    assert len(transactions) == 12
    assert transactions[0].transaction_date == date(2024, 1, 1)
    assert transactions[-1].transaction_date == date(2024, 12, 1)


def test_get_interest_transactions_filtered_by_year(db, test_user, test_loan):
    """Test retrieving interest transactions filtered by year"""
    service = LoanService(db)
    
    # Create transactions for 2024
    service.create_monthly_interest_transactions(
        loan_id=test_loan.id,
        user_id=test_user.id,
        year=2024
    )
    
    # Retrieve only 2024 transactions
    transactions = service.get_interest_transactions(
        loan_id=test_loan.id,
        user_id=test_user.id,
        year=2024
    )
    
    assert len(transactions) == 12
    assert all(t.transaction_date.year == 2024 for t in transactions)


def test_link_existing_transaction_to_loan(db, test_user, test_property, test_loan):
    """Test linking an existing transaction to a loan"""
    service = LoanService(db)
    
    # Create a manual transaction
    manual_transaction = Transaction(
        user_id=test_user.id,
        type=TransactionType.EXPENSE,
        amount=Decimal("900.00"),
        transaction_date=date(2024, 1, 15),
        description="Manual loan interest payment",
        expense_category=ExpenseCategory.OTHER
    )
    db.add(manual_transaction)
    db.commit()
    db.refresh(manual_transaction)
    
    # Link it to the loan
    updated = service.link_existing_transaction_to_loan(
        transaction_id=manual_transaction.id,
        loan_id=test_loan.id,
        user_id=test_user.id
    )
    
    assert updated.property_id == test_property.id
    assert updated.expense_category == ExpenseCategory.LOAN_INTEREST
    assert updated.is_deductible is True


def test_link_existing_transaction_ownership_validation(db, test_user, test_property, test_loan):
    """Test that linking validates ownership"""
    service = LoanService(db)
    
    # Create another user
    other_user = User(
        email="other@example.com",
        password_hash="hashed",
        name="Other User",
        user_type=UserType.LANDLORD
    )
    db.add(other_user)
    db.commit()
    
    # Create a transaction for other user
    other_transaction = Transaction(
        user_id=other_user.id,
        type=TransactionType.EXPENSE,
        amount=Decimal("900.00"),
        transaction_date=date(2024, 1, 15),
        description="Other user's transaction"
    )
    db.add(other_transaction)
    db.commit()
    
    # Try to link other user's transaction to test_user's loan
    with pytest.raises(ValueError, match="Transaction not found or does not belong to user"):
        service.link_existing_transaction_to_loan(
            transaction_id=other_transaction.id,
            loan_id=test_loan.id,
            user_id=test_user.id
        )


def test_interest_transactions_integration(db, test_user, test_property, test_loan):
    """Integration test: Create loan, generate transactions, verify totals"""
    service = LoanService(db)
    
    # Create interest transactions for 2024
    transactions = service.create_monthly_interest_transactions(
        loan_id=test_loan.id,
        user_id=test_user.id,
        year=2024
    )
    
    # Verify transaction count
    assert len(transactions) == 12
    
    # Calculate total from transactions
    total_from_transactions = sum(t.amount for t in transactions)
    
    # Calculate expected total from amortization schedule
    expected_total = service.calculate_annual_interest(test_loan.id, test_user.id, 2024)
    
    # Should match within rounding tolerance
    assert abs(total_from_transactions - expected_total) < Decimal("0.01")
    
    # Verify all transactions are linked to property
    assert all(t.property_id == test_property.id for t in transactions)
    
    # Verify all transactions are marked as deductible
    assert all(t.is_deductible for t in transactions)
    
    # Verify interest decreases over time (amortization)
    interest_amounts = [t.amount for t in transactions]
    assert interest_amounts[0] > interest_amounts[-1]  # First payment has more interest
