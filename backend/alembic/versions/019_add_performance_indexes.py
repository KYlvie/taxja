"""Add performance indexes for 10K+ user scale

Revision ID: 019
Revises: 018
Create Date: 2026-03-14 10:00:00.000000

Adds composite indexes on transactions and documents tables to support
efficient dashboard queries, filtered transaction lists, and document
lookups at scale.
"""
from alembic import op
import sqlalchemy as sa

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Dashboard: aggregate by user + year + type
    op.create_index(
        "idx_tx_user_date_type",
        "transactions",
        ["user_id", "transaction_date", "type"],
        if_not_exists=True,
    )
    # Transaction list: filtered by type, sorted by date desc
    op.create_index(
        "idx_tx_user_type_date_desc",
        "transactions",
        ["user_id", "type", sa.text("transaction_date DESC")],
        if_not_exists=True,
    )
    # Document list: sorted by upload time
    op.create_index(
        "idx_docs_user_uploaded",
        "documents",
        ["user_id", sa.text("uploaded_at DESC")],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("idx_docs_user_uploaded", table_name="documents")
    op.drop_index("idx_tx_user_type_date_desc", table_name="transactions")
    op.drop_index("idx_tx_user_date_type", table_name="transactions")
