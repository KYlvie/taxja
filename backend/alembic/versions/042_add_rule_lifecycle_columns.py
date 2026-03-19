"""Add lifecycle columns to user_classification_rules.

Adds last_hit_at, conflict_count, frozen for rule lifecycle management.

Revision ID: 042
Revises: 041
"""
from alembic import op
import sqlalchemy as sa

revision = "042"
down_revision = "041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_classification_rules",
        sa.Column("last_hit_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "user_classification_rules",
        sa.Column("conflict_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "user_classification_rules",
        sa.Column("frozen", sa.Boolean(), server_default="false", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("user_classification_rules", "frozen")
    op.drop_column("user_classification_rules", "conflict_count")
    op.drop_column("user_classification_rules", "last_hit_at")
