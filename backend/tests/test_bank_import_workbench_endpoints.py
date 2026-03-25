from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash
from app.models.bank_statement_import import (
    BankStatementImport,
    BankStatementImportSourceType,
    BankStatementLine,
    BankStatementLineResolutionReason,
    BankStatementLineStatus,
    BankStatementSuggestedAction,
)
from app.models.document import Document, DocumentType
from app.models.transaction import Transaction, TransactionType
from app.models.user_classification_rule import UserClassificationRule
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
    return _make_custom_bank_statement_document(
        db,
        user,
        file_name=file_name,
        transactions=[
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
    )


def _make_custom_bank_statement_document(
    db: Session,
    user: User,
    *,
    file_name: str,
    transactions: list[dict],
) -> Document:
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
                    "transactions": transactions,
                },
            },
        },
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def _low_confidence_result(category_type: str) -> SimpleNamespace:
    return SimpleNamespace(category=None, confidence=Decimal("0.00"), category_type=category_type)


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


def test_initialize_document_import_ignores_exact_duplicate_line_after_first_auto_create(
    client: TestClient,
    db: Session,
    bank_workbench_user: User,
    bank_workbench_auth_headers: dict,
):
    document = _make_custom_bank_statement_document(
        db,
        bank_workbench_user,
        file_name="duplicate-auto-create.pdf",
        transactions=[
            {
                "date": "2024-12-19",
                "amount": "-2.03",
                "counterparty": "T-Mobile Austria GmbH",
                "purpose": "Ratenplan 9001004040 vom 22.05.2023",
                "reference": "Ratenplan 9001004040 vom 22.05.2023",
            },
            {
                "date": "2024-12-19",
                "amount": "-2.03",
                "counterparty": "T-Mobile Austria GmbH",
                "purpose": "Ratenplan 9001004040 vom 22.05.2023",
                "reference": "Ratenplan 9001004040 vom 22.05.2023",
            },
        ],
    )

    with patch(
        "app.services.bank_import_service.TransactionClassifier.classify_transaction",
        return_value=ClassificationResult(category="telecom", confidence=Decimal("0.95"), method="test"),
    ):
        init_response = client.post(
            f"/api/v1/bank-import/document/{document.id}/initialize",
            headers=bank_workbench_auth_headers,
        )

    assert init_response.status_code == 200
    summary = init_response.json()["import"]
    assert summary["total_count"] == 2
    assert summary["auto_created_count"] == 1
    assert summary["ignored_count"] == 1
    assert summary["pending_review_count"] == 0

    lines_response = client.get(
        f"/api/v1/bank-import/imports/{summary['id']}/lines",
        headers=bank_workbench_auth_headers,
    )
    assert lines_response.status_code == 200
    lines = lines_response.json()["lines"]
    assert len(lines) == 2

    auto_created_line = next(line for line in lines if line["review_status"] == "auto_created")
    ignored_line = next(line for line in lines if line["review_status"] == "ignored_duplicate")

    assert ignored_line["created_transaction_id"] is None
    assert ignored_line["linked_transaction_id"] == auto_created_line["created_transaction_id"]

    tx_count = (
        db.query(Transaction)
        .filter(Transaction.user_id == bank_workbench_user.id)
        .count()
    )
    assert tx_count == 1


def test_confirm_create_line_ignores_exact_duplicate_instead_of_creating_second_transaction(
    client: TestClient,
    db: Session,
    bank_workbench_user: User,
    bank_workbench_auth_headers: dict,
):
    document = _make_custom_bank_statement_document(
        db,
        bank_workbench_user,
        file_name="duplicate-manual-create.pdf",
        transactions=[
            {
                "date": "2024-12-19",
                "amount": "-2.03",
                "counterparty": "T-Mobile Austria GmbH",
                "purpose": "Ratenplan 9001004040 vom 22.05.2023",
                "reference": "Ratenplan 9001004040 vom 22.05.2023",
            },
            {
                "date": "2024-12-19",
                "amount": "-2.03",
                "counterparty": "T-Mobile Austria GmbH",
                "purpose": "Ratenplan 9001004040 vom 22.05.2023",
                "reference": "Ratenplan 9001004040 vom 22.05.2023",
            },
        ],
    )

    with patch(
        "app.services.bank_import_service.TransactionClassifier.classify_transaction",
        return_value=ClassificationResult(category=None, confidence=Decimal("0.00"), method="test"),
    ):
        init_response = client.post(
            f"/api/v1/bank-import/document/{document.id}/initialize",
            headers=bank_workbench_auth_headers,
        )

    assert init_response.status_code == 200
    summary = init_response.json()["import"]
    assert summary["pending_review_count"] == 2

    lines_response = client.get(
        f"/api/v1/bank-import/imports/{summary['id']}/lines",
        headers=bank_workbench_auth_headers,
    )
    assert lines_response.status_code == 200
    lines = lines_response.json()["lines"]
    assert len(lines) == 2

    first_confirm = client.post(
        f"/api/v1/bank-import/lines/{lines[0]['id']}/confirm-create",
        headers=bank_workbench_auth_headers,
    )
    assert first_confirm.status_code == 200
    first_payload = first_confirm.json()
    created_transaction_id = first_payload["transaction"]["id"]
    assert first_payload["line"]["review_status"] == "auto_created"

    second_confirm = client.post(
        f"/api/v1/bank-import/lines/{lines[1]['id']}/confirm-create",
        headers=bank_workbench_auth_headers,
    )
    assert second_confirm.status_code == 200
    second_payload = second_confirm.json()
    assert second_payload["line"]["review_status"] == "ignored_duplicate"
    assert second_payload["line"]["created_transaction_id"] is None
    assert second_payload["line"]["linked_transaction_id"] == created_transaction_id
    assert second_payload["transaction"]["id"] == created_transaction_id

    tx_count = (
        db.query(Transaction)
        .filter(Transaction.user_id == bank_workbench_user.id)
        .count()
    )
    assert tx_count == 1


def test_confirm_create_line_force_creates_even_when_duplicate_exists(
    client: TestClient,
    db: Session,
    bank_workbench_user: User,
    bank_workbench_auth_headers: dict,
):
    document = _make_custom_bank_statement_document(
        db,
        bank_workbench_user,
        file_name="duplicate-force-create.pdf",
        transactions=[
            {
                "date": "2024-12-19",
                "amount": "-2.03",
                "counterparty": "T-Mobile Austria GmbH",
                "purpose": "Ratenplan 9001004040 vom 22.05.2023",
                "reference": "Ratenplan 9001004040 vom 22.05.2023",
            },
            {
                "date": "2024-12-19",
                "amount": "-2.03",
                "counterparty": "T-Mobile Austria GmbH",
                "purpose": "Ratenplan 9001004040 vom 22.05.2023",
                "reference": "Ratenplan 9001004040 vom 22.05.2023",
            },
        ],
    )

    with patch(
        "app.services.bank_import_service.TransactionClassifier.classify_transaction",
        return_value=ClassificationResult(category=None, confidence=Decimal("0.00"), method="test"),
    ):
        init_response = client.post(
            f"/api/v1/bank-import/document/{document.id}/initialize",
            headers=bank_workbench_auth_headers,
        )

    assert init_response.status_code == 200
    summary = init_response.json()["import"]

    lines_response = client.get(
        f"/api/v1/bank-import/imports/{summary['id']}/lines",
        headers=bank_workbench_auth_headers,
    )
    assert lines_response.status_code == 200
    lines = lines_response.json()["lines"]

    first_confirm = client.post(
        f"/api/v1/bank-import/lines/{lines[0]['id']}/confirm-create",
        headers=bank_workbench_auth_headers,
    )
    assert first_confirm.status_code == 200

    second_confirm = client.post(
        f"/api/v1/bank-import/lines/{lines[1]['id']}/confirm-create?force=true",
        headers=bank_workbench_auth_headers,
    )
    assert second_confirm.status_code == 200
    second_payload = second_confirm.json()
    assert second_payload["line"]["review_status"] == "auto_created"
    assert second_payload["line"]["created_transaction_id"] == second_payload["transaction"]["id"]

    tx_count = (
        db.query(Transaction)
        .filter(Transaction.user_id == bank_workbench_user.id)
        .count()
    )
    assert tx_count == 2


def test_confirm_create_line_reuses_fuzzy_existing_match_instead_of_creating_duplicate(
    client: TestClient,
    db: Session,
    bank_workbench_user: User,
    bank_workbench_auth_headers: dict,
):
    document = _make_custom_bank_statement_document(
        db,
        bank_workbench_user,
        file_name="duplicate-fuzzy-match.pdf",
        transactions=[
            {
                "date": "2024-12-21",
                "amount": "-2.03",
                "counterparty": "T-Mobile Austria GmbH",
                "purpose": "Ratenplan 9001004040 vom 24.05.2023",
                "reference": "Ratenplan 9001004040 vom 24.05.2023",
            },
        ],
    )

    existing_transaction = Transaction(
        user_id=bank_workbench_user.id,
        type=TransactionType.EXPENSE,
        amount=Decimal("2.03"),
        transaction_date=date(2024, 12, 19),
        description="Ratenplan 9001004040 vom 22.05.2023",
        bank_reconciled=True,
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
    summary = init_response.json()["import"]
    assert summary["ignored_count"] == 1

    lines_response = client.get(
        f"/api/v1/bank-import/imports/{summary['id']}/lines",
        headers=bank_workbench_auth_headers,
    )
    assert lines_response.status_code == 200
    line_id = lines_response.json()["lines"][0]["id"]

    confirm_response = client.post(
        f"/api/v1/bank-import/lines/{line_id}/confirm-create",
        headers=bank_workbench_auth_headers,
    )
    assert confirm_response.status_code == 200
    payload = confirm_response.json()
    assert payload["line"]["review_status"] == "ignored_duplicate"
    assert payload["line"]["created_transaction_id"] is None
    assert payload["line"]["linked_transaction_id"] == existing_transaction.id
    assert payload["transaction"]["id"] == existing_transaction.id

    tx_count = (
        db.query(Transaction)
        .filter(Transaction.user_id == bank_workbench_user.id)
        .count()
    )
    assert tx_count == 1


def test_initialize_document_import_reuses_monthly_match_with_same_amount_and_similar_text(
    client: TestClient,
    db: Session,
    bank_workbench_user: User,
    bank_workbench_auth_headers: dict,
):
    document = _make_custom_bank_statement_document(
        db,
        bank_workbench_user,
        file_name="duplicate-monthly-match.pdf",
        transactions=[
            {
                "date": "2024-08-01",
                "amount": "-9.31",
                "counterparty": "Helvetia Versicherungen AG",
                "purpose": "2468104430/POL 4002211691 8/2024 HG",
                "reference": "2468104430/POL 4002211691 8/2024 HG",
            },
        ],
    )

    existing_transaction = Transaction(
        user_id=bank_workbench_user.id,
        type=TransactionType.EXPENSE,
        amount=Decimal("9.31"),
        transaction_date=date(2024, 7, 1),
        description="2454026682/POL 4002211691 7/2024 HG",
        bank_reconciled=True,
    )
    db.add(existing_transaction)
    db.commit()
    db.refresh(existing_transaction)

    with patch(
        "app.services.bank_import_service.TransactionClassifier.classify_transaction",
        return_value=ClassificationResult(category="insurance", confidence=Decimal("0.95"), method="test"),
    ):
        init_response = client.post(
            f"/api/v1/bank-import/document/{document.id}/initialize",
            headers=bank_workbench_auth_headers,
        )

    assert init_response.status_code == 200
    summary = init_response.json()["import"]
    assert summary["ignored_count"] == 1

    lines_response = client.get(
        f"/api/v1/bank-import/imports/{summary['id']}/lines",
        headers=bank_workbench_auth_headers,
    )
    assert lines_response.status_code == 200
    line = lines_response.json()["lines"][0]
    assert line["review_status"] == "ignored_duplicate"
    assert line["linked_transaction_id"] == existing_transaction.id

    tx_count = (
        db.query(Transaction)
        .filter(Transaction.user_id == bank_workbench_user.id)
        .count()
    )
    assert tx_count == 1


def test_confirm_create_line_learns_strict_rule_for_future_bank_imports(
    client: TestClient,
    db: Session,
    bank_workbench_user: User,
    bank_workbench_auth_headers: dict,
):
    first_document = _make_custom_bank_statement_document(
        db,
        bank_workbench_user,
        file_name="helvetia-first.pdf",
        transactions=[
            {
                "date": "2026-01-15",
                "amount": "-120.50",
                "counterparty": "Helvetia Versicherungen AG",
                "purpose": "Helvetia Versicherungen AG Policy Premium",
                "reference": "POL-1",
            },
        ],
    )

    with patch(
        "app.services.bank_import_service.TransactionClassifier.classify_transaction",
        return_value=ClassificationResult(category="insurance", confidence=Decimal("0.80"), method="rule"),
    ):
        init_response = client.post(
            f"/api/v1/bank-import/document/{first_document.id}/initialize",
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

        create_response = client.post(
            f"/api/v1/bank-import/lines/{line_id}/confirm-create",
            headers=bank_workbench_auth_headers,
        )
        assert create_response.status_code == 200
        assert create_response.json()["line"]["review_status"] == "auto_created"

    rule = (
        db.query(UserClassificationRule)
        .filter(
            UserClassificationRule.user_id == bank_workbench_user.id,
            UserClassificationRule.original_description == "Helvetia Versicherungen AG Policy Premium",
            UserClassificationRule.txn_type == "expense",
        )
        .one()
    )
    assert rule.category == "insurance"
    assert rule.rule_type == "auto"
    assert rule.hit_count == 1

    second_document = _make_custom_bank_statement_document(
        db,
        bank_workbench_user,
        file_name="helvetia-second.pdf",
        transactions=[
            {
                "date": "2026-03-15",
                "amount": "-120.50",
                "counterparty": "Helvetia Versicherungen AG",
                "purpose": "Helvetia Versicherungen AG Policy Premium",
                "reference": "POL-2",
            },
        ],
    )

    with patch(
        "app.services.transaction_classifier.RuleBasedClassifier.classify",
        return_value=_low_confidence_result("expense"),
    ), patch(
        "app.services.transaction_classifier.MLClassifier.classify",
        return_value=_low_confidence_result("expense"),
    ), patch(
        "app.services.transaction_classifier.TransactionClassifier._try_llm_classify",
        return_value=None,
    ):
        second_init = client.post(
            f"/api/v1/bank-import/document/{second_document.id}/initialize",
            headers=bank_workbench_auth_headers,
        )
        assert second_init.status_code == 200
        summary = second_init.json()["import"]
        assert summary["auto_created_count"] == 1
        assert summary["pending_review_count"] == 0

        second_lines = client.get(
            f"/api/v1/bank-import/imports/{summary['id']}/lines",
            headers=bank_workbench_auth_headers,
        )
        assert second_lines.status_code == 200
        payload_line = second_lines.json()["lines"][0]
        assert payload_line["review_status"] == "auto_created"
        assert Decimal(payload_line["confidence_score"]) == Decimal("1.00")


def test_confirm_create_line_without_category_does_not_learn_rule(
    client: TestClient,
    db: Session,
    bank_workbench_user: User,
    bank_workbench_auth_headers: dict,
):
    first_document = _make_custom_bank_statement_document(
        db,
        bank_workbench_user,
        file_name="unknown-first.pdf",
        transactions=[
            {
                "date": "2026-01-15",
                "amount": "-19.99",
                "counterparty": "ZXQY Merchant",
                "purpose": "ZXQY Merchant Random Charge",
                "reference": "ZXQY-1",
            },
        ],
    )

    with patch(
        "app.services.bank_import_service.TransactionClassifier.classify_transaction",
        return_value=ClassificationResult(category=None, confidence=Decimal("0.00"), method="test"),
    ):
        init_response = client.post(
            f"/api/v1/bank-import/document/{first_document.id}/initialize",
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

        create_response = client.post(
            f"/api/v1/bank-import/lines/{line_id}/confirm-create",
            headers=bank_workbench_auth_headers,
        )
        assert create_response.status_code == 200

    assert (
        db.query(UserClassificationRule)
        .filter(
            UserClassificationRule.user_id == bank_workbench_user.id,
            UserClassificationRule.original_description == "ZXQY Merchant Random Charge",
            UserClassificationRule.txn_type == "expense",
        )
        .count()
        == 0
    )

    second_document = _make_custom_bank_statement_document(
        db,
        bank_workbench_user,
        file_name="unknown-second.pdf",
        transactions=[
            {
                "date": "2026-03-15",
                "amount": "-19.99",
                "counterparty": "ZXQY Merchant",
                "purpose": "ZXQY Merchant Random Charge",
                "reference": "ZXQY-2",
            },
        ],
    )

    with patch(
        "app.services.transaction_classifier.RuleBasedClassifier.classify",
        return_value=_low_confidence_result("expense"),
    ), patch(
        "app.services.transaction_classifier.MLClassifier.classify",
        return_value=_low_confidence_result("expense"),
    ), patch(
        "app.services.transaction_classifier.TransactionClassifier._try_llm_classify",
        return_value=None,
    ):
        second_init = client.post(
            f"/api/v1/bank-import/document/{second_document.id}/initialize",
            headers=bank_workbench_auth_headers,
        )
        assert second_init.status_code == 200
        summary = second_init.json()["import"]
        assert summary["auto_created_count"] == 0
        assert summary["pending_review_count"] == 1


def test_confirm_create_line_low_confidence_category_does_not_learn_rule(
    client: TestClient,
    db: Session,
    bank_workbench_user: User,
    bank_workbench_auth_headers: dict,
):
    first_document = _make_custom_bank_statement_document(
        db,
        bank_workbench_user,
        file_name="low-confidence-first.pdf",
        transactions=[
            {
                "date": "2026-01-15",
                "amount": "-14.20",
                "counterparty": "Low Confidence Telecom",
                "purpose": "Low Confidence Telecom Monthly",
                "reference": "LC-1",
            },
        ],
    )

    with patch(
        "app.services.bank_import_service.TransactionClassifier.classify_transaction",
        return_value=ClassificationResult(category="telecom", confidence=Decimal("0.65"), method="rule"),
    ):
        init_response = client.post(
            f"/api/v1/bank-import/document/{first_document.id}/initialize",
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

        create_response = client.post(
            f"/api/v1/bank-import/lines/{line_id}/confirm-create",
            headers=bank_workbench_auth_headers,
        )
        assert create_response.status_code == 200

    assert (
        db.query(UserClassificationRule)
        .filter(
            UserClassificationRule.user_id == bank_workbench_user.id,
            UserClassificationRule.original_description == "Low Confidence Telecom Monthly",
            UserClassificationRule.txn_type == "expense",
        )
        .count()
        == 0
    )


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


def test_restore_ignored_line_returns_it_to_pending_review(
    client: TestClient,
    db: Session,
    bank_workbench_user: User,
    bank_workbench_auth_headers: dict,
):
    document = _make_bank_statement_document(db, bank_workbench_user, "restore-line.pdf")

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
    assert ignore_response.json()["line"]["review_status"] == "ignored_duplicate"

    restore_response = client.post(
        f"/api/v1/bank-import/lines/{line_id}/restore",
        headers=bank_workbench_auth_headers,
    )
    assert restore_response.status_code == 200
    payload = restore_response.json()
    assert payload["line"]["review_status"] == "pending_review"
    assert payload["line"]["suggested_action"] == "create_new"
    assert payload["line"]["resolution_reason"] == "new"
    assert payload["line"]["reviewed_at"] is None
    assert payload["line"]["reviewed_by"] is None
    assert payload["line"]["linked_transaction_id"] is None
    assert payload["line"]["created_transaction_id"] is None


def test_undo_create_line_deletes_created_transaction_and_resets_line(
    client: TestClient,
    db: Session,
    bank_workbench_user: User,
    bank_workbench_auth_headers: dict,
):
    document = _make_bank_statement_document(db, bank_workbench_user, "undo-create-line.pdf")

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

    create_response = client.post(
        f"/api/v1/bank-import/lines/{line_id}/confirm-create",
        headers=bank_workbench_auth_headers,
    )
    assert create_response.status_code == 200
    transaction_id = create_response.json()["transaction"]["id"]

    undo_response = client.post(
        f"/api/v1/bank-import/lines/{line_id}/undo-create",
        headers=bank_workbench_auth_headers,
    )
    assert undo_response.status_code == 200
    payload = undo_response.json()
    assert payload["line"]["review_status"] == "pending_review"
    assert payload["line"]["resolution_reason"] == "revoked_create"
    assert payload["line"]["created_transaction_id"] is None
    assert payload["line"]["linked_transaction_id"] is None

    deleted_transaction = (
        db.query(Transaction)
        .filter(Transaction.id == transaction_id)
        .first()
    )
    assert deleted_transaction is None


def test_unmatch_line_resets_to_pending_and_clears_previous_match_candidate(
    client: TestClient,
    db: Session,
    bank_workbench_user: User,
    bank_workbench_auth_headers: dict,
):
    document = _make_bank_statement_document(db, bank_workbench_user, "unmatch-line.pdf")

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

    unmatch_response = client.post(
        f"/api/v1/bank-import/lines/{rent_line['id']}/unmatch",
        headers=bank_workbench_auth_headers,
    )
    assert unmatch_response.status_code == 200
    payload = unmatch_response.json()
    assert payload["line"]["review_status"] == "pending_review"
    assert payload["line"]["suggested_action"] == "create_new"
    assert payload["line"]["resolution_reason"] == "revoked_match"
    assert payload["line"]["created_transaction_id"] is None
    assert payload["line"]["linked_transaction_id"] is None

    db.refresh(existing_transaction)
    assert existing_transaction.bank_reconciled is False
    assert existing_transaction.bank_reconciled_at is None


def test_get_import_endpoints_repair_orphaned_bank_line_states(
    client: TestClient,
    db: Session,
    bank_workbench_user: User,
    bank_workbench_auth_headers: dict,
):
    statement_import = BankStatementImport(
        user_id=bank_workbench_user.id,
        source_type=BankStatementImportSourceType.DOCUMENT,
        tax_year=2026,
    )
    db.add(statement_import)
    db.flush()

    db.add_all([
        BankStatementLine(
            import_id=statement_import.id,
            line_date=date(2026, 1, 15),
            amount=Decimal("-62.23"),
            counterparty="T-Mobile Austria GmbH",
            purpose="Mobile invoice December",
            raw_reference="Mobile invoice December",
            normalized_fingerprint="orphan-auto-created",
            review_status=BankStatementLineStatus.AUTO_CREATED,
            suggested_action=BankStatementSuggestedAction.CREATE_NEW,
            linked_transaction_id=None,
            created_transaction_id=None,
            reviewed_at=datetime.utcnow(),
            reviewed_by=bank_workbench_user.id,
        ),
        BankStatementLine(
            import_id=statement_import.id,
            line_date=date(2026, 1, 16),
            amount=Decimal("2400.00"),
            counterparty="Salary GmbH",
            purpose="Payroll",
            raw_reference="Payroll",
            normalized_fingerprint="orphan-matched-existing",
            review_status=BankStatementLineStatus.MATCHED_EXISTING,
            suggested_action=BankStatementSuggestedAction.MATCH_EXISTING,
            linked_transaction_id=None,
            created_transaction_id=None,
            reviewed_at=datetime.utcnow(),
            reviewed_by=bank_workbench_user.id,
        ),
        BankStatementLine(
            import_id=statement_import.id,
            line_date=date(2026, 1, 17),
            amount=Decimal("-18.90"),
            counterparty="Candidate Merchant",
            purpose="Suggested match",
            raw_reference="Suggested match",
            normalized_fingerprint="orphan-candidate",
            review_status=BankStatementLineStatus.PENDING_REVIEW,
            suggested_action=BankStatementSuggestedAction.MATCH_EXISTING,
            linked_transaction_id=None,
            created_transaction_id=None,
            reviewed_at=datetime.utcnow(),
            reviewed_by=bank_workbench_user.id,
        ),
    ])
    db.commit()

    summary_response = client.get(
        f"/api/v1/bank-import/imports/{statement_import.id}",
        headers=bank_workbench_auth_headers,
    )
    assert summary_response.status_code == 200
    summary_payload = summary_response.json()["import"]
    assert summary_payload["auto_created_count"] == 0
    assert summary_payload["matched_existing_count"] == 0
    assert summary_payload["pending_review_count"] == 3

    lines_response = client.get(
        f"/api/v1/bank-import/imports/{statement_import.id}/lines",
        headers=bank_workbench_auth_headers,
    )
    assert lines_response.status_code == 200
    lines_payload = lines_response.json()["lines"]

    assert [line["review_status"] for line in lines_payload] == [
        "pending_review",
        "pending_review",
        "pending_review",
    ]
    assert [line["suggested_action"] for line in lines_payload] == [
        "create_new",
        "create_new",
        "create_new",
    ]
    assert [line["resolution_reason"] for line in lines_payload] == [
        "orphan_repaired",
        "orphan_repaired",
        "orphan_repaired",
    ]
    assert all(line["linked_transaction_id"] is None for line in lines_payload)
    assert all(line["created_transaction_id"] is None for line in lines_payload)

    db.expire_all()
    repaired_lines = (
        db.query(BankStatementLine)
        .filter(BankStatementLine.import_id == statement_import.id)
        .order_by(BankStatementLine.line_date, BankStatementLine.id)
        .all()
    )
    assert all(line.review_status == BankStatementLineStatus.PENDING_REVIEW for line in repaired_lines)
    assert all(line.suggested_action == BankStatementSuggestedAction.CREATE_NEW for line in repaired_lines)
    assert all(
        line.resolution_reason == BankStatementLineResolutionReason.ORPHAN_REPAIRED.value
        for line in repaired_lines
    )
    assert all(line.reviewed_at is None for line in repaired_lines)
    assert all(line.reviewed_by is None for line in repaired_lines)
