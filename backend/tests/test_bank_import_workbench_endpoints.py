from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash
from app.models.bank_statement_import import BankStatementImport, BankStatementLine, BankStatementLineStatus
from app.models.document import Document, DocumentType
from app.models.transaction import Transaction, TransactionType
from app.models.user import User, UserType
from app.services.transaction_classifier import ClassificationResult


@pytest.fixture
def bank_workbench_user(db: Session) -> User:
    user = User(
        email="bank-workbench@example.com",
        password_hash=get_password_hash("TestPassword123"),
        name="Bank Workbench User",
        user_type=UserType.LANDLORD,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def bank_workbench_auth_headers(bank_workbench_user: User) -> dict:
    token = create_access_token(data={"sub": bank_workbench_user.email})
    return {"Authorization": f"Bearer {token}"}


def _make_bank_statement_document(db: Session, user: User, file_name: str = "kontoauszug.pdf") -> Document:
    document = Document(
        user_id=user.id,
        document_type=DocumentType.BANK_STATEMENT,
        file_path=f"/documents/{file_name}",
        file_name=file_name,
        mime_type="application/pdf",
        uploaded_at=datetime.utcnow(),
        processed_at=datetime.utcnow(),
        confidence_score=Decimal("0.87"),
        ocr_result={
            "bank_name": "Erste Bank",
            "iban": "AT12 3456 7890 1234 5678",
            "import_suggestion": {
                "type": "import_bank_statement",
                "data": {
                    "bank_name": "Erste Bank",
                    "iban": "AT12 3456 7890 1234 5678",
                    "statement_period": {
                        "start": "2026-01-01",
                        "end": "2026-01-31",
                    },
                    "tax_year": 2026,
                    "transactions": [
                        {
                            "date": "2026-01-15",
                            "amount": "-120.50",
                            "counterparty": "Supermarket",
                            "purpose": "Groceries",
                            "reference": "REF-1",
                        },
                        {
                            "date": "2026-01-18",
                            "amount": "2400.00",
                            "counterparty": "Tenant",
                            "purpose": "Rent January",
                            "reference": "REF-2",
                        },
                    ],
                },
            },
        },
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def test_initialize_document_import_is_idempotent_after_line_review(
    client: TestClient,
    db: Session,
    bank_workbench_user: User,
    bank_workbench_auth_headers: dict,
):
    document = _make_bank_statement_document(db, bank_workbench_user)

    with patch(
        "app.services.bank_import_service.TransactionClassifier.classify_transaction",
        return_value=ClassificationResult(category=None, confidence=Decimal("0.00"), method="test"),
    ):
        first_response = client.post(
            f"/api/v1/bank-import/document/{document.id}/initialize",
            headers=bank_workbench_auth_headers,
        )
        assert first_response.status_code == 200
        first_import = first_response.json()["import"]
        assert first_import["pending_review_count"] == 2

        statement_import = (
            db.query(BankStatementImport)
            .filter(BankStatementImport.id == first_import["id"])
            .one()
        )
        first_line = statement_import.lines[0]

        ignore_response = client.post(
            f"/api/v1/bank-import/lines/{first_line.id}/ignore",
            headers=bank_workbench_auth_headers,
        )
        assert ignore_response.status_code == 200

        second_response = client.post(
            f"/api/v1/bank-import/document/{document.id}/initialize",
            headers=bank_workbench_auth_headers,
        )
        assert second_response.status_code == 200
        second_import = second_response.json()["import"]
        assert second_import["id"] == first_import["id"]
        assert second_import["ignored_count"] == 1
        assert second_import["pending_review_count"] == 1

        db.expire_all()
        persisted_lines = (
            db.query(BankStatementLine)
            .filter(BankStatementLine.import_id == first_import["id"])
            .all()
        )
        assert len(persisted_lines) == 2
        assert any(line.review_status == BankStatementLineStatus.IGNORED_DUPLICATE for line in persisted_lines)


def test_confirm_create_line_creates_reconciled_transaction(
    client: TestClient,
    db: Session,
    bank_workbench_user: User,
    bank_workbench_auth_headers: dict,
):
    document = _make_bank_statement_document(db, bank_workbench_user, "create-line.pdf")

    with patch(
        "app.services.bank_import_service.TransactionClassifier.classify_transaction",
        return_value=ClassificationResult(category=None, confidence=Decimal("0.00"), method="test"),
    ):
        init_response = client.post(
            f"/api/v1/bank-import/document/{document.id}/initialize",
            headers=bank_workbench_auth_headers,
        )
        assert init_response.status_code == 200
        import_id = init_response.json()["import"]["id"]

    line_response = client.get(
        f"/api/v1/bank-import/imports/{import_id}/lines",
        headers=bank_workbench_auth_headers,
    )
    assert line_response.status_code == 200
    line_id = line_response.json()["lines"][0]["id"]

    confirm_response = client.post(
        f"/api/v1/bank-import/lines/{line_id}/confirm-create",
        headers=bank_workbench_auth_headers,
    )
    assert confirm_response.status_code == 200
    payload = confirm_response.json()
    assert payload["line"]["review_status"] == "auto_created"
    assert payload["transaction"]["bank_reconciled"] is True
    assert payload["line"]["created_transaction_id"] == payload["transaction"]["id"]
    assert payload["line"]["linked_transaction_id"] == payload["transaction"]["id"]

    transaction = db.query(Transaction).filter(Transaction.id == payload["transaction"]["id"]).one()
    assert transaction.bank_reconciled is True
    assert transaction.bank_reconciled_at is not None
    assert transaction.document_id == document.id


def test_match_existing_line_links_transaction_without_creating_duplicate(
    client: TestClient,
    db: Session,
    bank_workbench_user: User,
    bank_workbench_auth_headers: dict,
):
    document = _make_bank_statement_document(db, bank_workbench_user, "match-line.pdf")

    existing_transaction = Transaction(
        user_id=bank_workbench_user.id,
        type=TransactionType.INCOME,
        amount=Decimal("2400.00"),
        transaction_date=date(2026, 1, 18),
        description="Rental income January",
        bank_reconciled=False,
    )
    db.add(existing_transaction)
    db.commit()
    db.refresh(existing_transaction)

    with patch(
        "app.services.bank_import_service.TransactionClassifier.classify_transaction",
        return_value=ClassificationResult(category=None, confidence=Decimal("0.00"), method="test"),
    ):
        init_response = client.post(
            f"/api/v1/bank-import/document/{document.id}/initialize",
            headers=bank_workbench_auth_headers,
        )
        assert init_response.status_code == 200
        import_id = init_response.json()["import"]["id"]

    lines_response = client.get(
        f"/api/v1/bank-import/imports/{import_id}/lines",
        headers=bank_workbench_auth_headers,
    )
    assert lines_response.status_code == 200
    rent_line = next(line for line in lines_response.json()["lines"] if line["amount"] == "2400.00")

    match_response = client.post(
        f"/api/v1/bank-import/lines/{rent_line['id']}/match-existing",
        headers=bank_workbench_auth_headers,
        json={"transaction_id": existing_transaction.id},
    )
    assert match_response.status_code == 200
    payload = match_response.json()
    assert payload["line"]["review_status"] == "matched_existing"
    assert payload["line"]["linked_transaction_id"] == existing_transaction.id
    assert payload["line"]["created_transaction_id"] is None
    assert payload["transaction"]["id"] == existing_transaction.id
    assert payload["transaction"]["bank_reconciled"] is True

    db.refresh(existing_transaction)
    assert existing_transaction.bank_reconciled is True
    assert existing_transaction.bank_reconciled_at is not None

    tx_count = (
        db.query(Transaction)
        .filter(Transaction.user_id == bank_workbench_user.id)
        .count()
    )
    assert tx_count == 1


def test_initialize_document_import_matches_existing_transaction_with_booking_date_gap(
    client: TestClient,
    db: Session,
    bank_workbench_user: User,
    bank_workbench_auth_headers: dict,
):
    document = _make_bank_statement_document(db, bank_workbench_user, "booking-gap.pdf")

    existing_transaction = Transaction(
        user_id=bank_workbench_user.id,
        type=TransactionType.INCOME,
        amount=Decimal("2400.00"),
        transaction_date=date(2026, 1, 23),
        description="Tenant Rent January",
        bank_reconciled=False,
    )
    db.add(existing_transaction)
    db.commit()
    db.refresh(existing_transaction)

    with patch(
        "app.services.bank_import_service.TransactionClassifier.classify_transaction",
        return_value=ClassificationResult(category=None, confidence=Decimal("0.00"), method="test"),
    ):
        init_response = client.post(
            f"/api/v1/bank-import/document/{document.id}/initialize",
            headers=bank_workbench_auth_headers,
        )

    assert init_response.status_code == 200
    payload = init_response.json()["import"]
    assert payload["matched_existing_count"] == 1

    lines_response = client.get(
        f"/api/v1/bank-import/imports/{payload['id']}/lines",
        headers=bank_workbench_auth_headers,
    )
    assert lines_response.status_code == 200
    rent_line = next(line for line in lines_response.json()["lines"] if line["amount"] == "2400.00")
    assert rent_line["review_status"] == "matched_existing"
    assert rent_line["linked_transaction_id"] == existing_transaction.id


def test_confirm_bank_transactions_accepts_fallback_transactions_payload(
    client: TestClient,
    db: Session,
    bank_workbench_user: User,
    bank_workbench_auth_headers: dict,
):
    document = _make_bank_statement_document(db, bank_workbench_user, "fallback-import.pdf")

    payload = {
        "transaction_indices": [0],
        "transactions": [
            {
                "date": "19.12.2024",
                "amount": "-2.03",
                "counterparty": "T-Mobile Austria GmbH",
                "purpose": "Ratenplan 9001004040 vom 22.05.2023",
                "raw_reference": "Ratenplan 9001004040 vom 22.05.2023",
                "fingerprint": "19.12.2024|-2.03|t-mobile austria gmbh|ratenplan 9001004040 vom 22.05.2023",
            },
            {
                "date": "16.12.2024",
                "amount": "-72.78",
                "counterparty": "T-Mobile Austria GmbH",
                "purpose": "Magenta Mobil Rechnung 908162761224",
                "raw_reference": "Magenta Mobil Rechnung 908162761224",
                "fingerprint": "16.12.2024|-72.78|t-mobile austria gmbh|magenta mobil rechnung 908162761224",
            },
        ],
    }

    response = client.post(
        f"/api/v1/documents/{document.id}/confirm-bank-transactions",
        headers=bank_workbench_auth_headers,
        json=payload,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["imported"] == 1
    assert len(body["created_transaction_ids"]) == 1

    created_transaction = (
        db.query(Transaction)
        .filter(Transaction.id == body["created_transaction_ids"][0])
        .one()
    )
    assert created_transaction.amount == Decimal("2.03")
    assert created_transaction.transaction_date == date(2024, 12, 19)
    assert created_transaction.description == "Ratenplan 9001004040 vom 22.05.2023"

    db.refresh(document)
    assert document.ocr_result["import_suggestion"]["status"] == "pending"
    assert document.ocr_result["import_suggestion"]["imported_count"] == 1
    assert document.ocr_result["import_suggestion"]["fallback_imported_fingerprints"] == [
        "19.12.2024|-2.03|t-mobile austria gmbh|ratenplan 9001004040 vom 22.05.2023",
    ]


def test_confirm_bank_transactions_only_marks_confirmed_after_all_fallback_lines_processed(
    client: TestClient,
    db: Session,
    bank_workbench_user: User,
    bank_workbench_auth_headers: dict,
):
    document = _make_bank_statement_document(db, bank_workbench_user, "fallback-complete.pdf")
    document.ocr_result = {
        **document.ocr_result,
        "tax_analysis": {"items": [{"description": "stale"}]},
        "transaction_suggestion": {"type": "create_transaction"},
    }
    db.add(document)
    db.commit()
    db.refresh(document)

    first_payload = {
        "transaction_indices": [0],
        "transactions": [
            {
                "date": "19.12.2024",
                "amount": "-2.03",
                "counterparty": "T-Mobile Austria GmbH",
                "purpose": "Ratenplan 9001004040 vom 22.05.2023",
                "raw_reference": "Ratenplan 9001004040 vom 22.05.2023",
                "fingerprint": "19.12.2024|-2.03|t-mobile austria gmbh|ratenplan 9001004040 vom 22.05.2023",
            },
            {
                "date": "16.12.2024",
                "amount": "-72.78",
                "counterparty": "T-Mobile Austria GmbH",
                "purpose": "Magenta Mobil Rechnung 908162761224",
                "raw_reference": "Magenta Mobil Rechnung 908162761224",
                "fingerprint": "16.12.2024|-72.78|t-mobile austria gmbh|magenta mobil rechnung 908162761224",
            },
        ],
    }
    second_payload = {
        "transaction_indices": [1],
        "transactions": first_payload["transactions"],
    }

    first_response = client.post(
        f"/api/v1/documents/{document.id}/confirm-bank-transactions",
        headers=bank_workbench_auth_headers,
        json=first_payload,
    )
    assert first_response.status_code == 200
    assert first_response.json()["suggestion_status"] == "pending"

    db.refresh(document)
    assert document.ocr_result["import_suggestion"]["status"] == "pending"
    assert "tax_analysis" not in document.ocr_result
    assert "transaction_suggestion" not in document.ocr_result

    second_response = client.post(
        f"/api/v1/documents/{document.id}/confirm-bank-transactions",
        headers=bank_workbench_auth_headers,
        json=second_payload,
    )
    assert second_response.status_code == 200
    assert second_response.json()["suggestion_status"] == "confirmed"
    assert second_response.json()["imported_count"] == 2

    db.refresh(document)
    assert document.ocr_result["import_suggestion"]["status"] == "confirmed"
    assert document.ocr_result["import_suggestion"]["imported_count"] == 2
    assert document.ocr_result["import_suggestion"]["fallback_imported_fingerprints"] == [
        "16.12.2024|-72.78|t-mobile austria gmbh|magenta mobil rechnung 908162761224",
        "19.12.2024|-2.03|t-mobile austria gmbh|ratenplan 9001004040 vom 22.05.2023",
    ]


def test_confirm_bank_transactions_uses_full_fallback_snapshot_for_completion_status(
    client: TestClient,
    db: Session,
    bank_workbench_user: User,
    bank_workbench_auth_headers: dict,
):
    document = _make_bank_statement_document(db, bank_workbench_user, "fallback-snapshot.pdf")
    document.ocr_result["import_suggestion"]["data"]["transactions"] = [
        {
            "date": "19.12.2024",
            "amount": "-2.03",
            "counterparty": "T-Mobile Austria GmbH",
            "purpose": "Ratenplan 9001004040 vom 22.05.2023",
            "reference": "Ratenplan 9001004040 vom 22.05.2023",
        }
    ]
    db.add(document)
    db.commit()
    db.refresh(document)

    payload = {
        "transaction_indices": [0],
        "transactions": [
            {
                "date": "19.12.2024",
                "amount": "-2.03",
                "counterparty": "T-Mobile Austria GmbH",
                "purpose": "Ratenplan 9001004040 vom 22.05.2023",
                "raw_reference": "Ratenplan 9001004040 vom 22.05.2023",
                "fingerprint": "19.12.2024|-2.03|t-mobile austria gmbh|ratenplan 9001004040 vom 22.05.2023",
            },
            {
                "date": "16.12.2024",
                "amount": "-72.78",
                "counterparty": "T-Mobile Austria GmbH",
                "purpose": "Magenta Mobil Rechnung 908162761224",
                "raw_reference": "Magenta Mobil Rechnung 908162761224",
                "fingerprint": "16.12.2024|-72.78|t-mobile austria gmbh|magenta mobil rechnung 908162761224",
            },
            {
                "date": "18.11.2024",
                "amount": "-64.26",
                "counterparty": "T-Mobile Austria GmbH",
                "purpose": "Magenta offener Saldo per 20.11.2024",
                "raw_reference": "Magenta offener Saldo per 20.11.2024",
                "fingerprint": "18.11.2024|-64.26|t-mobile austria gmbh|magenta offener saldo per 20.11.2024",
            },
        ],
    }

    response = client.post(
        f"/api/v1/documents/{document.id}/confirm-bank-transactions",
        headers=bank_workbench_auth_headers,
        json=payload,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["imported"] == 1
    assert body["imported_count"] == 1
    assert body["remaining_count"] == 2
    assert body["suggestion_status"] == "pending"

    db.refresh(document)
    assert document.ocr_result["import_suggestion"]["status"] == "pending"
    assert document.ocr_result["import_suggestion"]["fallback_total_actionable_count"] == 3
    assert document.ocr_result["import_suggestion"]["fallback_actionable_fingerprints"] == [
        "16.12.2024|-72.78|t-mobile austria gmbh|magenta mobil rechnung 908162761224",
        "18.11.2024|-64.26|t-mobile austria gmbh|magenta offener saldo per 20.11.2024",
        "19.12.2024|-2.03|t-mobile austria gmbh|ratenplan 9001004040 vom 22.05.2023",
    ]


def test_confirm_bank_transactions_recovers_imported_count_from_fingerprints(
    client: TestClient,
    db: Session,
    bank_workbench_user: User,
    bank_workbench_auth_headers: dict,
):
    document = _make_bank_statement_document(db, bank_workbench_user, "fallback-legacy-count.pdf")
    document.ocr_result = {
        **document.ocr_result,
        "import_suggestion": {
            **document.ocr_result["import_suggestion"],
            "status": "pending",
            "imported_count": 0,
            "fallback_total_actionable_count": 2,
            "fallback_imported_fingerprints": [
                "19.12.2024|-2.03|t-mobile austria gmbh|ratenplan 9001004040 vom 22.05.2023",
            ],
        },
    }
    db.add(document)
    db.commit()
    db.refresh(document)

    payload = {
        "transaction_indices": [1],
        "transactions": [
            {
                "date": "19.12.2024",
                "amount": "-2.03",
                "counterparty": "T-Mobile Austria GmbH",
                "purpose": "Ratenplan 9001004040 vom 22.05.2023",
                "raw_reference": "Ratenplan 9001004040 vom 22.05.2023",
                "fingerprint": "19.12.2024|-2.03|t-mobile austria gmbh|ratenplan 9001004040 vom 22.05.2023",
            },
            {
                "date": "16.12.2024",
                "amount": "-72.78",
                "counterparty": "T-Mobile Austria GmbH",
                "purpose": "Magenta Mobil Rechnung 908162761224",
                "raw_reference": "Magenta Mobil Rechnung 908162761224",
                "fingerprint": "16.12.2024|-72.78|t-mobile austria gmbh|magenta mobil rechnung 908162761224",
            },
        ],
    }

    response = client.post(
        f"/api/v1/documents/{document.id}/confirm-bank-transactions",
        headers=bank_workbench_auth_headers,
        json=payload,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["imported"] == 1
    assert body["imported_count"] == 2
    assert body["remaining_count"] == 0
    assert body["suggestion_status"] == "confirmed"

    db.refresh(document)
    assert document.ocr_result["import_suggestion"]["imported_count"] == 2
    assert document.ocr_result["import_suggestion"]["status"] == "confirmed"


def test_ignore_line_marks_duplicate_without_creating_transaction(
    client: TestClient,
    db: Session,
    bank_workbench_user: User,
    bank_workbench_auth_headers: dict,
):
    document = _make_bank_statement_document(db, bank_workbench_user, "ignore-line.pdf")

    with patch(
        "app.services.bank_import_service.TransactionClassifier.classify_transaction",
        return_value=ClassificationResult(category=None, confidence=Decimal("0.00"), method="test"),
    ):
        init_response = client.post(
            f"/api/v1/bank-import/document/{document.id}/initialize",
            headers=bank_workbench_auth_headers,
        )
        assert init_response.status_code == 200
        import_id = init_response.json()["import"]["id"]

    lines_response = client.get(
        f"/api/v1/bank-import/imports/{import_id}/lines",
        headers=bank_workbench_auth_headers,
    )
    assert lines_response.status_code == 200
    line_id = lines_response.json()["lines"][0]["id"]

    ignore_response = client.post(
        f"/api/v1/bank-import/lines/{line_id}/ignore",
        headers=bank_workbench_auth_headers,
    )
    assert ignore_response.status_code == 200
    payload = ignore_response.json()
    assert payload["line"]["review_status"] == "ignored_duplicate"
    assert payload["line"]["created_transaction_id"] is None
    assert payload["line"]["linked_transaction_id"] is None

    tx_count = (
        db.query(Transaction)
        .filter(Transaction.user_id == bank_workbench_user.id)
        .count()
    )
    assert tx_count == 0
