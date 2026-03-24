"""Add Google subject identifier to users.

Revision ID: 069_add_google_subject
Revises: 068_resync_doctypes
Create Date: 2026-03-24 05:20:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "069_add_google_subject"
down_revision = "068_resync_doctypes"
branch_labels = None
depends_on = None


def _column_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :table AND column_name = :column"
        ),
        {"table": table, "column": column},
    )
    return result.fetchone() is not None


def _index_exists(index_name: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM pg_indexes "
            "WHERE schemaname = current_schema() AND indexname = :index_name"
        ),
        {"index_name": index_name},
    )
    return result.fetchone() is not None


def upgrade() -> None:
    if not _column_exists("users", "google_subject"):
        op.add_column("users", sa.Column("google_subject", sa.String(length=255), nullable=True))

    if not _index_exists("ix_users_google_subject"):
        op.create_index(
            "ix_users_google_subject",
            "users",
            ["google_subject"],
            unique=True,
        )


def downgrade() -> None:
    if _index_exists("ix_users_google_subject"):
        op.drop_index("ix_users_google_subject", table_name="users")

    if _column_exists("users", "google_subject"):
        op.drop_column("users", "google_subject")
