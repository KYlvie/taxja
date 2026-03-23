from decimal import Decimal
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token
from app.models.document import DocumentType
from app.models.user import UserType
from app.tasks.ocr_tasks import _build_mietvertrag_suggestion
from tests.fixtures.models import create_test_document, create_test_user


def _auth_headers(email: str) -> dict[str, str]:
    token = create_access_token(data={"sub": email})
    return {"Authorization": f"Bearer {token}"}


def test_correct_ocr_rebuilds_rental_suggestion_after_manual_role_override(
    client: TestClient,
    db: Session,
    monkeypatch,
):
    monkeypatch.setattr(settings, "CONTRACT_ROLE_MODE", "strict")

    user = create_test_user(
        db,
        email="contract-role-review@example.com",
        name="OOHK Properties GmbH",
        user_type=UserType.LANDLORD,
    )
    user.email_verified = True
    db.commit()
    db.refresh(user)

    document = create_test_document(
        db,
        user=user,
        document_type=DocumentType.RENTAL_CONTRACT,
        file_name="mietvertrag-review.pdf",
        ocr_result={
            "monthly_rent": 1450.0,
            "property_address": "Argentinierstrasse 21, 1234 Wien",
            "tenant_name": "Fenghong Zhang",
            "landlord_name": "OOHK Properties GmbH",
            "start_date": "2026-03-01",
        },
        raw_text="Mietvertrag Vermieter OOHK Properties GmbH Mieter Fenghong Zhang",
        confidence_score=Decimal("0.86"),
    )

    initial_payload = _build_mietvertrag_suggestion(
        db,
        document,
        SimpleNamespace(raw_text=document.raw_text, confidence_score=Decimal("0.86")),
    )
    assert initial_payload["import_suggestion"] is not None

    response = client.post(
        f"/api/v1/documents/{document.id}/correct",
        headers=_auth_headers(user.email),
        json={
            "corrected_data": {
                "user_contract_role": "tenant",
            },
            "notes": "Role corrected during review",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert "user_contract_role" in payload["updated_fields"]

    db.refresh(document)
    assert document.ocr_result["user_contract_role"] == "tenant"
    assert document.ocr_result["user_contract_role_source"] == "manual_override"
    assert document.ocr_result["contract_role_resolution"]["strict_would_block"] is True
    assert document.ocr_result.get("import_suggestion") is None
    assert document.ocr_result["correction_history"][-1]["corrected_fields"] == [
        "user_contract_role"
    ]
