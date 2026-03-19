"""Add industry-specific expense categories: cleaning, clothing, software, shipping, fuel, education

Revision ID: 025
Revises: 022
Create Date: 2026-03-15
"""
from alembic import op

# revision identifiers
revision = "025"
down_revision = "022"
branch_labels = None
depends_on = None

NEW_VALUES = ["cleaning", "clothing", "software", "shipping", "fuel", "education"]


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
