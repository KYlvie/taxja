"""Helpers for materializing a single authoritative document transaction type."""

from __future__ import annotations

from typing import Any, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.transaction_enum_coercion import coerce_transaction_type
from app.models.document import Document
from app.models.transaction import Transaction
from app.services.document_transaction_suggestion_store import (
    iter_transaction_suggestion_refs,
)


def _normalize_transaction_type(value: Any) -> Optional[str]:
    normalized = coerce_transaction_type(value, default=None)
    return normalized.value if normalized is not None else None


def resolve_final_transaction_type(
    *,
    document: Optional[Document] = None,
    ocr_result: Optional[dict[str, Any]] = None,
    db: Optional[Session] = None,
    transaction: Optional[Transaction] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """Resolve the authoritative transaction type for a document.

    Precedence:
    1. Real linked transaction type
    2. Stored transaction suggestion type
    3. Legacy OCR transaction-type fields
    4. Early document direction fields
    """

    payload = ocr_result if isinstance(ocr_result, dict) else {}

    effective_transaction = transaction
    if (
        effective_transaction is None
        and document is not None
        and getattr(document, "transaction_id", None)
        and db is not None
    ):
        effective_transaction = (
            db.query(Transaction)
            .filter(Transaction.id == document.transaction_id)
            .first()
        )

    if effective_transaction is not None:
        resolved = _normalize_transaction_type(effective_transaction.type)
        if resolved:
            return resolved, "linked_transaction"

    direct_suggestion = payload.get("transaction_suggestion")
    if isinstance(direct_suggestion, dict) and not direct_suggestion.get("_stale"):
        resolved = _normalize_transaction_type(
            direct_suggestion.get("final_transaction_type")
            or direct_suggestion.get("transaction_type")
        )
        if resolved:
            return resolved, "transaction_suggestion"

    suggestion_refs = iter_transaction_suggestion_refs(payload, include_stale=False)
    suggestion_types = {
        normalized
        for normalized in (
            _normalize_transaction_type(ref.get("transaction_type"))
            for ref in suggestion_refs
        )
        if normalized
    }
    if len(suggestion_types) == 1:
        return next(iter(suggestion_types)), "transaction_suggestion"

    for key in (
        "final_transaction_type",
        "_transaction_type",
        "transaction_type",
        "document_transaction_direction",
        "transaction_direction",
    ):
        resolved = _normalize_transaction_type(payload.get(key))
        if resolved:
            return resolved, key

    return None, None


def materialize_final_transaction_type(
    *,
    document: Optional[Document] = None,
    ocr_result: Optional[dict[str, Any]] = None,
    db: Optional[Session] = None,
    transaction: Optional[Transaction] = None,
) -> Optional[str]:
    """Write the authoritative transaction type into OCR metadata."""

    payload = ocr_result if isinstance(ocr_result, dict) else {}
    resolved, source = resolve_final_transaction_type(
        document=document,
        ocr_result=payload,
        db=db,
        transaction=transaction,
    )

    if resolved:
        payload["final_transaction_type"] = resolved
        payload["final_transaction_type_source"] = source
    else:
        payload.pop("final_transaction_type", None)
        payload.pop("final_transaction_type_source", None)

    return resolved
