"""Tests for transaction CRUD endpoints"""
import pytest
from datetime import date, datetime
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.models.user import User, UserType
from app.models.transaction import Transaction, TransactionType, IncomeCategory, ExpenseCategory
from app.core.security import get_password_hash, create_access_token


@pytest.fixture
def test_user(db: Session) -> User:
    """Create a test user"""
    user = User(
        email="test@example.com",
        password_hash=get_password_hash("TestPassword123"),
        name="Test User",
        user_type=UserType.EMPLOYEE
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user: User) -> dict:
    """Create authentication headers with JWT token"""
    access_token = create_access_token(data={"sub": test_user.email})
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
def client() -> TestClient:
    """Create test client"""
    return TestClient(app)


def test_create_income_transaction(client: TestClient, auth_headers: dict, db: Session):
    """Test creating an income transaction"""
    transaction_data = {
        "type": "income",
        "amount": 3000.50,
        "transaction_date": "2026-01-15",
        "description": "Monthly salary",
        "income_category": "employment",
        "is_deductible": False
    }
    
    response = client.post(
        "/api/v1/transactions",
        json=transaction_data,
        headers=auth_headers
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["type"] == "income"
    assert Decimal(data["amount"]) == Decimal("3000.50")
    assert data["income_category"] == "employment"
    assert data["description"] == "Monthly salary"
    assert "id" in data
    assert "created_at" in data


def test_create_expense_transaction(client: TestClient, auth_headers: dict, db: Session):
    """Test creating an expense transaction"""
    transaction_data = {
        "type": "expense",
        "amount": 150.75,
        "transaction_date": "2026-01-20",
        "description": "Office supplies",
        "expense_category": "office_supplies",
        "is_deductible": True,
        "deduction_reason": "Business expense",
        "vat_rate": 0.20,
        "vat_amount": 25.13
    }
    
    response = client.post(
        "/api/v1/transactions",
        json=transaction_data,
        headers=auth_headers
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["type"] == "expense"
    assert Decimal(data["amount"]) == Decimal("150.75")
    assert data["expense_category"] == "office_supplies"
    assert data["is_deductible"] is True
    assert Decimal(data["vat_rate"]) == Decimal("0.2000")


def test_create_transaction_missing_category(client: TestClient, auth_headers: dict):
    """Test that creating a transaction without required category fails"""
    transaction_data = {
        "type": "income",
        "amount": 1000.00,
        "transaction_date": "2026-01-15",
        "description": "Test"
    }
    
    response = client.post(
        "/api/v1/transactions",
        json=transaction_data,
        headers=auth_headers
    )
    
    assert response.status_code == 400
    assert "income_category is required" in response.json()["detail"]


def test_create_transaction_invalid_amount(client: TestClient, auth_headers: dict):
    """Test that creating a transaction with negative amount fails"""
    transaction_data = {
        "type": "expense",
        "amount": -100.00,
        "transaction_date": "2026-01-15",
        "expense_category": "office_supplies"
    }
    
    response = client.post(
        "/api/v1/transactions",
        json=transaction_data,
        headers=auth_headers
    )
    
    assert response.status_code == 422  # Validation error


def test_get_transactions(client: TestClient, auth_headers: dict, test_user: User, db: Session):
    """Test getting list of transactions"""
    # Create test transactions
    transactions = [
        Transaction(
            user_id=test_user.id,
            type=TransactionType.INCOME,
            amount=Decimal("3000.00"),
            transaction_date=date(2026, 1, 15),
            description="Salary",
            income_category=IncomeCategory.EMPLOYMENT
        ),
        Transaction(
            user_id=test_user.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("150.00"),
            transaction_date=date(2026, 1, 20),
            description="Office supplies",
            expense_category=ExpenseCategory.OFFICE_SUPPLIES,
            is_deductible=True
        )
    ]
    
    for txn in transactions:
        db.add(txn)
    db.commit()
    
    response = client.get("/api/v1/transactions", headers=auth_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["transactions"]) == 2
    assert data["page"] == 1
    assert data["total_pages"] == 1


def test_get_transactions_with_filters(client: TestClient, auth_headers: dict, test_user: User, db: Session):
    """Test getting transactions with filters"""
    # Create test transactions
    transactions = [
        Transaction(
            user_id=test_user.id,
            type=TransactionType.INCOME,
            amount=Decimal("3000.00"),
            transaction_date=date(2026, 1, 15),
            income_category=IncomeCategory.EMPLOYMENT
        ),
        Transaction(
            user_id=test_user.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("150.00"),
            transaction_date=date(2026, 1, 20),
            expense_category=ExpenseCategory.OFFICE_SUPPLIES,
            is_deductible=True
        ),
        Transaction(
            user_id=test_user.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("50.00"),
            transaction_date=date(2026, 1, 25),
            expense_category=ExpenseCategory.GROCERIES,
            is_deductible=False
        )
    ]
    
    for txn in transactions:
        db.add(txn)
    db.commit()
    
    # Filter by type
    response = client.get("/api/v1/transactions?type=expense", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    
    # Filter by deductibility
    response = client.get("/api/v1/transactions?is_deductible=true", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    
    # Filter by date range
    response = client.get(
        "/api/v1/transactions?date_from=2026-01-20&date_to=2026-01-25",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2


def test_get_transaction_by_id(client: TestClient, auth_headers: dict, test_user: User, db: Session):
    """Test getting a specific transaction by ID"""
    transaction = Transaction(
        user_id=test_user.id,
        type=TransactionType.INCOME,
        amount=Decimal("3000.00"),
        transaction_date=date(2026, 1, 15),
        description="Salary",
        income_category=IncomeCategory.EMPLOYMENT
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    
    response = client.get(f"/api/v1/transactions/{transaction.id}", headers=auth_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == transaction.id
    assert data["description"] == "Salary"


def test_get_nonexistent_transaction(client: TestClient, auth_headers: dict):
    """Test getting a transaction that doesn't exist"""
    response = client.get("/api/v1/transactions/99999", headers=auth_headers)
    assert response.status_code == 404


def test_update_transaction(client: TestClient, auth_headers: dict, test_user: User, db: Session):
    """Test updating a transaction"""
    transaction = Transaction(
        user_id=test_user.id,
        type=TransactionType.EXPENSE,
        amount=Decimal("100.00"),
        transaction_date=date(2026, 1, 15),
        description="Original description",
        expense_category=ExpenseCategory.OFFICE_SUPPLIES,
        is_deductible=False
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    
    update_data = {
        "amount": 150.50,
        "description": "Updated description",
        "is_deductible": True,
        "deduction_reason": "Business expense"
    }
    
    response = client.put(
        f"/api/v1/transactions/{transaction.id}",
        json=update_data,
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert Decimal(data["amount"]) == Decimal("150.50")
    assert data["description"] == "Updated description"
    assert data["is_deductible"] is True
    assert data["deduction_reason"] == "Business expense"


def test_delete_transaction(client: TestClient, auth_headers: dict, test_user: User, db: Session):
    """Test deleting a transaction"""
    transaction = Transaction(
        user_id=test_user.id,
        type=TransactionType.EXPENSE,
        amount=Decimal("100.00"),
        transaction_date=date(2026, 1, 15),
        expense_category=ExpenseCategory.OFFICE_SUPPLIES
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    
    response = client.delete(f"/api/v1/transactions/{transaction.id}", headers=auth_headers)
    
    assert response.status_code == 204
    
    # Verify transaction is deleted
    deleted_txn = db.query(Transaction).filter(Transaction.id == transaction.id).first()
    assert deleted_txn is None


def test_unauthorized_access(client: TestClient):
    """Test that endpoints require authentication"""
    response = client.get("/api/v1/transactions")
    assert response.status_code == 401
    
    response = client.post("/api/v1/transactions", json={})
    assert response.status_code == 401


def test_user_can_only_access_own_transactions(client: TestClient, db: Session):
    """Test that users can only access their own transactions"""
    # Create two users
    user1 = User(
        email="user1@example.com",
        password_hash=get_password_hash("Password123"),
        name="User 1",
        user_type=UserType.EMPLOYEE
    )
    user2 = User(
        email="user2@example.com",
        password_hash=get_password_hash("Password123"),
        name="User 2",
        user_type=UserType.EMPLOYEE
    )
    db.add(user1)
    db.add(user2)
    db.commit()
    
    # Create transaction for user2
    transaction = Transaction(
        user_id=user2.id,
        type=TransactionType.INCOME,
        amount=Decimal("1000.00"),
        transaction_date=date(2026, 1, 15),
        income_category=IncomeCategory.EMPLOYMENT
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    
    # Try to access user2's transaction as user1
    token = create_access_token(data={"sub": user1.email})
    headers = {"Authorization": f"Bearer {token}"}
    
    response = client.get(f"/api/v1/transactions/{transaction.id}", headers=headers)
    assert response.status_code == 404  # Should not find transaction
