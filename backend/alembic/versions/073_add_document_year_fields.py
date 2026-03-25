"""add document year attribution fields

Revision ID: 073_add_document_year_fields
Revises: 072_add_document_date
Create Date: 2026-03-25 14:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "073_add_document_year_fields"
down_revision = "072_add_document_date"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("documents", sa.Column("document_year", sa.Integer(), nullable=True))
    op.add_column("documents", sa.Column("year_basis", sa.String(length=50), nullable=True))
    op.add_column("documents", sa.Column("year_confidence", sa.Numeric(3, 2), nullable=True))
    op.create_index("ix_documents_document_year", "documents", ["document_year"])


def downgrade():
    op.drop_index("ix_documents_document_year", table_name="documents")
    op.drop_column("documents", "year_confidence")
    op.drop_column("documents", "year_basis")
    op.drop_column("documents", "document_year")
