"""Functional tests for employer-light API endpoints."""
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models.document import DocumentType
from app.models.user import UserType
from tests.fixtures.models import create_test_document, create_test_user


def _auth_headers(email: str) -> dict[str, str]:
    token = create_access_token(data={"sub": email})
    return {"Authorization": f"Bearer {token}"}


def test_detect_payroll_document_and_review_context(client: TestClient, db: Session):
    """Processed payslips should create a missing-confirmation employer month."""
    user = create_test_user(
        db,
        email="employer-detect@example.com",
        user_type=UserType.SELF_EMPLOYED,
        employer_mode="occasional",
    )
    document = create_test_document(
        db,
        user,
        document_type=DocumentType.PAYSLIP,
        file_name="2026-03-payslip.pdf",
        confidence_score=Decimal("0.91"),
        ocr_result={
            "date": "2026-03-31",
            "gross_income": "4200.50",
            "net_income": "2890.10",
            "withheld_tax": "780.40",
        },
    )

    response = client.post(
        f"/api/v1/employer/documents/{document.id}/detect",
        headers=_auth_headers(user.email),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["detected"] is True
    assert data["reason"] is None
    assert data["month"]["year_month"] == "2026-03"
    assert data["month"]["status"] == "missing_confirmation"
    assert data["month"]["gross_wages"] == "4200.50"
    assert data["month"]["net_paid"] == "2890.10"
    assert data["month"]["documents"][0]["document_id"] == document.id

    review_response = client.get(
        f"/api/v1/employer/documents/{document.id}/review-context",
        headers=_auth_headers(user.email),
    )
    assert review_response.status_code == 200
    review_data = review_response.json()
    assert review_data["supported"] is True
    assert review_data["candidate_year_month"] == "2026-03"
    assert review_data["month"]["status"] == "missing_confirmation"


def test_confirm_payroll_updates_overview_and_list(client: TestClient, db: Session):
    """Confirming a payroll month should show up in month listing and yearly overview."""
    user = create_test_user(
        db,
        email="employer-confirm@example.com",
        user_type=UserType.MIXED,
        employer_mode="regular",
    )
    document = create_test_document(
        db,
        user,
        document_type=DocumentType.PAYSLIP,
        file_name="2026-05-payslip.pdf",
        ocr_result={"date": "2026-05-31"},
    )

    response = client.post(
        "/api/v1/employer/months/confirm-payroll",
        json={
            "year_month": "2026-05",
            "document_id": document.id,
            "source_type": "manual_summary",
            "payroll_signal": "payslip",
            "confidence": "0.93",
            "employee_count": 2,
            "gross_wages": "6100.00",
            "lohnsteuer": "880.55",
        },
        headers=_auth_headers(user.email),
    )

    assert response.status_code == 200
    month = response.json()
    assert month["status"] == "payroll_detected"
    assert month["employee_count"] == 2
    assert month["gross_wages"] == "6100.00"
    assert month["documents"][0]["document_id"] == document.id

    months_response = client.get(
        "/api/v1/employer/months?year=2026",
        headers=_auth_headers(user.email),
    )
    assert months_response.status_code == 200
    months = months_response.json()
    assert len(months) == 1
    assert months[0]["year_month"] == "2026-05"
    assert months[0]["status"] == "payroll_detected"

    overview_response = client.get(
        "/api/v1/employer/overview?year=2026",
        headers=_auth_headers(user.email),
    )
    assert overview_response.status_code == 200
    overview = overview_response.json()
    assert overview["employer_mode"] == "regular"
    assert overview["total_months"] == 1
    assert overview["payroll_months"] == 1
    assert overview["missing_confirmation_months"] == 0
    assert overview["next_deadline"] is not None


def test_mark_missing_confirmation_then_confirm_no_payroll_and_update_summary(
    client: TestClient,
    db: Session,
):
    """AI-style month prompts should allow missing-confirmation, no-payroll, and later summary edits."""
    user = create_test_user(
        db,
        email="employer-no-payroll@example.com",
        user_type=UserType.SELF_EMPLOYED,
        employer_mode="occasional",
    )

    missing_response = client.post(
        "/api/v1/employer/months/mark-missing-confirmation",
        json={
            "year_month": "2026-07",
            "source_type": "ai_signal",
            "payroll_signal": "payroll_bundle",
            "confidence": "0.72",
        },
        headers=_auth_headers(user.email),
    )

    assert missing_response.status_code == 200
    assert missing_response.json()["status"] == "missing_confirmation"

    no_payroll_response = client.post(
        "/api/v1/employer/months/confirm-no-payroll",
        json={"year_month": "2026-07", "note": "Seasonal pause"},
        headers=_auth_headers(user.email),
    )

    assert no_payroll_response.status_code == 200
    no_payroll_month = no_payroll_response.json()
    assert no_payroll_month["status"] == "no_payroll_confirmed"
    assert no_payroll_month["notes"] == "Seasonal pause"

    update_response = client.put(
        "/api/v1/employer/months/2026-07",
        json={"notes": "No staff in July", "employee_count": 0},
        headers=_auth_headers(user.email),
    )

    assert update_response.status_code == 200
    updated_month = update_response.json()
    assert updated_month["status"] == "no_payroll_confirmed"
    assert updated_month["notes"] == "No staff in July"
    assert updated_month["employee_count"] == 0


def test_detect_and_confirm_annual_archive_then_list(client: TestClient, db: Session):
    """Historical Lohnzettel files should move from detection to archived annual payroll packs."""
    user = create_test_user(
        db,
        email="annual-archive@example.com",
        user_type=UserType.MIXED,
        employer_mode="regular",
    )
    document = create_test_document(
        db,
        user,
        document_type=DocumentType.LOHNZETTEL,
        file_name="lohnzettel-2024.pdf",
        confidence_score=Decimal("0.88"),
        ocr_result={
            "tax_year": 2024,
            "employer": "OOHK Payroll",
            "gross_income": "18450.00",
            "withheld_tax": "2310.55",
        },
    )

    detect_response = client.post(
        f"/api/v1/employer/documents/{document.id}/detect-annual-archive",
        headers=_auth_headers(user.email),
    )

    assert detect_response.status_code == 200
    detect_data = detect_response.json()
    assert detect_data["detected"] is True
    assert detect_data["archive"]["status"] == "pending_confirmation"
    assert detect_data["archive"]["tax_year"] == 2024

    confirm_response = client.post(
        "/api/v1/employer/annual-archives/confirm",
        json={
            "tax_year": 2024,
            "document_id": document.id,
            "archive_signal": "lohnzettel",
            "source_type": "manual_archive",
            "confidence": "0.95",
            "employer_name": "OOHK Payroll",
            "gross_income": "18450.00",
            "withheld_tax": "2310.55",
            "notes": "Imported historical annual pack",
        },
        headers=_auth_headers(user.email),
    )

    assert confirm_response.status_code == 200
    archive = confirm_response.json()
    assert archive["status"] == "archived"
    assert archive["employer_name"] == "OOHK Payroll"
    assert archive["documents"][0]["document_id"] == document.id

    list_response = client.get(
        "/api/v1/employer/annual-archives",
        headers=_auth_headers(user.email),
    )
    assert list_response.status_code == 200
    archives = list_response.json()
    assert len(archives) == 1
    assert archives[0]["tax_year"] == 2024
    assert archives[0]["status"] == "archived"

    review_response = client.get(
        f"/api/v1/employer/documents/{document.id}/review-context",
        headers=_auth_headers(user.email),
    )
    assert review_response.status_code == 200
    review_data = review_response.json()
    assert review_data["supported"] is True
    assert review_data["candidate_tax_year"] == 2024
    assert review_data["annual_archive"]["status"] == "archived"


def test_employer_endpoint_returns_reason_for_unsupported_user_type(
    client: TestClient,
    db: Session,
):
    """Employee users should not activate employer-light flows even if employer_mode is set."""
    user = create_test_user(
        db,
        email="employee-employer-endpoint@example.com",
        user_type=UserType.EMPLOYEE,
        employer_mode="regular",
    )
    document = create_test_document(
        db,
        user,
        document_type=DocumentType.PAYSLIP,
        file_name="employee-payslip.pdf",
        ocr_result={"date": "2026-02-28"},
    )

    response = client.post(
        f"/api/v1/employer/documents/{document.id}/detect",
        headers=_auth_headers(user.email),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["detected"] is False
    assert data["reason"] == "user_type_not_supported"
    assert data["month"] is None
