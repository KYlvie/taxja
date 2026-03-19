"""Add account cancellation fields and deletion log table

Revision ID: 018
Revises: 017
Create Date: 2026-04-01 10:00:00.000000

Extends the users table with account cancellation / soft-delete fields
and creates the account_deletion_logs table for GDPR compliance auditing.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add cancellation fields to users and create account_deletion_logs."""

    # --- Users table: new columns ---
    op.add_column(
        "users",
        sa.Column(
            "account_status",
            sa.String(length=20),
            nullable=False,
            server_default="active",
        ),
    )
    op.add_column("users", sa.Column("deactivated_at", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("scheduled_deletion_at", sa.DateTime(), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "deletion_retry_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "users",
        sa.Column("cancellation_reason", sa.String(length=500), nullable=True),
    )

    # Index on account_status for filtering by status
    op.create_index("idx_users_account_status", "users", ["account_status"])

    # --- account_deletion_logs table ---
    op.create_table(
        "account_deletion_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("anonymous_user_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "deleted_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("data_types_deleted", sa.JSON(), nullable=True),
        sa.Column("deletion_method", sa.String(length=20), nullable=True),
        sa.Column("initiated_by", sa.String(length=20), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # Indexes for common audit queries
    op.create_index(
        "idx_deletion_logs_deleted_at",
        "account_deletion_logs",
        [sa.text("deleted_at DESC")],
    )
    op.create_index(
        "idx_deletion_logs_hash",
        "account_deletion_logs",
        ["anonymous_user_hash"],
    )


def downgrade() -> None:
    """Remove cancellation fields and drop account_deletion_logs."""

    # Drop account_deletion_logs indexes and table
    op.drop_index("idx_deletion_logs_hash", table_name="account_deletion_logs")
    op.drop_index("idx_deletion_logs_deleted_at", table_name="account_deletion_logs")
    op.drop_table("account_deletion_logs")

    # Drop users columns and index
    op.drop_index("idx_users_account_status", table_name="users")
    op.drop_column("users", "cancellation_reason")
    op.drop_column("users", "deletion_retry_count")
    op.drop_column("users", "scheduled_deletion_at")
    op.drop_column("users", "deactivated_at")
    op.drop_column("users", "account_status")
