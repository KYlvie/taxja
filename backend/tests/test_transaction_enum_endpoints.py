"""Focused tests for enum normalization across transaction endpoints."""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.v1.endpoints import transactions as transactions_endpoint
from app.core.security import create_access_token, get_password_hash
from app.models.transaction import ExpenseCategory, Transaction, TransactionType
from app.models.user import User, UserType


@pytest.fixture
def test_user(db: Session) -> User:
    user = User(
        email="enum-tests@example.com",
        password_hash=get_password_hash("TestPassword123"),
        name="Enum Tests",
        user_type=UserType.EMPLOYEE,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user: User) -> dict:
    access_token = create_access_token(data={"sub": test_user.email})
    return {"Authorization": f"Bearer {access_token}"}


def test_import_transactions_csv_accepts_enum_name_categories(
    client: TestClient,
    auth_headers: dict,
    db: Session,
):
    """CSV imports should accept enum names like MAINTENANCE, not only enum values."""
    csv_content = (
        "date,type,amount,description,category\n"
        "2026-03-18,expense,89.99,Workshop repair,MAINTENANCE\n"
    )

    response = client.post(
        "/api/v1/transactions/import",
        files={"file": ("transactions.csv", csv_content, "text/csv")},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] == 1
    assert data["transactions"][0]["category"] == "maintenance"

    transaction = db.query(Transaction).filter(Transaction.description == "Workshop repair").one()
    assert transaction.expense_category == ExpenseCategory.MAINTENANCE


def test_reclassify_accepts_enum_name_categories(
    client: TestClient,
    auth_headers: dict,
    test_user: User,
    db: Session,
    monkeypatch,
):
    """Bulk reclassification should accept enum names returned by classifiers."""
    transaction = Transaction(
        user_id=test_user.id,
        type=TransactionType.EXPENSE,
        amount=Decimal("99.00"),
        transaction_date=date(2026, 3, 18),
        description="Repair invoice",
        expense_category=ExpenseCategory.OTHER,
        is_deductible=False,
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    def mock_classify_transaction(self, transaction, current_user):
        return SimpleNamespace(
            category="MAINTENANCE",
            confidence=Decimal("0.88"),
            method="llm",
        )

    def mock_check(self, *args, **kwargs):
        return SimpleNamespace(
            is_deductible=True,
            reason="Reclassified as maintenance",
            requires_review=False,
        )

    monkeypatch.setattr(
        transactions_endpoint.TransactionClassifier,
        "classify_transaction",
        mock_classify_transaction,
    )
    monkeypatch.setattr(
        transactions_endpoint.DeductibilityChecker,
        "check",
        mock_check,
    )

    response = client.post("/api/v1/transactions/reclassify", headers=auth_headers)

    assert response.status_code == 200
    db.refresh(transaction)
    assert transaction.expense_category == ExpenseCategory.MAINTENANCE
    assert transaction.is_deductible is True
