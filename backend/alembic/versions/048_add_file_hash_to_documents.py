"""Add file_hash to documents for exact upload deduplication

Revision ID: 048_add_file_hash_to_documents
Revises: 047_employer_annual_archives
Create Date: 2026-03-17
"""
from alembic import op
import sqlalchemy as sa


revision = "048_add_file_hash_to_documents"
down_revision = "047_employer_annual_archives"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("file_hash", sa.String(length=64), nullable=True),
    )
    op.create_index(op.f("ix_documents_file_hash"), "documents", ["file_hash"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_documents_file_hash"), table_name="documents")
    op.drop_column("documents", "file_hash")
