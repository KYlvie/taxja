"""add insurance metadata to recurring transactions

Revision ID: 076_add_insurance_metadata_to_recurring_transactions
Revises: 075_add_rent_adjustment_document_type
Create Date: 2026-03-28
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "076_add_insurance_metadata_to_recurring_transactions"
down_revision = "075_add_rent_adjustment_document_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "recurring_transactions",
        sa.Column("insurance_metadata", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("recurring_transactions", "insurance_metadata")
