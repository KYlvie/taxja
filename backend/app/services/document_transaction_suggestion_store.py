"""Helpers for persisting and consuming stored document transaction suggestions."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable


def _is_transaction_suggestion_payload(payload: Any) -> bool:
    return isinstance(payload, dict) and payload.get("amount") is not None


def iter_transaction_suggestion_refs(
    ocr_result: dict[str, Any] | None,
    *,
    include_stale: bool = False,
) -> list[dict[str, Any]]:
    """Return in-place suggestion dicts stored in OCR result.

    Prefers `tax_analysis.items` when available, because that is the authoritative
    multi-suggestion container. Falls back to the legacy single
    `transaction_suggestion` payload.
    """
    if not isinstance(ocr_result, dict):
        return []

    tax_analysis = ocr_result.get("tax_analysis")
    items = tax_analysis.get("items") if isinstance(tax_analysis, dict) else None
    item_refs: list[dict[str, Any]] = []
    if isinstance(items, list):
        for item in items:
            if not _is_transaction_suggestion_payload(item):
                continue
            if not include_stale and item.get("_stale"):
                continue
            item_refs.append(item)
        if item_refs:
            return item_refs

    stored = ocr_result.get("transaction_suggestion")
    if _is_transaction_suggestion_payload(stored):
        if include_stale or not stored.get("_stale"):
            return [stored]

    return []


def copy_transaction_suggestions(
    ocr_result: dict[str, Any] | None,
    *,
    include_stale: bool = False,
) -> list[dict[str, Any]]:
    return [deepcopy(ref) for ref in iter_transaction_suggestion_refs(ocr_result, include_stale=include_stale)]


def mark_transaction_suggestions_stale(ocr_result: dict[str, Any] | None) -> bool:
    """Mark all stored transaction suggestions as stale."""
    refs = iter_transaction_suggestion_refs(ocr_result, include_stale=True)
    mutated = False
    for ref in refs:
        if not ref.get("_stale"):
            ref["_stale"] = True
            mutated = True
    return mutated


def _coerce_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def store_transaction_suggestions(
    ocr_result: dict[str, Any],
    suggestions: list[dict[str, Any]],
    *,
    json_safe: Callable[[Any], Any] | None = None,
) -> None:
    """Persist transaction suggestions into OCR result.

    Stores full metadata in `tax_analysis.items`. Keeps the legacy
    `transaction_suggestion` key only for single-suggestion documents so older
    consumers remain compatible.
    """
    normalized: list[dict[str, Any]] = []
    for suggestion in suggestions:
        if not isinstance(suggestion, dict):
            continue
        payload = dict(suggestion)
        if json_safe is not None:
            payload = json_safe(payload)
        normalized.append(payload)

    if not normalized:
        ocr_result.pop("transaction_suggestion", None)
        ocr_result.pop("tax_analysis", None)
        return

    if len(normalized) == 1:
        ocr_result["transaction_suggestion"] = normalized[0]
    else:
        ocr_result.pop("transaction_suggestion", None)

    ocr_result["tax_analysis"] = {
        "items": normalized,
        "is_split": len(normalized) > 1,
        "total_deductible": sum(
            _coerce_float(s.get("amount"))
            for s in normalized
            if s.get("is_deductible")
        ),
        "total_non_deductible": sum(
            _coerce_float(s.get("amount"))
            for s in normalized
            if not s.get("is_deductible")
        ),
    }
