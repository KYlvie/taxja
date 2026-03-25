from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace
from zipfile import ZipFile

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints import reports as reports_endpoint
from app.api.v1.endpoints.reports import TaxPackageExportCreateRequest, TaxPackageExportPreviewRequest
from app.models.document import DocumentType
from app.models.transaction import ExpenseCategory, TransactionType
from app.models.user import UserType
from app.services import tax_package_export_service as tax_package_service_module
from app.services.tax_package_export_service import TaxPackageExportService
from tests.fixtures.models import (
    create_test_document,
    create_test_transaction,
    create_test_user,
)


class FakeStorage:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}
        self.uploads: dict[str, bytes] = {}

    def file_exists(self, file_path: str) -> bool:
        return file_path in self.files

    def download_file(self, file_path: str) -> bytes | None:
        return self.files.get(file_path)

    def upload_file(self, file_bytes: bytes, file_path: str, content_type: str | None = None) -> bool:
        self.uploads[file_path] = file_bytes
        return True

    def get_file_url(self, file_path: str, expiration: int = 3600) -> str:
        return f"https://example.com/{file_path}"

    def delete_file(self, file_path: str) -> bool:
        self.uploads.pop(file_path, None)
        return True


def _install_fake_storage(monkeypatch: pytest.MonkeyPatch) -> FakeStorage:
    fake_storage = FakeStorage()
    monkeypatch.setattr(tax_package_service_module, "StorageService", lambda: fake_storage)
    return fake_storage


def test_tax_package_service_builds_simplified_archive_structure(db_session, monkeypatch):
    user = create_test_user(
        db_session,
        email="taxpackage@example.com",
        name="Tax Package User",
        user_type=UserType.SELF_EMPLOYED,
    )
    current_tx = create_test_transaction(
        db_session,
        user=user,
        transaction_type=TransactionType.EXPENSE,
        amount=Decimal("99.90"),
        transaction_date=date(2026, 2, 3),
        description="Phone bill",
        expense_category=ExpenseCategory.TELECOM,
        is_deductible=True,
    )
    create_test_transaction(
        db_session,
        user=user,
        transaction_type=TransactionType.EXPENSE,
        amount=Decimal("40.00"),
        transaction_date=date(2025, 12, 31),
        description="Previous year expense",
        expense_category=ExpenseCategory.OTHER,
    )

    receipt = create_test_document(
        db_session,
        user=user,
        document_type=DocumentType.RECEIPT,
        file_name="receipt.pdf",
        file_path="/docs/receipt.pdf",
        document_date=date(2026, 2, 2),
        transaction_id=current_tx.id,
        file_size=1024,
    )
    statement = create_test_document(
        db_session,
        user=user,
        document_type=DocumentType.BANK_STATEMENT,
        file_name="statement.pdf",
        file_path="/docs/statement.pdf",
        document_date=None,
        document_year=2026,
        year_basis="document_year",
        file_size=2048,
    )
    old_document = create_test_document(
        db_session,
        user=user,
        document_type=DocumentType.RECEIPT,
        file_name="old.pdf",
        file_path="/docs/old.pdf",
        document_date=date(2025, 2, 2),
        file_size=512,
    )
    statement.uploaded_at = datetime(2025, 12, 31, 23, 59, 0)
    receipt.uploaded_at = datetime(2026, 2, 5, 9, 0, 0)
    old_document.uploaded_at = datetime(2025, 2, 5, 9, 0, 0)
    db_session.commit()

    fake_storage = _install_fake_storage(monkeypatch)
    fake_storage.files = {
        "/docs/receipt.pdf": b"receipt-bytes",
        "/docs/statement.pdf": b"statement-bytes",
        "/docs/old.pdf": b"old-bytes",
    }

    service = TaxPackageExportService(db_session, user, 2026, "en")
    prepared = service._build_prepared_package("export-1")

    assert prepared["status"] == "ready"
    assert prepared["summary"]["transaction_count"] == 1
    assert prepared["summary"]["included_document_count"] == 2

    archive = ZipFile(BytesIO(prepared["artifacts"][0].payload))
    names = set(archive.namelist())

    assert "SUMMARY/tax-package-summary_2026_en.pdf" in names
    assert "TRANSACTIONS/transactions_2026.csv" in names
    assert "TRANSACTIONS/transactions_2026.pdf" in names
    assert any(name.startswith("DOCUMENTS/receipts-invoices/") for name in names)
    assert any(name.startswith("DOCUMENTS/bank-statements/") for name in names)
    assert not any(name.startswith("README/") for name in names)
    assert not any(name.startswith("REPORTS/") for name in names)
    assert all("old.pdf" not in name for name in names)

    csv_payload = archive.read("TRANSACTIONS/transactions_2026.csv").decode("utf-8-sig")
    assert "Phone bill" in csv_payload
    assert "Previous year expense" not in csv_payload


def test_tax_package_service_uses_document_year_and_foundation_opt_in(db_session, monkeypatch):
    user = create_test_user(
        db_session,
        email="year-foundation@example.com",
        name="Year Foundation User",
        user_type=UserType.SELF_EMPLOYED,
    )
    statement = create_test_document(
        db_session,
        user=user,
        document_type=DocumentType.BANK_STATEMENT,
        file_name="statement-year-only.pdf",
        file_path="/docs/statement-year-only.pdf",
        document_date=None,
        document_year=2026,
        year_basis="document_year",
        file_size=2000,
    )
    foundation = create_test_document(
        db_session,
        user=user,
        document_type=DocumentType.RENTAL_CONTRACT,
        file_name="lease.pdf",
        file_path="/docs/lease.pdf",
        document_date=date(2026, 1, 5),
        file_size=3000,
    )
    statement.uploaded_at = datetime(2025, 12, 31, 23, 59, 0)
    foundation.uploaded_at = datetime(2026, 1, 5, 12, 0, 0)
    db_session.commit()

    fake_storage = _install_fake_storage(monkeypatch)
    fake_storage.files = {
        "/docs/statement-year-only.pdf": b"statement",
        "/docs/lease.pdf": b"lease",
    }

    default_service = TaxPackageExportService(db_session, user, 2026, "en", include_foundation_materials=False)
    default_collection = default_service._collect_document_entries([])
    default_names = {entry.file_name for entry in default_collection["included_entries"]}
    assert default_names == {"statement-year-only.pdf"}
    assert default_collection["excluded_reasons"]["reason_foundation_opt_out"] == 1

    opted_in_service = TaxPackageExportService(db_session, user, 2026, "en", include_foundation_materials=True)
    opted_in_collection = opted_in_service._collect_document_entries([])
    families = {entry.file_name: entry.family for entry in opted_in_collection["included_entries"]}
    assert families["statement-year-only.pdf"] == "bank-statements"
    assert families["lease.pdf"] == "foundation-materials"


def test_tax_package_service_build_preview_reports_risks_and_document_counts(db_session, monkeypatch):
    user = create_test_user(
        db_session,
        email="preview-user@example.com",
        name="Preview User",
        user_type=UserType.SELF_EMPLOYED,
    )
    create_test_transaction(
        db_session,
        user=user,
        transaction_type=TransactionType.EXPENSE,
        amount=Decimal("88.00"),
        transaction_date=date(2026, 5, 7),
        description="Needs review transaction",
        expense_category=ExpenseCategory.OTHER,
        needs_review=True,
    )
    pending_document = create_test_document(
        db_session,
        user=user,
        document_type=DocumentType.RECEIPT,
        file_name="pending-receipt.pdf",
        file_path="/docs/pending-receipt.pdf",
        document_date=None,
        document_year=None,
        file_size=400,
    )
    pending_document.uploaded_at = datetime(2026, 5, 8, 10, 0, 0)
    pending_document.ocr_result = {"needs_review": True}
    db_session.commit()

    fake_storage = _install_fake_storage(monkeypatch)
    fake_storage.files = {
        "/docs/pending-receipt.pdf": b"receipt",
    }

    service = TaxPackageExportService(db_session, user, 2026, "zh")
    preview = service.build_preview()

    assert preview["has_warnings"] is True
    assert preview["summary"]["pending_tx_count"] == 1
    assert preview["summary"]["pending_document_count"] == 1
    assert preview["summary"]["uncertain_year_docs"] == 1
    assert [warning["key"] for warning in preview["warnings"]] == [
        "pending_tx_count",
        "pending_docs",
        "uncertain_year_docs",
    ]


def test_tax_package_service_includes_other_only_when_linked_to_exported_transactions(db_session, monkeypatch):
    user = create_test_user(
        db_session,
        email="other-linked@example.com",
        name="Other Linked User",
        user_type=UserType.SELF_EMPLOYED,
    )
    linked_tx = create_test_transaction(
        db_session,
        user=user,
        transaction_type=TransactionType.EXPENSE,
        amount=Decimal("12.34"),
        transaction_date=date(2026, 6, 10),
        description="Linked transaction",
        expense_category=ExpenseCategory.OTHER,
    )
    linked_other = create_test_document(
        db_session,
        user=user,
        document_type=DocumentType.OTHER,
        file_name="linked-other.pdf",
        file_path="/docs/linked-other.pdf",
        document_date=date(2026, 6, 10),
        transaction_id=linked_tx.id,
        file_size=100,
    )
    unlinked_other = create_test_document(
        db_session,
        user=user,
        document_type=DocumentType.OTHER,
        file_name="unlinked-other.pdf",
        file_path="/docs/unlinked-other.pdf",
        document_date=date(2026, 6, 11),
        file_size=100,
    )
    db_session.commit()

    fake_storage = _install_fake_storage(monkeypatch)
    fake_storage.files = {
        "/docs/linked-other.pdf": b"linked",
        "/docs/unlinked-other.pdf": b"unlinked",
    }

    service = TaxPackageExportService(db_session, user, 2026, "en")
    collection = service._collect_document_entries([linked_tx])

    included = {entry.file_name: entry.family for entry in collection["included_entries"]}
    assert included == {"linked-other.pdf": "other-linked"}
    assert collection["excluded_reasons"]["reason_other_unlinked"] == 1


def test_tax_package_service_fails_cleanly_when_export_exceeds_limits(db_session, monkeypatch):
    user = create_test_user(
        db_session,
        email="limit-user@example.com",
        name="Limit User",
        user_type=UserType.SELF_EMPLOYED,
    )
    create_test_document(
        db_session,
        user=user,
        document_type=DocumentType.RECEIPT,
        file_name="receipt-a.pdf",
        file_path="/docs/receipt-a.pdf",
        document_date=date(2026, 1, 1),
        file_size=100,
    )
    create_test_document(
        db_session,
        user=user,
        document_type=DocumentType.RECEIPT,
        file_name="receipt-b.pdf",
        file_path="/docs/receipt-b.pdf",
        document_date=date(2026, 1, 2),
        file_size=100,
    )
    db_session.commit()

    fake_storage = _install_fake_storage(monkeypatch)
    fake_storage.files = {
        "/docs/receipt-a.pdf": b"a",
        "/docs/receipt-b.pdf": b"b",
    }
    monkeypatch.setattr(tax_package_service_module, "MAX_DOCUMENTS", 1)

    service = TaxPackageExportService(db_session, user, 2026, "en")
    prepared = service._build_prepared_package("export-limit")

    assert prepared["status"] == "failed"
    assert prepared["failure"]["document_count"] == 2
    assert prepared["failure"]["max_documents"] == 1
    assert prepared["failure"]["largest_files"]


def test_create_tax_package_export_sync_returns_ready_state_without_leaking_storage_paths(db_session, monkeypatch):
    user = create_test_user(
        db_session,
        email="sync-endpoint@example.com",
        name="Sync Endpoint User",
        user_type=UserType.SELF_EMPLOYED,
    )

    monkeypatch.setenv("CELERY_EXPORT", "false")

    class FakeService:
        def __init__(self, db, user, tax_year, language, include_foundation_materials=False):
            assert db is db_session
            assert tax_year == 2026
            assert language == "zh"
            assert include_foundation_materials is True

        def build_status_payload(self, export_id, status):
            return {"export_id": export_id, "status": status}

        def export_to_storage(self, export_id):
            return {
                "export_id": export_id,
                "status": "ready",
                "part_count": 1,
                "parts": [{"part_number": 1, "file_name": "tax-package.zip", "download_url": "https://example.com/tax-package.zip", "size_bytes": 100}],
                "storage_paths": ["secret/path.zip"],
            }

    monkeypatch.setattr(reports_endpoint, "TaxPackageExportService", FakeService)

    response = reports_endpoint.create_tax_package_export(
        TaxPackageExportCreateRequest(
            tax_year=2026,
            language="zh",
            include_foundation_materials=True,
        ),
        current_user=user,
        db=db_session,
    )

    assert response["status"] == "ready"
    assert response["part_count"] == 1
    assert "storage_paths" not in response
    assert "user_id" not in response


def test_preview_tax_package_export_returns_preview_payload(db_session, monkeypatch):
    user = create_test_user(
        db_session,
        email="preview-endpoint@example.com",
        name="Preview Endpoint User",
        user_type=UserType.SELF_EMPLOYED,
    )

    class FakeService:
        def __init__(self, db, user, tax_year, language, include_foundation_materials=False):
            assert db is db_session
            assert tax_year == 2026
            assert language == "zh"
            assert include_foundation_materials is True

        def build_preview(self):
            return {
                "tax_year": 2026,
                "language": "zh",
                "include_foundation_materials": True,
                "has_warnings": True,
                "warnings": [{"key": "pending_tx_count", "label": "仍待审核的交易", "count": 2}],
                "summary": {
                    "pending_tx_count": 2,
                    "pending_document_count": 0,
                    "uncertain_year_docs": 0,
                    "skipped_files": [],
                },
            }

    monkeypatch.setattr(reports_endpoint, "TaxPackageExportService", FakeService)

    response = reports_endpoint.preview_tax_package_export(
        TaxPackageExportPreviewRequest(
            tax_year=2026,
            language="zh",
            include_foundation_materials=True,
        ),
        current_user=user,
        db=db_session,
    )

    assert response["has_warnings"] is True
    assert response["summary"]["pending_tx_count"] == 2


def test_create_tax_package_export_celery_returns_pending_state(db_session, monkeypatch):
    user = create_test_user(
        db_session,
        email="celery-endpoint@example.com",
        name="Celery Endpoint User",
        user_type=UserType.SELF_EMPLOYED,
    )

    monkeypatch.setenv("CELERY_EXPORT", "true")
    cached_states: dict[str, dict[str, object]] = {}

    monkeypatch.setattr(
        reports_endpoint,
        "async_export_tax_package",
        SimpleNamespace(delay=lambda **kwargs: SimpleNamespace(id="job-123")),
    )
    monkeypatch.setattr(
        reports_endpoint,
        "cache_tax_package_export_state",
        lambda export_id, state: cached_states.setdefault(export_id, state),
    )

    response = reports_endpoint.create_tax_package_export(
        TaxPackageExportCreateRequest(tax_year=2026, language="en"),
        current_user=user,
        db=db_session,
    )

    assert response["export_id"] == "job-123"
    assert response["status"] == "pending"
    assert "user_id" not in response
    assert cached_states["job-123"]["tax_year"] == 2026
    assert cached_states["job-123"]["user_id"] == user.id


def test_get_tax_package_export_status_rejects_foreign_cached_state(db_session, monkeypatch):
    user = create_test_user(
        db_session,
        email="status-ownership@example.com",
        name="Status Ownership User",
        user_type=UserType.SELF_EMPLOYED,
    )

    monkeypatch.setattr(
        reports_endpoint,
        "load_cached_tax_package_export_state",
        lambda export_id: {
            "export_id": export_id,
            "user_id": user.id + 1,
            "status": "ready",
        },
    )

    with pytest.raises(HTTPException) as exc_info:
        reports_endpoint.get_tax_package_export_status(
            "export-foreign",
            current_user=user,
            db=db_session,
        )

    assert exc_info.value.status_code == 404
