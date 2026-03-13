"""Add 7 Austrian Einkunftsarten income categories: agriculture, business, other_income

Adds the three missing income categories to align with Austrian tax law's
seven types of income (Einkunftsarten):
  Nr.1 agriculture (Land- und Forstwirtschaft)
  Nr.3 business (Gewerbebetrieb)
  Nr.7 other_income (Sonstige Einkünfte)

Existing categories remain unchanged:
  self_employment (Nr.2), employment (Nr.4), capital_gains (Nr.5), rental (Nr.6)

Revision ID: add_7_einkunftsarten
Revises: None
Create Date: 2026-03-06
"""
from alembic import op

revision = "add_7_einkunftsarten"
down_revision = None
branch_labels = None
depends_on = None

NEW_VALUES = ["agriculture", "business", "other_income"]


def upgrade() -> None:
    for val in NEW_VALUES:
        op.execute(
            f"ALTER TYPE incomecategory ADD VALUE IF NOT EXISTS '{val}'"
        )


def downgrade() -> None:
    # PostgreSQL does not support removing enum values easily.
    pass
