"""Add classification_method column to transactions

Revision ID: 038_cls_method
Revises: 037
Create Date: 2026-03-16
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "038_cls_method"
down_revision = "037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("classification_method", sa.String(20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("transactions", "classification_method")
