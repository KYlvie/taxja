"""Resolve the best document date from OCR result using a priority chain."""
from datetime import date
from typing import Any, Optional

DATE_FIELD_PRIORITY = [
    "document_date",
    "date",
    "invoice_date",
    "receipt_date",
    "purchase_date",
    "start_date",
]


def resolve_document_date(ocr_result: Optional[dict[str, Any]]) -> Optional[date]:
    """Extract the best document date from OCR result using priority chain.

    Checks fields in priority order: document_date, date, invoice_date,
    receipt_date, purchase_date, start_date. Returns the first valid
    calendar date found, or None.
    """
    if not ocr_result or not isinstance(ocr_result, dict):
        return None
    for field in DATE_FIELD_PRIORITY:
        value = ocr_result.get(field)
        if value and isinstance(value, str):
            try:
                return date.fromisoformat(value[:10])
            except (ValueError, TypeError):
                continue
    return None
