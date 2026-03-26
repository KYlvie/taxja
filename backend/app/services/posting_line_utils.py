"""Canonical posting-line helpers for transactions and reports."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set

from sqlalchemy.orm import Session
from app.core.transaction_enum_coercion import coerce_expense_category, coerce_income_category
from app.models.transaction import Transaction, TransactionType
from app.models.transaction_line_item import (
    TransactionLineItem,
    LineItemAllocationSource,
    LineItemPostingType,
)
from app.services.field_normalization import (
    normalize_amount,
    normalize_boolean_flag,
    normalize_currency,
    normalize_quantity,
    normalize_semantic_flags,
    normalize_vat_rate,
)


MONEY = Decimal("0.01")
RECONCILIATION_TOLERANCE = Decimal("0.01")


@dataclass(frozen=True)
class PostingRecord:
    """Normalized view of one canonical posting line."""

    transaction: Any
    line_item: Any | None
    type: TransactionType
    posting_type: LineItemPostingType
    amount: Decimal
    quantity: int
    total_amount: Decimal
    income_category: Any = None
    expense_category: Any = None
    category: Optional[str] = None
    is_deductible: bool = False
    document_id: Optional[int] = None
    vat_amount: Decimal = Decimal("0.00")
    vat_recoverable_amount: Decimal = Decimal("0.00")
    property_id: Any = None
    description: str = ""
    transaction_id: Optional[int] = None
    transaction_date: Any = None
    rule_bucket: Optional[str] = None


def quantize_money(value: Decimal | int | float | str | None) -> Decimal:
    """Normalize numeric values to 2dp Decimal."""
    if value is None:
        return Decimal("0.00")
    if isinstance(value, Decimal):
        raw = value
    else:
        normalized = normalize_amount(value)
        raw = normalized if normalized is not None else Decimal(str(value))
    return raw.quantize(MONEY, rounding=ROUND_HALF_UP)


def _normalize_line_quantity(value: Any) -> int:
    quantity = normalize_quantity(value)
    return quantity if quantity is not None else 1


def _normalize_line_vat_rate(value: Any, fallback: Any = None) -> Decimal | None:
    raw = value if value is not None else fallback
    normalized = normalize_vat_rate(raw)
    if normalized is None:
        return None
    return normalized / Decimal("100") if normalized > 1 else normalized


def _resolve_line_amount(raw: Mapping[str, Any], quantity: int) -> Decimal:
    unit_candidates = (
        raw.get("unit_price"),
        raw.get("price"),
        raw.get("unit_amount"),
        raw.get("amount"),
    )
    for candidate in unit_candidates:
        normalized = normalize_amount(candidate)
        if normalized is not None:
            return quantize_money(normalized)

    total_candidates = (
        raw.get("total_price"),
        raw.get("total"),
        raw.get("line_total"),
        raw.get("gross_total"),
        raw.get("net_total"),
    )
    for candidate in total_candidates:
        normalized_total = normalize_amount(candidate)
        if normalized_total is None:
            continue
        if quantity > 1:
            return quantize_money(normalized_total / Decimal(quantity))
        return quantize_money(normalized_total)

    return Decimal("0.00")


def default_posting_type_for_transaction_type(
    transaction_type: TransactionType | str | None,
) -> LineItemPostingType:
    """Map a parent transaction type to the matching mirror posting type."""
    raw = getattr(transaction_type, "value", transaction_type)
    mapping = {
        TransactionType.INCOME.value: LineItemPostingType.INCOME,
        TransactionType.EXPENSE.value: LineItemPostingType.EXPENSE,
        TransactionType.ASSET_ACQUISITION.value: LineItemPostingType.ASSET_ACQUISITION,
        TransactionType.LIABILITY_DRAWDOWN.value: LineItemPostingType.LIABILITY_DRAWDOWN,
        TransactionType.LIABILITY_REPAYMENT.value: LineItemPostingType.LIABILITY_REPAYMENT,
        TransactionType.TAX_PAYMENT.value: LineItemPostingType.TAX_PAYMENT,
        TransactionType.TRANSFER.value: LineItemPostingType.TRANSFER,
    }
    return mapping.get(raw, LineItemPostingType.EXPENSE)


def synthetic_transaction_type_for_posting(
    posting_type: LineItemPostingType | str | None,
) -> TransactionType:
    """Map a posting line back to a transaction-type-like semantic."""
    raw = getattr(posting_type, "value", posting_type)
    if raw in {LineItemPostingType.EXPENSE.value, LineItemPostingType.PRIVATE_USE.value}:
        return TransactionType.EXPENSE
    mapping = {
        LineItemPostingType.INCOME.value: TransactionType.INCOME,
        LineItemPostingType.ASSET_ACQUISITION.value: TransactionType.ASSET_ACQUISITION,
        LineItemPostingType.LIABILITY_DRAWDOWN.value: TransactionType.LIABILITY_DRAWDOWN,
        LineItemPostingType.LIABILITY_REPAYMENT.value: TransactionType.LIABILITY_REPAYMENT,
        LineItemPostingType.TAX_PAYMENT.value: TransactionType.TAX_PAYMENT,
        LineItemPostingType.TRANSFER.value: TransactionType.TRANSFER,
    }
    return mapping.get(raw, TransactionType.EXPENSE)


def coerce_posting_type(
    value: Any,
    *,
    fallback: LineItemPostingType,
) -> LineItemPostingType:
    """Coerce raw posting-type input to the enum with fallback."""
    if value is None:
        return fallback
    if isinstance(value, LineItemPostingType):
        return value
    try:
        return LineItemPostingType(getattr(value, "value", value))
    except ValueError:
        return fallback


def coerce_allocation_source(
    value: Any,
    *,
    fallback: LineItemAllocationSource = LineItemAllocationSource.MANUAL,
) -> LineItemAllocationSource:
    """Coerce raw allocation-source input to the enum with fallback."""
    if value is None:
        return fallback
    if isinstance(value, LineItemAllocationSource):
        return value
    try:
        return LineItemAllocationSource(getattr(value, "value", value))
    except ValueError:
        return fallback


def default_category_token(
    *,
    transaction_type: TransactionType | str | None,
    income_category: Any = None,
    expense_category: Any = None,
) -> Optional[str]:
    """Choose a category token for mirror lines and fallback records."""
    raw_type = getattr(transaction_type, "value", transaction_type)
    if raw_type == TransactionType.INCOME.value and income_category is not None:
        return getattr(income_category, "value", income_category)
    if expense_category is not None:
        return getattr(expense_category, "value", expense_category)
    return None


def build_mirror_line_item_payload(
    *,
    transaction_type: TransactionType | str,
    amount: Decimal | int | float | str,
    description: Optional[str],
    income_category: Any = None,
    expense_category: Any = None,
    is_deductible: bool = False,
    deduction_reason: Optional[str] = None,
    vat_rate: Decimal | None = None,
    vat_amount: Decimal | None = None,
    allocation_source: LineItemAllocationSource = LineItemAllocationSource.MANUAL,
    rule_bucket: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a canonical mirror line from the parent cash event."""
    posting_type = default_posting_type_for_transaction_type(transaction_type)
    category = default_category_token(
        transaction_type=transaction_type,
        income_category=income_category,
        expense_category=expense_category,
    )
    return {
        "description": description or "Transaction",
        "amount": quantize_money(amount),
        "quantity": 1,
        "posting_type": posting_type,
        "allocation_source": allocation_source,
        "category": category,
        "is_deductible": bool(is_deductible) if posting_type == LineItemPostingType.EXPENSE else False,
        "deduction_reason": deduction_reason if posting_type == LineItemPostingType.EXPENSE else None,
        "vat_rate": _normalize_line_vat_rate(vat_rate),
        "vat_amount": quantize_money(vat_amount) if vat_amount is not None else None,
        "vat_recoverable_amount": Decimal("0.00"),
        "rule_bucket": rule_bucket,
        "sort_order": 0,
    }


def normalize_line_item_payloads(
    *,
    transaction_type: TransactionType | str,
    transaction_amount: Decimal | int | float | str,
    description: Optional[str],
    income_category: Any = None,
    expense_category: Any = None,
    is_deductible: bool = False,
    deduction_reason: Optional[str] = None,
    vat_rate: Decimal | None = None,
    vat_amount: Decimal | None = None,
    line_items: Optional[Sequence[Mapping[str, Any]]] = None,
    default_allocation_source: LineItemAllocationSource = LineItemAllocationSource.MANUAL,
) -> List[Dict[str, Any]]:
    """Normalize line-item payloads and ensure at least one canonical line exists."""
    parent_type = (
        transaction_type
        if isinstance(transaction_type, TransactionType)
        else TransactionType(getattr(transaction_type, "value", transaction_type))
    )
    parent_amount = quantize_money(transaction_amount)
    fallback_posting_type = default_posting_type_for_transaction_type(parent_type)
    fallback_category = default_category_token(
        transaction_type=parent_type,
        income_category=income_category,
        expense_category=expense_category,
    )

    if not line_items:
        return [
            build_mirror_line_item_payload(
                transaction_type=parent_type,
                amount=parent_amount,
                description=description,
                income_category=income_category,
                expense_category=expense_category,
                is_deductible=is_deductible,
                deduction_reason=deduction_reason,
                vat_rate=vat_rate,
                vat_amount=vat_amount,
                allocation_source=default_allocation_source,
            )
        ]

    normalized: List[Dict[str, Any]] = []
    for idx, raw in enumerate(line_items):
        quantity = _normalize_line_quantity(raw.get("quantity", 1))
        posting_type = coerce_posting_type(
            raw.get("posting_type"),
            fallback=fallback_posting_type,
        )
        category = raw.get("category")
        if not category and posting_type in {
            LineItemPostingType.INCOME,
            LineItemPostingType.EXPENSE,
            LineItemPostingType.PRIVATE_USE,
        }:
            category = fallback_category

        deductible_flag = normalize_boolean_flag(raw.get("is_deductible"))
        deductible = deductible_flag if deductible_flag is not None else bool(raw.get("is_deductible", is_deductible))
        if posting_type != LineItemPostingType.EXPENSE:
            deductible = False

        normalized.append(
            {
                "description": (raw.get("description") or description or f"Line item {idx + 1}").strip(),
                "amount": _resolve_line_amount(raw, quantity),
                "quantity": quantity,
                "posting_type": posting_type,
                "allocation_source": coerce_allocation_source(
                    raw.get("allocation_source"),
                    fallback=default_allocation_source,
                ),
                "category": category,
                "is_deductible": deductible,
                "deduction_reason": (
                    raw.get("deduction_reason")
                    if posting_type == LineItemPostingType.EXPENSE
                    else None
                ),
                "vat_rate": _normalize_line_vat_rate(raw.get("vat_rate"), vat_rate),
                "vat_amount": (
                    quantize_money(raw.get("vat_amount"))
                    if raw.get("vat_amount") is not None
                    else None
                ),
                "vat_recoverable_amount": quantize_money(raw.get("vat_recoverable_amount")),
                "rule_bucket": raw.get("rule_bucket"),
                "currency": (
                    normalize_currency(raw.get("currency"))
                    or normalize_currency(raw.get("amount"))
                    or normalize_currency(raw.get("total_price"))
                    or normalize_currency(raw.get("total"))
                ),
                "semantic_flags": normalize_semantic_flags(
                    raw.get("semantic_flags"),
                    raw.get("description"),
                    raw.get("status"),
                    raw.get("note"),
                ),
                "sort_order": int(raw.get("sort_order", idx) or idx),
            }
        )

    validate_reconciliation(parent_amount, normalized)
    return normalized


def validate_reconciliation(
    transaction_amount: Decimal | int | float | str,
    line_items: Sequence[Mapping[str, Any]],
) -> None:
    """Validate the canonical reconciliation formula against the parent amount."""
    parent_amount = quantize_money(transaction_amount)
    reconstructed = Decimal("0.00")
    for line in line_items:
        reconstructed += (
            quantize_money(line.get("amount")) * _normalize_line_quantity(line.get("quantity", 1))
        ) + quantize_money(line.get("vat_recoverable_amount"))
    if abs(parent_amount - reconstructed) > RECONCILIATION_TOLERANCE:
        raise ValueError(
            "Line items do not reconcile with the parent amount. "
            f"Expected {parent_amount}, reconstructed {reconstructed}."
        )


def derive_parent_deductibility(
    line_items: Sequence[Mapping[str, Any]],
) -> tuple[bool, Optional[str]]:
    """Derive parent compatibility deductibility fields from canonical lines."""
    deductible_lines = [
        line
        for line in line_items
        if line.get("posting_type") == LineItemPostingType.EXPENSE and line.get("is_deductible")
    ]
    if not deductible_lines:
        return False, None

    mixed = any(
        line.get("posting_type") in {LineItemPostingType.PRIVATE_USE, LineItemPostingType.EXPENSE}
        and not line.get("is_deductible")
        for line in line_items
    )
    if mixed:
        return True, "Mixed deductibility confirmed at line-item level"

    reason = next(
        (
            line.get("deduction_reason")
            for line in deductible_lines
            if line.get("deduction_reason")
        ),
        None,
    )
    return True, reason


def replace_transaction_line_items(
    db: Session,
    transaction: Any,
    normalized_line_items: Sequence[Mapping[str, Any]],
) -> None:
    """Replace all stored line items for a transaction with canonical rows."""
    db.query(TransactionLineItem).filter(
        TransactionLineItem.transaction_id == transaction.id,
    ).delete()
    db.flush()

    for idx, li_data in enumerate(normalized_line_items):
        db.add(
            TransactionLineItem(
                transaction_id=transaction.id,
                description=li_data["description"],
                amount=li_data["amount"],
                quantity=li_data.get("quantity", 1),
                posting_type=li_data["posting_type"],
                allocation_source=li_data["allocation_source"],
                category=li_data.get("category"),
                is_deductible=li_data.get("is_deductible", False),
                deduction_reason=li_data.get("deduction_reason"),
                vat_rate=li_data.get("vat_rate"),
                vat_amount=li_data.get("vat_amount"),
                vat_recoverable_amount=li_data.get("vat_recoverable_amount", Decimal("0.00")),
                rule_bucket=li_data.get("rule_bucket"),
                sort_order=li_data.get("sort_order", idx),
            )
        )

    is_deductible, deduction_reason = derive_parent_deductibility(normalized_line_items)
    transaction.is_deductible = is_deductible
    transaction.deduction_reason = deduction_reason


def transaction_has_deductible_expense(transaction: Any) -> bool:
    """Whether a transaction contains any deductible expense postings."""
    if not getattr(transaction, "line_items", None):
        return (
            getattr(transaction, "type", None) == TransactionType.EXPENSE
            and bool(getattr(transaction, "is_deductible", False))
        )
    return any(
        record.posting_type == LineItemPostingType.EXPENSE and record.is_deductible
        for record in iter_transaction_posting_records(transaction)
    )


def recoverable_input_vat_for_transaction(transaction: Any) -> Decimal:
    """Resolve deductible input VAT for VAT reports and summaries.

    Canonical line items can carry partial or zero recoverable VAT even when the
    parent cash event still stores the gross invoice VAT. For legacy expense
    rows without explicit recoverable VAT, we keep the historical parent-level
    fallback so existing U1/UVA numbers do not suddenly drop to zero.
    """

    def _safe_money(value: Any) -> Decimal:
        try:
            return quantize_money(value)
        except Exception:
            return Decimal("0.00")

    transaction_type = getattr(transaction, "type", None)
    canonical_total = _safe_money(
        getattr(transaction, "vat_recoverable_amount_total", None),
    )

    if transaction_type == TransactionType.ASSET_ACQUISITION:
        return canonical_total

    if canonical_total > Decimal("0.00"):
        return canonical_total

    if transaction_type == TransactionType.EXPENSE:
        return _safe_money(getattr(transaction, "vat_amount", None))

    return Decimal("0.00")


def iter_transaction_posting_records(
    transaction: Any,
    *,
    include_private_use: bool = True,
) -> Iterable[PostingRecord]:
    """Yield normalized posting records for a transaction."""
    parent_type = getattr(transaction, "type", TransactionType.EXPENSE) or TransactionType.EXPENSE
    fallback_posting = default_posting_type_for_transaction_type(parent_type)

    raw_line_items = getattr(transaction, "line_items", None)
    try:
        line_items = list(raw_line_items or [])
    except TypeError:
        line_items = []
    if not line_items:
        posting_type = fallback_posting
        if posting_type == LineItemPostingType.PRIVATE_USE and not include_private_use:
            return
        amount = quantize_money(getattr(transaction, "amount", None))
        category = default_category_token(
            transaction_type=parent_type,
            income_category=getattr(transaction, "income_category", None),
            expense_category=getattr(transaction, "expense_category", None),
        )
        yield PostingRecord(
            transaction=transaction,
            line_item=None,
            type=synthetic_transaction_type_for_posting(posting_type),
            posting_type=posting_type,
            amount=amount,
            quantity=1,
            total_amount=amount,
            income_category=getattr(transaction, "income_category", None),
            expense_category=getattr(transaction, "expense_category", None),
            category=category,
            is_deductible=bool(getattr(transaction, "is_deductible", False))
            if posting_type == LineItemPostingType.EXPENSE
            else False,
            document_id=getattr(transaction, "document_id", None),
            vat_amount=quantize_money(getattr(transaction, "vat_amount", None)),
            vat_recoverable_amount=Decimal("0.00"),
            property_id=getattr(transaction, "property_id", None),
            description=getattr(transaction, "description", "") or "",
            transaction_id=getattr(transaction, "id", None),
            transaction_date=getattr(transaction, "transaction_date", None),
        )
        return

    for line_item in line_items:
        posting_type = coerce_posting_type(
            getattr(line_item, "posting_type", None),
            fallback=fallback_posting,
        )
        if posting_type == LineItemPostingType.PRIVATE_USE and not include_private_use:
            continue

        amount = quantize_money(getattr(line_item, "amount", None))
        quantity = int(getattr(line_item, "quantity", 1) or 1)
        category = getattr(line_item, "category", None) or default_category_token(
            transaction_type=parent_type,
            income_category=getattr(transaction, "income_category", None),
            expense_category=getattr(transaction, "expense_category", None),
        )
        category_token = getattr(category, "value", category)
        income_category = (
            coerce_income_category(category_token)
            if posting_type == LineItemPostingType.INCOME
            else None
        )
        expense_category = (
            coerce_expense_category(category_token)
            if posting_type in {LineItemPostingType.EXPENSE, LineItemPostingType.PRIVATE_USE}
            else None
        )
        yield PostingRecord(
            transaction=transaction,
            line_item=line_item,
            type=synthetic_transaction_type_for_posting(posting_type),
            posting_type=posting_type,
            amount=amount,
            quantity=quantity,
            total_amount=amount * quantity,
            income_category=income_category or getattr(transaction, "income_category", None),
            expense_category=expense_category or getattr(transaction, "expense_category", None),
            category=category_token,
            is_deductible=bool(getattr(line_item, "is_deductible", False))
            if posting_type == LineItemPostingType.EXPENSE
            else False,
            document_id=getattr(transaction, "document_id", None),
            vat_amount=quantize_money(getattr(line_item, "vat_amount", None)),
            vat_recoverable_amount=quantize_money(getattr(line_item, "vat_recoverable_amount", None)),
            property_id=getattr(transaction, "property_id", None),
            description=getattr(line_item, "description", None) or getattr(transaction, "description", "") or "",
            transaction_id=getattr(transaction, "id", None),
            transaction_date=getattr(transaction, "transaction_date", None),
            rule_bucket=getattr(line_item, "rule_bucket", None),
        )


def iter_posting_records(
    transactions: Iterable[Any],
    *,
    include_private_use: bool = True,
) -> Iterable[PostingRecord]:
    """Yield normalized posting records across multiple transactions."""
    for transaction in transactions:
        yield from iter_transaction_posting_records(
            transaction,
            include_private_use=include_private_use,
        )


def sum_postings(
    transactions: Iterable[Any],
    *,
    posting_types: Optional[Set[LineItemPostingType | str]] = None,
    deductible_only: bool = False,
    categories: Optional[Set[str]] = None,
    property_id: Any = None,
    include_private_use: bool = True,
) -> Decimal:
    """Sum normalized posting totals across transactions."""
    allowed_posting_types = {
        coerce_posting_type(value, fallback=LineItemPostingType.EXPENSE)
        for value in posting_types
    } if posting_types is not None else None
    total = Decimal("0.00")
    for record in iter_posting_records(
        transactions,
        include_private_use=include_private_use,
    ):
        if allowed_posting_types is not None and record.posting_type not in allowed_posting_types:
            continue
        if deductible_only and not record.is_deductible:
            continue
        if categories is not None and (record.category or "other") not in categories:
            continue
        if property_id is not None and record.property_id != property_id:
            continue
        total += record.total_amount
    return total


def sum_postings_by_category(
    transactions: Iterable[Any],
    *,
    posting_types: Optional[Set[LineItemPostingType | str]] = None,
    deductible_only: bool = False,
    categories: Optional[Set[str]] = None,
    property_id: Any = None,
    include_private_use: bool = False,
) -> Dict[str, Decimal]:
    """Aggregate posting totals by category token."""
    allowed_posting_types = {
        coerce_posting_type(value, fallback=LineItemPostingType.EXPENSE)
        for value in posting_types
    } if posting_types is not None else None
    result: Dict[str, Decimal] = {}
    for record in iter_posting_records(
        transactions,
        include_private_use=include_private_use,
    ):
        if allowed_posting_types is not None and record.posting_type not in allowed_posting_types:
            continue
        if deductible_only and not record.is_deductible:
            continue
        if property_id is not None and record.property_id != property_id:
            continue
        category = record.category or "other"
        if categories is not None and category not in categories:
            continue
        result[category] = result.get(category, Decimal("0.00")) + record.total_amount
    return result


def total_vat_recoverable(
    transactions: Iterable[Any],
    *,
    posting_types: Optional[Set[LineItemPostingType | str]] = None,
) -> Decimal:
    """Sum recoverable VAT carried on posting lines."""
    allowed_posting_types = {
        coerce_posting_type(value, fallback=LineItemPostingType.EXPENSE)
        for value in posting_types
    } if posting_types is not None else None
    total = Decimal("0.00")
    for record in iter_posting_records(transactions):
        if allowed_posting_types is not None and record.posting_type not in allowed_posting_types:
            continue
        total += record.vat_recoverable_amount
    return total
