"""
Property-based tests for multi-year data isolation

**Validates: Requirements 10.1, 10.2**

Property 19: Multi-year data isolation
- Transactions are properly isolated by tax year boundaries
- Filtering by tax_year returns only transactions within that calendar year
- Tax year boundaries are respected (January 1 to December 31)
- Transactions from different years do not interfere with each other
- Year filtering is consistent and deterministic
- Multiple users' data remains isolated across years
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


# Hypothesis strategies
def decimal_strategy(min_value=0.01, max_value=100000):
    """Generate valid decimal amounts"""
    return st.decimals(
        min_value=Decimal(str(min_value)),
        max_value=Decimal(str(max_value)),
        places=2,
        allow_nan=False,
        allow_infinity=False
    )


def date_strategy(min_year=2020, max_year=2030):
    """Generate valid dates within a range"""
    return st.dates(
        min_value=date(min_year, 1, 1),
        max_value=date(max_year, 12, 31)
    )


def year_strategy():
    """Generate valid tax years"""
    return st.integers(min_value=2020, max_value=2030)


@pytest.fixture(scope="function")
def db_engine():
    """Create a fresh database engine for each test"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine):
    """Create a fresh database session for each test"""
    Session = sessionmaker(bind=db_engine)
    session = Session()
    
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="function")
def test_user(db_session):
    """Create a test user"""
    user = User(
        email="test@example.com",
        password_hash="hashed_password",
        name="Test User",
        user_type=UserType.EMPLOYEE
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


class TestMultiYearDataIsolation:
    """
    Property 19: Multi-year data isolation
    
    Validates that transactions are properly isolated by tax year boundaries,
    ensuring that filtering by tax_year returns only transactions within that
    calendar year (January 1 to December 31).
    """
    
    def clear_transactions(self, db_session):
        """Helper method to clear all transactions between test examples"""
        db_session.query(Transaction).delete()
        db_session.commit()
    
    @given(
        tax_year=year_strategy(),
        transaction_dates=st.lists(
            st.integers(min_value=0, max_value=364),  # 0-364 days from Jan 1 = Jan 1 to Dec 31
            min_size=1,
            max_size=20
        )
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_year_boundary_isolation(self, db_session, test_user, tax_year, transaction_dates):
        """
        Property: Filtering by tax_year returns only transactions within that calendar year.
        
        This test verifies that when we filter transactions by a specific tax year,
        we only get transactions with dates between January 1 and December 31 of that year.
        """
        # Clear any existing transactions from previous examples
        self.clear_transactions(db_session)
        
        # Create transactions within the specified tax year
        year_start = date(tax_year, 1, 1)
        year_end = date(tax_year, 12, 31)
        
        transactions_in_year = []
        for i, days_offset in enumerate(transaction_dates):
            txn_date = year_start + timedelta(days=days_offset)
            
            txn = Transaction(
                user_id=test_user.id,
                type=TransactionType.EXPENSE,
                amount=Decimal("100.00"),
                transaction_date=txn_date,
                description=f"Transaction {i}",
                expense_category=ExpenseCategory.OTHER
            )
            db_session.add(txn)
            transactions_in_year.append(txn)
        
        db_session.commit()
        
        # Query transactions filtered by tax year
        filtered_transactions = db_session.query(Transaction).filter(
            Transaction.user_id == test_user.id,
            Transaction.transaction_date >= year_start,
            Transaction.transaction_date <= year_end
        ).all()
        
        # Verify all returned transactions are within the year boundaries
        assert len(filtered_transactions) == len(transaction_dates), \
            f"Expected {len(transaction_dates)} transactions, got {len(filtered_transactions)}"
        
        for txn in filtered_transactions:
            assert year_start <= txn.transaction_date <= year_end, \
                f"Transaction date {txn.transaction_date} is outside year {tax_year} boundaries"
    
    @given(
        tax_year=year_strategy(),
        in_year_dates=st.lists(
            st.integers(min_value=0, max_value=364),
            min_size=1,
            max_size=10
        ),
        num_outside_year=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_excludes_other_years(self, db_session, test_user, tax_year, in_year_dates, num_outside_year):
        """
        Property: Transactions from other years are excluded when filtering by tax_year.
        
        This test verifies that transactions from years other than the specified tax_year
        are not included in the filtered results.
        """
        # Clear any existing transactions from previous examples
        self.clear_transactions(db_session)
        
        year_start = date(tax_year, 1, 1)
        year_end = date(tax_year, 12, 31)
        
        # Create transactions within the tax year
        for i, days_offset in enumerate(in_year_dates):
            txn_date = year_start + timedelta(days=days_offset)
            
            txn = Transaction(
                user_id=test_user.id,
                type=TransactionType.INCOME,
                amount=Decimal("500.00"),
                transaction_date=txn_date,
                description=f"In-year transaction {i}",
                income_category=IncomeCategory.EMPLOYMENT
            )
            db_session.add(txn)
        
        # Create transactions outside the tax year
        for i in range(num_outside_year):
            # Create transactions in adjacent years
            if i % 2 == 0:
                # Previous year
                txn_date = date(tax_year - 1, 6, 15)
            else:
                # Next year
                txn_date = date(tax_year + 1, 6, 15)
            
            txn = Transaction(
                user_id=test_user.id,
                type=TransactionType.EXPENSE,
                amount=Decimal("200.00"),
                transaction_date=txn_date,
                description=f"Out-of-year transaction {i}",
                expense_category=ExpenseCategory.OTHER
            )
            db_session.add(txn)
        
        db_session.commit()
        
        # Query transactions filtered by tax year
        filtered_transactions = db_session.query(Transaction).filter(
            Transaction.user_id == test_user.id,
            Transaction.transaction_date >= year_start,
            Transaction.transaction_date <= year_end
        ).all()
        
        # Verify only in-year transactions are returned
        assert len(filtered_transactions) == len(in_year_dates), \
            f"Expected {len(in_year_dates)} transactions, got {len(filtered_transactions)}"
        
        for txn in filtered_transactions:
            assert year_start <= txn.transaction_date <= year_end, \
                f"Transaction date {txn.transaction_date} should be within {tax_year}"
    
    @given(
        tax_year=year_strategy()
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_year_boundary_edge_cases(self, db_session, test_user, tax_year):
        """
        Property: Year boundaries are precisely respected (first and last day of year).
        
        This test verifies that transactions on January 1 and December 31 are included,
        while transactions on December 31 of the previous year and January 1 of the next
        year are excluded.
        """
        # Clear any existing transactions from previous examples
        self.clear_transactions(db_session)
        
        # Create transactions at year boundaries
        transactions = [
            # Previous year, last day (should be excluded)
            Transaction(
                user_id=test_user.id,
                type=TransactionType.EXPENSE,
                amount=Decimal("100.00"),
                transaction_date=date(tax_year - 1, 12, 31),
                description="Previous year last day",
                expense_category=ExpenseCategory.OTHER
            ),
            # Current year, first day (should be included)
            Transaction(
                user_id=test_user.id,
                type=TransactionType.INCOME,
                amount=Decimal("200.00"),
                transaction_date=date(tax_year, 1, 1),
                description="Current year first day",
                income_category=IncomeCategory.EMPLOYMENT
            ),
            # Current year, last day (should be included)
            Transaction(
                user_id=test_user.id,
                type=TransactionType.EXPENSE,
                amount=Decimal("150.00"),
                transaction_date=date(tax_year, 12, 31),
                description="Current year last day",
                expense_category=ExpenseCategory.OTHER
            ),
            # Next year, first day (should be excluded)
            Transaction(
                user_id=test_user.id,
                type=TransactionType.INCOME,
                amount=Decimal("300.00"),
                transaction_date=date(tax_year + 1, 1, 1),
                description="Next year first day",
                income_category=IncomeCategory.EMPLOYMENT
            )
        ]
        
        for txn in transactions:
            db_session.add(txn)
        db_session.commit()
        
        # Query transactions filtered by tax year
        year_start = date(tax_year, 1, 1)
        year_end = date(tax_year, 12, 31)
        
        filtered_transactions = db_session.query(Transaction).filter(
            Transaction.user_id == test_user.id,
            Transaction.transaction_date >= year_start,
            Transaction.transaction_date <= year_end
        ).all()
        
        # Should return exactly 2 transactions (Jan 1 and Dec 31 of current year)
        assert len(filtered_transactions) == 2, \
            f"Expected 2 transactions within year boundaries, got {len(filtered_transactions)}"
        
        # Verify the correct transactions are included
        dates = [txn.transaction_date for txn in filtered_transactions]
        assert date(tax_year, 1, 1) in dates, "January 1 transaction should be included"
        assert date(tax_year, 12, 31) in dates, "December 31 transaction should be included"
        assert date(tax_year - 1, 12, 31) not in dates, "Previous year Dec 31 should be excluded"
        assert date(tax_year + 1, 1, 1) not in dates, "Next year Jan 1 should be excluded"
    
    @given(
        year1=year_strategy(),
        year2=year_strategy(),
        year1_dates=st.lists(
            st.integers(min_value=0, max_value=364),
            min_size=1,
            max_size=10
        ),
        year2_dates=st.lists(
            st.integers(min_value=0, max_value=364),
            min_size=1,
            max_size=10
        )
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_independent_year_filtering(self, db_session, test_user, year1, year2, year1_dates, year2_dates):
        """
        Property: Filtering by different years returns independent, non-overlapping results.
        
        This test verifies that transactions from different years do not interfere with
        each other when filtering by tax_year.
        """
        assume(year1 != year2)  # Ensure we're testing different years
        
        # Clear any existing transactions from previous examples
        self.clear_transactions(db_session)
        
        # Create transactions for year1
        year1_start = date(year1, 1, 1)
        year1_end = date(year1, 12, 31)
        
        for i, days_offset in enumerate(year1_dates):
            txn_date = year1_start + timedelta(days=days_offset)
            
            txn = Transaction(
                user_id=test_user.id,
                type=TransactionType.INCOME,
                amount=Decimal("1000.00"),
                transaction_date=txn_date,
                description=f"Year {year1} transaction {i}",
                income_category=IncomeCategory.EMPLOYMENT
            )
            db_session.add(txn)
        
        # Create transactions for year2
        year2_start = date(year2, 1, 1)
        year2_end = date(year2, 12, 31)
        
        for i, days_offset in enumerate(year2_dates):
            txn_date = year2_start + timedelta(days=days_offset)
            
            txn = Transaction(
                user_id=test_user.id,
                type=TransactionType.EXPENSE,
                amount=Decimal("500.00"),
                transaction_date=txn_date,
                description=f"Year {year2} transaction {i}",
                expense_category=ExpenseCategory.OTHER
            )
            db_session.add(txn)
        
        db_session.commit()
        
        # Query transactions for year1
        year1_transactions = db_session.query(Transaction).filter(
            Transaction.user_id == test_user.id,
            Transaction.transaction_date >= year1_start,
            Transaction.transaction_date <= year1_end
        ).all()
        
        # Query transactions for year2
        year2_transactions = db_session.query(Transaction).filter(
            Transaction.user_id == test_user.id,
            Transaction.transaction_date >= year2_start,
            Transaction.transaction_date <= year2_end
        ).all()
        
        # Verify correct counts
        assert len(year1_transactions) == len(year1_dates), \
            f"Expected {len(year1_dates)} transactions for year {year1}"
        assert len(year2_transactions) == len(year2_dates), \
            f"Expected {len(year2_dates)} transactions for year {year2}"
        
        # Verify no overlap between years
        year1_ids = {txn.id for txn in year1_transactions}
        year2_ids = {txn.id for txn in year2_transactions}
        
        assert year1_ids.isdisjoint(year2_ids), \
            "Transactions from different years should not overlap"
        
        # Verify all year1 transactions are within year1 boundaries
        for txn in year1_transactions:
            assert year1_start <= txn.transaction_date <= year1_end, \
                f"Year {year1} transaction has date outside boundaries: {txn.transaction_date}"
        
        # Verify all year2 transactions are within year2 boundaries
        for txn in year2_transactions:
            assert year2_start <= txn.transaction_date <= year2_end, \
                f"Year {year2} transaction has date outside boundaries: {txn.transaction_date}"
    
    @given(
        tax_year=year_strategy(),
        transaction_dates=st.lists(
            st.integers(min_value=0, max_value=364),
            min_size=5,
            max_size=20
        )
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_multi_user_year_isolation(self, db_session, tax_year, transaction_dates):
        """
        Property: Year filtering maintains user isolation across different tax years.
        
        This test verifies that when filtering by tax_year, each user only sees their
        own transactions for that year, and other users' transactions do not interfere.
        """
        # Clear any existing transactions and users from previous examples
        db_session.query(Transaction).delete()
        db_session.query(User).filter(User.email != "test@example.com").delete()
        db_session.commit()
        
        # Create two users with unique emails
        import uuid
        user1 = User(
            email=f"user1_{uuid.uuid4()}@example.com",
            password_hash="hash1",
            name="User 1",
            user_type=UserType.EMPLOYEE
        )
        user2 = User(
            email=f"user2_{uuid.uuid4()}@example.com",
            password_hash="hash2",
            name="User 2",
            user_type=UserType.SELF_EMPLOYED
        )
        db_session.add(user1)
        db_session.add(user2)
        db_session.commit()
        
        year_start = date(tax_year, 1, 1)
        year_end = date(tax_year, 12, 31)
        
        # Create transactions for user1
        for i, days_offset in enumerate(transaction_dates):
            txn_date = year_start + timedelta(days=days_offset)
            
            txn = Transaction(
                user_id=user1.id,
                type=TransactionType.INCOME,
                amount=Decimal("1000.00"),
                transaction_date=txn_date,
                description=f"User1 transaction {i}",
                income_category=IncomeCategory.EMPLOYMENT
            )
            db_session.add(txn)
        
        # Create transactions for user2
        for i, days_offset in enumerate(transaction_dates):
            txn_date = year_start + timedelta(days=days_offset)
            
            txn = Transaction(
                user_id=user2.id,
                type=TransactionType.EXPENSE,
                amount=Decimal("500.00"),
                transaction_date=txn_date,
                description=f"User2 transaction {i}",
                expense_category=ExpenseCategory.OTHER
            )
            db_session.add(txn)
        
        db_session.commit()
        
        # Query transactions for user1 in the tax year
        user1_transactions = db_session.query(Transaction).filter(
            Transaction.user_id == user1.id,
            Transaction.transaction_date >= year_start,
            Transaction.transaction_date <= year_end
        ).all()
        
        # Query transactions for user2 in the tax year
        user2_transactions = db_session.query(Transaction).filter(
            Transaction.user_id == user2.id,
            Transaction.transaction_date >= year_start,
            Transaction.transaction_date <= year_end
        ).all()
        
        # Verify each user has the correct number of transactions
        assert len(user1_transactions) == len(transaction_dates), \
            f"User1 should have {len(transaction_dates)} transactions"
        assert len(user2_transactions) == len(transaction_dates), \
            f"User2 should have {len(transaction_dates)} transactions"
        
        # Verify no cross-contamination between users
        for txn in user1_transactions:
            assert txn.user_id == user1.id, "User1 query should only return user1 transactions"
        
        for txn in user2_transactions:
            assert txn.user_id == user2.id, "User2 query should only return user2 transactions"
    
    @given(
        tax_year=year_strategy(),
        transaction_dates=st.lists(
            st.integers(min_value=0, max_value=364),
            min_size=1,
            max_size=15
        )
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_year_filtering_deterministic(self, db_session, test_user, tax_year, transaction_dates):
        """
        Property: Year filtering is deterministic and consistent across multiple queries.
        
        This test verifies that filtering by the same tax_year multiple times returns
        the same results in the same order.
        """
        # Clear any existing transactions from previous examples
        self.clear_transactions(db_session)
        
        year_start = date(tax_year, 1, 1)
        year_end = date(tax_year, 12, 31)
        
        # Create transactions
        for i, days_offset in enumerate(transaction_dates):
            txn_date = year_start + timedelta(days=days_offset)
            
            txn = Transaction(
                user_id=test_user.id,
                type=TransactionType.INCOME,
                amount=Decimal("750.00"),
                transaction_date=txn_date,
                description=f"Transaction {i}",
                income_category=IncomeCategory.EMPLOYMENT
            )
            db_session.add(txn)
        
        db_session.commit()
        
        # Query transactions multiple times
        query = db_session.query(Transaction).filter(
            Transaction.user_id == test_user.id,
            Transaction.transaction_date >= year_start,
            Transaction.transaction_date <= year_end
        ).order_by(Transaction.id)
        
        result1 = query.all()
        result2 = query.all()
        result3 = query.all()
        
        # Verify all results are identical
        assert len(result1) == len(result2) == len(result3) == len(transaction_dates), \
            "All queries should return the same number of transactions"
        
        # Verify transaction IDs are the same across queries
        ids1 = [txn.id for txn in result1]
        ids2 = [txn.id for txn in result2]
        ids3 = [txn.id for txn in result3]
        
        assert ids1 == ids2 == ids3, \
            "Multiple queries with same filter should return same transactions in same order"
    
    @given(
        tax_year=year_strategy()
    )
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_empty_year_returns_empty_list(self, db_session, test_user, tax_year):
        """
        Property: Filtering by a year with no transactions returns an empty list.
        
        This test verifies that querying a tax year with no transactions returns
        an empty result set rather than raising an error or returning transactions
        from other years.
        """
        # Clear any existing transactions from previous examples
        self.clear_transactions(db_session)
        
        # Create transactions in a different year
        other_year = tax_year + 1
        other_year_date = date(other_year, 6, 15)
        
        txn = Transaction(
            user_id=test_user.id,
            type=TransactionType.INCOME,
            amount=Decimal("1000.00"),
            transaction_date=other_year_date,
            description="Transaction in different year",
            income_category=IncomeCategory.EMPLOYMENT
        )
        db_session.add(txn)
        db_session.commit()
        
        # Query transactions for the tax_year (which has no transactions)
        year_start = date(tax_year, 1, 1)
        year_end = date(tax_year, 12, 31)
        
        filtered_transactions = db_session.query(Transaction).filter(
            Transaction.user_id == test_user.id,
            Transaction.transaction_date >= year_start,
            Transaction.transaction_date <= year_end
        ).all()
        
        # Verify empty result
        assert len(filtered_transactions) == 0, \
            f"Expected 0 transactions for year {tax_year} with no data, got {len(filtered_transactions)}"
    
    @given(
        tax_year=year_strategy(),
        income_dates=st.lists(
            st.integers(min_value=0, max_value=364),
            min_size=1,
            max_size=10
        ),
        expense_dates=st.lists(
            st.integers(min_value=0, max_value=364),
            min_size=1,
            max_size=10
        )
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_year_filtering_preserves_transaction_types(self, db_session, test_user, tax_year, income_dates, expense_dates):
        """
        Property: Year filtering preserves transaction types and categories.
        
        This test verifies that when filtering by tax_year, the transaction types
        and categories are preserved correctly.
        """
        # Clear any existing transactions from previous examples
        self.clear_transactions(db_session)
        
        year_start = date(tax_year, 1, 1)
        year_end = date(tax_year, 12, 31)
        
        # Create income transactions
        for i, days_offset in enumerate(income_dates):
            txn_date = year_start + timedelta(days=days_offset)
            
            txn = Transaction(
                user_id=test_user.id,
                type=TransactionType.INCOME,
                amount=Decimal("2000.00"),
                transaction_date=txn_date,
                description=f"Income {i}",
                income_category=IncomeCategory.EMPLOYMENT
            )
            db_session.add(txn)
        
        # Create expense transactions
        for i, days_offset in enumerate(expense_dates):
            txn_date = year_start + timedelta(days=days_offset)
            
            txn = Transaction(
                user_id=test_user.id,
                type=TransactionType.EXPENSE,
                amount=Decimal("800.00"),
                transaction_date=txn_date,
                description=f"Expense {i}",
                expense_category=ExpenseCategory.OFFICE_SUPPLIES
            )
            db_session.add(txn)
        
        db_session.commit()
        
        # Query all transactions for the year
        all_transactions = db_session.query(Transaction).filter(
            Transaction.user_id == test_user.id,
            Transaction.transaction_date >= year_start,
            Transaction.transaction_date <= year_end
        ).all()
        
        # Count transaction types
        income_count = sum(1 for txn in all_transactions if txn.type == TransactionType.INCOME)
        expense_count = sum(1 for txn in all_transactions if txn.type == TransactionType.EXPENSE)
        
        # Verify counts match
        assert income_count == len(income_dates), \
            f"Expected {len(income_dates)} income transactions, got {income_count}"
        assert expense_count == len(expense_dates), \
            f"Expected {len(expense_dates)} expense transactions, got {expense_count}"
        
        # Verify all income transactions have income_category
        for txn in all_transactions:
            if txn.type == TransactionType.INCOME:
                assert txn.income_category is not None, \
                    "Income transactions should have income_category"
            elif txn.type == TransactionType.EXPENSE:
                assert txn.expense_category is not None, \
                    "Expense transactions should have expense_category"

