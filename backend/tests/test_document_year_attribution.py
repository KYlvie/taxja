from datetime import date, datetime
from types import SimpleNamespace

from app.services.document_year_attribution import (
    materialize_document_temporal_metadata,
    resolve_document_year,
)


def _make_document(document_type="other", uploaded_at=datetime(2026, 3, 24, 10, 0, 0)):
    return SimpleNamespace(
        document_type=document_type,
        uploaded_at=uploaded_at,
        document_date=None,
        document_year=None,
        year_basis=None,
        year_confidence=None,
    )


def test_resolve_document_year_prefers_bank_statement_period_start():
    attribution = resolve_document_year(
        "bank_statement",
        {
            "period_start": "2024-06-26",
            "period_end": "2024-12-19",
            "transactions": [
                {"date": "2024-06-26"},
                {"date": "2024-12-19"},
            ],
        },
        uploaded_at=datetime(2026, 3, 24, 10, 0, 0),
    )

    assert attribution.document_year == 2024
    assert attribution.year_basis == "statement_period_start"
    assert attribution.year_confidence == 1.0
    assert attribution.period_start == date(2024, 6, 26)
    assert attribution.period_end == date(2024, 12, 19)


def test_resolve_document_year_uses_earliest_transaction_date_when_period_missing():
    attribution = resolve_document_year(
        "kontoauszug",
        {
            "transactions": [
                {"date": "2025-01-02"},
                {"date": "2024-12-31"},
            ]
        },
        uploaded_at=datetime(2026, 3, 24, 10, 0, 0),
    )

    assert attribution.document_year == 2024
    assert attribution.year_basis == "transaction_min_date"
    assert attribution.period_start == date(2024, 12, 31)
    assert attribution.period_end == date(2025, 1, 2)


def test_resolve_document_year_uses_tax_year_for_tax_documents():
    attribution = resolve_document_year(
        "einkommensteuerbescheid",
        {"tax_year": "2024", "date": "2026-03-24"},
        uploaded_at=datetime(2026, 3, 24, 10, 0, 0),
    )

    assert attribution.document_year == 2024
    assert attribution.year_basis == "tax_year"
    assert attribution.year_confidence == 1.0


def test_resolve_document_year_ignores_tax_year_for_non_tax_documents():
    attribution = resolve_document_year(
        "invoice",
        {"tax_year": "2024", "invoice_date": "2023-04-01"},
        uploaded_at=datetime(2026, 3, 24, 10, 0, 0),
    )

    assert attribution.document_year == 2023
    assert attribution.year_basis == "invoice_date"
    assert attribution.year_confidence == 0.85


def test_resolve_document_year_falls_back_to_exact_date_then_uploaded_at():
    invoice_attr = resolve_document_year(
        "invoice",
        {"invoice_date": "2023-04-01"},
        uploaded_at=datetime(2026, 3, 24, 10, 0, 0),
    )
    fallback_attr = resolve_document_year(
        "other",
        {},
        uploaded_at=datetime(2026, 3, 24, 10, 0, 0),
    )

    assert invoice_attr.document_year == 2023
    assert invoice_attr.year_basis == "invoice_date"
    assert invoice_attr.year_confidence == 0.85

    assert fallback_attr.document_year == 2026
    assert fallback_attr.year_basis == "created_at_fallback"
    assert fallback_attr.year_confidence == 0.25


def test_materialize_document_temporal_metadata_sets_bank_statement_fields():
    document = _make_document("bank_statement")
    ocr_result = {
        "statement_period": {
            "start": "2024-06-26",
            "end": "2024-12-19",
        }
    }

    materialize_document_temporal_metadata(document, ocr_result)

    assert document.document_date == date(2024, 6, 26)
    assert document.document_year == 2024
    assert document.year_basis == "statement_period_start"
    assert document.year_confidence == 1.0
    assert ocr_result["document_year"] == 2024
    assert ocr_result["year_basis"] == "statement_period_start"
    assert ocr_result["year_confidence"] == 1.0
