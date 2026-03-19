"""Add rule_type column to user_classification_rules

Revision ID: 041
Revises: 040
Create Date: 2026-03-16
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "041"
down_revision = "040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_classification_rules",
        sa.Column("rule_type", sa.String(10), nullable=False, server_default="strict"),
    )


def downgrade() -> None:
    op.drop_column("user_classification_rules", "rule_type")
