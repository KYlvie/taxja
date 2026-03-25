"""add bank statement line resolution reason

Revision ID: 071_bank_line_resolution
Revises: 070_align_bank_statement_enums
Create Date: 2026-03-25 00:20:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "071_bank_line_resolution"
down_revision = "070_align_bank_statement_enums"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = current_schema() AND table_name = :table_name"
        ),
        {"table_name": table_name},
    )
    return result.scalar() is not None


def _column_exists(table_name: str, column_name: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = current_schema() "
            "AND table_name = :table_name "
            "AND column_name = :column_name"
        ),
        {"table_name": table_name, "column_name": column_name},
    )
    return result.scalar() is not None


def upgrade() -> None:
    if not _table_exists("bank_statement_lines") or _column_exists(
        "bank_statement_lines", "resolution_reason"
    ):
        return

    op.add_column(
        "bank_statement_lines",
        sa.Column("resolution_reason", sa.String(length=64), nullable=True),
    )

    op.execute(
        sa.text(
            "UPDATE bank_statement_lines "
            "SET resolution_reason = 'new' "
            "WHERE review_status::text = 'pending_review' "
            "AND resolution_reason IS NULL"
        )
    )


def downgrade() -> None:
    if _table_exists("bank_statement_lines") and _column_exists(
        "bank_statement_lines", "resolution_reason"
    ):
        op.drop_column("bank_statement_lines", "resolution_reason")
