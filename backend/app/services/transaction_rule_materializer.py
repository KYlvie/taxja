"""Rule-driven canonical line-item materialization for transactions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.models.transaction import ExpenseCategory, Transaction, TransactionType
from app.models.transaction_line_item import (
    LineItemAllocationSource,
    LineItemPostingType,
)
from app.models.user import User, UserType
from app.services.business_deductibility_rules import get_business_type_override
from app.services.posting_line_utils import (
    iter_transaction_posting_records,
    normalize_line_item_payloads,
    quantize_money,
    replace_transaction_line_items,
)


HOME_OFFICE_RULE_BUCKET = "home_office_annual_cap"
HOME_OFFICE_ANNUAL_CAP = Decimal("300.00")


@dataclass(frozen=True)
class TransactionRuleContext:
    """Recalculation scope for a shared allocation rule."""

    tax_year: int
    rule_bucket: str


def _user_type_value(user: User) -> str:
    return getattr(getattr(user, "user_type", None), "value", getattr(user, "user_type", "")) or ""


def _expense_category_value(transaction: Transaction) -> Optional[str]:
    category = getattr(transaction, "expense_category", None)
    return getattr(category, "value", category)


def _split_vat_amount(
    total_vat_amount: Decimal | None,
    first_amount: Decimal,
    total_amount: Decimal,
) -> tuple[Optional[Decimal], Optional[Decimal]]:
    if total_vat_amount is None:
        return None, None
    total_vat = quantize_money(total_vat_amount)
    if total_amount <= Decimal("0.00"):
        return total_vat, Decimal("0.00")
    first_share = quantize_money((total_vat * first_amount) / total_amount)
    second_share = total_vat - first_share
    return first_share, second_share


def _build_split_line_items(
    transaction: Transaction,
    *,
    deductible_amount: Decimal,
    private_amount: Decimal,
    allocation_source: LineItemAllocationSource,
    deduction_reason: Optional[str],
    rule_bucket: Optional[str] = None,
) -> list[dict]:
    total_amount = quantize_money(transaction.amount)
    deductible_amount = quantize_money(deductible_amount)
    private_amount = quantize_money(private_amount)
    expense_category = _expense_category_value(transaction)
    deductible_vat, private_vat = _split_vat_amount(
        getattr(transaction, "vat_amount", None),
        deductible_amount,
        total_amount,
    )

    line_items: list[dict] = []
    description = getattr(transaction, "description", None) or "Transaction"

    if deductible_amount > Decimal("0.00"):
        line_items.append(
            {
                "description": (
                    description
                    if private_amount <= Decimal("0.00")
                    else f"{description} (deductible portion)"
                ),
                "amount": deductible_amount,
                "quantity": 1,
                "posting_type": LineItemPostingType.EXPENSE,
                "allocation_source": allocation_source,
                "category": expense_category,
                "is_deductible": True,
                "deduction_reason": deduction_reason,
                "vat_rate": getattr(transaction, "vat_rate", None),
                "vat_amount": deductible_vat,
                "vat_recoverable_amount": Decimal("0.00"),
                "rule_bucket": rule_bucket,
                "sort_order": 0,
            }
        )

    if private_amount > Decimal("0.00"):
        line_items.append(
            {
                "description": (
                    description
                    if deductible_amount <= Decimal("0.00")
                    else f"{description} (private portion)"
                ),
                "amount": private_amount,
                "quantity": 1,
                "posting_type": LineItemPostingType.PRIVATE_USE,
                "allocation_source": allocation_source,
                "category": expense_category,
                "is_deductible": False,
                "deduction_reason": None,
                "vat_rate": getattr(transaction, "vat_rate", None),
                "vat_amount": private_vat,
                "vat_recoverable_amount": Decimal("0.00"),
                "rule_bucket": rule_bucket,
                "sort_order": 1 if deductible_amount > Decimal("0.00") else 0,
            }
        )

    return normalize_line_item_payloads(
        transaction_type=transaction.type,
        transaction_amount=transaction.amount,
        description=description,
        income_category=transaction.income_category,
        expense_category=transaction.expense_category,
        is_deductible=bool(transaction.is_deductible),
        deduction_reason=deduction_reason,
        vat_rate=getattr(transaction, "vat_rate", None),
        vat_amount=getattr(transaction, "vat_amount", None),
        line_items=line_items,
        default_allocation_source=allocation_source,
    )


def get_transaction_rule_context(
    transaction: Transaction,
    user: User,
) -> Optional[TransactionRuleContext]:
    """Return the shared-rule recalculation scope for this transaction, if any."""
    if getattr(transaction, "type", None) != TransactionType.EXPENSE:
        return None
    if not getattr(transaction, "transaction_date", None):
        return None

    category = _expense_category_value(transaction)
    if (
        _user_type_value(user) == UserType.EMPLOYEE.value
        and category == ExpenseCategory.HOME_OFFICE.value
    ):
        return TransactionRuleContext(
            tax_year=transaction.transaction_date.year,
            rule_bucket=HOME_OFFICE_RULE_BUCKET,
        )
    return None


def build_auto_materialized_line_items(
    transaction: Transaction,
    user: User,
) -> tuple[Optional[list[dict]], Optional[TransactionRuleContext]]:
    """Build automatic rule-based line items for transactions without explicit splits."""
    if getattr(transaction, "type", None) != TransactionType.EXPENSE:
        return None, None

    expense_category = _expense_category_value(transaction)
    if not expense_category:
        return None, None

    rule_context = get_transaction_rule_context(transaction, user)
    if rule_context is not None:
        return None, rule_context

    override = get_business_type_override(
        getattr(user, "business_type", None),
        expense_category,
        business_industry=getattr(user, "business_industry", None),
    )
    deductible_pct = override.get("deductible_pct") if override else None
    if (
        override
        and override.get("is_deductible") is True
        and deductible_pct is not None
        and Decimal(str(deductible_pct)) > Decimal("0.00")
        and Decimal(str(deductible_pct)) < Decimal("1.00")
    ):
        total_amount = quantize_money(transaction.amount)
        deductible_amount = quantize_money(total_amount * Decimal(str(deductible_pct)))
        private_amount = total_amount - deductible_amount
        return (
            _build_split_line_items(
                transaction,
                deductible_amount=deductible_amount,
                private_amount=private_amount,
                allocation_source=LineItemAllocationSource.PERCENTAGE_RULE,
                deduction_reason=override.get("reason") or getattr(transaction, "deduction_reason", None),
            ),
            None,
        )

    return None, None


def _is_cap_rule_auto_managed(transaction: Transaction) -> bool:
    line_items = list(getattr(transaction, "line_items", []) or [])
    if not line_items or len(line_items) <= 1:
        return True
    return all(
        getattr(li, "allocation_source", None) == LineItemAllocationSource.CAP_RULE
        for li in line_items
    )


def _current_deductible_expense_total(transaction: Transaction) -> Decimal:
    total = Decimal("0.00")
    for record in iter_transaction_posting_records(transaction):
        if record.posting_type == LineItemPostingType.EXPENSE and record.is_deductible:
            total += record.total_amount
    return quantize_money(total)


def recompute_rule_bucket(
    db: Session,
    user_id: int,
    rule_context: TransactionRuleContext,
) -> None:
    """Recompute all auto-managed transactions inside one shared yearly bucket."""
    if rule_context.rule_bucket != HOME_OFFICE_RULE_BUCKET:
        return

    start_date = date(rule_context.tax_year, 1, 1)
    end_date = date(rule_context.tax_year, 12, 31)
    remaining_cap = HOME_OFFICE_ANNUAL_CAP

    transactions = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == user_id,
            Transaction.type == TransactionType.EXPENSE,
            Transaction.expense_category == ExpenseCategory.HOME_OFFICE,
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date <= end_date,
        )
        .order_by(Transaction.transaction_date.asc(), Transaction.id.asc())
        .all()
    )

    for transaction in transactions:
        total_amount = quantize_money(transaction.amount)
        if _is_cap_rule_auto_managed(transaction):
            deductible_amount = min(total_amount, remaining_cap)
            private_amount = total_amount - deductible_amount
            normalized_line_items = _build_split_line_items(
                transaction,
                deductible_amount=deductible_amount,
                private_amount=private_amount,
                allocation_source=LineItemAllocationSource.CAP_RULE,
                deduction_reason=(
                    getattr(transaction, "deduction_reason", None)
                    or "Home-office-Pauschale up to €300/year"
                ),
                rule_bucket=HOME_OFFICE_RULE_BUCKET,
            )
            replace_transaction_line_items(db, transaction, normalized_line_items)
            consumed = deductible_amount
        else:
            consumed = min(total_amount, _current_deductible_expense_total(transaction))

        remaining_cap = max(Decimal("0.00"), remaining_cap - consumed)
