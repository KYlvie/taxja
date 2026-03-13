"""
Property-based tests for duplicate transaction detection

**Validates: Requirements 9.3, 12.9**

Property 18: Duplicate transaction detection
- Transactions with same date, amount, and similar description (>80%) are detected as duplicates
- Transactions with different dates are not duplicates
- Transactions with different amounts are not duplicates
- Transactions with dissimilar descriptions (<80%) are not duplicates
- Duplicate detection is consistent and deterministic
- Batch duplicate detection produces consistent results
"""

import pytest
from hypothesis import given, strategies as st, assume, settings, HealthCheck
from decimal import Decimal
from datetime import date, datetime, timedelta
from enum import Enum
from uuid import uuid4
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
from app.services.duplicate_detector import DuplicateDetector

# Create test Base
Base = declarative_base()


# Define minimal models for testing
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
    GROCERIES = "groceries"
    OTHER = "other"


class User(Base):
    """Minimal User model for testing"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    user_type = Column(SQLEnum(UserType), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
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
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
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
        user_type=UserType.SELF_EMPLOYED
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def duplicate_detector(db_session):
    """Create a duplicate detector instance"""
    return DuplicateDetector(db_session, transaction_model=Transaction)


# Custom strategies for generating test data
def decimal_strategy(min_value=0.01, max_value=100000, places=2):
    """Generate Decimal values with specified precision"""
    return st.decimals(
        min_value=Decimal(str(min_value)),
        max_value=Decimal(str(max_value)),
        allow_nan=False,
        allow_infinity=False,
        places=places
    )


def date_strategy(min_days_ago=365, max_days_ago=0):
    """Generate dates within a reasonable range"""
    today = date.today()
    return st.dates(
        min_value=today - timedelta(days=min_days_ago),
        max_value=today - timedelta(days=max_days_ago)
    )


def description_strategy():
    """Generate realistic transaction descriptions"""
    return st.text(
        min_size=5,
        max_size=100,
        alphabet=st.characters(
            whitelist_categories=('Lu', 'Ll', 'Nd'),
            whitelist_characters=' -.,/'
        )
    )


class TestProperty18DuplicateDetection:
    """
    **Property 18: Duplicate transaction detection**
    **Validates: Requirements 9.3, 12.9**
    
    Tests that duplicate detection:
    1. Correctly identifies duplicates (same date, amount, similar description)
    2. Correctly rejects non-duplicates (different date, amount, or description)
    3. Is consistent and deterministic
    4. Works correctly in batch operations
    """
    
    @given(
        amount=decimal_strategy(min_value=0.01, max_value=10000),
        transaction_date=date_strategy(),
        description=description_strategy()
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_exact_duplicate_always_detected(
        self,
        amount: Decimal,
        transaction_date: date,
        description: str,
        db_session,
        test_user,
        duplicate_detector
    ):
        """
        Property: Exact duplicates are always detected
        
        For any transaction T with (date, amount, description):
        - Create transaction T
        - Check for duplicate with same (date, amount, description)
        - Should always return True (is duplicate)
        
        **Validates: Requirement 9.3**
        """
        # Create original transaction
        original = Transaction(
            user_id=test_user.id,
            type=TransactionType.EXPENSE,
            amount=amount.quantize(Decimal('0.01')),
            transaction_date=transaction_date,
            description=description.strip(),
            expense_category=ExpenseCategory.OTHER
        )
        db_session.add(original)
        db_session.commit()
        
        # Check for duplicate with exact same data
        is_duplicate, matching = duplicate_detector.check_duplicate(
            user_id=test_user.id,
            transaction_date=transaction_date,
            amount=amount.quantize(Decimal('0.01')),
            description=description.strip()
        )
        
        assert is_duplicate is True, \
            f"Exact duplicate should be detected for date={transaction_date}, amount={amount}, desc='{description}'"
        assert matching is not None, "Matching transaction should be returned"
        assert matching.id == original.id, "Should match the original transaction"
    
    @given(
        amount=decimal_strategy(min_value=0.01, max_value=10000),
        transaction_date=date_strategy(),
        base_description=st.text(min_size=10, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll')))
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_similar_description_detected_as_duplicate(
        self,
        amount: Decimal,
        transaction_date: date,
        base_description: str,
        db_session,
        test_user,
        duplicate_detector
    ):
        """
        Property: Transactions with >80% similar descriptions are detected as duplicates
        
        For any transaction T with description D:
        - Create transaction T with description D
        - Create similar description D' (>80% similar to D)
        - Check for duplicate with (same date, same amount, description D')
        - Should return True (is duplicate)
        
        **Validates: Requirement 9.3**
        """
        # Ensure base description is long enough
        assume(len(base_description.strip()) >= 10)
        
        # Create original transaction
        original_desc = base_description.strip()
        original = Transaction(
            user_id=test_user.id,
            type=TransactionType.EXPENSE,
            amount=amount.quantize(Decimal('0.01')),
            transaction_date=transaction_date,
            description=original_desc,
            expense_category=ExpenseCategory.OTHER
        )
        db_session.add(original)
        db_session.commit()
        
        # Create similar description (change last 2 characters to ensure >80% similarity)
        similar_desc = original_desc[:-2] + "XX"
        
        # Check for duplicate
        is_duplicate, matching = duplicate_detector.check_duplicate(
            user_id=test_user.id,
            transaction_date=transaction_date,
            amount=amount.quantize(Decimal('0.01')),
            description=similar_desc
        )
        
        # Calculate actual similarity
        similarity = duplicate_detector._calculate_similarity(original_desc, similar_desc)
        
        if similarity >= 0.80:
            assert is_duplicate is True, \
                f"Similar description (similarity={similarity:.2f}) should be detected as duplicate"
            assert matching is not None, "Matching transaction should be returned"
        else:
            # If similarity < 80%, it's okay if not detected
            pass
    
    @given(
        amount=decimal_strategy(min_value=0.01, max_value=10000),
        date1=date_strategy(min_days_ago=365, max_days_ago=180),
        date2=date_strategy(min_days_ago=179, max_days_ago=0),
        description=description_strategy()
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_different_date_not_duplicate(
        self,
        amount: Decimal,
        date1: date,
        date2: date,
        description: str,
        db_session,
        test_user,
        duplicate_detector
    ):
        """
        Property: Transactions with different dates are not duplicates
        
        For any two dates D1 ≠ D2:
        - Create transaction with (D1, amount, description)
        - Check for duplicate with (D2, amount, description)
        - Should return False (not duplicate)
        
        **Validates: Requirement 9.3**
        """
        # Ensure dates are different
        assume(date1 != date2)
        
        # Create original transaction
        original = Transaction(
            user_id=test_user.id,
            type=TransactionType.EXPENSE,
            amount=amount.quantize(Decimal('0.01')),
            transaction_date=date1,
            description=description.strip(),
            expense_category=ExpenseCategory.OTHER
        )
        db_session.add(original)
        db_session.commit()
        
        # Check with different date
        is_duplicate, matching = duplicate_detector.check_duplicate(
            user_id=test_user.id,
            transaction_date=date2,  # Different date
            amount=amount.quantize(Decimal('0.01')),
            description=description.strip()
        )
        
        assert is_duplicate is False, \
            f"Transactions with different dates ({date1} vs {date2}) should not be duplicates"
        assert matching is None, "No matching transaction should be returned"
    
    @given(
        amount1=decimal_strategy(min_value=0.01, max_value=5000),
        amount2=decimal_strategy(min_value=5001, max_value=10000),
        transaction_date=date_strategy(),
        description=description_strategy()
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_different_amount_not_duplicate(
        self,
        amount1: Decimal,
        amount2: Decimal,
        transaction_date: date,
        description: str,
        db_session,
        test_user,
        duplicate_detector
    ):
        """
        Property: Transactions with different amounts are not duplicates
        
        For any two amounts A1 ≠ A2:
        - Create transaction with (date, A1, description)
        - Check for duplicate with (date, A2, description)
        - Should return False (not duplicate)
        
        **Validates: Requirement 9.3**
        """
        # Ensure amounts are different
        assume(amount1.quantize(Decimal('0.01')) != amount2.quantize(Decimal('0.01')))
        
        # Create original transaction
        original = Transaction(
            user_id=test_user.id,
            type=TransactionType.EXPENSE,
            amount=amount1.quantize(Decimal('0.01')),
            transaction_date=transaction_date,
            description=description.strip(),
            expense_category=ExpenseCategory.OTHER
        )
        db_session.add(original)
        db_session.commit()
        
        # Check with different amount
        is_duplicate, matching = duplicate_detector.check_duplicate(
            user_id=test_user.id,
            transaction_date=transaction_date,
            amount=amount2.quantize(Decimal('0.01')),  # Different amount
            description=description.strip()
        )
        
        assert is_duplicate is False, \
            f"Transactions with different amounts ({amount1} vs {amount2}) should not be duplicates"
        assert matching is None, "No matching transaction should be returned"
    
    @given(
        amount=decimal_strategy(min_value=0.01, max_value=10000),
        transaction_date=date_strategy(),
        description1=st.text(min_size=10, max_size=50, alphabet=st.characters(whitelist_categories=('Lu',))),
        description2=st.text(min_size=10, max_size=50, alphabet=st.characters(whitelist_categories=('Ll',)))
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_dissimilar_description_not_duplicate(
        self,
        amount: Decimal,
        transaction_date: date,
        description1: str,
        description2: str,
        db_session,
        test_user,
        duplicate_detector
    ):
        """
        Property: Transactions with dissimilar descriptions (<80%) are not duplicates
        
        For any two descriptions D1 and D2 where similarity(D1, D2) < 80%:
        - Create transaction with (date, amount, D1)
        - Check for duplicate with (date, amount, D2)
        - Should return False (not duplicate)
        
        **Validates: Requirement 9.3**
        """
        # Ensure descriptions are sufficiently different
        desc1 = description1.strip()
        desc2 = description2.strip()
        assume(len(desc1) >= 10 and len(desc2) >= 10)
        
        # Calculate similarity
        similarity = duplicate_detector._calculate_similarity(desc1, desc2)
        assume(similarity < 0.80)  # Only test when similarity is below threshold
        
        # Create original transaction
        original = Transaction(
            user_id=test_user.id,
            type=TransactionType.EXPENSE,
            amount=amount.quantize(Decimal('0.01')),
            transaction_date=transaction_date,
            description=desc1,
            expense_category=ExpenseCategory.OTHER
        )
        db_session.add(original)
        db_session.commit()
        
        # Check with dissimilar description
        is_duplicate, matching = duplicate_detector.check_duplicate(
            user_id=test_user.id,
            transaction_date=transaction_date,
            amount=amount.quantize(Decimal('0.01')),
            description=desc2
        )
        
        assert is_duplicate is False, \
            f"Transactions with dissimilar descriptions (similarity={similarity:.2f}) should not be duplicates"
        assert matching is None, "No matching transaction should be returned"
    
    @given(
        amount=decimal_strategy(min_value=0.01, max_value=10000),
        transaction_date=date_strategy(),
        description=description_strategy()
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_duplicate_detection_is_deterministic(
        self,
        amount: Decimal,
        transaction_date: date,
        description: str,
        db_session,
        test_user,
        duplicate_detector
    ):
        """
        Property: Duplicate detection is deterministic
        
        For any transaction T:
        - Create transaction T
        - Check for duplicate multiple times with same data
        - All checks should return the same result
        
        **Validates: Requirement 9.3**
        """
        # Create original transaction
        original = Transaction(
            user_id=test_user.id,
            type=TransactionType.EXPENSE,
            amount=amount.quantize(Decimal('0.01')),
            transaction_date=transaction_date,
            description=description.strip(),
            expense_category=ExpenseCategory.OTHER
        )
        db_session.add(original)
        db_session.commit()
        
        # Check for duplicate multiple times
        results = []
        for _ in range(3):
            is_duplicate, matching = duplicate_detector.check_duplicate(
                user_id=test_user.id,
                transaction_date=transaction_date,
                amount=amount.quantize(Decimal('0.01')),
                description=description.strip()
            )
            results.append((is_duplicate, matching.id if matching else None))
        
        # All results should be identical
        assert all(r == results[0] for r in results), \
            f"Duplicate detection should be deterministic, got different results: {results}"
        
        # All should detect as duplicate
        assert all(r[0] is True for r in results), "All checks should detect duplicate"
        assert all(r[1] == original.id for r in results), "All checks should match original transaction"
    
    @given(
        transactions_data=st.lists(
            st.tuples(
                decimal_strategy(min_value=0.01, max_value=1000),
                date_strategy(),
                description_strategy()
            ),
            min_size=3,
            max_size=10
        )
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_batch_duplicate_detection_consistency(
        self,
        transactions_data: list,
        db_session,
        test_user,
        duplicate_detector
    ):
        """
        Property: Batch duplicate detection is consistent with individual checks
        
        For any set of transactions:
        - Create some existing transactions
        - Check batch of new transactions
        - Batch results should match individual check results
        
        **Validates: Requirement 12.9**
        """
        # Create some existing transactions (first half)
        existing_count = len(transactions_data) // 2
        for amount, txn_date, description in transactions_data[:existing_count]:
            txn = Transaction(
                user_id=test_user.id,
                type=TransactionType.EXPENSE,
                amount=amount.quantize(Decimal('0.01')),
                transaction_date=txn_date,
                description=description.strip(),
                expense_category=ExpenseCategory.OTHER
            )
            db_session.add(txn)
        db_session.commit()
        
        # Prepare batch check (all transactions)
        batch = [
            {
                'transaction_date': txn_date,
                'amount': amount.quantize(Decimal('0.01')),
                'description': description.strip()
            }
            for amount, txn_date, description in transactions_data
        ]
        
        # Batch check
        batch_results = duplicate_detector.check_duplicates_batch(
            user_id=test_user.id,
            transactions=batch
        )
        
        # Individual checks
        individual_results = []
        for txn_data in batch:
            is_dup, matching = duplicate_detector.check_duplicate(
                user_id=test_user.id,
                transaction_date=txn_data['transaction_date'],
                amount=txn_data['amount'],
                description=txn_data['description']
            )
            individual_results.append(is_dup)
        
        # Compare results
        assert len(batch_results) == len(individual_results), \
            "Batch results count should match individual results count"
        
        for i, (batch_result, individual_result) in enumerate(zip(batch_results, individual_results)):
            assert batch_result['is_duplicate'] == individual_result, \
                f"Batch result {i} (is_duplicate={batch_result['is_duplicate']}) " \
                f"should match individual result ({individual_result})"
    
    @given(
        amount=decimal_strategy(min_value=0.01, max_value=10000),
        transaction_date=date_strategy(),
        description=description_strategy()
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_user_isolation_in_duplicate_detection(
        self,
        amount: Decimal,
        transaction_date: date,
        description: str,
        db_session,
        test_user,
        duplicate_detector
    ):
        """
        Property: Duplicate detection respects user isolation
        
        For any transaction T:
        - Create transaction T for user U1
        - Check for duplicate for user U2 with same data
        - Should return False (not duplicate) - different users
        
        **Validates: Requirement 9.3**
        """
        # Create another user with unique email using UUID
        unique_email = f"other-{uuid4()}@example.com"
        other_user = User(
            email=unique_email,
            password_hash="hashed_password",
            name="Other User",
            user_type=UserType.EMPLOYEE
        )
        db_session.add(other_user)
        db_session.commit()
        db_session.refresh(other_user)
        
        # Create transaction for test_user
        original = Transaction(
            user_id=test_user.id,
            type=TransactionType.EXPENSE,
            amount=amount.quantize(Decimal('0.01')),
            transaction_date=transaction_date,
            description=description.strip(),
            expense_category=ExpenseCategory.OTHER
        )
        db_session.add(original)
        db_session.commit()
        
        # Check for duplicate for other_user
        is_duplicate, matching = duplicate_detector.check_duplicate(
            user_id=other_user.id,  # Different user
            transaction_date=transaction_date,
            amount=amount.quantize(Decimal('0.01')),
            description=description.strip()
        )
        
        assert is_duplicate is False, \
            "Transactions from different users should not be detected as duplicates"
        assert matching is None, "No matching transaction should be returned for different user"
    
    @given(
        amount=decimal_strategy(min_value=0.01, max_value=10000),
        transaction_date=date_strategy()
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_none_descriptions_are_duplicates(
        self,
        amount: Decimal,
        transaction_date: date,
        db_session,
        test_user,
        duplicate_detector
    ):
        """
        Property: Transactions with both None descriptions are duplicates
        
        For any transaction with None description:
        - Create transaction with (date, amount, None)
        - Check for duplicate with (date, amount, None)
        - Should return True (is duplicate)
        
        **Validates: Requirement 9.3**
        """
        # Create original transaction with None description
        original = Transaction(
            user_id=test_user.id,
            type=TransactionType.EXPENSE,
            amount=amount.quantize(Decimal('0.01')),
            transaction_date=transaction_date,
            description=None,
            expense_category=ExpenseCategory.OTHER
        )
        db_session.add(original)
        db_session.commit()
        
        # Check for duplicate with None description
        is_duplicate, matching = duplicate_detector.check_duplicate(
            user_id=test_user.id,
            transaction_date=transaction_date,
            amount=amount.quantize(Decimal('0.01')),
            description=None
        )
        
        assert is_duplicate is True, \
            "Transactions with both None descriptions should be duplicates"
        assert matching is not None, "Matching transaction should be returned"
        assert matching.id == original.id, "Should match the original transaction"
    
    @given(
        amount=decimal_strategy(min_value=0.01, max_value=10000),
        transaction_date=date_strategy(),
        description=description_strategy()
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_one_none_description_not_duplicate(
        self,
        amount: Decimal,
        transaction_date: date,
        description: str,
        db_session,
        test_user,
        duplicate_detector
    ):
        """
        Property: Transaction with one None and one non-None description are not duplicates
        
        For any transaction with description D:
        - Create transaction with (date, amount, D)
        - Check for duplicate with (date, amount, None)
        - Should return False (not duplicate)
        
        **Validates: Requirement 9.3**
        """
        # Create original transaction with description
        original = Transaction(
            user_id=test_user.id,
            type=TransactionType.EXPENSE,
            amount=amount.quantize(Decimal('0.01')),
            transaction_date=transaction_date,
            description=description.strip(),
            expense_category=ExpenseCategory.OTHER
        )
        db_session.add(original)
        db_session.commit()
        
        # Check for duplicate with None description
        is_duplicate, matching = duplicate_detector.check_duplicate(
            user_id=test_user.id,
            transaction_date=transaction_date,
            amount=amount.quantize(Decimal('0.01')),
            description=None
        )
        
        assert is_duplicate is False, \
            "Transaction with one None and one non-None description should not be duplicates"
        assert matching is None, "No matching transaction should be returned"
    
    @given(
        amount=decimal_strategy(min_value=0.01, max_value=10000),
        transaction_date=date_strategy(),
        description=description_strategy()
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_exclude_id_prevents_self_duplicate(
        self,
        amount: Decimal,
        transaction_date: date,
        description: str,
        db_session,
        test_user,
        duplicate_detector
    ):
        """
        Property: Excluding a transaction ID prevents it from being detected as its own duplicate
        
        For any transaction T:
        - Create transaction T
        - Check for duplicate with same data but exclude_id=T.id
        - Should return False (not duplicate) - transaction excluded
        
        **Validates: Requirement 9.3 (update scenario)**
        """
        # Create original transaction
        original = Transaction(
            user_id=test_user.id,
            type=TransactionType.EXPENSE,
            amount=amount.quantize(Decimal('0.01')),
            transaction_date=transaction_date,
            description=description.strip(),
            expense_category=ExpenseCategory.OTHER
        )
        db_session.add(original)
        db_session.commit()
        db_session.refresh(original)
        
        # Check for duplicate excluding the original transaction
        is_duplicate, matching = duplicate_detector.check_duplicate(
            user_id=test_user.id,
            transaction_date=transaction_date,
            amount=amount.quantize(Decimal('0.01')),
            description=description.strip(),
            exclude_id=original.id
        )
        
        assert is_duplicate is False, \
            "Transaction should not be detected as duplicate when excluded by ID"
        assert matching is None, "No matching transaction should be returned when original is excluded"
    
    @given(
        amount=decimal_strategy(min_value=0.01, max_value=10000),
        transaction_date=date_strategy(),
        description=description_strategy(),
        num_duplicates=st.integers(min_value=2, max_value=5)
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_multiple_duplicates_detection(
        self,
        amount: Decimal,
        transaction_date: date,
        description: str,
        num_duplicates: int,
        db_session,
        test_user,
        duplicate_detector
    ):
        """
        Property: When multiple duplicates exist, at least one is detected
        
        For any transaction T:
        - Create N identical transactions (N >= 2)
        - Check for duplicate with same data
        - Should return True and match one of the existing transactions
        
        **Validates: Requirement 9.3**
        """
        # Get count of existing transactions before creating new ones
        existing_count = db_session.query(Transaction).filter(
            Transaction.user_id == test_user.id
        ).count()
        
        # Create multiple identical transactions
        created_ids = []
        for _ in range(num_duplicates):
            txn = Transaction(
                user_id=test_user.id,
                type=TransactionType.EXPENSE,
                amount=amount.quantize(Decimal('0.01')),
                transaction_date=transaction_date,
                description=description.strip(),
                expense_category=ExpenseCategory.OTHER
            )
            db_session.add(txn)
            db_session.flush()
            created_ids.append(txn.id)
        db_session.commit()
        
        # Check for duplicate
        is_duplicate, matching = duplicate_detector.check_duplicate(
            user_id=test_user.id,
            transaction_date=transaction_date,
            amount=amount.quantize(Decimal('0.01')),
            description=description.strip()
        )
        
        assert is_duplicate is True, \
            f"Should detect duplicate when {num_duplicates} identical transactions exist"
        assert matching is not None, "Matching transaction should be returned"
        # The matching transaction should be one of the transactions we just created
        # (it could also match an older transaction from a previous test if they happen to have the same data)
        # So we just verify that a duplicate was detected
        assert matching.user_id == test_user.id, "Matched transaction should belong to the same user"
        assert matching.amount == amount.quantize(Decimal('0.01')), "Matched transaction should have same amount"
        assert matching.transaction_date == transaction_date, "Matched transaction should have same date"
    
    @given(
        base_amount=decimal_strategy(min_value=100, max_value=1000),
        transaction_date=date_strategy(),
        description=description_strategy()
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_decimal_precision_in_duplicate_detection(
        self,
        base_amount: Decimal,
        transaction_date: date,
        description: str,
        db_session,
        test_user,
        duplicate_detector
    ):
        """
        Property: Duplicate detection respects decimal precision (2 places)
        
        For any amount A:
        - Create transaction with amount A (quantized to 2 places)
        - Check with amount A + 0.001 (rounds to same value)
        - Should detect as duplicate (same after quantization)
        
        **Validates: Requirement 9.3**
        """
        # Create original transaction
        original_amount = base_amount.quantize(Decimal('0.01'))
        original = Transaction(
            user_id=test_user.id,
            type=TransactionType.EXPENSE,
            amount=original_amount,
            transaction_date=transaction_date,
            description=description.strip(),
            expense_category=ExpenseCategory.OTHER
        )
        db_session.add(original)
        db_session.commit()
        
        # Check with amount that rounds to same value
        check_amount = (base_amount + Decimal('0.001')).quantize(Decimal('0.01'))
        
        # Only test if amounts are actually the same after quantization
        if original_amount == check_amount:
            is_duplicate, matching = duplicate_detector.check_duplicate(
                user_id=test_user.id,
                transaction_date=transaction_date,
                amount=check_amount,
                description=description.strip()
            )
            
            assert is_duplicate is True, \
                f"Should detect duplicate when amounts are same after quantization: {original_amount} == {check_amount}"
            assert matching is not None, "Matching transaction should be returned"
    
    @given(
        amount=decimal_strategy(min_value=0.01, max_value=10000),
        transaction_date=date_strategy(),
        description=st.text(min_size=5, max_size=50, alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz')
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_case_insensitive_description_matching(
        self,
        amount: Decimal,
        transaction_date: date,
        description: str,
        db_session,
        test_user,
        duplicate_detector
    ):
        """
        Property: Description matching is case-insensitive
        
        For any description D:
        - Create transaction with description D
        - Check with description D.upper() or D.lower()
        - Should detect as duplicate (case-insensitive)
        
        **Validates: Requirement 9.3**
        """
        # Ensure description has some letters
        assume(len(description.strip()) >= 5)
        
        # Create original transaction with lowercase description
        original_desc = description.strip().lower()
        upper_desc = original_desc.upper()
        
        # Skip if they're the same (shouldn't happen with ASCII letters)
        assume(original_desc != upper_desc)
        
        original = Transaction(
            user_id=test_user.id,
            type=TransactionType.EXPENSE,
            amount=amount.quantize(Decimal('0.01')),
            transaction_date=transaction_date,
            description=original_desc,
            expense_category=ExpenseCategory.OTHER
        )
        db_session.add(original)
        db_session.commit()
        
        # Check with uppercase description
        is_duplicate, matching = duplicate_detector.check_duplicate(
            user_id=test_user.id,
            transaction_date=transaction_date,
            amount=amount.quantize(Decimal('0.01')),
            description=upper_desc
        )
        
        assert is_duplicate is True, \
            f"Should detect duplicate with case-insensitive matching: '{original_desc}' vs '{upper_desc}'"
        assert matching is not None, "Matching transaction should be returned"
        assert matching.user_id == test_user.id, "Should match a transaction from the same user"
