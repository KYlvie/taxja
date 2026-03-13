"""
Tests for multi-year data isolation functionality.

Requirements tested:
- 10.1: THE Tax_System SHALL 允许用户在不同 Tax_Year 之间切换
- 10.2: THE Tax_System SHALL 为每个 Tax_Year 独立存储交易记录和税务计算结果
"""
import pytest
from datetime import date
from decimal import Decimal
from sqlalchemy.orm import Session
from app.models.transaction import Transaction, TransactionType, IncomeCategory, ExpenseCategory
from app.models.user import User


@pytest.fixture
def test_user(db: Session) -> User:
    """Create a test user"""
    user = User(
        email="test@example.com",
        hashed_password="hashed_password",
        full_name="Test User",
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def multi_year_transactions(db: Session, test_user: User):
    """Create transactions across multiple years"""
    transactions = [
        # 2024 transactions
        Transaction(
            user_id=test_user.id,
            type=TransactionType.INCOME,
            amount=Decimal("3000.00"),
            transaction_date=date(2024, 1, 15),
            description="2024 January Income",
            income_category=IncomeCategory.EMPLOYMENT
        ),
        Transaction(
            user_id=test_user.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("500.00"),
            transaction_date=date(2024, 6, 20),
            description="2024 June Expense",
            expense_category=ExpenseCategory.OFFICE_SUPPLIES
        ),
        Transaction(
            user_id=test_user.id,
            type=TransactionType.INCOME,
            amount=Decimal("3500.00"),
            transaction_date=date(2024, 12, 31),
            description="2024 December Income",
            income_category=IncomeCategory.EMPLOYMENT
        ),
        
        # 2025 transactions
        Transaction(
            user_id=test_user.id,
            type=TransactionType.INCOME,
            amount=Decimal("4000.00"),
            transaction_date=date(2025, 1, 1),
            description="2025 January Income",
            income_category=IncomeCategory.EMPLOYMENT
        ),
        Transaction(
            user_id=test_user.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("800.00"),
            transaction_date=date(2025, 7, 15),
            description="2025 July Expense",
            expense_category=ExpenseCategory.EQUIPMENT
        ),
        Transaction(
            user_id=test_user.id,
            type=TransactionType.INCOME,
            amount=Decimal("4200.00"),
            transaction_date=date(2025, 12, 30),
            description="2025 December Income",
            income_category=IncomeCategory.SELF_EMPLOYMENT
        ),
        
        # 2026 transactions
        Transaction(
            user_id=test_user.id,
            type=TransactionType.INCOME,
            amount=Decimal("5000.00"),
            transaction_date=date(2026, 1, 1),
            description="2026 January Income",
            income_category=IncomeCategory.EMPLOYMENT
        ),
        Transaction(
            user_id=test_user.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("1000.00"),
            transaction_date=date(2026, 3, 10),
            description="2026 March Expense",
            expense_category=ExpenseCategory.TRAVEL
        ),
        Transaction(
            user_id=test_user.id,
            type=TransactionType.INCOME,
            amount=Decimal("5500.00"),
            transaction_date=date(2026, 12, 31),
            description="2026 December Income",
            income_category=IncomeCategory.RENTAL
        ),
    ]
    
    for txn in transactions:
        db.add(txn)
    
    db.commit()
    return transactions


class TestMultiYearDataIsolation:
    """Test multi-year data isolation functionality"""
    
    def test_filter_by_tax_year_2024(self, db: Session, test_user: User, multi_year_transactions):
        """Test filtering transactions by tax year 2024"""
        # Query transactions for 2024
        year_start = date(2024, 1, 1)
        year_end = date(2024, 12, 31)
        
        transactions = db.query(Transaction).filter(
            Transaction.user_id == test_user.id,
            Transaction.transaction_date >= year_start,
            Transaction.transaction_date <= year_end
        ).all()
        
        # Should have exactly 3 transactions from 2024
        assert len(transactions) == 3
        
        # Verify all transactions are from 2024
        for txn in transactions:
            assert txn.transaction_date.year == 2024
        
        # Verify specific transactions
        descriptions = [txn.description for txn in transactions]
        assert "2024 January Income" in descriptions
        assert "2024 June Expense" in descriptions
        assert "2024 December Income" in descriptions
    
    def test_filter_by_tax_year_2025(self, db: Session, test_user: User, multi_year_transactions):
        """Test filtering transactions by tax year 2025"""
        year_start = date(2025, 1, 1)
        year_end = date(2025, 12, 31)
        
        transactions = db.query(Transaction).filter(
            Transaction.user_id == test_user.id,
            Transaction.transaction_date >= year_start,
            Transaction.transaction_date <= year_end
        ).all()
        
        # Should have exactly 3 transactions from 2025
        assert len(transactions) == 3
        
        # Verify all transactions are from 2025
        for txn in transactions:
            assert txn.transaction_date.year == 2025
        
        # Verify specific transactions
        descriptions = [txn.description for txn in transactions]
        assert "2025 January Income" in descriptions
        assert "2025 July Expense" in descriptions
        assert "2025 December Income" in descriptions
    
    def test_filter_by_tax_year_2026(self, db: Session, test_user: User, multi_year_transactions):
        """Test filtering transactions by tax year 2026"""
        year_start = date(2026, 1, 1)
        year_end = date(2026, 12, 31)
        
        transactions = db.query(Transaction).filter(
            Transaction.user_id == test_user.id,
            Transaction.transaction_date >= year_start,
            Transaction.transaction_date <= year_end
        ).all()
        
        # Should have exactly 3 transactions from 2026
        assert len(transactions) == 3
        
        # Verify all transactions are from 2026
        for txn in transactions:
            assert txn.transaction_date.year == 2026
        
        # Verify specific transactions
        descriptions = [txn.description for txn in transactions]
        assert "2026 January Income" in descriptions
        assert "2026 March Expense" in descriptions
        assert "2026 December Income" in descriptions
    
    def test_year_boundary_isolation_start(self, db: Session, test_user: User, multi_year_transactions):
        """Test that year boundaries are respected at year start (January 1)"""
        # Query for 2025 should include January 1, 2025
        year_start = date(2025, 1, 1)
        year_end = date(2025, 12, 31)
        
        transactions = db.query(Transaction).filter(
            Transaction.user_id == test_user.id,
            Transaction.transaction_date >= year_start,
            Transaction.transaction_date <= year_end
        ).all()
        
        # Should include the January 1, 2025 transaction
        jan_1_transactions = [txn for txn in transactions if txn.transaction_date == date(2025, 1, 1)]
        assert len(jan_1_transactions) == 1
        assert jan_1_transactions[0].description == "2025 January Income"
        
        # Should NOT include December 31, 2024
        dec_31_2024 = [txn for txn in transactions if txn.transaction_date == date(2024, 12, 31)]
        assert len(dec_31_2024) == 0
    
    def test_year_boundary_isolation_end(self, db: Session, test_user: User, multi_year_transactions):
        """Test that year boundaries are respected at year end (December 31)"""
        # Query for 2024 should include December 31, 2024
        year_start = date(2024, 1, 1)
        year_end = date(2024, 12, 31)
        
        transactions = db.query(Transaction).filter(
            Transaction.user_id == test_user.id,
            Transaction.transaction_date >= year_start,
            Transaction.transaction_date <= year_end
        ).all()
        
        # Should include the December 31, 2024 transaction
        dec_31_transactions = [txn for txn in transactions if txn.transaction_date == date(2024, 12, 31)]
        assert len(dec_31_transactions) == 1
        assert dec_31_transactions[0].description == "2024 December Income"
        
        # Should NOT include January 1, 2025
        jan_1_2025 = [txn for txn in transactions if txn.transaction_date == date(2025, 1, 1)]
        assert len(jan_1_2025) == 0
    
    def test_calculate_year_totals_2024(self, db: Session, test_user: User, multi_year_transactions):
        """Test calculating totals for a specific year (2024)"""
        year_start = date(2024, 1, 1)
        year_end = date(2024, 12, 31)
        
        # Get all 2024 transactions
        transactions = db.query(Transaction).filter(
            Transaction.user_id == test_user.id,
            Transaction.transaction_date >= year_start,
            Transaction.transaction_date <= year_end
        ).all()
        
        # Calculate totals
        total_income = sum(
            txn.amount for txn in transactions if txn.type == TransactionType.INCOME
        )
        total_expenses = sum(
            txn.amount for txn in transactions if txn.type == TransactionType.EXPENSE
        )
        
        # Verify totals
        assert total_income == Decimal("6500.00")  # 3000 + 3500
        assert total_expenses == Decimal("500.00")
        assert total_income - total_expenses == Decimal("6000.00")
    
    def test_calculate_year_totals_2025(self, db: Session, test_user: User, multi_year_transactions):
        """Test calculating totals for a specific year (2025)"""
        year_start = date(2025, 1, 1)
        year_end = date(2025, 12, 31)
        
        transactions = db.query(Transaction).filter(
            Transaction.user_id == test_user.id,
            Transaction.transaction_date >= year_start,
            Transaction.transaction_date <= year_end
        ).all()
        
        total_income = sum(
            txn.amount for txn in transactions if txn.type == TransactionType.INCOME
        )
        total_expenses = sum(
            txn.amount for txn in transactions if txn.type == TransactionType.EXPENSE
        )
        
        # Verify totals
        assert total_income == Decimal("8200.00")  # 4000 + 4200
        assert total_expenses == Decimal("800.00")
        assert total_income - total_expenses == Decimal("7400.00")
    
    def test_calculate_year_totals_2026(self, db: Session, test_user: User, multi_year_transactions):
        """Test calculating totals for a specific year (2026)"""
        year_start = date(2026, 1, 1)
        year_end = date(2026, 12, 31)
        
        transactions = db.query(Transaction).filter(
            Transaction.user_id == test_user.id,
            Transaction.transaction_date >= year_start,
            Transaction.transaction_date <= year_end
        ).all()
        
        total_income = sum(
            txn.amount for txn in transactions if txn.type == TransactionType.INCOME
        )
        total_expenses = sum(
            txn.amount for txn in transactions if txn.type == TransactionType.EXPENSE
        )
        
        # Verify totals
        assert total_income == Decimal("10500.00")  # 5000 + 5500
        assert total_expenses == Decimal("1000.00")
        assert total_income - total_expenses == Decimal("9500.00")
    
    def test_no_cross_year_contamination(self, db: Session, test_user: User, multi_year_transactions):
        """Test that filtering by one year doesn't include transactions from other years"""
        # Get 2025 transactions
        year_start = date(2025, 1, 1)
        year_end = date(2025, 12, 31)
        
        transactions_2025 = db.query(Transaction).filter(
            Transaction.user_id == test_user.id,
            Transaction.transaction_date >= year_start,
            Transaction.transaction_date <= year_end
        ).all()
        
        # Verify no 2024 or 2026 transactions are included
        for txn in transactions_2025:
            assert txn.transaction_date.year == 2025
            assert txn.transaction_date.year != 2024
            assert txn.transaction_date.year != 2026
    
    def test_empty_year_returns_no_transactions(self, db: Session, test_user: User, multi_year_transactions):
        """Test that querying a year with no transactions returns empty result"""
        # Query for 2023 (no transactions)
        year_start = date(2023, 1, 1)
        year_end = date(2023, 12, 31)
        
        transactions = db.query(Transaction).filter(
            Transaction.user_id == test_user.id,
            Transaction.transaction_date >= year_start,
            Transaction.transaction_date <= year_end
        ).all()
        
        assert len(transactions) == 0
    
    def test_multiple_users_year_isolation(self, db: Session, multi_year_transactions):
        """Test that year filtering respects user isolation"""
        # Create another user
        user2 = User(
            email="user2@example.com",
            hashed_password="hashed_password",
            full_name="User Two",
            is_active=True
        )
        db.add(user2)
        db.commit()
        
        # Add transactions for user2 in 2025
        txn_user2 = Transaction(
            user_id=user2.id,
            type=TransactionType.INCOME,
            amount=Decimal("9999.00"),
            transaction_date=date(2025, 6, 15),
            description="User2 2025 Income",
            income_category=IncomeCategory.EMPLOYMENT
        )
        db.add(txn_user2)
        db.commit()
        
        # Query user1's 2025 transactions
        test_user = db.query(User).filter(User.email == "test@example.com").first()
        year_start = date(2025, 1, 1)
        year_end = date(2025, 12, 31)
        
        user1_transactions = db.query(Transaction).filter(
            Transaction.user_id == test_user.id,
            Transaction.transaction_date >= year_start,
            Transaction.transaction_date <= year_end
        ).all()
        
        # Should only have user1's transactions
        assert len(user1_transactions) == 3
        for txn in user1_transactions:
            assert txn.user_id == test_user.id
            assert "User2" not in txn.description
