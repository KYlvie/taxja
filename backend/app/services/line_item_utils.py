"""Shared utilities for line-item-aware transaction aggregation.

When a transaction has line_items, we use per-item category and deductibility
instead of the whole-transaction amount. This ensures a Billa receipt with
€15 office supplies + €10 groceries correctly reports €15 under office_supplies
rather than €25 under whichever category the transaction-level field holds.

For transactions WITHOUT line items, we fall back to the legacy behavior:
transaction.amount + transaction.expense_category + transaction.is_deductible.
"""
from decimal import Decimal
from typing import Dict, List, Optional, Set

from app.models.transaction import Transaction, TransactionType, ExpenseCategory


def sum_deductible_by_category(
    transactions: List[Transaction],
    categories: Optional[List[ExpenseCategory]] = None,
    property_id=None,
) -> Dict[str, Decimal]:
    """Aggregate deductible amounts grouped by category using line items.

    Args:
        transactions: List of Transaction objects (should be expenses).
        categories: If provided, only include these expense categories.
                    Applies to both transaction-level and line-item-level categories.
        property_id: If provided, only include transactions for this property.

    Returns:
        Dict mapping category string → total deductible Decimal amount.
        e.g. {"office_supplies": Decimal("30.00"), "cleaning": Decimal("5.00")}
    """
    cat_values: Optional[Set[str]] = None
    if categories is not None:
        cat_values = {c.value if hasattr(c, "value") else str(c) for c in categories}

    result: Dict[str, Decimal] = {}

    for t in transactions:
        if t.type != TransactionType.EXPENSE:
            continue
        if property_id is not None and t.property_id != property_id:
            continue

        # Use the line-item-aware property from Transaction model
        items_by_cat = t.deductible_items_by_category  # dict[str, Decimal]

        for cat, amount in items_by_cat.items():
            if cat_values is not None and cat not in cat_values:
                continue
            result[cat] = result.get(cat, Decimal("0")) + amount

    return result


def sum_deductible_expenses(
    transactions: List[Transaction],
    categories: Optional[List[ExpenseCategory]] = None,
    property_id=None,
) -> Decimal:
    """Sum total deductible expense amount using line items.

    This replaces the old pattern of:
        sum(t.amount for t in txns if t.is_deductible)

    With line-item awareness:
        sum of deductible line item amounts (or full amount if no line items).
    """
    by_cat = sum_deductible_by_category(transactions, categories, property_id)
    return sum(by_cat.values(), Decimal("0"))


def sum_expenses_by_category(
    transactions: List[Transaction],
    categories: Optional[List[ExpenseCategory]] = None,
    deductible_only: bool = False,
) -> Dict[str, Decimal]:
    """Aggregate ALL expense amounts grouped by category using line items.

    Unlike sum_deductible_by_category, this includes non-deductible items too
    (unless deductible_only=True).

    For transactions with line items: each item contributes to its own category.
    For transactions without line items: the whole amount goes to expense_category.
    """
    cat_values: Optional[Set[str]] = None
    if categories is not None:
        cat_values = {c.value if hasattr(c, "value") else str(c) for c in categories}

    result: Dict[str, Decimal] = {}

    for t in transactions:
        if t.type != TransactionType.EXPENSE:
            continue

        if t.has_line_items:
            for li in t.line_items:
                if deductible_only and not li.is_deductible:
                    continue
                cat = li.category or "other"
                if cat_values is not None and cat not in cat_values:
                    continue
                amt = li.amount * li.quantity
                result[cat] = result.get(cat, Decimal("0")) + amt
        else:
            if deductible_only and not t.is_deductible:
                continue
            cat = (
                t.expense_category.value
                if t.expense_category
                else "other"
            )
            if cat_values is not None and cat not in cat_values:
                continue
            result[cat] = result.get(cat, Decimal("0")) + (t.amount or Decimal("0"))

    return result
