"""Add new expense categories: vehicle, telecom, rent, bank_fees, svs_contributions

Revision ID: add_new_expense_cats
Revises: None
Create Date: 2026-03-06
"""
from alembic import op

# revision identifiers
revision = "add_new_expense_cats"
down_revision = "001"
branch_labels = None
depends_on = None

NEW_VALUES = ["vehicle", "telecom", "rent", "bank_fees", "svs_contributions"]


def upgrade() -> None:
    # PostgreSQL: add new enum values to the expensecategory type
    for val in NEW_VALUES:
        op.execute(
            f"ALTER TYPE expensecategory ADD VALUE IF NOT EXISTS '{val}'"
        )


def downgrade() -> None:
    # PostgreSQL does not support removing enum values easily.
    # A full migration would require recreating the type.
    pass
