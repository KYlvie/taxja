"""add document_date column to documents table

Revision ID: 072_add_document_date
Revises: 071_bank_line_resolution
Create Date: 2026-03-25 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from datetime import date


# revision identifiers, used by Alembic.
revision = "072_add_document_date"
down_revision = "071_bank_line_resolution"
branch_labels = None
depends_on = None

# Priority chain for resolving document date from OCR result
DATE_FIELD_PRIORITY = [
    "document_date", "date", "invoice_date",
    "receipt_date", "purchase_date", "start_date",
]

BATCH_SIZE = 500


def _resolve_document_date(ocr_result):
    """Extract the best document date from OCR result using priority chain."""
    if not ocr_result or not isinstance(ocr_result, dict):
        return None
    for field in DATE_FIELD_PRIORITY:
        value = ocr_result.get(field)
        if value and isinstance(value, str):
            try:
                return date.fromisoformat(value[:10])
            except (ValueError, TypeError):
                continue
    return None


def upgrade():
    # 1. Add nullable column (metadata-only on PostgreSQL, no table rewrite)
    op.add_column("documents", sa.Column("document_date", sa.Date(), nullable=True))
    op.create_index("ix_documents_document_date", "documents", ["document_date"])

    # 2. Batched backfill for existing rows with OCR results
    conn = op.get_bind()
    documents_table = sa.table(
        "documents",
        sa.column("id", sa.Integer),
        sa.column("ocr_result", sa.JSON),
        sa.column("document_date", sa.Date),
    )

    while True:
        rows = conn.execute(
            sa.select(documents_table.c.id, documents_table.c.ocr_result)
            .where(documents_table.c.ocr_result.isnot(None))
            .where(documents_table.c.document_date.is_(None))
            .limit(BATCH_SIZE)
        ).fetchall()

        if not rows:
            break

        for row in rows:
            resolved = _resolve_document_date(row.ocr_result)
            if resolved is not None:
                conn.execute(
                    documents_table.update()
                    .where(documents_table.c.id == row.id)
                    .values(document_date=resolved)
                )

        conn.commit()


def downgrade():
    op.drop_index("ix_documents_document_date", table_name="documents")
    op.drop_column("documents", "document_date")
