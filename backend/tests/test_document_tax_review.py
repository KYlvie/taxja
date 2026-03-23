"""Functional tests for legacy receipt tax-review backfill."""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models.document import DocumentType
from app.models.user import UserType
from tests.fixtures.models import create_test_document, create_test_user


def _auth_headers(email: str) -> dict[str, str]:
    token = create_access_token(data={"sub": email})
    return {"Authorization": f"Bearer {token}"}


def test_get_document_backfills_line_item_tax_judgment(client: TestClient, db: Session):
    """Opening a legacy receipt should populate system tax judgments per line item."""
    user = create_test_user(
        db,
        email="legacy-receipt@example.com",
        user_type=UserType.MIXED,
        business_type="freiberufler",
        business_industry="it_dienstleistung",
    )
    document = create_test_document(
        db,
        user,
        document_type=DocumentType.RECEIPT,
        file_name="legacy-receipt.pdf",
        file_size=128,
        mime_type="application/pdf",
        ocr_result={
            "merchant": "",
            "amount": 6.58,
            "line_items": [
                {"name": "Lebensmittel Einkauf", "total": 1.59, "quantity": 1},
                {"name": "Druckerpapier A4", "total": 4.99, "quantity": 1},
            ],
        },
    )

    response = client.get(
        f"/api/v1/documents/{document.id}",
        headers=_auth_headers(user.email),
    )

    assert response.status_code == 200
    data = response.json()["ocr_result"]
    items = data["line_items"]
    assert items[0]["category"] == "groceries"
    assert items[0]["is_deductible"] is False
    assert items[0]["deduction_reason"]
    assert items[1]["category"] in {"office_supplies", "equipment"}
    assert items[1]["is_deductible"] is True
    assert items[1]["deduction_reason"]
    assert data["tax_analysis"]["deductible_amount"] == 4.99
    assert data["tax_analysis"]["non_deductible_amount"] == 1.59
