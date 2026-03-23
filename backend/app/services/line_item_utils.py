"""Backward-compatible wrappers around canonical posting-line aggregation."""
from decimal import Decimal
from typing import Dict, List, Optional, Set

from app.models.transaction import Transaction, ExpenseCategory
from app.models.transaction_line_item import LineItemPostingType
from app.services.posting_line_utils import sum_postings, sum_postings_by_category


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
    cat_values: Optional[Set[str]] = (
        {c.value if hasattr(c, "value") else str(c) for c in categories}
        if categories is not None
        else None
    )
    return sum_postings_by_category(
        transactions,
        posting_types={LineItemPostingType.EXPENSE},
        deductible_only=True,
        categories=cat_values,
        property_id=property_id,
    )


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
    cat_values: Optional[Set[str]] = (
        {c.value if hasattr(c, "value") else str(c) for c in categories}
        if categories is not None
        else None
    )
    return sum_postings(
        transactions,
        posting_types={LineItemPostingType.EXPENSE},
        deductible_only=True,
        categories=cat_values,
        property_id=property_id,
    )


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
    cat_values: Optional[Set[str]] = (
        {c.value if hasattr(c, "value") else str(c) for c in categories}
        if categories is not None
        else None
    )
    return sum_postings_by_category(
        transactions,
        posting_types={LineItemPostingType.EXPENSE},
        deductible_only=deductible_only,
        categories=cat_values,
    )
