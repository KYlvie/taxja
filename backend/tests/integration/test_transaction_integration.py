"""Integration tests for current transaction API contracts."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.core.security import get_password_hash
from app.models.credit_balance import CreditBalance
from app.models.credit_cost_config import CreditCostConfig
from app.models.transaction import ExpenseCategory, IncomeCategory, Transaction, TransactionType
from app.models.user import User, UserType


def _seed_transaction_access(db, user: User, *, balance: int = 10) -> None:
    existing_cost = (
        db.query(CreditCostConfig)
        .filter(CreditCostConfig.operation == "transaction_entry")
        .first()
    )
    if existing_cost is None:
        db.add(
            CreditCostConfig(
                operation="transaction_entry",
                credit_cost=1,
                description="Transaction entry",
                is_active=True,
            )
        )

    if db.query(CreditBalance).filter(CreditBalance.user_id == user.id).first() is None:
        db.add(
            CreditBalance(
                user_id=user.id,
                plan_balance=balance,
                topup_balance=0,
                overage_enabled=False,
                overage_credits_used=0,
                has_unpaid_overage=False,
                unpaid_overage_periods=0,
            )
        )
    db.commit()


def _get_user(db, email: str = "testuser@example.com") -> User:
    return db.query(User).filter(User.email == email).first()


def _add_transaction(
    db,
    *,
    user_id: int,
    txn_type: TransactionType,
    amount: str,
    txn_date: date,
    description: str,
    income_category: IncomeCategory | None = None,
    expense_category: ExpenseCategory | None = None,
    is_deductible: bool = False,
):
    transaction = Transaction(
        user_id=user_id,
        type=txn_type,
        amount=Decimal(amount),
        transaction_date=txn_date,
        description=description,
        income_category=income_category,
        expense_category=expense_category,
        is_deductible=is_deductible,
    )
    db.add(transaction)
    db.flush()
    return transaction


@pytest.fixture
def transaction_enabled_user(db, test_user):
    user = _get_user(db, test_user["email"])
    _seed_transaction_access(db, user)
    db.refresh(user)
    return user


@pytest.fixture
def transaction_authenticated_client(client, test_user, transaction_enabled_user):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": test_user["email"],
            "password": test_user["password"],
        },
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    client.headers = {
        **client.headers,
        "Authorization": f"Bearer {token}",
    }
    return client


class TestTransactionCRUD:
    """Current transaction CRUD behavior."""

    def test_create_income_transaction(self, transaction_authenticated_client, db, transaction_enabled_user):
        response = transaction_authenticated_client.post(
            "/api/v1/transactions",
            json={
                "type": "income",
                "amount": 3500.00,
                "transaction_date": "2026-01-15",
                "description": "Monthly salary",
                "income_category": "employment",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["type"] == "income"
        assert Decimal(data["amount"]) == Decimal("3500.00")
        assert data["transaction_date"] == "2026-01-15"
        assert data["income_category"] == "employment"
        assert data["expense_category"] is None
        assert response.headers["X-Credits-Remaining"] == "9"

        balance = (
            db.query(CreditBalance)
            .filter(CreditBalance.user_id == transaction_enabled_user.id)
            .first()
        )
        assert balance.plan_balance == 9

    def test_create_expense_transaction_with_vat(self, transaction_authenticated_client):
        response = transaction_authenticated_client.post(
            "/api/v1/transactions",
            json={
                "type": "expense",
                "amount": 150.75,
                "transaction_date": "2026-01-20",
                "description": "Office supplies",
                "expense_category": "office_supplies",
                "is_deductible": True,
                "deduction_reason": "Business expense",
                "vat_rate": 0.20,
                "vat_amount": 25.13,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["type"] == "expense"
        assert Decimal(data["amount"]) == Decimal("150.75")
        assert data["expense_category"] == "office_supplies"
        assert data["is_deductible"] is True
        assert Decimal(data["vat_rate"]) == Decimal("0.2000")
        assert Decimal(data["vat_amount"]) == Decimal("25.13")

    def test_get_transaction_by_id(self, transaction_authenticated_client):
        create_response = transaction_authenticated_client.post(
            "/api/v1/transactions",
            json={
                "type": "income",
                "amount": 2000.00,
                "transaction_date": "2026-02-01",
                "description": "Freelance project",
                "income_category": "self_employment",
            },
        )
        transaction_id = create_response.json()["id"]

        response = transaction_authenticated_client.get(f"/api/v1/transactions/{transaction_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == transaction_id
        assert data["description"] == "Freelance project"
        assert data["income_category"] == "self_employment"

    def test_list_transactions_with_current_pagination_shape(self, transaction_authenticated_client):
        payloads = [
            {
                "type": "income",
                "amount": 3000.00,
                "transaction_date": "2026-01-01",
                "description": "Salary Jan",
                "income_category": "employment",
            },
            {
                "type": "expense",
                "amount": 100.00,
                "transaction_date": "2026-01-05",
                "description": "Office rent",
                "expense_category": "rent",
                "is_deductible": True,
            },
            {
                "type": "income",
                "amount": 3000.00,
                "transaction_date": "2026-02-01",
                "description": "Salary Feb",
                "income_category": "employment",
            },
        ]

        for payload in payloads:
            response = transaction_authenticated_client.post("/api/v1/transactions", json=payload)
            assert response.status_code == 201

        response = transaction_authenticated_client.get("/api/v1/transactions")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["transactions"]) == 3
        assert data["page"] == 1
        assert data["page_size"] == 50
        assert data["total_pages"] == 1

    def test_update_transaction(self, transaction_authenticated_client):
        create_response = transaction_authenticated_client.post(
            "/api/v1/transactions",
            json={
                "type": "expense",
                "amount": 100.00,
                "transaction_date": "2026-01-10",
                "description": "Original description",
                "expense_category": "other",
            },
        )
        transaction_id = create_response.json()["id"]

        response = transaction_authenticated_client.put(
            f"/api/v1/transactions/{transaction_id}",
            json={
                "amount": 150.00,
                "description": "Updated description",
                "expense_category": "office_supplies",
                "is_deductible": True,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert Decimal(data["amount"]) == Decimal("150.00")
        assert data["description"] == "Updated description"
        assert data["expense_category"] == "office_supplies"
        assert data["is_deductible"] is True

    def test_delete_transaction(self, transaction_authenticated_client):
        create_response = transaction_authenticated_client.post(
            "/api/v1/transactions",
            json={
                "type": "expense",
                "amount": 50.00,
                "transaction_date": "2026-01-15",
                "description": "To be deleted",
                "expense_category": "other",
            },
        )
        transaction_id = create_response.json()["id"]

        delete_response = transaction_authenticated_client.delete(f"/api/v1/transactions/{transaction_id}")
        assert delete_response.status_code == 204

        get_response = transaction_authenticated_client.get(f"/api/v1/transactions/{transaction_id}")
        assert get_response.status_code == 404


class TestTransactionValidation:
    """Current validation behavior."""

    def test_create_transaction_requires_authentication(self, client):
        response = client.post(
            "/api/v1/transactions",
            json={
                "type": "income",
                "amount": 1000.00,
                "transaction_date": "2026-01-01",
                "description": "Test",
                "income_category": "employment",
            },
        )
        assert response.status_code == 401

    def test_create_transaction_with_negative_amount(self, transaction_authenticated_client):
        response = transaction_authenticated_client.post(
            "/api/v1/transactions",
            json={
                "type": "income",
                "amount": -100.00,
                "transaction_date": "2026-01-01",
                "description": "Invalid amount",
                "income_category": "employment",
            },
        )
        assert response.status_code == 422

    def test_create_transaction_with_future_date(self, transaction_authenticated_client):
        future_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        response = transaction_authenticated_client.post(
            "/api/v1/transactions",
            json={
                "type": "income",
                "amount": 1000.00,
                "transaction_date": future_date,
                "description": "Future transaction",
                "income_category": "employment",
            },
        )
        assert response.status_code == 422

    def test_create_transaction_requires_matching_category_field(self, transaction_authenticated_client):
        response = transaction_authenticated_client.post(
            "/api/v1/transactions",
            json={
                "type": "income",
                "amount": 1000.00,
                "transaction_date": "2026-01-01",
                "description": "Missing category",
            },
        )
        assert response.status_code == 422


class TestTransactionClassificationAndReview:
    """Current review-related behavior."""

    def test_create_requires_explicit_category_in_current_contract(
        self,
        transaction_authenticated_client,
    ):
        response = transaction_authenticated_client.post(
            "/api/v1/transactions",
            json={
                "type": "expense",
                "amount": 120.00,
                "transaction_date": "2026-01-20",
                "description": "OBI Bueromaterial",
            },
        )

        assert response.status_code == 422

    def test_mark_transaction_reviewed(self, transaction_authenticated_client, db):
        user = _get_user(db)
        transaction = _add_transaction(
            db,
            user_id=user.id,
            txn_type=TransactionType.EXPENSE,
            amount="80.00",
            txn_date=date(2026, 1, 12),
            description="Needs review",
            expense_category=ExpenseCategory.OTHER,
            is_deductible=False,
        )
        transaction.needs_review = True
        transaction.reviewed = False
        db.commit()

        review_response = transaction_authenticated_client.post(
            f"/api/v1/transactions/{transaction.id}/review"
        )
        assert review_response.status_code == 200
        reviewed = review_response.json()
        assert reviewed["reviewed"] is True
        assert reviewed["needs_review"] is False


class TestTransactionYearAndUserIsolation:
    """Current filtering and user isolation behavior."""

    def test_transactions_filtered_by_tax_year(self, transaction_authenticated_client):
        payloads = [
            {
                "type": "income",
                "amount": 3000.00,
                "transaction_date": "2024-12-15",
                "description": "2024 income",
                "income_category": "employment",
            },
            {
                "type": "income",
                "amount": 3000.00,
                "transaction_date": "2026-01-15",
                "description": "2026 income",
                "income_category": "employment",
            },
            {
                "type": "income",
                "amount": 3000.00,
                "transaction_date": "2026-02-15",
                "description": "2026 income 2",
                "income_category": "employment",
            },
            {
                "type": "income",
                "amount": 3000.00,
                "transaction_date": "2025-01-15",
                "description": "2025 income",
                "income_category": "employment",
            },
        ]

        for payload in payloads:
            response = transaction_authenticated_client.post("/api/v1/transactions", json=payload)
            assert response.status_code == 201

        response = transaction_authenticated_client.get("/api/v1/transactions?tax_year=2026")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        for item in data["transactions"]:
            assert item["transaction_date"].startswith("2026-")

    def test_users_cannot_see_other_users_transactions(self, client, db):
        user1 = User(
            email="employee1@example.com",
            name="Employee One",
            password_hash=get_password_hash("TestPassword123!"),
            user_type=UserType.EMPLOYEE,
            two_factor_enabled=False,
            email_verified=True,
        )
        user2 = User(
            email="selfemployed1@example.com",
            name="Self Employed One",
            password_hash=get_password_hash("TestPassword123!"),
            user_type=UserType.SELF_EMPLOYED,
            two_factor_enabled=False,
            email_verified=True,
        )
        db.add_all([user1, user2])
        db.commit()
        db.refresh(user1)
        db.refresh(user2)
        _seed_transaction_access(db, user1, balance=3)
        _seed_transaction_access(db, user2, balance=3)

        login_user1 = client.post(
            "/api/v1/auth/login",
            json={
                "email": user1.email,
                "password": "TestPassword123!",
            },
        )
        assert login_user1.status_code == 200
        headers1 = {"Authorization": f"Bearer {login_user1.json()['access_token']}"}

        create_response = client.post(
            "/api/v1/transactions",
            json={
                "type": "income",
                "amount": 1000.00,
                "transaction_date": "2026-01-15",
                "description": "User1 transaction",
                "income_category": "employment",
            },
            headers=headers1,
        )
        assert create_response.status_code == 201
        transaction_id = create_response.json()["id"]

        login_user2 = client.post(
            "/api/v1/auth/login",
            json={
                "email": user2.email,
                "password": "TestPassword123!",
            },
        )
        assert login_user2.status_code == 200
        headers2 = {"Authorization": f"Bearer {login_user2.json()['access_token']}"}

        list_response = client.get("/api/v1/transactions", headers=headers2)
        assert list_response.status_code == 200
        assert all(
            item["description"] != "User1 transaction"
            for item in list_response.json()["transactions"]
        )

        get_response = client.get(f"/api/v1/transactions/{transaction_id}", headers=headers2)
        assert get_response.status_code == 404
