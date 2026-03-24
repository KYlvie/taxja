"""align bank statement enum-backed columns

Revision ID: 070_align_bank_statement_enums
Revises: 069_add_google_subject
Create Date: 2026-03-24 17:05:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "070_align_bank_statement_enums"
down_revision = "069_add_google_subject"
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


def _column_udt_name(table_name: str, column_name: str) -> str | None:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT udt_name FROM information_schema.columns "
            "WHERE table_schema = current_schema() "
            "AND table_name = :table_name AND column_name = :column_name"
        ),
        {"table_name": table_name, "column_name": column_name},
    )
    row = result.fetchone()
    return row[0] if row else None


def _align_enum_column(
    table_name: str,
    column_name: str,
    enum_name: str,
    default_literal: str | None = None,
) -> None:
    if not _table_exists(table_name):
        return

    current_udt = _column_udt_name(table_name, column_name)
    if current_udt == enum_name:
        return

    if default_literal is not None:
        op.execute(
            sa.text(
                f'ALTER TABLE "{table_name}" ALTER COLUMN "{column_name}" DROP DEFAULT'
            )
        )

    op.execute(
        sa.text(
            f'ALTER TABLE "{table_name}" '
            f'ALTER COLUMN "{column_name}" TYPE {enum_name} '
            f'USING "{column_name}"::text::{enum_name}'
        )
    )

    if default_literal is not None:
        op.execute(
            sa.text(
                f"ALTER TABLE \"{table_name}\" ALTER COLUMN \"{column_name}\" "
                f"SET DEFAULT '{default_literal}'::{enum_name}"
            )
        )


def upgrade() -> None:
    bind = op.get_bind()

    postgresql.ENUM(
        "csv",
        "mt940",
        "document",
        name="bankstatementimportsourcetype",
    ).create(bind, checkfirst=True)
    postgresql.ENUM(
        "pending_review",
        "auto_created",
        "matched_existing",
        "ignored_duplicate",
        name="bankstatementlinestatus",
    ).create(bind, checkfirst=True)
    postgresql.ENUM(
        "create_new",
        "match_existing",
        "ignore",
        name="bankstatementsuggestedaction",
    ).create(bind, checkfirst=True)

    _align_enum_column(
        table_name="bank_statement_imports",
        column_name="source_type",
        enum_name="bankstatementimportsourcetype",
    )
    _align_enum_column(
        table_name="bank_statement_lines",
        column_name="review_status",
        enum_name="bankstatementlinestatus",
        default_literal="pending_review",
    )
    _align_enum_column(
        table_name="bank_statement_lines",
        column_name="suggested_action",
        enum_name="bankstatementsuggestedaction",
        default_literal="create_new",
    )


def downgrade() -> None:
    if _table_exists("bank_statement_lines"):
        op.execute(
            sa.text(
                'ALTER TABLE "bank_statement_lines" ALTER COLUMN "review_status" DROP DEFAULT'
            )
        )
        if _column_udt_name("bank_statement_lines", "review_status") == "bankstatementlinestatus":
            op.execute(
                sa.text(
                    'ALTER TABLE "bank_statement_lines" ALTER COLUMN "review_status" TYPE VARCHAR USING "review_status"::text'
                )
            )
        if _column_udt_name("bank_statement_lines", "suggested_action") == "bankstatementsuggestedaction":
            op.execute(
                sa.text(
                    'ALTER TABLE "bank_statement_lines" ALTER COLUMN "suggested_action" DROP DEFAULT'
                )
            )
            op.execute(
                sa.text(
                    'ALTER TABLE "bank_statement_lines" ALTER COLUMN "suggested_action" TYPE VARCHAR USING "suggested_action"::text'
                )
            )

    if _table_exists("bank_statement_imports") and _column_udt_name(
        "bank_statement_imports", "source_type"
    ) == "bankstatementimportsourcetype":
        op.execute(
            sa.text(
                'ALTER TABLE "bank_statement_imports" ALTER COLUMN "source_type" TYPE VARCHAR USING "source_type"::text'
            )
        )

    postgresql.ENUM(name="bankstatementsuggestedaction").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="bankstatementlinestatus").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="bankstatementimportsourcetype").drop(op.get_bind(), checkfirst=True)
