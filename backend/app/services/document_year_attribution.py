"""Helpers for resolving and materializing document year attribution."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import re
from typing import Any, Iterable, Optional

from app.services.document_date_resolver import resolve_document_date


YEAR_BASIS_CONFIDENCE: dict[str, float] = {
    "statement_period_start": 1.00,
    "transaction_min_date": 0.90,
    "tax_year": 1.00,
    "document_date": 0.85,
    "date": 0.85,
    "invoice_date": 0.85,
    "receipt_date": 0.85,
    "purchase_date": 0.85,
    "start_date": 0.85,
    "created_at_fallback": 0.25,
}

DATE_FALLBACK_FIELDS = [
    "document_date",
    "date",
    "invoice_date",
    "receipt_date",
    "purchase_date",
    "start_date",
]

BANK_STATEMENT_TYPES = {
    "bank_statement",
    "kontoauszug",
}

TAX_YEAR_TYPES = {
    "property_tax",
    "lohnzettel",
    "svs_notice",
    "einkommensteuerbescheid",
    "e1_form",
    "l1_form",
    "l1k_beilage",
    "l1ab_beilage",
    "e1a_beilage",
    "e1b_beilage",
    "e1kv_beilage",
    "u1_form",
    "u30_form",
}

_DATE_PATTERNS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y.%m.%d",
    "%d.%m.%Y",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d.%m.%y",
    "%d/%m/%y",
    "%d-%m-%y",
)

_DATE_IN_TEXT_RE = re.compile(r"\b\d{1,4}[./-]\d{1,2}[./-]\d{1,4}\b")


@dataclass(frozen=True)
class YearAttribution:
    document_year: Optional[int]
    year_basis: Optional[str]
    year_confidence: Optional[float]
    period_start: Optional[date] = None
    period_end: Optional[date] = None


def _normalize_document_type(value: Any) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "value"):
        return str(value.value).lower()
    return str(value).lower()


def _parse_date_value(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if not isinstance(value, str):
        return None

    candidate = value.strip()
    if not candidate:
        return None

    for fmt in _DATE_PATTERNS:
        try:
            return datetime.strptime(candidate[:10], fmt).date()
        except ValueError:
            continue

    for match in _DATE_IN_TEXT_RE.finditer(candidate):
        text = match.group(0)
        for fmt in _DATE_PATTERNS:
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue

    return None


def _parse_year(value: Any) -> Optional[int]:
    if isinstance(value, int):
        year = value
    elif isinstance(value, str):
        digits = re.search(r"\b(19|20)\d{2}\b", value)
        if not digits:
            return None
        year = int(digits.group(0))
    else:
        return None

    if 1900 <= year <= 2100:
        return year
    return None


def _extract_statement_period(ocr_result: dict[str, Any]) -> tuple[Optional[date], Optional[date]]:
    period_start = _parse_date_value(ocr_result.get("period_start"))
    period_end = _parse_date_value(ocr_result.get("period_end"))

    statement_period = ocr_result.get("statement_period")
    if (period_start is None or period_end is None) and isinstance(statement_period, dict):
        period_start = period_start or _parse_date_value(statement_period.get("start"))
        period_end = period_end or _parse_date_value(statement_period.get("end"))

    if (period_start is None or period_end is None) and isinstance(statement_period, str):
        matches = [_parse_date_value(match.group(0)) for match in _DATE_IN_TEXT_RE.finditer(statement_period)]
        dates = [d for d in matches if d is not None]
        if dates:
            if period_start is None:
                period_start = min(dates)
            if period_end is None:
                period_end = max(dates)

    return period_start, period_end


def _extract_transaction_dates(transactions: Iterable[Any]) -> list[date]:
    dates: list[date] = []
    for tx in transactions:
        if not isinstance(tx, dict):
            continue
        parsed = _parse_date_value(tx.get("date"))
        if parsed is not None:
            dates.append(parsed)
    return dates


def _candidate_transaction_dates(ocr_result: dict[str, Any]) -> list[date]:
    date_candidates: list[date] = []

    for key in ("transactions", "parsed_transactions"):
        raw = ocr_result.get(key)
        if isinstance(raw, list):
            date_candidates.extend(_extract_transaction_dates(raw))

    import_suggestion = ocr_result.get("import_suggestion")
    if isinstance(import_suggestion, dict):
        data = import_suggestion.get("data")
        if isinstance(data, dict):
            txs = data.get("transactions")
            if isinstance(txs, list):
                date_candidates.extend(_extract_transaction_dates(txs))

    # Preserve order while deduplicating
    seen: set[date] = set()
    deduped: list[date] = []
    for tx_date in sorted(date_candidates):
        if tx_date not in seen:
            seen.add(tx_date)
            deduped.append(tx_date)
    return deduped


def _fallback_date_field(ocr_result: dict[str, Any]) -> tuple[Optional[date], Optional[str]]:
    for field in DATE_FALLBACK_FIELDS:
        parsed = _parse_date_value(ocr_result.get(field))
        if parsed is not None:
            return parsed, field
    return None, None


def resolve_document_year(
    document_type: Any,
    ocr_result: Optional[dict[str, Any]],
    *,
    uploaded_at: Optional[datetime] = None,
) -> YearAttribution:
    if not isinstance(ocr_result, dict):
        ocr_result = {}

    normalized_type = _normalize_document_type(document_type)

    if normalized_type in BANK_STATEMENT_TYPES:
        period_start, period_end = _extract_statement_period(ocr_result)
        if period_start is not None:
            return YearAttribution(
                document_year=period_start.year,
                year_basis="statement_period_start",
                year_confidence=YEAR_BASIS_CONFIDENCE["statement_period_start"],
                period_start=period_start,
                period_end=period_end,
            )

        transaction_dates = _candidate_transaction_dates(ocr_result)
        if transaction_dates:
            return YearAttribution(
                document_year=transaction_dates[0].year,
                year_basis="transaction_min_date",
                year_confidence=YEAR_BASIS_CONFIDENCE["transaction_min_date"],
                period_start=transaction_dates[0],
                period_end=transaction_dates[-1],
            )

    tax_year = _parse_year(ocr_result.get("tax_year"))
    if normalized_type in TAX_YEAR_TYPES and tax_year is not None:
        return YearAttribution(
            document_year=tax_year,
            year_basis="tax_year",
            year_confidence=YEAR_BASIS_CONFIDENCE["tax_year"],
        )

    fallback_date, basis = _fallback_date_field(ocr_result)
    if fallback_date is not None and basis is not None:
        return YearAttribution(
            document_year=fallback_date.year,
            year_basis=basis,
            year_confidence=YEAR_BASIS_CONFIDENCE[basis],
        )

    if uploaded_at is not None:
        return YearAttribution(
            document_year=uploaded_at.year,
            year_basis="created_at_fallback",
            year_confidence=YEAR_BASIS_CONFIDENCE["created_at_fallback"],
        )

    return YearAttribution(
        document_year=None,
        year_basis=None,
        year_confidence=None,
    )


def materialize_document_temporal_metadata(document: Any, ocr_result: Optional[dict[str, Any]]) -> YearAttribution:
    if not isinstance(ocr_result, dict):
        ocr_result = {}

    attribution = resolve_document_year(
        getattr(document, "document_type", None),
        ocr_result,
        uploaded_at=getattr(document, "uploaded_at", None),
    )

    materialized_date = resolve_document_date(ocr_result)
    normalized_type = _normalize_document_type(getattr(document, "document_type", None))
    if materialized_date is None and normalized_type in BANK_STATEMENT_TYPES:
        materialized_date = attribution.period_start

    document.document_date = materialized_date
    document.document_year = attribution.document_year
    document.year_basis = attribution.year_basis
    document.year_confidence = attribution.year_confidence

    if materialized_date is not None and "document_date" not in ocr_result:
        ocr_result["document_date"] = materialized_date.isoformat()
    if attribution.period_start is not None and not ocr_result.get("period_start"):
        ocr_result["period_start"] = attribution.period_start.isoformat()
    if attribution.period_end is not None and not ocr_result.get("period_end"):
        ocr_result["period_end"] = attribution.period_end.isoformat()

    if attribution.document_year is not None:
        ocr_result["document_year"] = attribution.document_year
    else:
        ocr_result.pop("document_year", None)

    if attribution.year_basis is not None:
        ocr_result["year_basis"] = attribution.year_basis
    else:
        ocr_result.pop("year_basis", None)

    if attribution.year_confidence is not None:
        ocr_result["year_confidence"] = attribution.year_confidence
    else:
        ocr_result.pop("year_confidence", None)

    return attribution
