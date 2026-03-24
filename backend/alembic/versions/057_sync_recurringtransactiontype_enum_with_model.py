"""Sync recurringtransactiontype enum with the current model.

Revision ID: 057_sync_recur_types
Revises: 056_sync_doctypes
Create Date: 2026-03-20
"""

from alembic import op


revision = "057_sync_recur_types"
down_revision = "056_sync_doctypes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "ALTER TYPE recurringtransactiontype ADD VALUE IF NOT EXISTS 'insurance_premium'"
        )
        op.execute(
            "ALTER TYPE recurringtransactiontype ADD VALUE IF NOT EXISTS 'loan_repayment'"
        )

    op.drop_constraint(
        "check_source_entity_required",
        "recurring_transactions",
        type_="check",
    )
    op.create_check_constraint(
        "check_source_entity_required",
        "recurring_transactions",
        "(recurring_type = 'rental_income' AND property_id IS NOT NULL) OR "
        "(recurring_type = 'loan_interest' AND loan_id IS NOT NULL) OR "
        "(recurring_type = 'depreciation' AND property_id IS NOT NULL) OR "
        "(recurring_type IN ('other_income', 'other_expense', 'manual', 'insurance_premium', 'loan_repayment'))",
    )


def downgrade() -> None:
    op.drop_constraint(
        "check_source_entity_required",
        "recurring_transactions",
        type_="check",
    )
    op.create_check_constraint(
        "check_source_entity_required",
        "recurring_transactions",
        "(recurring_type = 'rental_income' AND property_id IS NOT NULL) OR "
        "(recurring_type = 'loan_interest' AND loan_id IS NOT NULL) OR "
        "(recurring_type = 'depreciation' AND property_id IS NOT NULL) OR "
        "(recurring_type IN ('other_income', 'other_expense', 'manual'))",
    )
    # PostgreSQL does not support removing enum values.
