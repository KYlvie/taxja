"""Add ai_review_notes column to transactions table

Revision ID: 022
Revises: 021
Create Date: 2026-03-15
"""
from alembic import op
import sqlalchemy as sa

revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("ai_review_notes", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("transactions", "ai_review_notes")
