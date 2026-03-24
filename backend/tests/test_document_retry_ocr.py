from datetime import datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from types import SimpleNamespace

from app.api.v1.endpoints import documents as documents_endpoint
from app.core.security import create_access_token
from app.models.bank_statement_import import (
    BankStatementImport,
    BankStatementImportSourceType,
    BankStatementLine,
    BankStatementLineStatus,
    BankStatementSuggestedAction,
)
from app.models.document import Document, DocumentType
from app.models.transaction import Transaction, TransactionType
from tests.fixtures.models import create_test_user


def _auth_headers(email: str) -> dict[str, str]:
    token = create_access_token(data={"sub": email})
    return {"Authorization": f"Bearer {token}"}


def _make_document(
    *,
    user_id: int,
    document_type: DocumentType = DocumentType.RECEIPT,
    file_name: str,
    ocr_result: dict | None = None,
    transaction_id: int | None = None,
    raw_text: str = "old raw text",
    confidence_score: float = 0.92,
) -> Document:
    return Document(
        user_id=user_id,
        document_type=document_type,
        file_path=f"documents/{file_name}",
        file_name=file_name,
        file_size=1024,
        mime_type="application/pdf",
        ocr_result=ocr_result,
        raw_text=raw_text,
        confidence_score=confidence_score,
        processed_at=datetime.utcnow(),
        transaction_id=transaction_id,
    )


def test_retry_ocr_keeps_previous_result_until_new_run_finishes(
    client: TestClient,
    db: Session,
    monkeypatch,
):
    user = create_test_user(db, email="retry-ocr@example.com")
    user.email_verified = True
    db.commit()
    db.refresh(user)

    document = _make_document(
        user_id=user.id,
        file_name="retry-ocr.pdf",
        ocr_result={
            "merchant": "Billa",
            "_pipeline": {"current_state": "completed"},
        },
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    queued_document_ids: list[int] = []
    billed_document_ids: list[int] = []

    class DummyOCRTask:
        @staticmethod
        def delay(document_id: int):
            queued_document_ids.append(document_id)

    def fake_deduct_ocr_scan_credits(db_session, user_id: int, charged_document_id: int):
        assert user_id == user.id
        billed_document_ids.append(charged_document_id)
        return SimpleNamespace(
            balance_after=SimpleNamespace(available_without_overage=1975)
        )

    monkeypatch.setattr(documents_endpoint, "process_document_ocr", DummyOCRTask)
    monkeypatch.setattr(
        documents_endpoint,
        "_deduct_ocr_scan_credits",
        fake_deduct_ocr_scan_credits,
    )

    response = client.post(
        f"/api/v1/documents/{document.id}/retry-ocr",
        headers=_auth_headers(user.email),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["document_id"] == document.id
    assert payload["current_state"] == "processing_phase_1"
    assert payload["previous_result_retained"] is True
    assert response.headers["X-Credits-Remaining"] == "1975"

    db.refresh(document)
    assert document.raw_text == "old raw text"
    assert float(document.confidence_score) == 0.92
    assert document.ocr_result["merchant"] == "Billa"
    assert document.ocr_result["_pipeline"]["current_state"] == "processing_phase_1"
    assert document.ocr_result["_pipeline"]["ocr_provider_override"] == "anthropic"
    assert document.ocr_result["_pipeline"]["reprocess_mode"] == "claude_direct"
    assert "reprocess_requested_at" in document.ocr_result["_pipeline"]
    assert payload["vision_provider_preference"] == "anthropic"
    assert payload["reprocess_mode"] == "claude_direct"
    assert billed_document_ids == [document.id]
    assert queued_document_ids == [document.id]


def test_retry_ocr_rejects_confirmed_document_before_queueing(
    client: TestClient,
    db: Session,
    monkeypatch,
):
    user = create_test_user(db, email="retry-ocr-confirmed@example.com")
    user.email_verified = True
    db.commit()
    db.refresh(user)

    document = _make_document(
        user_id=user.id,
        file_name="confirmed.pdf",
        ocr_result={
            "confirmed": True,
            "_pipeline": {"current_state": "completed"},
        },
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    def _should_not_queue(*args, **kwargs):
        raise AssertionError("retry-ocr should not queue confirmed documents")

    def _should_not_bill(*args, **kwargs):
        raise AssertionError("retry-ocr should not bill confirmed documents")

    monkeypatch.setattr(documents_endpoint.process_document_ocr, "delay", _should_not_queue)
    monkeypatch.setattr(documents_endpoint, "_deduct_ocr_scan_credits", _should_not_bill)

    response = client.post(
        f"/api/v1/documents/{document.id}/retry-ocr",
        headers=_auth_headers(user.email),
    )

    assert response.status_code == 409
    assert (
        response.json()["detail"]
        == "Cannot reprocess a document that is already confirmed or linked to a transaction."
    )


def test_retry_ocr_rejects_confirmed_contract_suggestion_before_queueing(
    client: TestClient,
    db: Session,
    monkeypatch,
):
    user = create_test_user(db, email="retry-ocr-confirmed-contract@example.com")
    user.email_verified = True
    db.commit()
    db.refresh(user)

    document = _make_document(
        user_id=user.id,
        document_type=DocumentType.PURCHASE_CONTRACT,
        file_name="confirmed-contract.pdf",
        ocr_result={
            "import_suggestion": {
                "type": "create_property",
                "status": "confirmed",
                "property_id": "prop-123",
            },
            "_pipeline": {"current_state": "completed"},
        },
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    def _should_not_queue(*args, **kwargs):
        raise AssertionError("retry-ocr should not queue confirmed contract documents")

    def _should_not_bill(*args, **kwargs):
        raise AssertionError("retry-ocr should not bill confirmed contract documents")

    monkeypatch.setattr(documents_endpoint.process_document_ocr, "delay", _should_not_queue)
    monkeypatch.setattr(documents_endpoint, "_deduct_ocr_scan_credits", _should_not_bill)

    response = client.post(
        f"/api/v1/documents/{document.id}/retry-ocr",
        headers=_auth_headers(user.email),
    )

    assert response.status_code == 409
    assert (
        response.json()["detail"]
        == "Cannot reprocess a document that is already confirmed or linked to a transaction."
    )


def test_retry_ocr_rejects_document_that_is_already_processing(
    client: TestClient,
    db: Session,
    monkeypatch,
):
    user = create_test_user(db, email="retry-ocr-processing@example.com")
    user.email_verified = True
    db.commit()
    db.refresh(user)

    document = _make_document(
        user_id=user.id,
        file_name="processing.pdf",
        ocr_result={
            "_pipeline": {"current_state": "processing_phase_2"},
        },
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    def _should_not_queue(*args, **kwargs):
        raise AssertionError("retry-ocr should not queue already-processing documents")

    def _should_not_bill(*args, **kwargs):
        raise AssertionError("retry-ocr should not bill already-processing documents")

    monkeypatch.setattr(documents_endpoint.process_document_ocr, "delay", _should_not_queue)
    monkeypatch.setattr(documents_endpoint, "_deduct_ocr_scan_credits", _should_not_bill)

    response = client.post(
        f"/api/v1/documents/{document.id}/retry-ocr",
        headers=_auth_headers(user.email),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Document is already being processed."


def test_retry_ocr_rejects_document_with_linked_transactions_even_without_document_transaction_id(
    client: TestClient,
    db: Session,
    monkeypatch,
):
    user = create_test_user(db, email="retry-ocr-linked@example.com")
    user.email_verified = True
    db.commit()
    db.refresh(user)

    document = _make_document(
        user_id=user.id,
        document_type=DocumentType.BANK_STATEMENT,
        file_name="linked-bank-statement.pdf",
        ocr_result={
            "import_suggestion": {
                "type": "import_bank_statement",
                "status": "pending",
            },
            "_pipeline": {"current_state": "completed"},
        },
        transaction_id=None,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    transaction = Transaction(
        user_id=user.id,
        type=TransactionType.EXPENSE,
        amount=Decimal("33.00"),
        transaction_date=datetime.utcnow().date(),
        description="Linked bank line transaction",
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    statement_import = BankStatementImport(
        user_id=user.id,
        source_type=BankStatementImportSourceType.DOCUMENT,
        source_document_id=document.id,
        tax_year=2024,
    )
    db.add(statement_import)
    db.flush()

    db.add(
        BankStatementLine(
            import_id=statement_import.id,
            line_date=datetime.utcnow().date(),
            amount=Decimal("-33.00"),
            counterparty="T-Mobile",
            purpose="Invoice 123",
            raw_reference="Invoice 123",
            normalized_fingerprint="fp-linked-1",
            review_status=BankStatementLineStatus.AUTO_CREATED,
            suggested_action=BankStatementSuggestedAction.CREATE_NEW,
            confidence_score=Decimal("0.90"),
            linked_transaction_id=transaction.id,
            created_transaction_id=transaction.id,
            reviewed_by=user.id,
            reviewed_at=datetime.utcnow(),
        )
    )
    db.commit()

    def _should_not_queue(*args, **kwargs):
        raise AssertionError("retry-ocr should not queue linked bank statement documents")

    def _should_not_bill(*args, **kwargs):
        raise AssertionError("retry-ocr should not bill linked bank statement documents")

    monkeypatch.setattr(documents_endpoint.process_document_ocr, "delay", _should_not_queue)
    monkeypatch.setattr(documents_endpoint, "_deduct_ocr_scan_credits", _should_not_bill)

    response = client.post(
        f"/api/v1/documents/{document.id}/retry-ocr",
        headers=_auth_headers(user.email),
    )

    assert response.status_code == 409
    assert (
        response.json()["detail"]
        == "Cannot reprocess a document that is already confirmed or linked to a transaction."
    )


def test_get_documents_exposes_linked_transaction_count_for_bank_statement_documents(
    client: TestClient,
    db: Session,
):
    user = create_test_user(db, email="retry-ocr-list@example.com")
    user.email_verified = True
    db.commit()
    db.refresh(user)

    document = _make_document(
        user_id=user.id,
        document_type=DocumentType.BANK_STATEMENT,
        file_name="count-bank-statement.pdf",
        ocr_result={
            "import_suggestion": {
                "type": "import_bank_statement",
                "status": "pending",
            }
        },
        transaction_id=None,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    transaction = Transaction(
        user_id=user.id,
        type=TransactionType.EXPENSE,
        amount=Decimal("72.78"),
        transaction_date=datetime.utcnow().date(),
        description="Created from bank statement",
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    statement_import = BankStatementImport(
        user_id=user.id,
        source_type=BankStatementImportSourceType.DOCUMENT,
        source_document_id=document.id,
        tax_year=2024,
    )
    db.add(statement_import)
    db.flush()

    db.add(
        BankStatementLine(
            import_id=statement_import.id,
            line_date=datetime.utcnow().date(),
            amount=Decimal("-72.78"),
            counterparty="T-Mobile",
            purpose="Invoice 456",
            raw_reference="Invoice 456",
            normalized_fingerprint="fp-count-1",
            review_status=BankStatementLineStatus.AUTO_CREATED,
            suggested_action=BankStatementSuggestedAction.CREATE_NEW,
            confidence_score=Decimal("0.90"),
            linked_transaction_id=transaction.id,
            created_transaction_id=transaction.id,
            reviewed_by=user.id,
            reviewed_at=datetime.utcnow(),
        )
    )
    db.commit()

    response = client.get(
        "/api/v1/documents?page=1&page_size=20",
        headers=_auth_headers(user.email),
    )

    assert response.status_code == 200
    payload = response.json()
    returned = next(item for item in payload["documents"] if item["id"] == document.id)
    assert returned["linked_transaction_count"] == 1


def test_batch_reprocess_all_skips_confirmed_documents_without_transaction_links(
    client: TestClient,
    db: Session,
    monkeypatch,
):
    user = create_test_user(db, email="retry-ocr-batch@example.com")
    user.email_verified = True
    user.language = "en"
    db.commit()
    db.refresh(user)

    confirmed_document = _make_document(
        user_id=user.id,
        file_name="confirmed-receipt.pdf",
        ocr_result={"confirmed": True},
        raw_text="keep confirmed raw text",
    )
    confirmed_contract_document = _make_document(
        user_id=user.id,
        document_type=DocumentType.PURCHASE_CONTRACT,
        file_name="confirmed-contract.pdf",
        ocr_result={
            "import_suggestion": {
                "type": "create_property",
                "status": "confirmed",
                "property_id": "123",
            }
        },
        raw_text="keep contract raw text",
    )
    pending_document = _make_document(
        user_id=user.id,
        file_name="pending-receipt.pdf",
        ocr_result={"merchant": "Billa"},
        raw_text="clear pending raw text",
    )
    db.add_all([confirmed_document, confirmed_contract_document, pending_document])
    db.commit()
    db.refresh(confirmed_document)
    db.refresh(confirmed_contract_document)
    db.refresh(pending_document)

    queued_document_ids: list[int] = []

    class DummyOCRTask:
        @staticmethod
        def delay(document_id: int):
            queued_document_ids.append(document_id)

    monkeypatch.setattr(documents_endpoint, "process_document_ocr", DummyOCRTask)

    response = client.post(
        "/api/v1/documents/batch/reprocess-all",
        headers=_auth_headers(user.email),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["document_ids"] == [pending_document.id]
    assert queued_document_ids == [pending_document.id]

    db.refresh(confirmed_document)
    db.refresh(confirmed_contract_document)
    db.refresh(pending_document)

    assert confirmed_document.ocr_result == {"confirmed": True}
    assert confirmed_document.raw_text == "keep confirmed raw text"
    assert confirmed_contract_document.ocr_result == {
        "import_suggestion": {
            "type": "create_property",
            "status": "confirmed",
            "property_id": "123",
        }
    }
    assert confirmed_contract_document.raw_text == "keep contract raw text"

    assert pending_document.ocr_result is None
    assert pending_document.raw_text is None
    assert pending_document.confidence_score is None
    assert pending_document.processed_at is None


def test_batch_reprocess_all_skips_auto_created_asset_outcomes_without_transaction_links(
    client: TestClient,
    db: Session,
    monkeypatch,
):
    user = create_test_user(db, email="retry-ocr-batch-asset@example.com")
    user.email_verified = True
    user.language = "en"
    db.commit()
    db.refresh(user)

    auto_created_asset_document = _make_document(
        user_id=user.id,
        document_type=DocumentType.PURCHASE_CONTRACT,
        file_name="asset-contract.pdf",
        ocr_result={
            "asset_outcome": {
                "status": "auto_created",
                "asset_id": "asset-1",
            }
        },
        raw_text="keep asset raw text",
    )
    pending_document = _make_document(
        user_id=user.id,
        file_name="pending-asset-retry.pdf",
        ocr_result={"merchant": "Billa"},
        raw_text="clear pending raw text",
    )
    db.add_all([auto_created_asset_document, pending_document])
    db.commit()
    db.refresh(auto_created_asset_document)
    db.refresh(pending_document)

    queued_document_ids: list[int] = []

    class DummyOCRTask:
        @staticmethod
        def delay(document_id: int):
            queued_document_ids.append(document_id)

    monkeypatch.setattr(documents_endpoint, "process_document_ocr", DummyOCRTask)

    response = client.post(
        "/api/v1/documents/batch/reprocess-all",
        headers=_auth_headers(user.email),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["document_ids"] == [pending_document.id]
    assert queued_document_ids == [pending_document.id]

    db.refresh(auto_created_asset_document)
    db.refresh(pending_document)

    assert auto_created_asset_document.ocr_result == {
        "asset_outcome": {
            "status": "auto_created",
            "asset_id": "asset-1",
        }
    }
    assert auto_created_asset_document.raw_text == "keep asset raw text"
    assert pending_document.ocr_result is None
