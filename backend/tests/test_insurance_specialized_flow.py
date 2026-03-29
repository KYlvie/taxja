from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from app.models.document import DocumentType
from app.models.recurring_transaction import RecurringTransaction, RecurringTransactionType, RecurrenceFrequency
from app.models.transaction_line_item import LineItemPostingType
from app.services.recurring_transaction_service import RecurringTransactionService
from app.tasks.ocr_tasks import (
    _build_versicherung_suggestion,
    create_insurance_recurring_from_suggestion,
)
from tests.fixtures.models import create_test_document, create_test_user
from app.models.user import UserType


def test_sepa_insurance_document_creates_single_expense(db_session, monkeypatch):
    user = create_test_user(
        db_session,
        email="insurance-sepa@example.com",
        name="Maria Steiner",
        user_type=UserType.SELF_EMPLOYED,
    )
    document = create_test_document(
        db_session,
        user=user,
        document_type=DocumentType.VERSICHERUNGSBESTAETIGUNG,
        file_name="zuerich-sepa.pdf",
        ocr_result={},
        raw_text="SEPA Lastschrift Haushaltsversicherung Monatsprämie EUR 28,40",
    )

    monkeypatch.setattr(
        "app.services.ocr_engine.OCREngine.extract_by_type",
        lambda self, doc, doc_type: {
            "document_subtype": "sepa_beleg",
            "insurer_name": "Zürich Versicherungs-AG",
            "insurance_type": "Haushaltsversicherung",
            "insurance_subtype": "haushaltsversicherung",
            "versicherungsnehmer": "Maria Steiner",
            "polizze_nr": "ZH-123",
            "vertragsbeginn": "2024-01-01",
            "payment_frequency": "monthly",
            "payment_amount": 28.40,
            "premium_annual_brutto": 340.80,
        },
    )
    monkeypatch.setattr(
        "app.services.ocr_engine.OCREngine.re_extract_insurance_fields",
        lambda *args, **kwargs: None,
    )

    payload = _build_versicherung_suggestion(
        db_session,
        document,
        SimpleNamespace(raw_text=document.raw_text, confidence_score=Decimal("0.95")),
    )

    db_session.refresh(document)

    assert payload["import_suggestion"] is None
    assert document.transaction_id is not None
    assert document.ocr_result["insurance_auto_action"]["type"] == "created_single_expense"


def test_confirmed_insurance_recurring_persists_metadata_and_scheduler_splits(db_session):
    user = create_test_user(
        db_session,
        email="insurance-recurring@example.com",
        name="Maria Steiner",
        user_type=UserType.SELF_EMPLOYED,
    )
    document = create_test_document(
        db_session,
        user=user,
        document_type=DocumentType.VERSICHERUNGSBESTAETIGUNG,
        file_name="allianz-rs.pdf",
        ocr_result={
            "import_suggestion": {
                "type": "create_insurance_recurring",
                "status": "pending",
                "data": {},
            }
        },
        raw_text="Allianz Rechtsschutz",
    )

    suggestion_data = {
        "document_subtype": "jahresbestaetigung",
        "insurer_name": "Allianz Elementar",
        "insurance_type": "Rechtsschutzversicherung",
        "insurance_subtype": "rechtsschutz",
        "polizze_nr": "AL-987",
        "versicherungsnehmer": "Maria Steiner",
        "vertragsbeginn": "2024-01-01",
        "payment_frequency": "quarterly",
        "payment_amount": 92.16,
        "premium_annual_brutto": 363.12,
        "deductibility_status": "partially_deductible",
        "deductibility_hint": "Only the professional portion is deductible.",
        "input_fields": ["beruflicher_anteil_pct"],
        "split_mode": "beruflicher_anteil_split",
    }

    result = create_insurance_recurring_from_suggestion(
        db_session,
        document,
        suggestion_data,
        {
            "beruflicher_anteil_pct": 60,
            "override_payment_amount": 100.00,
            "override_payment_frequency": "quarterly",
            "dedup_resolution": "ignore_existing",
        },
    )

    recurring = (
        db_session.query(RecurringTransaction)
        .filter(RecurringTransaction.id == result["recurring_id"])
        .first()
    )
    assert recurring is not None
    assert recurring.amount == Decimal("100.00")
    assert recurring.frequency == RecurrenceFrequency.QUARTERLY
    assert recurring.insurance_metadata["deductible_pct"] == 0.6
    assert recurring.insurance_metadata["beruflicher_anteil_pct"] == 60

    service = RecurringTransactionService(db_session)
    generated = service.generate_due_transactions(target_date=recurring.start_date, user_id=user.id)
    assert len(generated) == 1

    transaction = generated[0]
    db_session.refresh(transaction)
    assert len(transaction.line_items) == 2
    assert transaction.line_items[0].posting_type == LineItemPostingType.EXPENSE
    assert transaction.line_items[1].posting_type == LineItemPostingType.PRIVATE_USE
    assert transaction.line_items[0].amount == Decimal("60.00")
    assert transaction.line_items[1].amount == Decimal("40.00")


def test_jahresbestaetigung_without_explicit_frequency_keeps_only_annual_amount(db_session, monkeypatch):
    user = create_test_user(
        db_session,
        email="insurance-jahresbetrag@example.com",
        name="Maria Steiner",
        user_type=UserType.SELF_EMPLOYED,
    )
    document = create_test_document(
        db_session,
        user=user,
        document_type=DocumentType.VERSICHERUNGSBESTAETIGUNG,
        file_name="grawe-jahresbestaetigung.pdf",
        ocr_result={},
        raw_text="Jahresbestätigung Gesamt bezahlt EUR 1.662,36",
    )

    monkeypatch.setattr(
        "app.services.ocr_engine.OCREngine.extract_by_type",
        lambda self, doc, doc_type: {
            "document_subtype": "jahresbestaetigung",
            "insurer_name": "GRAWE",
            "insurance_type": "Private Krankenversicherung",
            "insurance_subtype": "private_krankenversicherung",
            "versicherungsnehmer": "Maria Steiner",
            "polizze_nr": "GR-2024-55",
            "vertragsbeginn": "2022-03-01",
            "premium_annual_brutto": 1662.36,
        },
    )
    monkeypatch.setattr(
        "app.services.ocr_engine.OCREngine.re_extract_insurance_fields",
        lambda *args, **kwargs: None,
    )

    payload = _build_versicherung_suggestion(
        db_session,
        document,
        SimpleNamespace(raw_text=document.raw_text, confidence_score=Decimal("0.95")),
    )

    suggestion = payload["import_suggestion"]
    assert suggestion is not None
    assert suggestion["data"]["premium_annual_brutto"] == 1662.36
    assert suggestion["data"]["payment_amount"] is None


def test_archive_only_marks_insurance_suggestion_as_confirmed_terminal_state(db_session):
    user = create_test_user(
        db_session,
        email="insurance-archive@example.com",
        name="Maria Steiner",
        user_type=UserType.SELF_EMPLOYED,
    )
    document = create_test_document(
        db_session,
        user=user,
        document_type=DocumentType.VERSICHERUNGSBESTAETIGUNG,
        file_name="bedingungen.pdf",
        ocr_result={
            "import_suggestion": {
                "type": "archive_insurance_document",
                "status": "pending",
                "data": {
                    "document_subtype": "bedingungen",
                    "insurer_name": "UNIQA",
                    "insurance_type": "Berufshaftpflichtversicherung",
                },
            }
        },
        raw_text="Versicherungsbedingungen",
    )

    result = create_insurance_recurring_from_suggestion(
        db_session,
        document,
        document.ocr_result["import_suggestion"]["data"],
        {
            "archive_only": True,
            "archive_reason_code": "reference_only",
        },
    )

    db_session.refresh(document)
    suggestion = document.ocr_result["import_suggestion"]

    assert result["archive_only"] is True
    assert suggestion["status"] == "confirmed"
    assert suggestion["resolution"] == "archive_only"
    assert suggestion["archive_reason_code"] == "reference_only"
