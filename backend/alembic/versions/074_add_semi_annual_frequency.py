"""Add semi_annual value to recurrencefrequency enum.

Insurance policies in Austria commonly use halbjährlich (semi-annual) payment
frequency. This adds the missing enum value to support it.

Revision ID: 074_add_semi_annual_frequency
Revises: 073_add_document_year_fields
Create Date: 2026-03-28 12:00:00.000000
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "074_add_semi_annual_frequency"
down_revision = "073_add_document_year_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE recurrencefrequency ADD VALUE IF NOT EXISTS 'semi_annual'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values.
    pass
