"""add bank statement workbench tables

Revision ID: 067_bank_statement_workbench
Revises: 066_fk_ondelete
Create Date: 2026-03-23 12:15:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "067_bank_statement_workbench"
down_revision = "066_fk_ondelete"
branch_labels = None
depends_on = None


def _column_exists(table, column):
    """Check if a column already exists in a table."""
    from alembic import op as _op
    conn = _op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :table AND column_name = :column"
        ),
        {"table": table, "column": column},
    )
    return result.fetchone() is not None


def _table_exists(table):
    """Check if a table already exists."""
    from alembic import op as _op
    conn = _op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_name = :table"
        ),
        {"table": table},
    )
    return result.fetchone() is not None


def upgrade() -> None:
    if not _column_exists("transactions", "bank_reconciled"):
        op.add_column(
            "transactions",
            sa.Column("bank_reconciled", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        op.alter_column("transactions", "bank_reconciled", server_default=None)

    if not _column_exists("transactions", "bank_reconciled_at"):
        op.add_column(
            "transactions",
            sa.Column("bank_reconciled_at", sa.DateTime(), nullable=True),
        )

    if _table_exists("bank_statement_imports"):
        return  # Tables already created, skip

    op.create_table(
        "bank_statement_imports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("source_document_id", sa.Integer(), nullable=True),
        sa.Column("bank_name", sa.String(length=255), nullable=True),
        sa.Column("iban", sa.String(length=64), nullable=True),
        sa.Column("statement_period", sa.JSON(), nullable=True),
        sa.Column("tax_year", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["source_document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_bank_statement_imports_user_document",
        "bank_statement_imports",
        ["user_id", "source_document_id"],
    )

    op.create_table(
        "bank_statement_lines",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("import_id", sa.Integer(), nullable=False),
        sa.Column("line_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("counterparty", sa.String(length=255), nullable=True),
        sa.Column("purpose", sa.Text(), nullable=True),
        sa.Column("raw_reference", sa.Text(), nullable=True),
        sa.Column("normalized_fingerprint", sa.String(length=255), nullable=False),
        sa.Column("review_status", sa.String(length=32), nullable=False, server_default="pending_review"),
        sa.Column("suggested_action", sa.String(length=32), nullable=False, server_default="create_new"),
        sa.Column("confidence_score", sa.Numeric(5, 3), nullable=True),
        sa.Column("linked_transaction_id", sa.Integer(), nullable=True),
        sa.Column("created_transaction_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("reviewed_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["created_transaction_id"], ["transactions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["import_id"], ["bank_statement_imports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["linked_transaction_id"], ["transactions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_bank_statement_lines_import_status",
        "bank_statement_lines",
        ["import_id", "review_status"],
    )
    op.create_index(
        "ix_bank_statement_lines_fingerprint",
        "bank_statement_lines",
        ["normalized_fingerprint"],
    )


def downgrade() -> None:
    op.drop_index("ix_bank_statement_lines_fingerprint", table_name="bank_statement_lines")
    op.drop_index("ix_bank_statement_lines_import_status", table_name="bank_statement_lines")
    op.drop_table("bank_statement_lines")
    op.drop_index("ix_bank_statement_imports_user_document", table_name="bank_statement_imports")
    op.drop_table("bank_statement_imports")
    op.drop_column("transactions", "bank_reconciled_at")
    op.drop_column("transactions", "bank_reconciled")
