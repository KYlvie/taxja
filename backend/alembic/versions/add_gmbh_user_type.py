"""Add gmbh to UserType enum

Revision ID: add_gmbh_user_type
Revises: add_new_expense_cats
Create Date: 2026-03-06
"""
from alembic import op

revision = "add_gmbh_user_type"
down_revision = "add_new_expense_cats"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add 'gmbh' to the usertype enum in PostgreSQL
    op.execute("ALTER TYPE usertype ADD VALUE IF NOT EXISTS 'gmbh'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values directly.
    # A full enum recreation would be needed for a real downgrade.
    pass
