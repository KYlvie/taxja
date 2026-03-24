"""Add onboarding_dismiss_count to users table.

Revision ID: 058_onboarding_dismiss
Revises: 057_sync_recur_types
Create Date: 2026-03-21
"""

from alembic import op
import sqlalchemy as sa


revision = "058_onboarding_dismiss"
down_revision = "057_sync_recur_types"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("onboarding_dismiss_count", sa.Integer(), nullable=False, server_default="0"),
    )
    # Backfill: users who already completed onboarding get count=3
    op.execute(
        "UPDATE users SET onboarding_dismiss_count = 3 WHERE onboarding_completed = true"
    )


def downgrade() -> None:
    op.drop_column("users", "onboarding_dismiss_count")
