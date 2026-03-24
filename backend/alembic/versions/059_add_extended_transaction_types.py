"""Add extended transaction types and relax recurring transaction type constraint.

Revision ID: 059_extended_txn_types
Revises: 058_onboarding_dismiss
Create Date: 2026-03-21
"""

from alembic import op


revision = "059_extended_txn_types"
down_revision = "058_onboarding_dismiss"
branch_labels = None
depends_on = None


TRANSACTIONTYPE_VALUES = [
    "ASSET_ACQUISITION",
    "LIABILITY_DRAWDOWN",
    "LIABILITY_REPAYMENT",
    "TAX_PAYMENT",
    "TRANSFER",
]

RECURRING_TRANSACTION_TYPE_CHECK_SQL = (
    "transaction_type IN ("
    "'income', "
    "'expense', "
    "'asset_acquisition', "
    "'liability_drawdown', "
    "'liability_repayment', "
    "'tax_payment', "
    "'transfer'"
    ")"
)


def upgrade() -> None:
    with op.get_context().autocommit_block():
        for value in TRANSACTIONTYPE_VALUES:
            op.execute(f"ALTER TYPE transactiontype ADD VALUE IF NOT EXISTS '{value}'")

    op.drop_constraint(
        "check_transaction_type_valid",
        "recurring_transactions",
        type_="check",
    )
    op.create_check_constraint(
        "check_transaction_type_valid",
        "recurring_transactions",
        RECURRING_TRANSACTION_TYPE_CHECK_SQL,
    )


def downgrade() -> None:
    op.drop_constraint(
        "check_transaction_type_valid",
        "recurring_transactions",
        type_="check",
    )
    op.create_check_constraint(
        "check_transaction_type_valid",
        "recurring_transactions",
        "transaction_type IN ('income', 'expense')",
    )
    # PostgreSQL does not support removing enum values.
