"""
API tests for multi-year data isolation functionality.

Tests the tax_year query parameter in the GET /api/v1/transactions endpoint.
"""
import pytest
from datetime import date
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.models.transaction import Transaction, TransactionType, IncomeCategory, ExpenseCategory
from app.models.user import User
from app.core.security import create_access_token


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


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
def auth_headers(test_user: User):
    """Create authentication headers"""
    access_token = create_access_token(subject=test_user.email)
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
def multi_year_transactions(db: Session, test_user: User):
    """Create transactions across multiple years"""
    transactions = [
        # 2024
        Transaction(
            user_id=test_user.id,
            type=TransactionType.INCOME,
            amount=Decimal("1000.00"),
            transaction_date=date(2024, 3, 15),
            description="2024 Q1 Income",
            income_category=IncomeCategory.EMPLOYMENT
        ),
        Transaction(
            user_id=test_user.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("200.00"),
            transaction_date=date(2024, 9, 20),
            description="2024 Q3 Expense",
            expense_category=ExpenseCategory.OFFICE_SUPPLIES
        ),
        
        # 2025
        Transaction(
            user_id=test_user.id,
            type=TransactionType.INCOME,
            amount=Decimal("2000.00"),
            transaction_date=date(2025, 2, 10),
            description="2025 Q1 Income",
            income_category=IncomeCategory.SELF_EMPLOYMENT
        ),
        Transaction(
            user_id=test_user.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("300.00"),
            transaction_date=date(2025, 8, 5),
            description="2025 Q3 Expense",
            expense_category=ExpenseCategory.EQUIPMENT
        ),
        
        # 2026
        Transaction(
            user_id=test_user.id,
            type=TransactionType.INCOME,
            amount=Decimal("3000.00"),
            transaction_date=date(2026, 1, 5),
            description="2026 Q1 Income",
            income_category=IncomeCategory.RENTAL
        ),
        Transaction(
            user_id=test_user.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("400.00"),
            transaction_date=date(2026, 11, 25),
            description="2026 Q4 Expense",
            expense_category=ExpenseCategory.TRAVEL
        ),
    ]
    
    for txn in transactions:
        db.add(txn)
    
    db.commit()
    return transactions


class TestMultiYearAPI:
    """Test multi-year data isolation via API"""
    
    def test_get_transactions_with_tax_year_2024(
        self, client: TestClient, auth_headers: dict, multi_year_transactions
    ):
        """Test GET /api/v1/transactions with tax_year=2024"""
        response = client.get(
            "/api/v1/transactions",
            headers=auth_headers,
            params={"tax_year": 2024}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have 2 transactions from 2024
        assert data["total"] == 2
        assert len(data["transactions"]) == 2
        
        # Verify all transactions are from 2024
        for txn in data["transactions"]:
            txn_date = date.fromisoformat(txn["transaction_date"])
            assert txn_date.year == 2024
    
    def test_get_transactions_with_tax_year_2025(
        self, client: TestClient, auth_headers: dict, multi_year_transactions
    ):
        """Test GET /api/v1/transactions with tax_year=2025"""
        response = client.get(
            "/api/v1/transactions",
            headers=auth_headers,
            params={"tax_year": 2025}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have 2 transactions from 2025
        assert data["total"] == 2
        assert len(data["transactions"]) == 2
        
        # Verify all transactions are from 2025
        for txn in data["transactions"]:
            txn_date = date.fromisoformat(txn["transaction_date"])
            assert txn_date.year == 2025
    
    def test_get_transactions_with_tax_year_2026(
        self, client: TestClient, auth_headers: dict, multi_year_transactions
    ):
        """Test GET /api/v1/transactions with tax_year=2026"""
        response = client.get(
            "/api/v1/transactions",
            headers=auth_headers,
            params={"tax_year": 2026}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have 2 transactions from 2026
        assert data["total"] == 2
        assert len(data["transactions"]) == 2
        
        # Verify all transactions are from 2026
        for txn in data["transactions"]:
            txn_date = date.fromisoformat(txn["transaction_date"])
            assert txn_date.year == 2026
    
    def test_get_transactions_without_tax_year(
        self, client: TestClient, auth_headers: dict, multi_year_transactions
    ):
        """Test GET /api/v1/transactions without tax_year (should return all)"""
        response = client.get(
            "/api/v1/transactions",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have all 6 transactions
        assert data["total"] == 6
        assert len(data["transactions"]) == 6
    
    def test_tax_year_with_other_filters(
        self, client: TestClient, auth_headers: dict, multi_year_transactions
    ):
        """Test tax_year combined with other filters"""
        # Filter by tax_year=2025 and type=income
        response = client.get(
            "/api/v1/transactions",
            headers=auth_headers,
            params={
                "tax_year": 2025,
                "type": "income"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have 1 income transaction from 2025
        assert data["total"] == 1
        assert len(data["transactions"]) == 1
        assert data["transactions"][0]["type"] == "income"
        assert data["transactions"][0]["description"] == "2025 Q1 Income"
    
    def test_tax_year_with_date_range(
        self, client: TestClient, auth_headers: dict, multi_year_transactions
    ):
        """Test tax_year combined with date_from/date_to"""
        # Filter by tax_year=2026 and date_from
        response = client.get(
            "/api/v1/transactions",
            headers=auth_headers,
            params={
                "tax_year": 2026,
                "date_from": "2026-06-01"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have 1 transaction (Q4 expense in November)
        assert data["total"] == 1
        assert len(data["transactions"]) == 1
        assert data["transactions"][0]["description"] == "2026 Q4 Expense"
    
    def test_tax_year_empty_result(
        self, client: TestClient, auth_headers: dict, multi_year_transactions
    ):
        """Test tax_year with no matching transactions"""
        response = client.get(
            "/api/v1/transactions",
            headers=auth_headers,
            params={"tax_year": 2023}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have no transactions
        assert data["total"] == 0
        assert len(data["transactions"]) == 0
    
    def test_tax_year_invalid_value(
        self, client: TestClient, auth_headers: dict, multi_year_transactions
    ):
        """Test tax_year with invalid value"""
        # Test with year too low
        response = client.get(
            "/api/v1/transactions",
            headers=auth_headers,
            params={"tax_year": 1800}
        )
        
        assert response.status_code == 422  # Validation error
        
        # Test with year too high
        response = client.get(
            "/api/v1/transactions",
            headers=auth_headers,
            params={"tax_year": 2200}
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_tax_year_pagination(
        self, client: TestClient, auth_headers: dict, db: Session, test_user: User
    ):
        """Test tax_year with pagination"""
        # Create many transactions for 2025
        for i in range(15):
            txn = Transaction(
                user_id=test_user.id,
                type=TransactionType.INCOME,
                amount=Decimal(f"{100 + i}.00"),
                transaction_date=date(2025, 1, i + 1),
                description=f"2025 Transaction {i + 1}",
                income_category=IncomeCategory.EMPLOYMENT
            )
            db.add(txn)
        db.commit()
        
        # Get first page
        response = client.get(
            "/api/v1/transactions",
            headers=auth_headers,
            params={
                "tax_year": 2025,
                "page": 1,
                "page_size": 10
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have 10 transactions on first page
        assert len(data["transactions"]) == 10
        assert data["total"] == 17  # 15 new + 2 from fixture
        assert data["page"] == 1
        assert data["total_pages"] == 2
        
        # Get second page
        response = client.get(
            "/api/v1/transactions",
            headers=auth_headers,
            params={
                "tax_year": 2025,
                "page": 2,
                "page_size": 10
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have 7 transactions on second page
        assert len(data["transactions"]) == 7
        assert data["page"] == 2
    
    def test_tax_year_sorting(
        self, client: TestClient, auth_headers: dict, multi_year_transactions
    ):
        """Test tax_year with sorting"""
        # Sort by amount ascending
        response = client.get(
            "/api/v1/transactions",
            headers=auth_headers,
            params={
                "tax_year": 2025,
                "sort_by": "amount",
                "sort_order": "asc"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should be sorted by amount
        amounts = [Decimal(txn["amount"]) for txn in data["transactions"]]
        assert amounts == sorted(amounts)
        assert amounts[0] == Decimal("300.00")  # Expense
        assert amounts[1] == Decimal("2000.00")  # Income
