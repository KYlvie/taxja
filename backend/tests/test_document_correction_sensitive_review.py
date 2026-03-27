from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.api.v1.endpoints.documents import correct_ocr_results
from app.models.document import DocumentType
from app.models.user import UserType
from app.schemas.ocr_review import OCRCorrectionRequest
from tests.fixtures.models import create_test_document, create_test_user


def test_correct_ocr_allows_confirmed_loan_contract_review_save(
    db_session: Session,
):
    user = create_test_user(
        db_session,
        email="loan-contract-review@example.com",
        name="Mag. Eva Wimmer",
        user_type=UserType.LANDLORD,
    )
    user.email_verified = True
    db_session.commit()
    db_session.refresh(user)

    document = create_test_document(
        db_session,
        user=user,
        document_type=DocumentType.LOAN_CONTRACT,
        file_name="kreditvertrag-review.pdf",
        ocr_result={
            "loan_amount": 250000.0,
            "interest_rate": 2.4,
            "monthly_payment": 980.0,
            "lender_name": "Raiffeisenbank Wien",
            "borrower_name": "Mag. Eva Wimmer",
            "property_address": "Praterstrasse 1, 1020 Wien",
            "start_date": "2026-01-01",
            "confirmed": True,
            "confirmed_at": "2026-03-23T22:35:01.536798",
            "confirmed_by": user.id,
        },
        raw_text=(
            "Kreditvertrag Darlehensnehmer Mag. Eva Wimmer "
            "Darlehensgeber Raiffeisenbank Wien"
        ),
        confidence_score=Decimal("0.82"),
    )

    response = correct_ocr_results(
        None,
        document.id,
        OCRCorrectionRequest(
            corrected_data={
                "_document_type": "loan_contract",
                "_transaction_type": "expense",
                "user_contract_role": "borrower",
                "confirmed": True,
                "confirmed_at": "2026-03-23T22:35:01.536798",
                "confirmed_by": user.id,
            },
            notes="Reviewed from the document detail page",
        ),
        current_user=user,
        db=db_session,
    )

    assert "user_contract_role" in response.updated_fields

    db_session.refresh(document)
    assert document.ocr_result["user_contract_role"] == "borrower"
    assert document.ocr_result["user_contract_role_source"] == "manual_override"
    assert document.ocr_result["import_suggestion"]["type"] == "create_loan_repayment"
    assert document.ocr_result["import_suggestion"]["status"] == "pending"


def test_correct_ocr_allows_document_type_change_only_from_other_or_unknown(
    db_session: Session,
):
    user = create_test_user(
        db_session,
        email="other-doc-review@example.com",
        name="Mag. Nina Leitner",
        user_type=UserType.LANDLORD,
    )
    user.email_verified = True
    db_session.commit()
    db_session.refresh(user)

    document = create_test_document(
        db_session,
        user=user,
        document_type=DocumentType.OTHER,
        file_name="unknown-doc.pdf",
        ocr_result={
            "merchant": "Sample Merchant",
            "amount": 120.0,
        },
        raw_text="Sample OCR text",
        confidence_score=Decimal("0.71"),
    )

    response = correct_ocr_results(
        None,
        document.id,
        OCRCorrectionRequest(
            corrected_data={
                "_document_type": "bank_statement",
            },
            notes="Reclassify generic document",
        ),
        current_user=user,
        db=db_session,
    )

    db_session.refresh(document)
    assert "document_type" in response.updated_fields
    assert document.document_type == DocumentType.BANK_STATEMENT


def test_correct_ocr_rejects_document_type_change_for_non_other_documents(
    db_session: Session,
):
    user = create_test_user(
        db_session,
        email="locked-doc-review@example.com",
        name="DI Markus Kern",
        user_type=UserType.LANDLORD,
    )
    user.email_verified = True
    db_session.commit()
    db_session.refresh(user)

    document = create_test_document(
        db_session,
        user=user,
        document_type=DocumentType.INVOICE,
        file_name="invoice-review.pdf",
        ocr_result={
            "merchant": "Invoice Merchant",
            "amount": 99.0,
        },
        raw_text="Invoice OCR text",
        confidence_score=Decimal("0.91"),
    )

    with pytest.raises(Exception) as exc_info:
        correct_ocr_results(
            None,
            document.id,
            OCRCorrectionRequest(
                corrected_data={
                    "_document_type": "bank_statement",
                },
                notes="Attempt to force different type",
            ),
            current_user=user,
            db=db_session,
        )

    db_session.refresh(document)
    assert document.document_type == DocumentType.INVOICE
    assert "Other or Unknown" in str(exc_info.value)
