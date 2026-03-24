"""Tests for document upload and OCR transaction deduplication."""
import asyncio
import io
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from fastapi import BackgroundTasks, HTTPException
from PIL import Image
from starlette.datastructures import Headers, UploadFile

from app.api.v1.endpoints import documents as documents_endpoint
from app.models.bank_statement_import import (
    BankStatementImport,
    BankStatementImportSourceType,
    BankStatementLine,
    BankStatementLineStatus,
    BankStatementSuggestedAction,
)
from app.models.document import Document, DocumentType
from app.models.transaction import ExpenseCategory, Transaction, TransactionType
from app.models.user import User, UserType
from app.services.storage_service import StorageUnavailableError
from app.services.ocr_transaction_service import OCRTransactionService


def _make_user(db, email: str = "dedup@example.com") -> User:
    user = User(
        email=email,
        password_hash="hashed",
        name="Dedup User",
        user_type=UserType.SELF_EMPLOYED,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_document(
    db,
    user_id: int,
    *,
    file_name: str,
    file_hash: str | None = None,
    file_size: int = 128,
    uploaded_at: datetime | None = None,
    processed_at: datetime | None = None,
    raw_text: str | None = None,
    ocr_result=None,
) -> Document:
    document = Document(
        user_id=user_id,
        document_type=DocumentType.RECEIPT,
        file_path=f"users/{user_id}/documents/{file_name}",
        file_name=file_name,
        file_hash=file_hash,
        file_size=file_size,
        mime_type="application/pdf",
        uploaded_at=uploaded_at or datetime.utcnow(),
        processed_at=processed_at,
        raw_text=raw_text,
        ocr_result=ocr_result,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def _make_bank_import_line(
    db,
    user: User,
    *,
    transaction_id: int | None = None,
    review_status: BankStatementLineStatus = BankStatementLineStatus.PENDING_REVIEW,
    suggested_action: BankStatementSuggestedAction = BankStatementSuggestedAction.CREATE_NEW,
    amount: Decimal = Decimal("100.00"),
) -> BankStatementLine:
    statement_import = BankStatementImport(
        user_id=user.id,
        source_type=BankStatementImportSourceType.DOCUMENT,
        tax_year=2026,
    )
    db.add(statement_import)
    db.flush()

    line = BankStatementLine(
        import_id=statement_import.id,
        line_date=date(2026, 1, 15),
        amount=amount,
        counterparty="Delete cascade counterparty",
        purpose="Delete cascade purpose",
        raw_reference="DELETE-CASCADE-REF",
        normalized_fingerprint=f"delete-cascade-{statement_import.id}-{amount}",
        review_status=review_status,
        suggested_action=suggested_action,
        linked_transaction_id=transaction_id,
        created_transaction_id=transaction_id if review_status == BankStatementLineStatus.AUTO_CREATED else None,
        reviewed_at=datetime.utcnow(),
        reviewed_by=user.id,
    )
    db.add(line)
    db.commit()
    db.refresh(line)
    return line


def _make_upload_file(
    filename: str,
    content: bytes,
    content_type: str = "application/pdf",
) -> UploadFile:
    return UploadFile(
        filename=filename,
        file=io.BytesIO(content),
        headers=Headers({"content-type": content_type}),
    )


def _make_image_bytes(color: str) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (200, 300), color=color).save(buffer, format="PNG")
    return buffer.getvalue()


def _make_request():
    request = MagicMock()
    request.headers = {}
    return request


class _DummyDeduction:
    def __init__(self, available_without_overage: int = 999):
        self.balance_after = type(
            "_DummyBalanceAfter",
            (),
            {"available_without_overage": available_without_overage},
        )()


def test_upload_document_reuses_existing_processed_duplicate(db, monkeypatch):
    """Exact duplicate uploads should reuse the existing document and skip OCR requeue."""
    user = _make_user(db)
    content = b"same-pdf-binary"
    file_hash = documents_endpoint._compute_file_hash(content)
    existing = _make_document(
        db,
        user.id,
        file_name="existing.pdf",
        file_hash=file_hash,
        processed_at=datetime.utcnow(),
        raw_text="recognized text",
        ocr_result={"amount": 12.5},
    )

    storage = MagicMock()
    scheduled = []
    monkeypatch.setattr(documents_endpoint, "get_storage_service", lambda: storage)
    monkeypatch.setattr(
        documents_endpoint,
        "_schedule_ocr_processing",
        lambda background_tasks, document_id: scheduled.append(document_id),
    )

    response = asyncio.run(
        documents_endpoint.upload_document(
            request=_make_request(),
            background_tasks=BackgroundTasks(),
            file=_make_upload_file("duplicate.pdf", content),
            property_id=None,
            current_user=user,
            db=db,
        )
    )

    assert response.id == existing.id
    assert response.deduplicated is True
    assert response.duplicate_of_document_id == existing.id
    assert "Existing document reused" in response.message
    assert db.query(Document).count() == 1
    storage.upload_file.assert_not_called()
    assert scheduled == []


def test_batch_upload_deduplicates_within_same_request(db, monkeypatch):
    """Batch uploads should create one document and reuse it for exact duplicates."""
    user = _make_user(db, email="batch@example.com")
    content = b"shared-batch-content"

    storage = MagicMock()
    storage.upload_file.return_value = True
    scheduled = []
    monkeypatch.setattr(documents_endpoint, "get_storage_service", lambda: storage)
    monkeypatch.setattr(
        documents_endpoint,
        "_schedule_ocr_processing",
        lambda background_tasks, document_id: scheduled.append(document_id),
    )
    monkeypatch.setattr(
        documents_endpoint,
        "_deduct_ocr_scan_credits",
        lambda db, user_id, document_id: _DummyDeduction(),
    )

    response = asyncio.run(
        documents_endpoint.batch_upload_documents(
            request=_make_request(),
            background_tasks=BackgroundTasks(),
            files=[
                _make_upload_file("first.pdf", content),
                _make_upload_file("second.pdf", content),
            ],
            property_id=None,
            current_user=user,
            db=db,
        )
    )

    assert response.total_uploaded == 1
    assert len(response.successful) == 2
    assert response.successful[0].deduplicated is False
    assert response.successful[1].deduplicated is True
    assert db.query(Document).count() == 1
    assert storage.upload_file.call_count == 1
    assert len(scheduled) == 1


def test_duplicate_upload_restarts_ocr_only_after_failed_processing(db, monkeypatch):
    """A duplicate upload may retrigger OCR only for an already-failed document."""
    user = _make_user(db, email="retry@example.com")
    content = b"failed-doc-content"
    file_hash = documents_endpoint._compute_file_hash(content)
    failed_document = _make_document(
        db,
        user.id,
        file_name="failed.pdf",
        file_hash=file_hash,
        processed_at=datetime.utcnow(),
        raw_text=None,
        ocr_result=None,
    )

    storage = MagicMock()
    scheduled = []
    monkeypatch.setattr(documents_endpoint, "get_storage_service", lambda: storage)
    monkeypatch.setattr(
        documents_endpoint,
        "_schedule_ocr_processing",
        lambda background_tasks, document_id: scheduled.append(document_id),
    )

    response = asyncio.run(
        documents_endpoint.upload_document(
            request=_make_request(),
            background_tasks=BackgroundTasks(),
            file=_make_upload_file("retry.pdf", content),
            property_id=None,
            current_user=user,
            db=db,
        )
    )

    assert response.id == failed_document.id
    assert response.deduplicated is True
    assert "processing restarted" in response.message
    assert scheduled == [failed_document.id]
    storage.upload_file.assert_not_called()


def test_duplicate_upload_matches_legacy_document_without_file_hash(db, monkeypatch):
    """Legacy documents without file_hash should be lazily backfilled and reused."""
    user = _make_user(db, email="legacy-dedup@example.com")
    content = b"legacy-upload-content"
    existing = _make_document(
        db,
        user.id,
        file_name="legacy.pdf",
        file_hash=None,
        file_size=len(content),
        processed_at=datetime.utcnow(),
        raw_text="already processed",
        ocr_result={"amount": 19.99},
    )

    storage = MagicMock()
    storage.download_file.return_value = content
    scheduled = []
    monkeypatch.setattr(documents_endpoint, "get_storage_service", lambda: storage)
    monkeypatch.setattr(
        documents_endpoint,
        "_schedule_ocr_processing",
        lambda background_tasks, document_id: scheduled.append(document_id),
    )

    response = asyncio.run(
        documents_endpoint.upload_document(
            request=_make_request(),
            background_tasks=BackgroundTasks(),
            file=_make_upload_file("legacy-reupload.pdf", content),
            property_id=None,
            current_user=user,
            db=db,
        )
    )

    db.refresh(existing)
    assert response.id == existing.id
    assert response.deduplicated is True
    assert existing.file_hash == documents_endpoint._compute_file_hash(content)
    assert db.query(Document).count() == 1
    storage.upload_file.assert_not_called()
    assert scheduled == []


def test_upload_document_returns_503_when_storage_service_is_unavailable(db, monkeypatch):
    """Storage endpoint failures should surface as a fast 503, not an internal error."""
    user = _make_user(db, email="storage-down@example.com")
    user.language = "en"
    db.commit()
    request = _make_request()

    def _raise_storage_unavailable():
        raise StorageUnavailableError("storage down")

    monkeypatch.setattr(documents_endpoint, "get_storage_service", _raise_storage_unavailable)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            documents_endpoint.upload_document(
                request=request,
                background_tasks=BackgroundTasks(),
                file=_make_upload_file("storage-down.pdf", b"pdf-content"),
                property_id=None,
                current_user=user,
                db=db,
            )
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "Failed to upload file to storage."
    assert db.query(Document).count() == 0


def test_upload_document_returns_503_when_storage_upload_fails(db, monkeypatch):
    """A failed object-store write should not bubble up as a raw boto exception."""
    user = _make_user(db, email="storage-write-failed@example.com")
    user.language = "en"
    db.commit()
    request = _make_request()

    storage = MagicMock()
    storage.upload_file.return_value = False
    monkeypatch.setattr(documents_endpoint, "get_storage_service", lambda: storage)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            documents_endpoint.upload_document(
                request=request,
                background_tasks=BackgroundTasks(),
                file=_make_upload_file("storage-failed.pdf", b"pdf-content"),
                property_id=None,
                current_user=user,
                db=db,
            )
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "Failed to upload file to storage."
    assert db.query(Document).count() == 0


def test_create_transaction_from_suggestion_creates_new_transaction(db):
    """A unique OCR suggestion should create a new linked transaction."""
    user = _make_user(db, email="ocr-create@example.com")
    document = _make_document(db, user.id, file_name="receipt-create.pdf")
    service = OCRTransactionService(db)

    result = service.create_transaction_from_suggestion_with_result(
        {
            "document_id": document.id,
            "transaction_type": TransactionType.EXPENSE.value,
            "amount": "42.50",
            "date": "2026-03-01",
            "description": "BILLA Supermarket",
            "category": ExpenseCategory.GROCERIES.value,
            "is_deductible": False,
            "deduction_reason": "Private groceries",
            "confidence": 0.88,
            "needs_review": False,
        },
        user.id,
    )

    db.refresh(document)
    assert result.created is True
    assert result.transaction.id is not None
    assert result.transaction.document_id == document.id
    assert document.transaction_id == result.transaction.id
    assert db.query(Transaction).count() == 1


def test_create_transaction_from_suggestion_reuses_duplicate_transaction(db):
    """OCR auto-create should skip creating a duplicate transaction."""
    user = _make_user(db, email="ocr-duplicate@example.com")
    document = _make_document(db, user.id, file_name="receipt-duplicate.pdf")
    existing_transaction = Transaction(
        user_id=user.id,
        type=TransactionType.EXPENSE,
        amount=Decimal("42.50"),
        transaction_date=date(2026, 3, 1),
        description="BILLA Supermarket",
        expense_category=ExpenseCategory.GROCERIES,
        document_id=None,
        import_source="ocr",
        needs_review=False,
    )
    db.add(existing_transaction)
    db.commit()
    db.refresh(existing_transaction)

    service = OCRTransactionService(db)
    result = service.create_transaction_from_suggestion_with_result(
        {
            "document_id": document.id,
            "transaction_type": TransactionType.EXPENSE.value,
            "amount": "42.50",
            "date": "2026-03-01",
            "description": "BILLA Supermarket",
            "category": ExpenseCategory.GROCERIES.value,
            "is_deductible": False,
            "deduction_reason": "Private groceries",
            "confidence": 0.88,
            "needs_review": False,
        },
        user.id,
    )

    db.refresh(document)
    assert result.created is False
    assert result.transaction.id == existing_transaction.id
    assert result.duplicate_of_id == existing_transaction.id
    assert result.duplicate_confidence == 1.0
    assert db.query(Transaction).count() == 1
    assert document.transaction_id == existing_transaction.id


def test_create_transaction_from_suggestion_accepts_uppercase_enum_name_category(db):
    """OCR auto-create should accept enum names like MAINTENANCE from LLM suggestions."""
    user = _make_user(db, email="ocr-uppercase-category@example.com")
    document = _make_document(db, user.id, file_name="receipt-uppercase-category.pdf")
    service = OCRTransactionService(db)

    result = service.create_transaction_from_suggestion_with_result(
        {
            "document_id": document.id,
            "transaction_type": "EXPENSE",
            "amount": "237.90",
            "date": "2024-12-30",
            "description": "OAMTC: battery replacement and coolant",
            "category": "MAINTENANCE",
            "is_deductible": True,
            "deduction_reason": "Betrieblich veranlasste Fahrzeugwartung",
            "confidence": 0.92,
            "needs_review": False,
        },
        user.id,
    )

    db.refresh(document)
    assert result.created is True
    assert result.transaction.type == TransactionType.EXPENSE
    assert result.transaction.expense_category == ExpenseCategory.MAINTENANCE
    assert result.transaction.document_id == document.id
    assert document.transaction_id == result.transaction.id


def test_upload_image_group_creates_one_pdf_document(db, monkeypatch):
    """Uploading multiple images together should create one combined PDF document."""
    user = _make_user(db, email="grouped@example.com")
    storage = MagicMock()
    storage.upload_file.return_value = True
    scheduled = []
    monkeypatch.setattr(documents_endpoint, "get_storage_service", lambda: storage)
    monkeypatch.setattr(
        documents_endpoint,
        "_schedule_ocr_processing",
        lambda background_tasks, document_id: scheduled.append(document_id),
    )
    monkeypatch.setattr(
        documents_endpoint,
        "_deduct_ocr_scan_credits",
        lambda db, user_id, document_id: _DummyDeduction(),
    )

    response = asyncio.run(
        documents_endpoint.upload_image_group(
            request=_make_request(),
            background_tasks=BackgroundTasks(),
            files=[
                _make_upload_file("page-1.png", _make_image_bytes("red"), "image/png"),
                _make_upload_file("page-2.png", _make_image_bytes("blue"), "image/png"),
            ],
            property_id=None,
            current_user=user,
            db=db,
        )
    )

    created_document = db.query(Document).one()
    assert response.id == created_document.id
    assert response.mime_type == "application/pdf"
    assert response.file_name.endswith(".pdf")
    assert response.deduplicated is False
    assert created_document.mime_type == "application/pdf"
    assert created_document.file_size > 0
    assert storage.upload_file.call_count == 1
    assert scheduled == [created_document.id]


def test_upload_image_group_reuses_existing_duplicate_document(db, monkeypatch):
    """The same ordered set of images should deduplicate to the existing combined document."""
    user = _make_user(db, email="grouped-duplicate@example.com")
    storage = MagicMock()
    storage.upload_file.return_value = True
    scheduled = []
    monkeypatch.setattr(documents_endpoint, "get_storage_service", lambda: storage)
    monkeypatch.setattr(
        documents_endpoint,
        "_schedule_ocr_processing",
        lambda background_tasks, document_id: scheduled.append(document_id),
    )
    monkeypatch.setattr(
        documents_endpoint,
        "_deduct_ocr_scan_credits",
        lambda db, user_id, document_id: _DummyDeduction(),
    )

    first_response = asyncio.run(
        documents_endpoint.upload_image_group(
            request=_make_request(),
            background_tasks=BackgroundTasks(),
            files=[
                _make_upload_file("page-1.png", _make_image_bytes("green"), "image/png"),
                _make_upload_file("page-2.png", _make_image_bytes("yellow"), "image/png"),
            ],
            property_id=None,
            current_user=user,
            db=db,
        )
    )

    second_response = asyncio.run(
        documents_endpoint.upload_image_group(
            request=_make_request(),
            background_tasks=BackgroundTasks(),
            files=[
                _make_upload_file("page-1.png", _make_image_bytes("green"), "image/png"),
                _make_upload_file("page-2.png", _make_image_bytes("yellow"), "image/png"),
            ],
            property_id=None,
            current_user=user,
            db=db,
        )
    )

    assert first_response.id == second_response.id
    assert second_response.deduplicated is True
    assert second_response.duplicate_of_document_id == first_response.id
    assert db.query(Document).count() == 1
    assert storage.upload_file.call_count == 1
    assert scheduled == [first_response.id]


def test_delete_document_with_data_resets_auto_created_bank_line(db, monkeypatch):
    user = _make_user(db, email="delete-cascade@example.com")
    document = _make_document(
        db,
        user.id,
        file_name="delete-me.pdf",
    )

    transaction = Transaction(
        user_id=user.id,
        type=TransactionType.EXPENSE,
        amount=Decimal("100.00"),
        transaction_date=date(2026, 1, 15),
        description="Cascade delete transaction",
        expense_category=ExpenseCategory.OTHER,
        document_id=document.id,
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    line = _make_bank_import_line(
        db,
        user,
        transaction_id=transaction.id,
        review_status=BankStatementLineStatus.AUTO_CREATED,
        suggested_action=BankStatementSuggestedAction.CREATE_NEW,
    )

    monkeypatch.setattr(documents_endpoint, "get_storage_service", lambda: MagicMock())

    documents_endpoint.delete_document(
        request=_make_request(),
        document_id=document.id,
        delete_mode="with_data",
        current_user=user,
        db=db,
    )

    db.refresh(line)
    assert line.review_status == BankStatementLineStatus.PENDING_REVIEW
    assert line.suggested_action == BankStatementSuggestedAction.CREATE_NEW
    assert line.linked_transaction_id is None
    assert line.created_transaction_id is None
    assert line.reviewed_at is None
    assert line.reviewed_by is None
    assert db.query(Transaction).filter(Transaction.id == transaction.id).first() is None
    assert db.query(Document).filter(Document.id == document.id).first() is None
