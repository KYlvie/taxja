"""Add insurance_premium and loan_repayment to recurringtransactiontype enum.

Also updates check_source_entity_required constraint to allow these new types
without requiring property_id or loan_id.

Revision ID: 051
Revises: 050_add_asset_tax_fields_to_properties
Create Date: 2026-03-18
"""
from alembic import op

revision = "051"
down_revision = "050_add_asset_tax_fields_to_properties"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new enum values
    op.execute(
        "ALTER TYPE recurringtransactiontype ADD VALUE IF NOT EXISTS 'insurance_premium'"
    )
    op.execute(
        "ALTER TYPE recurringtransactiontype ADD VALUE IF NOT EXISTS 'loan_repayment'"
    )

    # Update CHECK constraint to include new types
    op.drop_constraint(
        "check_source_entity_required", "recurring_transactions", type_="check"
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
    # Restore original CHECK constraint
    op.drop_constraint(
        "check_source_entity_required", "recurring_transactions", type_="check"
    )
    op.create_check_constraint(
        "check_source_entity_required",
        "recurring_transactions",
        "(recurring_type = 'rental_income' AND property_id IS NOT NULL) OR "
        "(recurring_type = 'loan_interest' AND loan_id IS NOT NULL) OR "
        "(recurring_type = 'depreciation' AND property_id IS NOT NULL) OR "
        "(recurring_type IN ('other_income', 'other_expense', 'manual'))",
    )
    # PostgreSQL does not support removing enum values
