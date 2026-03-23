"""Helpers for selecting and valuing transactions in financial reports."""

from decimal import Decimal

from app.models.recurring_transaction import RecurringTransactionType
from app.models.transaction import TransactionType
from app.models.transaction_line_item import LineItemPostingType
from app.models.user import UserType
from app.services.posting_line_utils import iter_transaction_posting_records


_EA_USER_TYPES = {
    UserType.EMPLOYEE,
    UserType.SELF_EMPLOYED,
    UserType.LANDLORD,
    UserType.MIXED,
}

_BILANZ_RELEVANT_TYPES = {
    TransactionType.INCOME,
    TransactionType.EXPENSE,
    TransactionType.ASSET_ACQUISITION,
    TransactionType.LIABILITY_DRAWDOWN,
    TransactionType.LIABILITY_REPAYMENT,
    TransactionType.TAX_PAYMENT,
}

_SALDENLISTE_GMBH_TYPES = {
    TransactionType.INCOME,
    TransactionType.EXPENSE,
    TransactionType.ASSET_ACQUISITION,
    TransactionType.LIABILITY_DRAWDOWN,
    TransactionType.LIABILITY_REPAYMENT,
}


def is_legacy_loan_repayment_expense(transaction) -> bool:
    """Whether an expense transaction came from the old loan repayment flow."""
    if transaction.type != TransactionType.EXPENSE:
        return False

    recurring = getattr(transaction, "source_recurring", None)
    recurring_type = getattr(recurring, "recurring_type", None)
    if recurring_type == RecurringTransactionType.LOAN_REPAYMENT:
        return True
    if getattr(recurring_type, "value", None) == RecurringTransactionType.LOAN_REPAYMENT.value:
        return True
    return False


def _posting_types_for_reporting(transaction) -> set[LineItemPostingType]:
    posting_types = {
        record.posting_type
        for record in iter_transaction_posting_records(
            transaction,
            include_private_use=False,
        )
    }
    if posting_types:
        return posting_types

    transaction_type = getattr(transaction, "type", None)
    mapping = {
        TransactionType.INCOME: LineItemPostingType.INCOME,
        TransactionType.EXPENSE: LineItemPostingType.EXPENSE,
        TransactionType.ASSET_ACQUISITION: LineItemPostingType.ASSET_ACQUISITION,
        TransactionType.LIABILITY_DRAWDOWN: LineItemPostingType.LIABILITY_DRAWDOWN,
        TransactionType.LIABILITY_REPAYMENT: LineItemPostingType.LIABILITY_REPAYMENT,
        TransactionType.TAX_PAYMENT: LineItemPostingType.TAX_PAYMENT,
        TransactionType.TRANSFER: LineItemPostingType.TRANSFER,
    }
    if transaction_type in mapping:
        return {mapping[transaction_type]}
    return set()


def should_include_in_ea_report(transaction) -> bool:
    """E/A reports only include income/expense rows and exclude legacy loan repayments."""
    if is_legacy_loan_repayment_expense(transaction):
        return False
    posting_types = _posting_types_for_reporting(transaction)
    return bool(
        posting_types.intersection(
            {LineItemPostingType.INCOME, LineItemPostingType.EXPENSE}
        )
    )


def requires_profit_loss_category(transaction) -> bool:
    """Whether a transaction should carry an income/expense category for tax reporting."""
    return should_include_in_ea_report(transaction)


def should_include_in_bilanz_report(transaction) -> bool:
    """Bilanz/GuV keeps operational and balance-sheet events, excluding legacy loan repayments."""
    if is_legacy_loan_repayment_expense(transaction):
        return False
    posting_types = _posting_types_for_reporting(transaction)
    return bool(
        posting_types.intersection(
            {
                LineItemPostingType.INCOME,
                LineItemPostingType.EXPENSE,
                LineItemPostingType.ASSET_ACQUISITION,
                LineItemPostingType.LIABILITY_DRAWDOWN,
                LineItemPostingType.LIABILITY_REPAYMENT,
                LineItemPostingType.TAX_PAYMENT,
            }
        )
    )


def should_include_in_saldenliste(transaction, user_type: UserType) -> bool:
    """Saldenliste scope depends on the user's accounting model."""
    if is_legacy_loan_repayment_expense(transaction):
        return False
    posting_types = _posting_types_for_reporting(transaction)
    if user_type in _EA_USER_TYPES:
        return bool(
            posting_types.intersection(
                {LineItemPostingType.INCOME, LineItemPostingType.EXPENSE}
            )
        )
    return bool(
        posting_types.intersection(
            {
                LineItemPostingType.INCOME,
                LineItemPostingType.EXPENSE,
                LineItemPostingType.ASSET_ACQUISITION,
                LineItemPostingType.LIABILITY_DRAWDOWN,
                LineItemPostingType.LIABILITY_REPAYMENT,
            }
        )
    )


def cash_balance_delta(transaction) -> Decimal:
    """Return the signed cash impact of a transaction for balance-sheet estimates."""
    if is_legacy_loan_repayment_expense(transaction):
        return Decimal("0")

    amount = transaction.amount or Decimal("0")
    if transaction.type in {TransactionType.INCOME, TransactionType.LIABILITY_DRAWDOWN}:
        return amount
    if transaction.type in {
        TransactionType.EXPENSE,
        TransactionType.ASSET_ACQUISITION,
        TransactionType.LIABILITY_REPAYMENT,
        TransactionType.TAX_PAYMENT,
    }:
        return -amount
    return Decimal("0")


def saldenliste_signed_amount(transaction) -> Decimal:
    """Return the signed amount to post in Saldenliste accounts."""
    amount = transaction.amount or Decimal("0")
    if transaction.type == TransactionType.LIABILITY_REPAYMENT:
        return -amount
    return amount
