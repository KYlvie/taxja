"""Unit tests for shared transaction enum normalization helpers."""
from app.core.transaction_enum_coercion import (
    coerce_expense_category,
    coerce_income_category,
    coerce_transaction_type,
)
from app.models.transaction import ExpenseCategory, IncomeCategory, TransactionType


def test_coerce_transaction_type_accepts_value_name_and_enum_instance():
    assert coerce_transaction_type("expense") == TransactionType.EXPENSE
    assert coerce_transaction_type("EXPENSE") == TransactionType.EXPENSE
    assert coerce_transaction_type("LIABILITY_REPAYMENT") == TransactionType.LIABILITY_REPAYMENT
    assert coerce_transaction_type("liability-repayment") == TransactionType.LIABILITY_REPAYMENT
    assert coerce_transaction_type(TransactionType.INCOME) == TransactionType.INCOME


def test_coerce_categories_accept_common_variants():
    assert coerce_expense_category("MAINTENANCE") == ExpenseCategory.MAINTENANCE
    assert coerce_expense_category("home office") == ExpenseCategory.HOME_OFFICE
    assert coerce_expense_category("professional-services") == ExpenseCategory.PROFESSIONAL_SERVICES
    assert coerce_income_category("OTHER_INCOME") == IncomeCategory.OTHER_INCOME
    assert coerce_income_category("self employment") == IncomeCategory.SELF_EMPLOYMENT


def test_coerce_category_returns_default_for_unknown_values():
    assert coerce_expense_category("NOT_A_REAL_CATEGORY", default=ExpenseCategory.OTHER) == ExpenseCategory.OTHER
    assert coerce_income_category("NOT_A_REAL_CATEGORY", default=IncomeCategory.OTHER_INCOME) == IncomeCategory.OTHER_INCOME
