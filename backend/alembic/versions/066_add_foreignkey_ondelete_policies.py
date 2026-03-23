"""Add ondelete policies to ForeignKey constraints missing them.

Revision ID: 066_fk_ondelete
Revises: 065
Create Date: 2026-03-23

Affected tables/columns:
  - documents.user_id              → CASCADE
  - documents.transaction_id       → SET NULL
  - documents.parent_document_id   → SET NULL
  - transactions.user_id           → CASCADE
  - transactions.document_id       → SET NULL
  - classification_corrections.transaction_id → CASCADE
  - classification_corrections.user_id        → CASCADE
  - tax_reports.user_id            → CASCADE
  - loss_carryforwards.user_id     → CASCADE
  - notifications.user_id          → CASCADE
  - chat_messages.user_id          → CASCADE
  - user_classification_rules.user_id → CASCADE
  - user_deductibility_rules.user_id  → CASCADE
  - employer_months.user_id        → CASCADE
  - employer_month_documents.employer_month_id → CASCADE
  - employer_month_documents.document_id       → CASCADE
  - employer_annual_archives.user_id           → CASCADE
  - employer_annual_archive_documents.annual_archive_id → CASCADE
  - employer_annual_archive_documents.document_id       → CASCADE
  - tax_filing_data.user_id           → CASCADE
  - tax_filing_data.source_document_id → SET NULL
"""

from alembic import op

revision = "066_fk_ondelete"
down_revision = "065_add_reminder_states_table"
branch_labels = None
depends_on = None

# (table, column, referred_table, ondelete_action)
FK_SPECS = [
    ("documents", "user_id", "users", "CASCADE"),
    ("documents", "transaction_id", "transactions", "SET NULL"),
    ("documents", "parent_document_id", "documents", "SET NULL"),
    ("transactions", "user_id", "users", "CASCADE"),
    ("transactions", "document_id", "documents", "SET NULL"),
    ("classification_corrections", "transaction_id", "transactions", "CASCADE"),
    ("classification_corrections", "user_id", "users", "CASCADE"),
    ("tax_reports", "user_id", "users", "CASCADE"),
    ("loss_carryforwards", "user_id", "users", "CASCADE"),
    ("notifications", "user_id", "users", "CASCADE"),
    ("chat_messages", "user_id", "users", "CASCADE"),
    ("user_classification_rules", "user_id", "users", "CASCADE"),
    ("user_deductibility_rules", "user_id", "users", "CASCADE"),
    ("employer_months", "user_id", "users", "CASCADE"),
    ("employer_month_documents", "employer_month_id", "employer_months", "CASCADE"),
    ("employer_month_documents", "document_id", "documents", "CASCADE"),
    ("employer_annual_archives", "user_id", "users", "CASCADE"),
    ("employer_annual_archive_documents", "annual_archive_id", "employer_annual_archives", "CASCADE"),
    ("employer_annual_archive_documents", "document_id", "documents", "CASCADE"),
    ("tax_filing_data", "user_id", "users", "CASCADE"),
    ("tax_filing_data", "source_document_id", "documents", "SET NULL"),
]


def _fk_name(table: str, column: str) -> str:
    """Generate a deterministic FK constraint name."""
    return f"fk_{table}_{column}"


def _old_fk_name(table: str, column: str, referred: str) -> str:
    """Common auto-generated FK name pattern used by SQLAlchemy/Alembic."""
    return f"{table}_{column}_fkey"


def upgrade() -> None:
    for table, column, referred, action in FK_SPECS:
        # Determine the referred column (always 'id')
        referred_col = "id"

        # Drop old FK (try both naming conventions)
        old_name = _old_fk_name(table, column, referred)
        try:
            op.drop_constraint(old_name, table, type_="foreignkey")
        except Exception:
            # Constraint may have a different name; try the other pattern
            try:
                op.drop_constraint(_fk_name(table, column), table, type_="foreignkey")
            except Exception:
                pass

        # Create new FK with ondelete
        op.create_foreign_key(
            _fk_name(table, column),
            table,
            referred,
            [column],
            [referred_col],
            ondelete=action,
        )


def downgrade() -> None:
    for table, column, referred, _action in FK_SPECS:
        referred_col = "id"

        try:
            op.drop_constraint(_fk_name(table, column), table, type_="foreignkey")
        except Exception:
            pass

        # Recreate without ondelete
        old_name = _old_fk_name(table, column, referred)
        op.create_foreign_key(
            old_name,
            table,
            referred,
            [column],
            [referred_col],
        )
