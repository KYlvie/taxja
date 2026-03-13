"""Add property-related expense categories

Revision ID: 003_add_property_expense_categories
Revises: 002
Create Date: 2026-03-07
"""
from alembic import op

# revision identifiers
revision = "003_add_property_expense_categories"
down_revision = "002"
branch_labels = None
depends_on = None

NEW_VALUES = [
    "property_management_fees",
    "property_insurance",
    "depreciation_afa"
]


def upgrade() -> None:
    """Add new property-related expense category enum values"""
    # PostgreSQL: add new enum values to the expensecategory type
    # Note: LOAN_INTEREST, PROPERTY_TAX, MAINTENANCE, and UTILITIES already exist
    for val in NEW_VALUES:
        op.execute(
            f"ALTER TYPE expensecategory ADD VALUE IF NOT EXISTS '{val}'"
        )


def downgrade() -> None:
    """
    PostgreSQL does not support removing enum values easily.
    A full migration would require recreating the type and migrating data.
    For safety, downgrade is not implemented.
    """
    pass
