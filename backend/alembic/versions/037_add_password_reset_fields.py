"""Add password reset token fields to users table

Revision ID: 037
Revises: 036_add_business_industry
Create Date: 2026-03-15
"""
from alembic import op
import sqlalchemy as sa


revision = "037"
down_revision = "036_add_business_industry"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_reset_token", sa.String(255), nullable=True, index=True))
    op.add_column("users", sa.Column("password_reset_sent_at", sa.DateTime, nullable=True))


def downgrade() -> None:
    op.drop_column("users", "password_reset_sent_at")
    op.drop_column("users", "password_reset_token")
