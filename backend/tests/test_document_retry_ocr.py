from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from types import SimpleNamespace

from app.api.v1.endpoints import documents as documents_endpoint
from app.core.security import create_access_token
from app.models.document import Document, DocumentType
from tests.fixtures.models import create_test_user


def _auth_headers(email: str) -> dict[str, str]:
    token = create_access_token(data={"sub": email})
    return {"Authorization": f"Bearer {token}"}


def test_retry_ocr_keeps_previous_result_until_new_run_finishes(
    client: TestClient,
    db: Session,
    monkeypatch,
):
    user = create_test_user(db, email="retry-ocr@example.com")
    user.email_verified = True
    db.commit()
    db.refresh(user)

    document = Document(
        user_id=user.id,
        document_type=DocumentType.RECEIPT,
        file_path="documents/retry-ocr.pdf",
        file_name="retry-ocr.pdf",
        file_size=1024,
        mime_type="application/pdf",
        ocr_result={
            "merchant": "Billa",
            "_pipeline": {"current_state": "completed"},
        },
        raw_text="old raw text",
        confidence_score=0.92,
        processed_at=datetime.utcnow(),
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
