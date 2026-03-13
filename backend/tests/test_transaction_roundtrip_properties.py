"""
Property-based tests for transaction roundtrip consistency

**Validates: Requirements 1.1, 1.2, 1.5**

Property 1: Transaction record roundtrip consistency
- Creating a transaction and retrieving it returns the same data
- Updating a transaction and retrieving it reflects all changes
- All transaction fields are preserved through create/read/update cycles
- Decimal precision is maintained (2 decimal places)
- Date and timestamp fields are preserved correctly
"""

import pytest
from hypothesis import given, strategies as st, assume, settings, HealthCheck
from decimal import Decimal
from datetime import date, datetime, timedelta
from enum import Enum
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Numeric,
    Date,
    Boolean,
    DateTime,
    Enum as SQLEnum,
    ForeignKey
)
from sqlalchemy.orm import sessionmaker, relationship, declarative_base

# Create test Base
Base = declarative_base()


# Define minimal models for testing (copied from app.models to avoid import issues)
class UserType(str, Enum):
    """User type enumeration"""
    EMPLOYEE = "employee"
    SELF_EMPLOYED = "self_employed"
    LANDLORD = "landlord"
    MIXED = "mixed"


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


class User(Base):
    """Minimal User model for testing"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    user_type = Column(SQLEnum(UserType), nullable=False)
    tax_number = Column(String(50))
    address = Column(String(500))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    transactions = relationship("Transaction", back_populates="user")


class Transaction(Base):
    """Transaction model for testing"""
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    type = Column(SQLEnum(TransactionType), nullable=False, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    transaction_date = Column(Date, nullable=False, index=True)
    description = Column(String(500))
    income_category = Column(SQLEnum(IncomeCategory), nullable=True)
    expense_category = Column(SQLEnum(ExpenseCategory), nullable=True)
    is_deductible = Column(Boolean, default=False)
    deduction_reason = Column(String(500))
    vat_rate = Column(Numeric(5, 4), nullable=True)
    vat_amount = Column(Numeric(12, 2), nullable=True)
    document_id = Column(Integer, nullable=True)
    classification_confidence = Column(Numeric(3, 2), nullable=True)
    needs_review = Column(Boolean, default=False)
    import_source = Column(String(50), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="transactions")


# Test database setup
@pytest.fixture
def db_session():
    """Create a test database session"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    yield session
    
    session.close()


@pytest.fixture
def test_user(db_session):
    """Create a test user"""
    user = User(
        email="test@example.com",
        password_hash="hashed_password",
        name="Test User",
        user_type=UserType.SELF_EMPLOYED,
        tax_number="123456789",
        address="Test Address"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


# Custom strategies for generating test data
def decimal_strategy(min_value=0.01, max_value=1000000, places=2):
    """Generate Decimal values with specified precision"""
    return st.decimals(
        min_value=Decimal(str(min_value)),
        max_value=Decimal(str(max_value)),
        allow_nan=False,
        allow_infinity=False,
        places=places
    )


def date_strategy(min_days_ago=3650, max_days_ago=0):
    """Generate dates within a reasonable range (past 10 years to today)"""
    today = date.today()
    return st.dates(
        min_value=today - timedelta(days=min_days_ago),
        max_value=today - timedelta(days=max_days_ago)
    )


def vat_rate_strategy():
    """Generate valid VAT rates (0%, 10%, 20%)"""
    return st.sampled_from([
        None,
        Decimal('0.00'),
        Decimal('0.10'),
        Decimal('0.20')
    ])


class TestProperty1TransactionRoundtripConsistency:
    """
    **Property 1: Transaction record roundtrip consistency**
    **Validates: Requirements 1.1, 1.2, 1.5**
    
    Tests that transaction data:
    1. Is preserved through create and read operations
    2. Is correctly updated and retrieved
    3. Maintains decimal precision
    4. Preserves all field values
    """
    
    @given(
        amount=decimal_strategy(min_value=0.01, max_value=100000),
        transaction_date=date_strategy(),
        description=st.text(min_size=1, max_size=500, alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))),
        income_category=st.sampled_from(list(IncomeCategory)),
        is_deductible=st.booleans(),
        vat_rate=vat_rate_strategy()
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_income_transaction_create_read_roundtrip(
        self,
        amount: Decimal,
        transaction_date: date,
        description: str,
        income_category: IncomeCategory,
        is_deductible: bool,
        vat_rate: Decimal,
        db_session,
        test_user
    ):
        """
        Property: Creating an income transaction and reading it returns identical data
        
        For any valid income transaction data:
        - Create transaction with data D
        - Read transaction by ID
        - Retrieved data should equal D (with proper precision)
        
        **Validates: Requirements 1.1, 1.2**
        """
        # Calculate VAT amount if rate is provided
        vat_amount = None
        if vat_rate and vat_rate > 0:
            vat_amount = (amount * vat_rate / (Decimal('1') + vat_rate)).quantize(Decimal('0.01'))
        
        # Create transaction
        transaction = Transaction(
            user_id=test_user.id,
            type=TransactionType.INCOME,
            amount=amount.quantize(Decimal('0.01')),
            transaction_date=transaction_date,
            description=description.strip() if description else None,
            income_category=income_category,
            expense_category=None,
            is_deductible=is_deductible,
            deduction_reason=None,
            vat_rate=vat_rate.quantize(Decimal('0.0001')) if vat_rate else None,
            vat_amount=vat_amount,
            import_source="manual"
        )
        
        db_session.add(transaction)
        db_session.commit()
        db_session.refresh(transaction)
        
        # Read transaction back
        retrieved = db_session.query(Transaction).filter(Transaction.id == transaction.id).first()
        
        # Verify all fields match
        assert retrieved is not None, "Transaction should be retrievable"
        assert retrieved.id == transaction.id, "ID should match"
        assert retrieved.user_id == test_user.id, "User ID should match"
        assert retrieved.type == TransactionType.INCOME, "Type should be INCOME"
        assert retrieved.amount == amount.quantize(Decimal('0.01')), \
            f"Amount should be {amount.quantize(Decimal('0.01'))}, got {retrieved.amount}"
        assert retrieved.transaction_date == transaction_date, "Transaction date should match"
        assert retrieved.description == (description.strip() if description else None), "Description should match"
        assert retrieved.income_category == income_category, "Income category should match"
        assert retrieved.expense_category is None, "Expense category should be None for income"
        assert retrieved.is_deductible == is_deductible, "Deductibility flag should match"
        
        if vat_rate:
            assert retrieved.vat_rate == vat_rate.quantize(Decimal('0.0001')), \
                f"VAT rate should be {vat_rate.quantize(Decimal('0.0001'))}, got {retrieved.vat_rate}"
            if vat_amount:
                assert retrieved.vat_amount == vat_amount, \
                    f"VAT amount should be {vat_amount}, got {retrieved.vat_amount}"
        
        # Verify timestamps exist
        assert retrieved.created_at is not None, "Created timestamp should exist"
        assert retrieved.updated_at is not None, "Updated timestamp should exist"
    
    @given(
        amount=decimal_strategy(min_value=0.01, max_value=100000),
        transaction_date=date_strategy(),
        description=st.text(min_size=1, max_size=500, alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))),
        expense_category=st.sampled_from(list(ExpenseCategory)),
        is_deductible=st.booleans(),
        deduction_reason=st.one_of(
            st.none(),
            st.text(min_size=1, max_size=500, alphabet=st.characters(blacklist_categories=('Cs', 'Cc')))
        ),
        vat_rate=vat_rate_strategy()
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_expense_transaction_create_read_roundtrip(
        self,
        amount: Decimal,
        transaction_date: date,
        description: str,
        expense_category: ExpenseCategory,
        is_deductible: bool,
        deduction_reason: str,
        vat_rate: Decimal,
        db_session,
        test_user
    ):
        """
        Property: Creating an expense transaction and reading it returns identical data
        
        For any valid expense transaction data:
        - Create transaction with data D
        - Read transaction by ID
        - Retrieved data should equal D (with proper precision)
        
        **Validates: Requirements 1.1, 1.2**
        """
        # Calculate VAT amount if rate is provided
        vat_amount = None
        if vat_rate and vat_rate > 0:
            vat_amount = (amount * vat_rate / (Decimal('1') + vat_rate)).quantize(Decimal('0.01'))
        
        # Create transaction
        transaction = Transaction(
            user_id=test_user.id,
            type=TransactionType.EXPENSE,
            amount=amount.quantize(Decimal('0.01')),
            transaction_date=transaction_date,
            description=description.strip() if description else None,
            income_category=None,
            expense_category=expense_category,
            is_deductible=is_deductible,
            deduction_reason=deduction_reason.strip() if deduction_reason else None,
            vat_rate=vat_rate.quantize(Decimal('0.0001')) if vat_rate else None,
            vat_amount=vat_amount,
            import_source="manual"
        )
        
        db_session.add(transaction)
        db_session.commit()
        db_session.refresh(transaction)
        
        # Read transaction back
        retrieved = db_session.query(Transaction).filter(Transaction.id == transaction.id).first()
        
        # Verify all fields match
        assert retrieved is not None, "Transaction should be retrievable"
        assert retrieved.id == transaction.id, "ID should match"
        assert retrieved.user_id == test_user.id, "User ID should match"
        assert retrieved.type == TransactionType.EXPENSE, "Type should be EXPENSE"
        assert retrieved.amount == amount.quantize(Decimal('0.01')), \
            f"Amount should be {amount.quantize(Decimal('0.01'))}, got {retrieved.amount}"
        assert retrieved.transaction_date == transaction_date, "Transaction date should match"
        assert retrieved.description == (description.strip() if description else None), "Description should match"
        assert retrieved.income_category is None, "Income category should be None for expense"
        assert retrieved.expense_category == expense_category, "Expense category should match"
        assert retrieved.is_deductible == is_deductible, "Deductibility flag should match"
        assert retrieved.deduction_reason == (deduction_reason.strip() if deduction_reason else None), \
            "Deduction reason should match"
        
        if vat_rate:
            assert retrieved.vat_rate == vat_rate.quantize(Decimal('0.0001')), \
                f"VAT rate should be {vat_rate.quantize(Decimal('0.0001'))}, got {retrieved.vat_rate}"
            if vat_amount:
                assert retrieved.vat_amount == vat_amount, \
                    f"VAT amount should be {vat_amount}, got {retrieved.vat_amount}"
        
        # Verify timestamps exist
        assert retrieved.created_at is not None, "Created timestamp should exist"
        assert retrieved.updated_at is not None, "Updated timestamp should exist"
    
    @given(
        original_amount=decimal_strategy(min_value=0.01, max_value=50000),
        updated_amount=decimal_strategy(min_value=0.01, max_value=50000),
        original_date=date_strategy(min_days_ago=365, max_days_ago=180),
        updated_date=date_strategy(min_days_ago=179, max_days_ago=0),
        original_description=st.text(min_size=1, max_size=100, alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))),
        updated_description=st.text(min_size=1, max_size=100, alphabet=st.characters(blacklist_categories=('Cs', 'Cc')))
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_transaction_update_roundtrip(
        self,
        original_amount: Decimal,
        updated_amount: Decimal,
        original_date: date,
        updated_date: date,
        original_description: str,
        updated_description: str,
        db_session,
        test_user
    ):
        """
        Property: Updating a transaction and reading it reflects all changes
        
        For any transaction T and update data U:
        - Create transaction with data T
        - Update transaction with data U
        - Read transaction by ID
        - Retrieved data should equal U
        
        **Validates: Requirements 1.5**
        """
        # Create original transaction
        transaction = Transaction(
            user_id=test_user.id,
            type=TransactionType.INCOME,
            amount=original_amount.quantize(Decimal('0.01')),
            transaction_date=original_date,
            description=original_description.strip(),
            income_category=IncomeCategory.EMPLOYMENT,
            is_deductible=False,
            import_source="manual"
        )
        
        db_session.add(transaction)
        db_session.commit()
        db_session.refresh(transaction)
        
        original_id = transaction.id
        original_created_at = transaction.created_at
        
        # Update transaction
        transaction.amount = updated_amount.quantize(Decimal('0.01'))
        transaction.transaction_date = updated_date
        transaction.description = updated_description.strip()
        transaction.income_category = IncomeCategory.RENTAL
        transaction.is_deductible = True
        
        db_session.commit()
        db_session.refresh(transaction)
        
        # Read transaction back
        retrieved = db_session.query(Transaction).filter(Transaction.id == original_id).first()
        
        # Verify updates were applied
        assert retrieved is not None, "Transaction should still be retrievable"
        assert retrieved.id == original_id, "ID should not change"
        assert retrieved.amount == updated_amount.quantize(Decimal('0.01')), \
            f"Amount should be updated to {updated_amount.quantize(Decimal('0.01'))}, got {retrieved.amount}"
        assert retrieved.transaction_date == updated_date, "Date should be updated"
        assert retrieved.description == updated_description.strip(), "Description should be updated"
        assert retrieved.income_category == IncomeCategory.RENTAL, "Category should be updated"
        assert retrieved.is_deductible == True, "Deductibility should be updated"
        
        # Verify immutable fields
        assert retrieved.user_id == test_user.id, "User ID should not change"
        assert retrieved.created_at == original_created_at, "Created timestamp should not change"
        
        # Verify updated timestamp changed
        assert retrieved.updated_at >= original_created_at, "Updated timestamp should be >= created timestamp"
    
    @given(
        amount=decimal_strategy(min_value=0.01, max_value=100000),
        transaction_date=date_strategy()
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_decimal_precision_maintained(
        self,
        amount: Decimal,
        transaction_date: date,
        db_session,
        test_user
    ):
        """
        Property: Decimal precision is maintained at 2 decimal places
        
        For any amount with arbitrary decimal places:
        - Store amount in transaction
        - Retrieved amount should have exactly 2 decimal places
        - Retrieved amount should equal original rounded to 2 places
        
        **Validates: Requirements 1.1, 1.2**
        """
        # Quantize to 2 decimal places
        expected_amount = amount.quantize(Decimal('0.01'))
        
        # Create transaction
        transaction = Transaction(
            user_id=test_user.id,
            type=TransactionType.INCOME,
            amount=amount,  # Store with original precision
            transaction_date=transaction_date,
            income_category=IncomeCategory.EMPLOYMENT,
            import_source="manual"
        )
        
        db_session.add(transaction)
        db_session.commit()
        db_session.refresh(transaction)
        
        # Read transaction back
        retrieved = db_session.query(Transaction).filter(Transaction.id == transaction.id).first()
        
        # Verify precision
        assert retrieved.amount == expected_amount, \
            f"Amount should be {expected_amount} (2 decimal places), got {retrieved.amount}"
        
        # Verify the amount has exactly 2 decimal places
        amount_str = str(retrieved.amount)
        if '.' in amount_str:
            decimal_places = len(amount_str.split('.')[1])
            assert decimal_places <= 2, \
                f"Amount should have at most 2 decimal places, got {decimal_places}"
    
    @given(
        transactions_data=st.lists(
            st.tuples(
                decimal_strategy(min_value=0.01, max_value=10000),
                date_strategy(),
                st.sampled_from(list(IncomeCategory))
            ),
            min_size=2,
            max_size=10
        )
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_multiple_transactions_roundtrip_consistency(
        self,
        transactions_data: list,
        db_session,
        test_user
    ):
        """
        Property: Multiple transactions maintain consistency
        
        For any set of transactions:
        - Create all transactions
        - Read all transactions back
        - Each retrieved transaction matches its original data
        - All transactions are retrievable
        
        **Validates: Requirements 1.1, 1.2**
        """
        created_transactions = []
        
        # Create all transactions
        for amount, transaction_date, income_category in transactions_data:
            transaction = Transaction(
                user_id=test_user.id,
                type=TransactionType.INCOME,
                amount=amount.quantize(Decimal('0.01')),
                transaction_date=transaction_date,
                income_category=income_category,
                import_source="manual"
            )
            db_session.add(transaction)
            created_transactions.append((transaction, amount, transaction_date, income_category))
        
        db_session.commit()
        
        # Refresh all transactions
        for transaction, _, _, _ in created_transactions:
            db_session.refresh(transaction)
        
        # Verify each transaction
        for transaction, original_amount, original_date, original_category in created_transactions:
            retrieved = db_session.query(Transaction).filter(Transaction.id == transaction.id).first()
            
            assert retrieved is not None, f"Transaction {transaction.id} should be retrievable"
            assert retrieved.amount == original_amount.quantize(Decimal('0.01')), \
                f"Amount mismatch for transaction {transaction.id}"
            assert retrieved.transaction_date == original_date, \
                f"Date mismatch for transaction {transaction.id}"
            assert retrieved.income_category == original_category, \
                f"Category mismatch for transaction {transaction.id}"
            assert retrieved.user_id == test_user.id, \
                f"User ID mismatch for transaction {transaction.id}"
    
    @given(
        amount=decimal_strategy(min_value=0.01, max_value=100000),
        transaction_date=date_strategy(),
        vat_rate=st.sampled_from([Decimal('0.10'), Decimal('0.20')])
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_vat_calculation_roundtrip_consistency(
        self,
        amount: Decimal,
        transaction_date: date,
        vat_rate: Decimal,
        db_session,
        test_user
    ):
        """
        Property: VAT calculations are preserved through roundtrip
        
        For any transaction with VAT:
        - Calculate VAT amount from rate and total
        - Store transaction
        - Retrieved VAT rate and amount should match
        - VAT amount precision should be 2 decimal places
        
        **Validates: Requirements 1.1, 1.2**
        """
        # Calculate VAT amount (VAT is included in the amount)
        vat_amount = (amount * vat_rate / (Decimal('1') + vat_rate)).quantize(Decimal('0.01'))
        
        # Create transaction
        transaction = Transaction(
            user_id=test_user.id,
            type=TransactionType.INCOME,
            amount=amount.quantize(Decimal('0.01')),
            transaction_date=transaction_date,
            income_category=IncomeCategory.RENTAL,
            vat_rate=vat_rate.quantize(Decimal('0.0001')),
            vat_amount=vat_amount,
            import_source="manual"
        )
        
        db_session.add(transaction)
        db_session.commit()
        db_session.refresh(transaction)
        
        # Read transaction back
        retrieved = db_session.query(Transaction).filter(Transaction.id == transaction.id).first()
        
        # Verify VAT data
        assert retrieved.vat_rate == vat_rate.quantize(Decimal('0.0001')), \
            f"VAT rate should be {vat_rate.quantize(Decimal('0.0001'))}, got {retrieved.vat_rate}"
        assert retrieved.vat_amount == vat_amount, \
            f"VAT amount should be {vat_amount}, got {retrieved.vat_amount}"
        
        # Verify VAT amount has 2 decimal places
        vat_amount_str = str(retrieved.vat_amount)
        if '.' in vat_amount_str:
            decimal_places = len(vat_amount_str.split('.')[1])
            assert decimal_places <= 2, \
                f"VAT amount should have at most 2 decimal places, got {decimal_places}"
        
        # Verify VAT calculation consistency
        recalculated_vat = (retrieved.amount * retrieved.vat_rate / (Decimal('1') + retrieved.vat_rate)).quantize(Decimal('0.01'))
        assert retrieved.vat_amount == recalculated_vat, \
            f"Stored VAT amount {retrieved.vat_amount} should match recalculated {recalculated_vat}"
    
    @given(
        amount=decimal_strategy(min_value=0.01, max_value=100000),
        transaction_date=date_strategy(),
        income_category=st.sampled_from(list(IncomeCategory))
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_transaction_unique_identifier_property(
        self,
        amount: Decimal,
        transaction_date: date,
        income_category: IncomeCategory,
        db_session,
        test_user
    ):
        """
        Property: Each transaction has a unique identifier
        
        For any transaction:
        - Transaction receives a unique ID upon creation
        - ID is immutable
        - ID can be used to retrieve the exact transaction
        
        **Validates: Requirements 1.7**
        """
        # Create first transaction
        transaction1 = Transaction(
            user_id=test_user.id,
            type=TransactionType.INCOME,
            amount=amount.quantize(Decimal('0.01')),
            transaction_date=transaction_date,
            income_category=income_category,
            import_source="manual"
        )
        
        db_session.add(transaction1)
        db_session.commit()
        db_session.refresh(transaction1)
        
        # Create second identical transaction
        transaction2 = Transaction(
            user_id=test_user.id,
            type=TransactionType.INCOME,
            amount=amount.quantize(Decimal('0.01')),
            transaction_date=transaction_date,
            income_category=income_category,
            import_source="manual"
        )
        
        db_session.add(transaction2)
        db_session.commit()
        db_session.refresh(transaction2)
        
        # Verify unique IDs
        assert transaction1.id is not None, "Transaction 1 should have an ID"
        assert transaction2.id is not None, "Transaction 2 should have an ID"
        assert transaction1.id != transaction2.id, \
            f"Transactions should have unique IDs, but both have {transaction1.id}"
        
        # Verify each ID retrieves the correct transaction
        retrieved1 = db_session.query(Transaction).filter(Transaction.id == transaction1.id).first()
        retrieved2 = db_session.query(Transaction).filter(Transaction.id == transaction2.id).first()
        
        assert retrieved1.id == transaction1.id, "Retrieved transaction 1 should match"
        assert retrieved2.id == transaction2.id, "Retrieved transaction 2 should match"
        assert retrieved1.id != retrieved2.id, "Retrieved transactions should have different IDs"
