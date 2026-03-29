from datetime import date
from decimal import Decimal

from app.models.document import DocumentType
from app.models.recurring_transaction import RecurringTransaction
from app.models.transaction import TransactionType
from app.models.user import UserType
from app.services.dashboard_service import DashboardService
from app.services.ocr_transaction_service import OCRTransactionService
from tests.fixtures.models import create_test_document, create_test_user


def _svs_payload(
    user_id: int,
    *,
    subtype: str,
    beitragsjahr: int,
    amount: str | Decimal | None = None,
    quarter: int | None = None,
    doc_date: date | None = None,
) -> dict:
    payload: dict = {
        "_user_id": user_id,
        "svs_subtype": subtype,
        "beitragsjahr": beitragsjahr,
        "tax_year": beitragsjahr,
        "date": (doc_date or date(beitragsjahr, 1, 15)).isoformat(),
        "raw_text": f"SVS {subtype} {beitragsjahr}",
    }
    if quarter is not None:
        payload["quarter"] = quarter
    if amount is not None:
        if subtype == "saeumniszuschlag":
            payload["saeumniszuschlag_betrag"] = amount
        elif subtype == "nachforderung":
            payload["nachzahlung"] = amount
        elif subtype == "gutschrift":
            payload["gutschrift"] = amount
        elif subtype == "ratenzahlung":
            payload["ratenbetrag"] = amount
            payload["ratenanzahl"] = 6
        else:
            payload["beitrag_gesamt"] = amount
    return payload


def test_svs_vorschreibung_duplicate_same_year_quarter_amount_dedups(db):
    user = create_test_user(db, email="svs-dedup-v@example.com", user_type=UserType.SELF_EMPLOYED)
    create_test_document(
        db,
        user,
        document_type=DocumentType.SVS_NOTICE,
        file_name="svs_q1_existing.pdf",
        ocr_result={
            "svs_subtype": "vorschreibung",
            "beitragsjahr": 2024,
            "quarter": 1,
            "beitrag_gesamt": "3271.87",
            "date": "2024-01-15",
        },
    )

    service = OCRTransactionService(db)
    result = service._extract_from_svs_notice(
        _svs_payload(
            user.id,
            subtype="vorschreibung",
            beitragsjahr=2024,
            quarter=1,
            amount="3271.87",
        )
    )

    assert result is None


def test_svs_vorschreibung_different_quarter_or_amount_do_not_dedup(db):
    user = create_test_user(db, email="svs-vorschreibung@example.com", user_type=UserType.SELF_EMPLOYED)
    create_test_document(
        db,
        user,
        document_type=DocumentType.SVS_NOTICE,
        file_name="svs_q1_existing.pdf",
        ocr_result={
            "svs_subtype": "vorschreibung",
            "beitragsjahr": 2024,
            "quarter": 1,
            "beitrag_gesamt": "3271.87",
            "date": "2024-01-15",
        },
    )

    service = OCRTransactionService(db)
    q2 = service._extract_from_svs_notice(
        _svs_payload(
            user.id,
            subtype="vorschreibung",
            beitragsjahr=2024,
            quarter=2,
            amount="3271.87",
            doc_date=date(2024, 4, 15),
        )
    )
    reduced = service._extract_from_svs_notice(
        _svs_payload(
            user.id,
            subtype="vorschreibung",
            beitragsjahr=2024,
            quarter=3,
            amount="2453.55",
            doc_date=date(2024, 7, 15),
        )
    )

    assert q2 is not None
    assert q2["_svs_subtype"] == "vorschreibung"
    assert q2["_quarter"] == 2
    assert q2["_beitragsjahr"] == 2024

    assert reduced is not None
    assert reduced["_quarter"] == 3
    assert Decimal(str(reduced["amount"])) == Decimal("2453.55")


def test_svs_nachforderung_dedups_by_beitragsjahr_only(db):
    user = create_test_user(db, email="svs-nf@example.com", user_type=UserType.SELF_EMPLOYED)
    create_test_document(
        db,
        user,
        document_type=DocumentType.SVS_NOTICE,
        file_name="svs_nf_2024.pdf",
        ocr_result={
            "svs_subtype": "nachforderung",
            "beitragsjahr": 2024,
            "nachzahlung": "2657.00",
            "date": "2026-03-10",
        },
    )

    service = OCRTransactionService(db)
    duplicate = service._extract_from_svs_notice(
        _svs_payload(
            user.id,
            subtype="nachforderung",
            beitragsjahr=2024,
            amount="2657.00",
            doc_date=date(2026, 3, 10),
        )
    )
    different_year = service._extract_from_svs_notice(
        _svs_payload(
            user.id,
            subtype="nachforderung",
            beitragsjahr=2023,
            amount="3226.42",
            doc_date=date(2026, 3, 20),
        )
    )

    assert duplicate is None
    assert different_year is not None
    assert different_year["_beitragsjahr"] == 2023


def test_svs_gutschrift_is_income_and_dedups_by_beitragsjahr(db):
    user = create_test_user(db, email="svs-gs@example.com", user_type=UserType.SELF_EMPLOYED)
    doc = create_test_document(
        db,
        user,
        document_type=DocumentType.SVS_NOTICE,
        file_name="svs_gs_2024.pdf",
        ocr_result={},
    )
    service = OCRTransactionService(db)

    transaction_data = service._extract_from_svs_notice(
        _svs_payload(
            user.id,
            subtype="gutschrift",
            beitragsjahr=2024,
            amount="2633.20",
            doc_date=date(2026, 4, 2),
        )
    )

    assert transaction_data is not None
    classification = service._classify_from_ocr(doc, transaction_data, user.id)
    assert classification["transaction_type"] == TransactionType.INCOME.value

    create_test_document(
        db,
        user,
        document_type=DocumentType.SVS_NOTICE,
        file_name="svs_gs_existing.pdf",
        ocr_result={
            "svs_subtype": "gutschrift",
            "beitragsjahr": 2024,
            "gutschrift": "2633.20",
            "date": "2026-04-02",
        },
    )
    duplicate = service._extract_from_svs_notice(
        _svs_payload(
            user.id,
            subtype="gutschrift",
            beitragsjahr=2024,
            amount="2633.20",
            doc_date=date(2026, 4, 3),
        )
    )
    assert duplicate is None


def test_svs_saeumniszuschlag_dedups_by_beitragsjahr_and_quarter(db):
    user = create_test_user(db, email="svs-sz@example.com", user_type=UserType.SELF_EMPLOYED)
    create_test_document(
        db,
        user,
        document_type=DocumentType.SVS_NOTICE,
        file_name="svs_sz_q3.pdf",
        ocr_result={
            "svs_subtype": "saeumniszuschlag",
            "beitragsjahr": 2024,
            "quarter": 3,
            "saeumniszuschlag_betrag": "65.44",
            "date": "2024-09-15",
        },
    )

    service = OCRTransactionService(db)
    duplicate = service._extract_from_svs_notice(
        _svs_payload(
            user.id,
            subtype="saeumniszuschlag",
            beitragsjahr=2024,
            quarter=3,
            amount="65.44",
            doc_date=date(2024, 9, 20),
        )
    )
    q4 = service._extract_from_svs_notice(
        _svs_payload(
            user.id,
            subtype="saeumniszuschlag",
            beitragsjahr=2024,
            quarter=4,
            amount="65.44",
            doc_date=date(2024, 12, 15),
        )
    )

    assert duplicate is None
    assert q4 is not None
    assert q4["_quarter"] == 4
    assert q4["_beitragsjahr"] == 2024


def test_svs_ratenzahlung_creates_monthly_recurring_once(db):
    user = create_test_user(db, email="svs-rz@example.com", user_type=UserType.SELF_EMPLOYED)
    service = OCRTransactionService(db)

    first = service._extract_from_svs_notice(
        _svs_payload(
            user.id,
            subtype="ratenzahlung",
            beitragsjahr=2024,
            amount="442.84",
            doc_date=date(2026, 4, 1),
        )
    )
    second = service._extract_from_svs_notice(
        _svs_payload(
            user.id,
            subtype="ratenzahlung",
            beitragsjahr=2024,
            amount="442.84",
            doc_date=date(2026, 4, 2),
        )
    )

    recurring = db.query(RecurringTransaction).filter(RecurringTransaction.user_id == user.id).all()

    assert first is None
    assert second is None
    assert len(recurring) == 1
    assert recurring[0].template == "svs_ratenzahlung"
    assert recurring[0].frequency.value == "monthly"


def test_svs_jahresbestaetigung_creates_no_transaction(db):
    user = create_test_user(db, email="svs-jb@example.com", user_type=UserType.SELF_EMPLOYED)
    service = OCRTransactionService(db)

    result = service._extract_from_svs_notice(
        _svs_payload(
            user.id,
            subtype="jahresbestaetigung",
            beitragsjahr=2024,
            amount="13087.48",
            doc_date=date(2025, 1, 10),
        )
    )

    assert result is None


def test_dashboard_svs_quarter_reminder_uses_real_due_dates(db, monkeypatch):
    user = create_test_user(db, email="svs-dashboard@example.com", user_type=UserType.SELF_EMPLOYED)
    create_test_document(
        db,
        user,
        document_type=DocumentType.SVS_NOTICE,
        file_name="svs_q1_uploaded.pdf",
        ocr_result={
            "svs_subtype": "vorschreibung",
            "beitragsjahr": 2024,
            "quarter": 1,
            "beitrag_gesamt": "3271.87",
            "date": "2024-01-15",
        },
    )

    monkeypatch.setattr(DashboardService, "_today", staticmethod(lambda: date(2024, 8, 15)))
    service = DashboardService(db)
    august = service.get_suggestions(user.id, 2024, language="de")
    august_quarters = sorted(
        s["svs_quarter"]
        for s in august["suggestions"]
        if s.get("document_type") == DocumentType.SVS_NOTICE.value and s.get("svs_quarter") is not None
    )

    monkeypatch.setattr(DashboardService, "_today", staticmethod(lambda: date(2024, 9, 1)))
    september = service.get_suggestions(user.id, 2024, language="de")
    september_quarters = sorted(
        s["svs_quarter"]
        for s in september["suggestions"]
        if s.get("document_type") == DocumentType.SVS_NOTICE.value and s.get("svs_quarter") is not None
    )

    assert august_quarters == [2]
    assert september_quarters == [2, 3]
