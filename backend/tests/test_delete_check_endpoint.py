"""Tests for the transaction delete-check endpoint and _check_transaction_associations helper."""
import pytest
from datetime import date
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models.user import User, UserType
from app.models.transaction import Transaction, TransactionType, ExpenseCategory, IncomeCategory
from app.models.document import Document, DocumentType
from app.core.security import get_password_hash, create_access_token


@pytest.fixture
def test_user(db: Session) -> User:
    user = User(
        email="deletecheck@example.com",
        password_hash=get_password_hash("TestPassword123"),
        name="Delete Check User",
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


def _make_transaction(db, user, **kwargs):
    defaults = dict(
        user_id=user.id,
        type=TransactionType.EXPENSE,
        amount=Decimal("100.00"),
        transaction_date=date(2026, 1, 15),
        expense_category=ExpenseCategory.OFFICE_SUPPLIES,
    )
    defaults.update(kwargs)
    txn = Transaction(**defaults)
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn


def _make_document(db, user, **kwargs):
    defaults = dict(
        user_id=user.id,
        document_type=DocumentType.RECEIPT,
        file_path="/fake/path.pdf",
        file_name="receipt.pdf",
    )
    defaults.update(kwargs)
    doc = Document(**defaults)
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


# --- Endpoint tests ---


def test_delete_check_no_associations(
    client: TestClient, auth_headers: dict, test_user: User, db: Session
):
    """Plain transaction with no document or recurring → can_delete=True, warning_type=null."""
    txn = _make_transaction(db, test_user)

    resp = client.get(f"/api/v1/transactions/{txn.id}/delete-check", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["can_delete"] is True
    assert data["warning_type"] is None
    assert data["document_id"] is None
    assert data["document_name"] is None
    assert data["linked_transaction_count"] is None
    assert data["is_from_recurring"] is False


def test_delete_check_document_only(
    client: TestClient, auth_headers: dict, test_user: User, db: Session
):
    """Transaction is the sole transaction for its document → document_only, can_delete=False."""
    doc = _make_document(db, test_user, file_name="invoice_only.pdf")
    txn = _make_transaction(db, test_user, document_id=doc.id)

    resp = client.get(f"/api/v1/transactions/{txn.id}/delete-check", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["can_delete"] is False
    assert data["warning_type"] == "document_only"
    assert data["document_id"] == doc.id
    assert data["document_name"] == "invoice_only.pdf"
    assert data["linked_transaction_count"] == 1


def test_delete_check_document_multi(
    client: TestClient, auth_headers: dict, test_user: User, db: Session
):
    """Multiple transactions share the same document → document_multi, can_delete=True."""
    doc = _make_document(db, test_user, file_name="multi.pdf")
    txn1 = _make_transaction(db, test_user, document_id=doc.id, description="first")
    txn2 = _make_transaction(db, test_user, document_id=doc.id, description="second")

    resp = client.get(f"/api/v1/transactions/{txn1.id}/delete-check", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["can_delete"] is True
    assert data["warning_type"] == "document_multi"
    assert data["document_id"] == doc.id
    assert data["document_name"] == "multi.pdf"
    assert data["linked_transaction_count"] == 2


def test_delete_check_recurring(
    client: TestClient, auth_headers: dict, test_user: User, db: Session
):
    """Transaction from a recurring rule (no document) → recurring warning."""
    txn = _make_transaction(db, test_user, source_recurring_id=42)

    resp = client.get(f"/api/v1/transactions/{txn.id}/delete-check", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["can_delete"] is True
    assert data["warning_type"] == "recurring"
    assert data["is_from_recurring"] is True
    assert data["document_id"] is None


def test_delete_check_document_takes_priority_over_recurring(
    client: TestClient, auth_headers: dict, test_user: User, db: Session
):
    """When both document_id and source_recurring_id are set, document warning takes priority."""
    doc = _make_document(db, test_user, file_name="combo.pdf")
    txn = _make_transaction(db, test_user, document_id=doc.id, source_recurring_id=99)

    resp = client.get(f"/api/v1/transactions/{txn.id}/delete-check", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()

    # document_only takes priority since it's the only txn for this doc
    assert data["warning_type"] == "document_only"
    assert data["is_from_recurring"] is True


def test_delete_check_not_found(
    client: TestClient, auth_headers: dict, db: Session
):
    """Non-existent transaction returns 404."""
    resp = client.get("/api/v1/transactions/999999/delete-check", headers=auth_headers)
    assert resp.status_code == 404


def test_delete_check_unauthorized(client: TestClient, db: Session):
    """Unauthenticated request returns 401."""
    resp = client.get("/api/v1/transactions/1/delete-check")
    assert resp.status_code == 401
