from datetime import datetime
from io import BytesIO
from zipfile import ZipFile

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.v1.endpoints import documents as documents_endpoint
from app.core.security import create_access_token
from app.models.document import Document, DocumentType
from tests.fixtures.models import create_test_user


def _auth_headers(email: str) -> dict[str, str]:
    token = create_access_token(data={"sub": email})
    return {"Authorization": f"Bearer {token}"}


def _make_document(
    *,
    user_id: int,
    file_name: str,
    document_type: DocumentType = DocumentType.BANK_STATEMENT,
    uploaded_at: datetime,
    document_date=None,
    document_year=None,
    year_basis=None,
    year_confidence=None,
    ocr_result=None,
) -> Document:
    return Document(
        user_id=user_id,
        document_type=document_type,
        file_path=f"documents/{file_name}",
        file_name=file_name,
        file_size=1024,
        mime_type="application/pdf",
        uploaded_at=uploaded_at,
        processed_at=uploaded_at,
        document_date=document_date,
        document_year=document_year,
        year_basis=year_basis,
        year_confidence=year_confidence,
        ocr_result=ocr_result or {},
        raw_text=file_name,
        confidence_score=0.95,
    )


def test_documents_endpoint_filters_by_document_year_when_document_date_missing(
    client: TestClient,
    db: Session,
):
    user = create_test_user(db, email="document-year-filter@example.com")
    user.email_verified = True
    db.commit()
    db.refresh(user)

    matching = _make_document(
        user_id=user.id,
        file_name="statement-2024.pdf",
        uploaded_at=datetime(2026, 3, 24, 10, 0, 0),
        document_year=2024,
        year_basis="statement_period_start",
        year_confidence=1.0,
        ocr_result={"document_year": 2024},
    )
    non_matching = _make_document(
        user_id=user.id,
        file_name="statement-2025.pdf",
        uploaded_at=datetime(2026, 3, 24, 10, 5, 0),
        document_year=2025,
        year_basis="statement_period_start",
        year_confidence=1.0,
        ocr_result={"document_year": 2025},
    )
    db.add_all([matching, non_matching])
    db.commit()

    response = client.get(
        "/api/v1/documents"
        "?sort_by=document_date"
        "&start_date=2024-01-01T00:00:00"
        "&end_date=2024-12-31T23:59:59",
        headers=_auth_headers(user.email),
    )

    assert response.status_code == 200
    payload = response.json()
    returned_names = [item["file_name"] for item in payload["documents"]]
    assert returned_names == ["statement-2024.pdf"]


def test_export_zip_filters_by_document_year_when_document_date_missing(
    client: TestClient,
    db: Session,
    monkeypatch,
):
    user = create_test_user(db, email="document-year-export@example.com")
    user.email_verified = True
    db.commit()
    db.refresh(user)

    matching = _make_document(
        user_id=user.id,
        file_name="statement-2024.pdf",
        uploaded_at=datetime(2026, 3, 24, 10, 0, 0),
        document_year=2024,
        year_basis="statement_period_start",
        year_confidence=1.0,
        ocr_result={"document_year": 2024},
    )
    non_matching = _make_document(
        user_id=user.id,
        file_name="statement-2025.pdf",
        uploaded_at=datetime(2026, 3, 24, 10, 5, 0),
        document_year=2025,
        year_basis="statement_period_start",
        year_confidence=1.0,
        ocr_result={"document_year": 2025},
    )
    db.add_all([matching, non_matching])
    db.commit()

    class FakeStorage:
        def download_file(self, file_path: str) -> bytes:
            return f"content:{file_path}".encode("utf-8")

    monkeypatch.setattr(documents_endpoint, "get_storage_service", lambda: FakeStorage())

    response = client.get(
        "/api/v1/documents/export-zip"
        "?sort_by=document_date"
        "&start_date=2024-01-01T00:00:00"
        "&end_date=2024-12-31T23:59:59",
        headers=_auth_headers(user.email),
    )

    assert response.status_code == 200
    archive = ZipFile(BytesIO(response.content))
    names = archive.namelist()
    assert "2024/statement-2024.pdf" in names
    assert "2025/statement-2025.pdf" not in names


def test_export_years_returns_authoritative_document_years(
    client: TestClient,
    db: Session,
):
    user = create_test_user(db, email="document-export-years@example.com")
    user.email_verified = True
    db.commit()
    db.refresh(user)

    db.add_all(
        [
            _make_document(
                user_id=user.id,
                file_name="statement-2024.pdf",
                uploaded_at=datetime(2026, 3, 24, 10, 0, 0),
                document_year=2024,
                year_basis="statement_period_start",
                year_confidence=1.0,
                ocr_result={"document_year": 2024},
            ),
            _make_document(
                user_id=user.id,
                file_name="statement-2024-2.pdf",
                uploaded_at=datetime(2026, 3, 24, 10, 5, 0),
                document_year=2024,
                year_basis="statement_period_start",
                year_confidence=1.0,
                ocr_result={"document_year": 2024},
            ),
            _make_document(
                user_id=user.id,
                file_name="statement-2025.pdf",
                uploaded_at=datetime(2026, 3, 24, 10, 10, 0),
                document_year=2025,
                year_basis="statement_period_start",
                year_confidence=1.0,
                ocr_result={"document_year": 2025},
            ),
        ]
    )
    db.commit()

    response = client.get(
        "/api/v1/documents/export-years",
        headers=_auth_headers(user.email),
    )

    assert response.status_code == 200
    assert response.json() == {
        "years": [
            {"year": 2025, "count": 1, "total_size_bytes": 1024},
            {"year": 2024, "count": 2, "total_size_bytes": 2048},
        ]
    }


def test_export_zip_supports_explicit_document_year_filter(
    client: TestClient,
    db: Session,
    monkeypatch,
):
    user = create_test_user(db, email="document-year-explicit-export@example.com")
    user.email_verified = True
    db.commit()
    db.refresh(user)

    matching = _make_document(
        user_id=user.id,
        file_name="statement-2024.pdf",
        uploaded_at=datetime(2026, 3, 24, 10, 0, 0),
        document_year=2024,
        year_basis="statement_period_start",
        year_confidence=1.0,
        ocr_result={"document_year": 2024},
    )
    non_matching = _make_document(
        user_id=user.id,
        file_name="statement-2025.pdf",
        uploaded_at=datetime(2026, 3, 24, 10, 5, 0),
        document_year=2025,
        year_basis="statement_period_start",
        year_confidence=1.0,
        ocr_result={"document_year": 2025},
    )
    db.add_all([matching, non_matching])
    db.commit()

    class FakeStorage:
        def download_file(self, file_path: str) -> bytes:
            return f"content:{file_path}".encode("utf-8")

    monkeypatch.setattr(documents_endpoint, "get_storage_service", lambda: FakeStorage())

    response = client.get(
        "/api/v1/documents/export-zip"
        "?sort_by=document_date"
        "&document_year=2024",
        headers=_auth_headers(user.email),
    )

    assert response.status_code == 200
    assert 'documents_2024.zip' in response.headers["content-disposition"]
    archive = ZipFile(BytesIO(response.content))
    names = archive.namelist()
    assert "2024/statement-2024.pdf" in names
    assert "2025/statement-2025.pdf" not in names
