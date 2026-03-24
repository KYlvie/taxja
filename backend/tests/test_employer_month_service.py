from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.document import DocumentType
from app.models.user import UserType
from app.services.employer_month_service import EmployerMonthService
from tests.fixtures.models import create_test_document, create_test_user


def test_review_context_for_payslip_returns_existing_month(db: Session):
    user = create_test_user(
        db,
        email="employer-month@example.com",
        user_type=UserType.SELF_EMPLOYED,
        employer_mode="occasional",
    )
    document = create_test_document(
        db,
        user,
        document_type=DocumentType.PAYSLIP,
        file_name="2026-03-payslip.pdf",
        ocr_result={
            "date": "2026-03-31",
            "gross_income": "4200.50",
            "net_income": "2890.10",
            "withheld_tax": "780.40",
        },
    )

    service = EmployerMonthService(db)
    service.mark_payroll_detected(
        user.id,
        "2026-03",
        document_id=document.id,
        source_type="test",
        payroll_signal="payslip",
        summary={"gross_wages": Decimal("4200.50")},
    )
    db.commit()

    context = service.get_document_review_context(user, document.id)

    assert context["supported"] is True
    assert context["reason"] is None
    assert context["candidate_year_month"] == "2026-03"
    assert context["month"] is not None
    assert context["month"].status.value == "payroll_detected"
    assert context["month"].gross_wages == Decimal("4200.50")


def test_review_context_for_historical_lohnzettel_returns_archive(db: Session):
    user = create_test_user(
        db,
        email="historical-archive@example.com",
        user_type=UserType.MIXED,
        employer_mode="regular",
    )
    document = create_test_document(
        db,
        user,
        document_type=DocumentType.LOHNZETTEL,
        file_name="lohnzettel-2024.pdf",
        ocr_result={
            "tax_year": 2024,
            "employer": "OOHK Payroll",
            "gross_income": "18450.00",
            "withheld_tax": "2310.55",
        },
    )

    service = EmployerMonthService(db)
    service.confirm_annual_archive(
        user.id,
        2024,
        document_id=document.id,
        archive_signal="lohnzettel",
        source_type="test",
        summary={
            "employer_name": "OOHK Payroll",
            "gross_income": Decimal("18450.00"),
            "withheld_tax": Decimal("2310.55"),
        },
    )
    db.commit()

    context = service.get_document_review_context(user, document.id)

    assert context["supported"] is True
    assert context["candidate_tax_year"] == 2024
    assert context["annual_archive"] is not None
    assert context["annual_archive"].status.value == "archived"
    assert context["annual_archive"].employer_name == "OOHK Payroll"


def test_review_context_rejects_unsupported_user_type(db: Session):
    user = create_test_user(
        db,
        email="employee-review@example.com",
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

    service = EmployerMonthService(db)
    context = service.get_document_review_context(user, document.id)

    assert context["supported"] is False
    assert context["reason"] == "user_type_not_supported"
    assert context["month"] is None
    assert context["annual_archive"] is None
