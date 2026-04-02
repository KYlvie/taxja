"""Add rent_adjustment value to documenttype enum.

Supports Indexanpassungsschreiben / Mietzinserhöhung document type for
automatic rent adjustment detection and recurring transaction updates.

Revision ID: 075_add_rent_adjustment_document_type
Revises: 074_add_semi_annual_frequency
Create Date: 2026-03-28 18:00:00.000000
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "075_add_rent_adjustment_document_type"
down_revision = "074_add_semi_annual_frequency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE documenttype ADD VALUE IF NOT EXISTS 'rent_adjustment'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values.
    pass
