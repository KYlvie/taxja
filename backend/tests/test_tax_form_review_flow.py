from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models.document import Document, DocumentType
from tests.fixtures.models import create_test_user


def _auth_headers(email: str) -> dict[str, str]:
    token = create_access_token(data={"sub": email})
    return {"Authorization": f"Bearer {token}"}


def test_confirm_tax_data_synthesizes_missing_import_suggestion(
    client: TestClient,
    db: Session,
):
    user = create_test_user(db, email="u1-confirm@example.com")
    user.email_verified = True
    db.commit()
    db.refresh(user)

    document = Document(
        user_id=user.id,
        document_type=DocumentType.U1_FORM,
        file_path="documents/u1-form.pdf",
        file_name="u1-form.pdf",
        file_size=2048,
        mime_type="application/pdf",
        ocr_result={
            "tax_year": 2019,
            "kz_029": 13684.40,
            "kz_060": 2988.40,
            "kz_095": 10121.00,
        },
        raw_text="U1 Umsatzsteuererklaerung 2019",
        confidence_score=0.25,
        processed_at=datetime.utcnow(),
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    response = client.post(
        f"/api/v1/documents/{document.id}/confirm-tax-data",
        headers=_auth_headers(user.email),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data_type"] == "u1"
    assert payload["tax_year"] == 2019

    db.refresh(document)
    suggestion = document.ocr_result["import_suggestion"]
    assert suggestion["type"] == "import_u1"
    assert suggestion["status"] == "confirmed"
    assert suggestion["data"]["kz_029"] == 13684.40
    assert suggestion["tax_filing_data_id"] == payload["tax_filing_data_id"]


def test_correct_ocr_results_syncs_tax_import_suggestion_data(
    client: TestClient,
    db: Session,
):
    user = create_test_user(db, email="u1-correct@example.com")
    user.email_verified = True
    db.commit()
    db.refresh(user)

    document = Document(
        user_id=user.id,
        document_type=DocumentType.U1_FORM,
        file_path="documents/u1-review.pdf",
        file_name="u1-review.pdf",
        file_size=2048,
        mime_type="application/pdf",
        ocr_result={
            "tax_year": 2019,
            "kz_029": 13684.40,
            "import_suggestion": {
                "type": "import_u1",
                "status": "pending",
                "data": {"tax_year": 2019, "kz_029": 13684.40},
                "confidence": 0.25,
            },
        },
        raw_text="U1 Umsatzsteuererklaerung 2019",
        confidence_score=0.25,
        processed_at=datetime.utcnow(),
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    response = client.post(
        f"/api/v1/documents/{document.id}/correct",
        headers=_auth_headers(user.email),
        json={
            "corrected_data": {
                "_document_type": "u1_form",
                "tax_year": 2019,
                "kz_029": 14000.0,
            }
        },
    )

    assert response.status_code == 200

    db.refresh(document)
    suggestion = document.ocr_result["import_suggestion"]
    assert suggestion["type"] == "import_u1"
    assert suggestion["status"] == "pending"
    assert suggestion["data"]["kz_029"] == 14000.0


def test_confirm_tax_data_supports_e1_forms(
    client: TestClient,
    db: Session,
):
    user = create_test_user(db, email="e1-confirm@example.com")
    user.email_verified = True
    db.commit()
    db.refresh(user)

    document = Document(
        user_id=user.id,
        document_type=DocumentType.E1_FORM,
        file_path="documents/e1-form.pdf",
        file_name="e1-form.pdf",
        file_size=2048,
        mime_type="application/pdf",
        ocr_result={
            "tax_year": 2025,
            "taxpayer_name": "Erika Musterfrau",
            "steuernummer": "12 345/6789",
            "all_kz_values": {"kz_9040": 1200.0},
        },
        raw_text="E1 Einkommensteuererklaerung 2025",
        confidence_score=0.42,
        processed_at=datetime.utcnow(),
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    response = client.post(
        f"/api/v1/documents/{document.id}/confirm-tax-data",
        headers=_auth_headers(user.email),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data_type"] == "e1_form"
    assert payload["tax_year"] == 2025

    db.refresh(document)
    suggestion = document.ocr_result["import_suggestion"]
    assert suggestion["type"] == "import_e1"
    assert suggestion["status"] == "confirmed"
    assert suggestion["tax_filing_data_id"] == payload["tax_filing_data_id"]


def test_confirm_tax_data_supports_bescheid_documents(
    client: TestClient,
    db: Session,
):
    user = create_test_user(db, email="bescheid-confirm@example.com")
    user.email_verified = True
    db.commit()
    db.refresh(user)

    document = Document(
        user_id=user.id,
        document_type=DocumentType.EINKOMMENSTEUERBESCHEID,
        file_path="documents/bescheid.pdf",
        file_name="bescheid.pdf",
        file_size=2048,
        mime_type="application/pdf",
        ocr_result={
            "tax_year": 2024,
            "taxpayer_name": "Erika Musterfrau",
            "steuernummer": "98 765/4321",
            "festgesetzte_einkommensteuer": 574.6,
        },
        raw_text="Einkommensteuerbescheid 2024",
        confidence_score=0.51,
        processed_at=datetime.utcnow(),
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    response = client.post(
        f"/api/v1/documents/{document.id}/confirm-tax-data",
        headers=_auth_headers(user.email),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data_type"] == "einkommensteuerbescheid"
    assert payload["tax_year"] == 2024

    db.refresh(document)
    suggestion = document.ocr_result["import_suggestion"]
    assert suggestion["type"] == "import_bescheid"
    assert suggestion["status"] == "confirmed"
    assert suggestion["tax_filing_data_id"] == payload["tax_filing_data_id"]


def test_confirm_tax_data_infers_tax_year_from_lohnzettel_date(
    client: TestClient,
    db: Session,
):
    user = create_test_user(db, email="lohnzettel-infer@example.com")
    user.email_verified = True
    db.commit()
    db.refresh(user)

    document = Document(
        user_id=user.id,
        document_type=DocumentType.LOHNZETTEL,
        file_path="documents/l16.pdf",
        file_name="l16.pdf",
        file_size=2048,
        mime_type="application/pdf",
        ocr_result={
            "employee_name": "Mag. Thomas Gruber",
            "employer_name": "Siemens Osterreich AG",
            "date": "2024-01-01",
            "gross_income": 62400.0,
            "withheld_tax": 12480.0,
        },
        raw_text="Lohnzettel (L16) fur 2024",
        confidence_score=0.64,
        processed_at=datetime.utcnow(),
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    response = client.post(
        f"/api/v1/documents/{document.id}/confirm-tax-data",
        headers=_auth_headers(user.email),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data_type"] == "lohnzettel"
    assert payload["tax_year"] == 2024

    db.refresh(document)
    suggestion = document.ocr_result["import_suggestion"]
    assert suggestion["type"] == "import_lohnzettel"
    assert suggestion["status"] == "confirmed"
    assert suggestion["data"]["tax_year"] == 2024


def test_confirm_tax_data_returns_400_when_tax_year_cannot_be_inferred(
    client: TestClient,
    db: Session,
):
    user = create_test_user(db, email="lohnzettel-missing-year@example.com")
    user.email_verified = True
    db.commit()
    db.refresh(user)

    document = Document(
        user_id=user.id,
        document_type=DocumentType.LOHNZETTEL,
        file_path="documents/lohnzettel-no-year.pdf",
        file_name="lohnzettel-no-year.pdf",
        file_size=2048,
        mime_type="application/pdf",
        ocr_result={
            "employee_name": "Mag. Thomas Gruber",
            "employer_name": "Siemens Osterreich AG",
            "gross_income": 62400.0,
            "withheld_tax": 12480.0,
        },
        raw_text="Lohnzettel ohne eindeutiges Jahr",
        confidence_score=0.64,
        processed_at=datetime.utcnow(),
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    response = client.post(
        f"/api/v1/documents/{document.id}/confirm-tax-data",
        headers=_auth_headers(user.email),
    )

    assert response.status_code == 400
    assert "tax_year" in response.json()["detail"]
