"""Add monthly_credits and overage_price_per_credit to plans table.

Sets default values for existing plans:
  - Free: 50 credits/month, no overage
  - Plus: 500 credits/month, €0.04/credit overage
  - Pro: 2000 credits/month, €0.03/credit overage

Revision ID: 052
Revises: 051
Create Date: 2026-03-20
"""
import sqlalchemy as sa
from alembic import op

revision = "052"
down_revision = "051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns
    op.add_column(
        "plans",
        sa.Column("monthly_credits", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "plans",
        sa.Column("overage_price_per_credit", sa.Numeric(6, 4), nullable=True),
    )

    # Fill default values for existing plan records
    op.execute(
        "UPDATE plans SET monthly_credits = 50, overage_price_per_credit = NULL "
        "WHERE plan_type = 'free'"
    )
    op.execute(
        "UPDATE plans SET monthly_credits = 500, overage_price_per_credit = 0.0400 "
        "WHERE plan_type = 'plus'"
    )
    op.execute(
        "UPDATE plans SET monthly_credits = 2000, overage_price_per_credit = 0.0300 "
        "WHERE plan_type = 'pro'"
    )

    # Remove server_default now that existing rows are populated
    op.alter_column("plans", "monthly_credits", server_default=None)


def downgrade() -> None:
    op.drop_column("plans", "overage_price_per_credit")
    op.drop_column("plans", "monthly_credits")
