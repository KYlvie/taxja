"""Unit tests for duplicate transaction detection"""
import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
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
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship
from app.services.duplicate_detector import DuplicateDetector


# Create test models (simplified versions without app dependencies)
Base = declarative_base()


class UserType(str, Enum):
    """User type enumeration"""
    EMPLOYEE = "employee"
    LANDLORD = "landlord"
    SELF_EMPLOYED = "self_employed"
    SMALL_BUSINESS = "small_business"


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
    """Test User model"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    user_type = Column(SQLEnum(UserType), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    transactions = relationship("Transaction", back_populates="user")


class Transaction(Base):
    """Test Transaction model"""
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


# Test fixtures
@pytest.fixture(scope="function")
def db_engine():
    """Create test database engine"""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture(scope="function")
def db(db_engine):
    """Create test database session"""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_user(db: Session) -> User:
    """Create a test user"""
    user = User(
        email="test@example.com",
        hashed_password="hashed_password",
        full_name="Test User",
        user_type=UserType.EMPLOYEE,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def duplicate_detector(db: Session) -> DuplicateDetector:
    """Create a duplicate detector instance"""
    return DuplicateDetector(db, transaction_model=Transaction)


class TestDuplicateDetector:
    """Test suite for DuplicateDetector"""
    
    def test_exact_duplicate_detected(
        self,
        db: Session,
        test_user: User,
        duplicate_detector: DuplicateDetector
    ):
        """Test that exact duplicates are detected"""
        # Create original transaction
        original = Transaction(
            user_id=test_user.id,
            type=TransactionType.EXPENSE,
            amount=Decimal('100.00'),
            transaction_date=date(2026, 1, 15),
            description="BILLA Supermarket",
            expense_category=ExpenseCategory.GROCERIES
        )
        db.add(original)
        db.commit()
        
        # Check for duplicate
        is_duplicate, matching = duplicate_detector.check_duplicate(
            user_id=test_user.id,
            transaction_date=date(2026, 1, 15),
            amount=Decimal('100.00'),
            description="BILLA Supermarket"
        )
        
        assert is_duplicate is True
        assert matching is not None
        assert matching.id == original.id
    
    def test_similar_description_detected(
        self,
        db: Session,
        test_user: User,
        duplicate_detector: DuplicateDetector
    ):
        """Test that similar descriptions (>80%) are detected as duplicates"""
        # Create original transaction
        original = Transaction(
            user_id=test_user.id,
            type=TransactionType.EXPENSE,
            amount=Decimal('50.00'),
            transaction_date=date(2026, 1, 20),
            description="SPAR Supermarket Vienna",
            expense_category=ExpenseCategory.GROCERIES
        )
        db.add(original)
        db.commit()
        
        # Check with slightly different description (should be >80% similar)
        is_duplicate, matching = duplicate_detector.check_duplicate(
            user_id=test_user.id,
            transaction_date=date(2026, 1, 20),
            amount=Decimal('50.00'),
            description="SPAR Supermarket Wien"  # Vienna vs Wien
        )
        
        assert is_duplicate is True
        assert matching is not None
        assert matching.id == original.id
    
    def test_different_date_not_duplicate(
        self,
        db: Session,
        test_user: User,
        duplicate_detector: DuplicateDetector
    ):
        """Test that transactions with different dates are not duplicates"""
        # Create original transaction
        original = Transaction(
            user_id=test_user.id,
            type=TransactionType.EXPENSE,
            amount=Decimal('75.00'),
            transaction_date=date(2026, 1, 10),
            description="HOFER Store",
            expense_category=ExpenseCategory.GROCERIES
        )
        db.add(original)
        db.commit()
        
        # Check with different date
        is_duplicate, matching = duplicate_detector.check_duplicate(
            user_id=test_user.id,
            transaction_date=date(2026, 1, 11),  # Different date
            amount=Decimal('75.00'),
            description="HOFER Store"
        )
        
        assert is_duplicate is False
        assert matching is None
    
    def test_different_amount_not_duplicate(
        self,
        db: Session,
        test_user: User,
        duplicate_detector: DuplicateDetector
    ):
        """Test that transactions with different amounts are not duplicates"""
        # Create original transaction
        original = Transaction(
            user_id=test_user.id,
            type=TransactionType.EXPENSE,
            amount=Decimal('100.00'),
            transaction_date=date(2026, 1, 15),
            description="LIDL Store",
            expense_category=ExpenseCategory.GROCERIES
        )
        db.add(original)
        db.commit()
        
        # Check with different amount
        is_duplicate, matching = duplicate_detector.check_duplicate(
            user_id=test_user.id,
            transaction_date=date(2026, 1, 15),
            amount=Decimal('100.01'),  # Different amount
            description="LIDL Store"
        )
        
        assert is_duplicate is False
        assert matching is None
    
    def test_dissimilar_description_not_duplicate(
        self,
        db: Session,
        test_user: User,
        duplicate_detector: DuplicateDetector
    ):
        """Test that transactions with dissimilar descriptions (<80%) are not duplicates"""
        # Create original transaction
        original = Transaction(
            user_id=test_user.id,
            type=TransactionType.EXPENSE,
            amount=Decimal('50.00'),
            transaction_date=date(2026, 1, 20),
            description="BILLA Supermarket",
            expense_category=ExpenseCategory.GROCERIES
        )
        db.add(original)
        db.commit()
        
        # Check with very different description
        is_duplicate, matching = duplicate_detector.check_duplicate(
            user_id=test_user.id,
            transaction_date=date(2026, 1, 20),
            amount=Decimal('50.00'),
            description="Office supplies purchase"  # Completely different
        )
        
        assert is_duplicate is False
        assert matching is None
    
    def test_none_descriptions_identical(
        self,
        db: Session,
        test_user: User,
        duplicate_detector: DuplicateDetector
    ):
        """Test that two None descriptions are considered identical"""
        # Create original transaction with no description
        original = Transaction(
            user_id=test_user.id,
            type=TransactionType.EXPENSE,
            amount=Decimal('25.00'),
            transaction_date=date(2026, 1, 25),
            description=None,
            expense_category=ExpenseCategory.OTHER
        )
        db.add(original)
        db.commit()
        
        # Check with None description
        is_duplicate, matching = duplicate_detector.check_duplicate(
            user_id=test_user.id,
            transaction_date=date(2026, 1, 25),
            amount=Decimal('25.00'),
            description=None
        )
        
        assert is_duplicate is True
        assert matching is not None
        assert matching.id == original.id
    
    def test_one_none_description_not_duplicate(
        self,
        db: Session,
        test_user: User,
        duplicate_detector: DuplicateDetector
    ):
        """Test that one None and one non-None description are not duplicates"""
        # Create original transaction with description
        original = Transaction(
            user_id=test_user.id,
            type=TransactionType.EXPENSE,
            amount=Decimal('30.00'),
            transaction_date=date(2026, 1, 28),
            description="Some description",
            expense_category=ExpenseCategory.OTHER
        )
        db.add(original)
        db.commit()
        
        # Check with None description
        is_duplicate, matching = duplicate_detector.check_duplicate(
            user_id=test_user.id,
            transaction_date=date(2026, 1, 28),
            amount=Decimal('30.00'),
            description=None
        )
        
        assert is_duplicate is False
        assert matching is None
    
    def test_exclude_id_parameter(
        self,
        db: Session,
        test_user: User,
        duplicate_detector: DuplicateDetector
    ):
        """Test that exclude_id parameter works correctly"""
        # Create original transaction
        original = Transaction(
            user_id=test_user.id,
            type=TransactionType.EXPENSE,
            amount=Decimal('40.00'),
            transaction_date=date(2026, 2, 1),
            description="Test transaction",
            expense_category=ExpenseCategory.OTHER
        )
        db.add(original)
        db.commit()
        
        # Check duplicate excluding the original (for update scenario)
        is_duplicate, matching = duplicate_detector.check_duplicate(
            user_id=test_user.id,
            transaction_date=date(2026, 2, 1),
            amount=Decimal('40.00'),
            description="Test transaction",
            exclude_id=original.id
        )
        
        assert is_duplicate is False
        assert matching is None
    
    def test_different_user_not_duplicate(
        self,
        db: Session,
        test_user: User,
        duplicate_detector: DuplicateDetector
    ):
        """Test that transactions from different users are not duplicates"""
        # Create another user
        other_user = User(
            email="other@example.com",
            hashed_password="hashed_password",
            full_name="Other User",
            user_type=UserType.EMPLOYEE,
            is_active=True
        )
        db.add(other_user)
        db.commit()
        
        # Create transaction for other user
        other_txn = Transaction(
            user_id=other_user.id,
            type=TransactionType.EXPENSE,
            amount=Decimal('60.00'),
            transaction_date=date(2026, 2, 5),
            description="Shared description",
            expense_category=ExpenseCategory.OTHER
        )
        db.add(other_txn)
        db.commit()
        
        # Check for test_user (should not find duplicate)
        is_duplicate, matching = duplicate_detector.check_duplicate(
            user_id=test_user.id,
            transaction_date=date(2026, 2, 5),
            amount=Decimal('60.00'),
            description="Shared description"
        )
        
        assert is_duplicate is False
        assert matching is None
    
    def test_batch_duplicate_check(
        self,
        db: Session,
        test_user: User,
        duplicate_detector: DuplicateDetector
    ):
        """Test batch duplicate checking"""
        # Create existing transactions
        existing1 = Transaction(
            user_id=test_user.id,
            type=TransactionType.EXPENSE,
            amount=Decimal('100.00'),
            transaction_date=date(2026, 3, 1),
            description="BILLA Purchase",
            expense_category=ExpenseCategory.GROCERIES
        )
        existing2 = Transaction(
            user_id=test_user.id,
            type=TransactionType.EXPENSE,
            amount=Decimal('50.00'),
            transaction_date=date(2026, 3, 2),
            description="SPAR Purchase",
            expense_category=ExpenseCategory.GROCERIES
        )
        db.add_all([existing1, existing2])
        db.commit()
        
        # Batch check
        batch = [
            {
                'transaction_date': date(2026, 3, 1),
                'amount': Decimal('100.00'),
                'description': 'BILLA Purchase'  # Duplicate
            },
            {
                'transaction_date': date(2026, 3, 3),
                'amount': Decimal('75.00'),
                'description': 'New Purchase'  # Not duplicate
            },
            {
                'transaction_date': date(2026, 3, 2),
                'amount': Decimal('50.00'),
                'description': 'SPAR Purchase'  # Duplicate
            }
        ]
        
        results = duplicate_detector.check_duplicates_batch(
            user_id=test_user.id,
            transactions=batch
        )
        
        assert len(results) == 3
        assert results[0]['is_duplicate'] is True
        assert results[0]['duplicate_of_id'] == existing1.id
        assert results[0]['duplicate_confidence'] is not None
        assert results[1]['is_duplicate'] is False
        assert results[1]['duplicate_of_id'] is None
        assert results[2]['is_duplicate'] is True
        assert results[2]['duplicate_of_id'] == existing2.id
    
    def test_find_duplicates_in_existing(
        self,
        db: Session,
        test_user: User,
        duplicate_detector: DuplicateDetector
    ):
        """Test finding duplicates in existing transactions"""
        # Create duplicate transactions
        txn1 = Transaction(
            user_id=test_user.id,
            type=TransactionType.EXPENSE,
            amount=Decimal('80.00'),
            transaction_date=date(2026, 4, 1),
            description="Duplicate transaction",
            expense_category=ExpenseCategory.OTHER
        )
        txn2 = Transaction(
            user_id=test_user.id,
            type=TransactionType.EXPENSE,
            amount=Decimal('80.00'),
            transaction_date=date(2026, 4, 1),
            description="Duplicate transaction",
            expense_category=ExpenseCategory.OTHER
        )
        txn3 = Transaction(
            user_id=test_user.id,
            type=TransactionType.EXPENSE,
            amount=Decimal('90.00'),
            transaction_date=date(2026, 4, 2),
            description="Unique transaction",
            expense_category=ExpenseCategory.OTHER
        )
        db.add_all([txn1, txn2, txn3])
        db.commit()
        
        # Find duplicates
        duplicates = duplicate_detector.find_duplicates_in_existing(
            user_id=test_user.id
        )
        
        assert len(duplicates) == 1
        dup_txn1, dup_txn2, similarity = duplicates[0]
        assert {dup_txn1.id, dup_txn2.id} == {txn1.id, txn2.id}
        assert similarity >= 0.80
    
    def test_similarity_calculation_edge_cases(
        self,
        duplicate_detector: DuplicateDetector
    ):
        """Test similarity calculation edge cases"""
        # Both None
        assert duplicate_detector._calculate_similarity(None, None) == 1.0
        
        # One None
        assert duplicate_detector._calculate_similarity(None, "text") == 0.0
        assert duplicate_detector._calculate_similarity("text", None) == 0.0
        
        # Both empty
        assert duplicate_detector._calculate_similarity("", "") == 1.0
        
        # One empty
        assert duplicate_detector._calculate_similarity("", "text") == 0.0
        assert duplicate_detector._calculate_similarity("text", "") == 0.0
        
        # Identical
        assert duplicate_detector._calculate_similarity("test", "test") == 1.0
        
        # Case insensitive
        similarity = duplicate_detector._calculate_similarity("Test", "test")
        assert similarity == 1.0
        
        # Whitespace normalized
        similarity = duplicate_detector._calculate_similarity("  test  ", "test")
        assert similarity == 1.0
    
    def test_similarity_threshold_boundary(
        self,
        db: Session,
        test_user: User,
        duplicate_detector: DuplicateDetector
    ):
        """Test similarity threshold boundary (80%)"""
        # Create original transaction
        original = Transaction(
            user_id=test_user.id,
            type=TransactionType.EXPENSE,
            amount=Decimal('100.00'),
            transaction_date=date(2026, 5, 1),
            description="ABCDEFGHIJ",  # 10 characters
            expense_category=ExpenseCategory.OTHER
        )
        db.add(original)
        db.commit()
        
        # Test with 80% similar description (8 matching characters)
        # "ABCDEFGHIJ" vs "ABCDEFGHXX" = 80% similar
        is_duplicate, matching = duplicate_detector.check_duplicate(
            user_id=test_user.id,
            transaction_date=date(2026, 5, 1),
            amount=Decimal('100.00'),
            description="ABCDEFGHXX"
        )
        
        # Should be detected as duplicate (>= 80%)
        assert is_duplicate is True
        assert matching is not None


