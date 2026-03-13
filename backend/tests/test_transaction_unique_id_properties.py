"""Property-based tests for transaction unique identifier

**Validates: Requirements 1.7**
- Requirement 1.7: THE Tax_System SHALL generate unique identifiers for each transaction
"""
import os
import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

import pytest
from hypothesis import given, strategies as st, assume, settings
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.base import Base
from app.models.transaction import Transaction, TransactionType, IncomeCategory, ExpenseCategory
from app.models.user import User, UserType


# Test database setup
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="function")
def test_db():
    """Create a fresh in-memory database for each test"""
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def test_user(test_db):
    """Create a test user"""
    user = User(
        email="test@example.com",
        password_hash="hashed_password",
        name="Test User",
        user_type=UserType.EMPLOYEE,
        family_info={},
        commuting_info={}
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


# Hypothesis strategies for generating test data
def transaction_strategy(user_id: int):
    """Strategy for generating valid transaction data"""
    return st.builds(
        lambda type_val, amount, desc, txn_date: {
            "user_id": user_id,
            "type": type_val,
            "amount": Decimal(str(amount)),
            "description": desc,
            "transaction_date": txn_date,
            "income_category": IncomeCategory.EMPLOYMENT if type_val == TransactionType.INCOME else None,
            "expense_category": ExpenseCategory.OTHER if type_val == TransactionType.EXPENSE else None,
        },
        type_val=st.sampled_from([TransactionType.INCOME, TransactionType.EXPENSE]),
        amount=st.floats(min_value=0.01, max_value=100000.0).map(lambda x: round(x, 2)),
        desc=st.text(min_size=1, max_size=100, alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))),
        txn_date=st.dates(
            min_value=date(2020, 1, 1),
            max_value=date(2030, 12, 31)
        )
    )


class TestTransactionUniqueIdentifierProperties:
    """Property-based tests for transaction unique identifier generation"""
    
    @given(st.integers(min_value=1, max_value=100))
    @settings(max_examples=50)
    def test_property_2_all_transaction_ids_are_unique(self, num_transactions: int, test_db, test_user):
        """
        **Validates: Requirements 1.7**
        
        Property 2: Transaction unique identifier
        
        For any collection of transactions, all system-generated transaction IDs must be unique.
        No two different transactions should have the same ID.
        """
        # Generate multiple transactions
        transactions = []
        
        for i in range(num_transactions):
            txn = Transaction(
                user_id=test_user.id,
                type=TransactionType.INCOME if i % 2 == 0 else TransactionType.EXPENSE,
                amount=Decimal(str(100.00 + i)),
                description=f"Transaction {i}",
                transaction_date=date(2026, 1, 1) + timedelta(days=i),
                income_category=IncomeCategory.EMPLOYMENT if i % 2 == 0 else None,
                expense_category=ExpenseCategory.OTHER if i % 2 == 1 else None
            )
            test_db.add(txn)
        
        # Commit all transactions
        test_db.commit()
        
        # Retrieve all transactions
        all_transactions = test_db.query(Transaction).filter(
            Transaction.user_id == test_user.id
        ).all()
        
        # Extract all IDs
        transaction_ids = [txn.id for txn in all_transactions]
        
        # Verify all IDs are unique
        assert len(transaction_ids) == len(set(transaction_ids)), \
            f"Transaction IDs are not unique! Found {len(transaction_ids)} transactions but only {len(set(transaction_ids))} unique IDs"
        
        # Verify we have the expected number of transactions
        assert len(transaction_ids) == num_transactions, \
            f"Expected {num_transactions} transactions but found {len(transaction_ids)}"
    
    @given(
        st.lists(
            st.tuples(
                st.sampled_from([TransactionType.INCOME, TransactionType.EXPENSE]),
                st.floats(min_value=0.01, max_value=100000.0).map(lambda x: round(x, 2)),
                st.text(min_size=1, max_size=100, alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))),
                st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31))
            ),
            min_size=2,
            max_size=50
        )
    )
    @settings(max_examples=50)
    def test_property_2_identical_transactions_get_different_ids(
        self,
        transaction_data_list,
        test_db,
        test_user
    ):
        """
        **Validates: Requirements 1.7**
        
        Property 2: Transaction unique identifier
        
        Even when creating transactions with identical data (same amount, date, description),
        each transaction should receive a unique ID.
        """
        transactions = []
        
        for txn_type, amount, description, txn_date in transaction_data_list:
            txn = Transaction(
                user_id=test_user.id,
                type=txn_type,
                amount=Decimal(str(amount)),
                description=description,
                transaction_date=txn_date,
                income_category=IncomeCategory.EMPLOYMENT if txn_type == TransactionType.INCOME else None,
                expense_category=ExpenseCategory.OTHER if txn_type == TransactionType.EXPENSE else None
            )
            test_db.add(txn)
            transactions.append(txn)
        
        # Commit all transactions
        test_db.commit()
        
        # Refresh to get IDs
        for txn in transactions:
            test_db.refresh(txn)
        
        # Extract all IDs
        transaction_ids = [txn.id for txn in transactions]
        
        # Verify all IDs are unique
        assert len(transaction_ids) == len(set(transaction_ids)), \
            f"Duplicate IDs found! IDs: {transaction_ids}"
        
        # Verify all IDs are not None
        assert all(txn_id is not None for txn_id in transaction_ids), \
            "Some transactions have None as ID"
        
        # Verify all IDs are positive integers
        assert all(isinstance(txn_id, int) and txn_id > 0 for txn_id in transaction_ids), \
            f"All IDs should be positive integers, got: {transaction_ids}"
    
    @given(st.integers(min_value=2, max_value=20))
    @settings(max_examples=30)
    def test_property_2_ids_are_sequential_and_unique(
        self,
        num_transactions: int,
        test_db,
        test_user
    ):
        """
        **Validates: Requirements 1.7**
        
        Property 2: Transaction unique identifier
        
        Transaction IDs should be sequential (auto-incrementing) and unique.
        Each new transaction should get an ID greater than all previous IDs.
        """
        previous_max_id = 0
        transaction_ids = []
        
        for i in range(num_transactions):
            txn = Transaction(
                user_id=test_user.id,
                type=TransactionType.INCOME,
                amount=Decimal("100.00"),
                description=f"Test transaction {i}",
                transaction_date=date(2026, 1, 1),
                income_category=IncomeCategory.EMPLOYMENT
            )
            test_db.add(txn)
            test_db.commit()
            test_db.refresh(txn)
            
            # Verify ID is greater than previous max
            assert txn.id > previous_max_id, \
                f"Transaction ID {txn.id} is not greater than previous max {previous_max_id}"
            
            # Verify ID is not in the list of previous IDs
            assert txn.id not in transaction_ids, \
                f"Transaction ID {txn.id} already exists in {transaction_ids}"
            
            transaction_ids.append(txn.id)
            previous_max_id = txn.id
        
        # Final verification: all IDs are unique
        assert len(transaction_ids) == len(set(transaction_ids)), \
            f"Duplicate IDs found in final list: {transaction_ids}"
    
    @given(
        st.integers(min_value=1, max_value=20),
        st.integers(min_value=1, max_value=20)
    )
    @settings(max_examples=30)
    def test_property_2_multiple_users_have_unique_transaction_ids(
        self,
        num_user1_transactions: int,
        num_user2_transactions: int,
        test_db
    ):
        """
        **Validates: Requirements 1.7**
        
        Property 2: Transaction unique identifier
        
        Transaction IDs should be globally unique across all users, not just unique per user.
        """
        # Create two users
        user1 = User(
            email="user1@example.com",
            password_hash="hash1",
            name="User 1",
            user_type=UserType.EMPLOYEE
        )
        user2 = User(
            email="user2@example.com",
            password_hash="hash2",
            name="User 2",
            user_type=UserType.SELF_EMPLOYED
        )
        test_db.add(user1)
        test_db.add(user2)
        test_db.commit()
        test_db.refresh(user1)
        test_db.refresh(user2)
        
        all_transaction_ids = []
        
        # Create transactions for user 1
        for i in range(num_user1_transactions):
            txn = Transaction(
                user_id=user1.id,
                type=TransactionType.INCOME,
                amount=Decimal("100.00"),
                description=f"User1 transaction {i}",
                transaction_date=date(2026, 1, 1),
                income_category=IncomeCategory.EMPLOYMENT
            )
            test_db.add(txn)
            test_db.commit()
            test_db.refresh(txn)
            all_transaction_ids.append(txn.id)
        
        # Create transactions for user 2
        for i in range(num_user2_transactions):
            txn = Transaction(
                user_id=user2.id,
                type=TransactionType.EXPENSE,
                amount=Decimal("50.00"),
                description=f"User2 transaction {i}",
                transaction_date=date(2026, 1, 1),
                expense_category=ExpenseCategory.OTHER
            )
            test_db.add(txn)
            test_db.commit()
            test_db.refresh(txn)
            all_transaction_ids.append(txn.id)
        
        # Verify all IDs are globally unique
        assert len(all_transaction_ids) == len(set(all_transaction_ids)), \
            f"Transaction IDs are not globally unique across users! IDs: {all_transaction_ids}"
        
        # Verify we have the expected total number of transactions
        total_expected = num_user1_transactions + num_user2_transactions
        assert len(all_transaction_ids) == total_expected, \
            f"Expected {total_expected} total transactions but found {len(all_transaction_ids)}"
    
    @given(st.integers(min_value=1, max_value=50))
    @settings(max_examples=30)
    def test_property_2_deleted_ids_are_not_reused(
        self,
        num_transactions: int,
        test_db,
        test_user
    ):
        """
        **Validates: Requirements 1.7**
        
        Property 2: Transaction unique identifier
        
        When transactions are deleted, their IDs should not be reused for new transactions.
        This ensures historical integrity and prevents ID collision.
        """
        # Create initial transactions
        initial_ids = []
        for i in range(num_transactions):
            txn = Transaction(
                user_id=test_user.id,
                type=TransactionType.INCOME,
                amount=Decimal("100.00"),
                description=f"Transaction {i}",
                transaction_date=date(2026, 1, 1),
                income_category=IncomeCategory.EMPLOYMENT
            )
            test_db.add(txn)
            test_db.commit()
            test_db.refresh(txn)
            initial_ids.append(txn.id)
        
        # Delete all transactions
        test_db.query(Transaction).filter(
            Transaction.user_id == test_user.id
        ).delete()
        test_db.commit()
        
        # Create new transactions
        new_ids = []
        for i in range(num_transactions):
            txn = Transaction(
                user_id=test_user.id,
                type=TransactionType.EXPENSE,
                amount=Decimal("50.00"),
                description=f"New transaction {i}",
                transaction_date=date(2026, 1, 1),
                expense_category=ExpenseCategory.OTHER
            )
            test_db.add(txn)
            test_db.commit()
            test_db.refresh(txn)
            new_ids.append(txn.id)
        
        # Verify new IDs are different from initial IDs
        # (IDs should continue incrementing, not reuse deleted IDs)
        overlapping_ids = set(initial_ids) & set(new_ids)
        assert len(overlapping_ids) == 0, \
            f"Deleted IDs were reused! Overlapping IDs: {overlapping_ids}"
        
        # Verify all new IDs are greater than all initial IDs
        max_initial_id = max(initial_ids)
        min_new_id = min(new_ids)
        assert min_new_id > max_initial_id, \
            f"New IDs should be greater than deleted IDs. Max initial: {max_initial_id}, Min new: {min_new_id}"
    
    @given(st.integers(min_value=1, max_value=30))
    @settings(max_examples=30)
    def test_property_2_concurrent_inserts_maintain_uniqueness(
        self,
        num_transactions: int,
        test_db,
        test_user
    ):
        """
        **Validates: Requirements 1.7**
        
        Property 2: Transaction unique identifier
        
        Even when transactions are created in rapid succession (simulating concurrent inserts),
        all IDs should remain unique.
        """
        transactions = []
        
        # Create all transaction objects first (simulating concurrent preparation)
        for i in range(num_transactions):
            txn = Transaction(
                user_id=test_user.id,
                type=TransactionType.INCOME if i % 2 == 0 else TransactionType.EXPENSE,
                amount=Decimal(str(100.00 + i * 10)),
                description=f"Concurrent transaction {i}",
                transaction_date=date(2026, 1, 1) + timedelta(days=i % 30),
                income_category=IncomeCategory.EMPLOYMENT if i % 2 == 0 else None,
                expense_category=ExpenseCategory.OTHER if i % 2 == 1 else None
            )
            transactions.append(txn)
        
        # Add all at once (simulating bulk insert)
        test_db.add_all(transactions)
        test_db.commit()
        
        # Refresh all to get IDs
        for txn in transactions:
            test_db.refresh(txn)
        
        # Extract IDs
        transaction_ids = [txn.id for txn in transactions]
        
        # Verify uniqueness
        assert len(transaction_ids) == len(set(transaction_ids)), \
            f"Concurrent inserts resulted in duplicate IDs! IDs: {transaction_ids}"
        
        # Verify all IDs are valid
        assert all(txn_id is not None and txn_id > 0 for txn_id in transaction_ids), \
            f"Some IDs are invalid: {transaction_ids}"
