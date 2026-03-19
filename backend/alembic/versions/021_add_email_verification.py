"""Add email verification fields to users table

Revision ID: 021
Revises: 020
Create Date: 2026-03-15
"""
from alembic import op
import sqlalchemy as sa

revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email_verified", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("users", sa.Column("email_verification_token", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("email_verification_sent_at", sa.DateTime(), nullable=True))
    op.create_index("ix_users_email_verification_token", "users", ["email_verification_token"])
    # Mark all existing users as verified
    op.execute("UPDATE users SET email_verified = true")


def downgrade() -> None:
    op.drop_index("ix_users_email_verification_token", table_name="users")
    op.drop_column("users", "email_verification_sent_at")
    op.drop_column("users", "email_verification_token")
    op.drop_column("users", "email_verified")
