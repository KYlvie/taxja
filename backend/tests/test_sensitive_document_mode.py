from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.models.document import DocumentType
from app.models.liability import Liability, LiabilityType
from app.models.recurring_transaction import (
    RecurrenceFrequency,
    RecurringTransaction,
    RecurringTransactionType,
)
from app.models.user import UserType
from app.services.ocr_transaction_service import OCRTransactionService
from app.tasks.ocr_tasks import (
    _build_kreditvertrag_suggestion,
    _build_versicherung_suggestion,
    create_insurance_recurring_from_suggestion,
    create_loan_from_suggestion,
    create_standalone_loan_repayment,
    refresh_contract_role_sensitive_suggestions,
)
from tests.fixtures.models import create_test_document, create_test_user


def test_loan_confirm_gate_blocks_unknown_role_in_strict(db, monkeypatch):
    monkeypatch.setattr(settings, "SENSITIVE_DOCUMENT_MODE", "strict")

    user = create_test_user(
        db,
        email="loan-unknown@example.com",
        name="Fenghong Zhang",
        user_type=UserType.EMPLOYEE,
    )
    document = create_test_document(
        db,
        user=user,
        document_type=DocumentType.LOAN_CONTRACT,
        file_name="loan.pdf",
        ocr_result={
            "loan_amount": 250000.0,
            "interest_rate": 3.2,
            "monthly_payment": 1215.0,
            "lender_name": "Sparkasse Wien",
            "start_date": "2026-01-01",
        },
        raw_text="Kreditvertrag Darlehensgeber Sparkasse Wien Darlehensbetrag EUR 250000",
        confidence_score=Decimal("0.88"),
    )

    with pytest.raises(ValueError, match="Loan creation is blocked"):
        create_loan_from_suggestion(
            db,
            document,
            {
                "loan_amount": 250000.0,
                "interest_rate": 3.2,
                "monthly_payment": 1215.0,
                "lender_name": "Sparkasse Wien",
                "start_date": "2026-01-01",
            },
        )


def test_insurance_provider_like_role_normalizes_to_unknown_in_strict(db, monkeypatch):
    monkeypatch.setattr(settings, "SENSITIVE_DOCUMENT_MODE", "strict")

    user = create_test_user(
        db,
        email="insurance-unknown@example.com",
        name="Fenghong Zhang",
        user_type=UserType.EMPLOYEE,
    )
    document = create_test_document(
        db,
        user=user,
        document_type=DocumentType.VERSICHERUNGSBESTAETIGUNG,
        file_name="insurance.pdf",
        ocr_result={
            "praemie": 540.0,
            "zahlungsfrequenz": "jährlich",
            "versicherer": "Allianz Österreich",
            "insurance_type": "car_insurance",
            "start_date": "2026-03-01",
        },
        raw_text="Versicherungsschein Versicherer Allianz Österreich Jahresprämie 540,00",
        confidence_score=Decimal("0.82"),
    )

    payload = _build_versicherung_suggestion(
        db,
        document,
        SimpleNamespace(raw_text=document.raw_text, confidence_score=Decimal("0.82")),
    )
    db.refresh(document)

    assert payload["import_suggestion"] is None
    assert document.ocr_result["user_contract_role"] == "unknown"
    assert document.ocr_result["contract_role_resolution"]["normalized_from"] == "provider"
    assert document.ocr_result["contract_role_resolution"]["strict_would_block"] is True


def test_insurance_duplicate_check_reuses_existing_recurring(db, monkeypatch):
    monkeypatch.setattr(settings, "SENSITIVE_DOCUMENT_MODE", "shadow")

    user = create_test_user(
        db,
        email="insurance-duplicate@example.com",
        name="Fenghong Zhang",
        user_type=UserType.EMPLOYEE,
    )
    document = create_test_document(
        db,
        user=user,
        document_type=DocumentType.VERSICHERUNGSBESTAETIGUNG,
        file_name="insurance-duplicate.pdf",
        ocr_result={
            "praemie": 120.0,
            "zahlungsfrequenz": "monthly",
            "versicherungsnehmer": "Fenghong Zhang",
            "versicherer": "Allianz Österreich",
            "insurance_type": "health",
            "start_date": "2026-03-01",
        },
        raw_text="Versicherungsnehmer Fenghong Zhang Versicherer Allianz Österreich Monatsprämie 120,00",
        confidence_score=Decimal("0.84"),
    )
    payload = _build_versicherung_suggestion(
        db,
        document,
        SimpleNamespace(raw_text=document.raw_text, confidence_score=Decimal("0.84")),
    )

    existing = RecurringTransaction(
        user_id=user.id,
        recurring_type=RecurringTransactionType.INSURANCE_PREMIUM,
        description="Insurance premium (health) - Allianz Österreich",
        amount=Decimal("120.00"),
        transaction_type="expense",
        category="insurance",
        frequency=RecurrenceFrequency.MONTHLY,
        start_date=date(2026, 3, 15),
        end_date=None,
        day_of_month=1,
        is_active=True,
        next_generation_date=date(2026, 4, 1),
        notes="insurance_type=health; insurer_name=Allianz Österreich",
    )
    db.add(existing)
    db.commit()
    db.refresh(existing)

    result = create_insurance_recurring_from_suggestion(
        db,
        document,
        payload["import_suggestion"]["data"],
    )
    db.refresh(document)

    assert result["duplicate_reused"] is True
    assert result["recurring_id"] == existing.id
    assert document.ocr_result["import_suggestion"]["duplicate_of_recurring_id"] == existing.id


def test_standalone_loan_confirmation_promotes_to_property_loan_when_address_matches(db, monkeypatch):
    monkeypatch.setattr(settings, "SENSITIVE_DOCUMENT_MODE", "shadow")

    user = create_test_user(
        db,
        email="loan-promote@example.com",
        name="Ing. Klaus Bauer",
        business_name="Ing. Klaus Bauer",
        user_type=UserType.SELF_EMPLOYED,
    )
    document = create_test_document(
        db,
        user=user,
        document_type=DocumentType.LOAN_CONTRACT,
        file_name="loan-promote.pdf",
        ocr_result={
            "property_address": "Argentinierstrasse 21, 1234 Wien",
            "borrower_name": "Ing. Klaus Bauer",
        },
        raw_text="Kreditvertrag Kreditnehmer Ing. Klaus Bauer",
        confidence_score=Decimal("0.93"),
    )

    monkeypatch.setattr(
        "app.tasks.ocr_tasks._match_property_for_loan_contract",
        lambda *args, **kwargs: ("prop-1", "Argentinierstrasse 21, 1234 Wien", False),
    )

    promoted = {}

    def _fake_create_loan_from_suggestion(db_session, doc, suggestion_data):
        promoted["data"] = suggestion_data
        return {"loan_id": "loan-1", "property_id": "prop-1"}

    monkeypatch.setattr(
        "app.tasks.ocr_tasks.create_loan_from_suggestion",
        _fake_create_loan_from_suggestion,
    )

    result = create_standalone_loan_repayment(
        db,
        document,
        {
            "monthly_payment": 1508.33,
            "property_address": "Argentinierstrasse 21, 1234 Wien",
            "lender_name": "Erste Bank",
            "start_date": "2026-03-01",
        },
    )

    assert result["property_id"] == "prop-1"
    assert promoted["data"]["matched_property_id"] == "prop-1"


def test_standalone_loan_confirmation_without_property_creates_standalone_liability(db, monkeypatch):
    monkeypatch.setattr(settings, "SENSITIVE_DOCUMENT_MODE", "shadow")

    user = create_test_user(
        db,
        email="loan-unlinked@example.com",
        name="Ing. Klaus Bauer",
        business_name="Ing. Klaus Bauer",
        user_type=UserType.SELF_EMPLOYED,
    )
    document = create_test_document(
        db,
        user=user,
        document_type=DocumentType.LOAN_CONTRACT,
        file_name="loan-unlinked.pdf",
        ocr_result={
            "property_address": "Unmatched Street 99, 9999 Wien",
            "borrower_name": "Ing. Klaus Bauer",
            "import_suggestion": {
                "type": "create_loan_repayment",
                "status": "pending",
                "data": {
                    "loan_amount": 250000.0,
                    "interest_rate": 3.2,
                    "monthly_payment": 1508.33,
                    "property_address": "Unmatched Street 99, 9999 Wien",
                    "lender_name": "Erste Bank",
                    "start_date": "2026-03-01",
                },
            },
        },
        raw_text="Kreditvertrag Kreditnehmer Ing. Klaus Bauer",
        confidence_score=Decimal("0.93"),
    )

    monkeypatch.setattr(
        "app.tasks.ocr_tasks._match_property_for_loan_contract",
        lambda *args, **kwargs: (None, None, False),
    )

    result = create_standalone_loan_repayment(
        db,
        document,
        document.ocr_result["import_suggestion"]["data"],
    )
    db.refresh(document)

    liability = db.query(Liability).filter(Liability.id == result["liability_id"]).one()

    assert result["acknowledged_only"] is False
    assert result["liability_id"] == liability.id
    assert result["generated_count"] == 0
    assert result["created_transaction"] is True
    assert liability.liability_type == LiabilityType.BUSINESS_LOAN
    assert liability.source_document_id == document.id
    assert (
        db.query(RecurringTransaction)
        .filter(RecurringTransaction.user_id == user.id)
        .count()
        == 1
    )
    assert document.ocr_result["import_suggestion"]["status"] == "confirmed"
    assert "acknowledged_only" not in document.ocr_result["import_suggestion"]
    assert document.ocr_result["import_suggestion"]["liability_id"] == liability.id
    assert (
        document.ocr_result["import_suggestion"]["data"]["created_liability_id"]
        == liability.id
    )


def test_invoice_proforma_is_blocked_in_strict_before_transaction_suggestion(db, monkeypatch):
    monkeypatch.setattr(settings, "SENSITIVE_DOCUMENT_MODE", "strict")

    user = create_test_user(
        db,
        email="proforma@example.com",
        name="ZH TECH SOLUTIONS E.U.",
        user_type=UserType.SELF_EMPLOYED,
        business_type="freiberufler",
    )
    document = create_test_document(
        db,
        user=user,
        document_type=DocumentType.INVOICE,
        file_name="proforma.pdf",
        ocr_result={
            "amount": 900.0,
            "date": "2026-03-01",
            "supplier": "Cloud Vendor GmbH",
            "invoice_to": "ZH TECH SOLUTIONS E.U.",
        },
        raw_text="Proforma Rechnung Invoice to ZH TECH SOLUTIONS E.U. Supplier Cloud Vendor GmbH Total EUR 900,00",
        confidence_score=Decimal("0.79"),
    )

    suggestions = OCRTransactionService(db).create_split_suggestions(document.id, user.id)
    db.refresh(document)

    assert suggestions == []
    assert document.ocr_result["document_transaction_direction"] == "expense"
    assert document.ocr_result["commercial_document_semantics"] == "proforma"
    assert document.ocr_result["transaction_direction_resolution"]["strict_would_block"] is True


def test_receipt_direction_defaults_to_receipt_semantics(db, monkeypatch):
    monkeypatch.setattr(settings, "SENSITIVE_DOCUMENT_MODE", "shadow")

    user = create_test_user(
        db,
        email="receipt@example.com",
        name="Fenghong Zhang",
        user_type=UserType.SELF_EMPLOYED,
        business_type="freiberufler",
    )
    document = create_test_document(
        db,
        user=user,
        document_type=DocumentType.RECEIPT,
        file_name="receipt.pdf",
        ocr_result={
            "amount": 48.70,
            "date": "2026-03-02",
            "merchant": "OMV",
            "product_summary": "Fuel",
        },
        raw_text="OMV Kassenbon Betrag 48,70 Fuel",
        confidence_score=Decimal("0.83"),
    )
    service = OCRTransactionService(db)
    original_classify = service._classify_from_ocr
    service._classify_from_ocr = lambda *args, **kwargs: {
        "transaction_type": "expense",
        "category": "fuel",
        "is_deductible": True,
        "deduction_reason": "Fuel expense",
        "confidence": 0.88,
        "classification_method": "rule",
        "requires_review": False,
    }

    try:
        suggestions = service.create_split_suggestions(document.id, user.id)
    finally:
        service._classify_from_ocr = original_classify

    db.refresh(document)
    assert suggestions
    assert suggestions[0]["commercial_document_semantics"] == "receipt"
    assert suggestions[0]["document_transaction_direction"] == "expense"
    assert document.ocr_result["commercial_document_semantics"] == "receipt"


def test_bank_statement_refresh_only_updates_direction_metadata(db, monkeypatch):
    monkeypatch.setattr(settings, "SENSITIVE_DOCUMENT_MODE", "shadow")

    user = create_test_user(
        db,
        email="statement@example.com",
        name="Fenghong Zhang",
        user_type=UserType.EMPLOYEE,
    )
    document = create_test_document(
        db,
        user=user,
        document_type=DocumentType.BANK_STATEMENT,
        file_name="statement.pdf",
        ocr_result={
            "account_holder": "Fenghong Zhang",
            "statement_period": "2026-03",
        },
        raw_text="Kontoauszug Soll Haben Buchungsliste",
        confidence_score=Decimal("0.73"),
    )

    payload = refresh_contract_role_sensitive_suggestions(db, document)
    db.refresh(document)

    assert payload["transaction_direction_resolution"]["gate_enabled"] is False
    assert document.ocr_result["transaction_direction_resolution"]["gate_enabled"] is False
    assert document.ocr_result["commercial_document_semantics"] == "unknown"
