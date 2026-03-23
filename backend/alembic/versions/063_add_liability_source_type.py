"""Add source_type metadata to liabilities.

Revision ID: 063_add_liability_source_type
Revises: 062_add_liabilities_table
Create Date: 2026-03-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "063_add_liability_source_type"
down_revision = "062_add_liabilities_table"
branch_labels = None
depends_on = None


source_type_enum = postgresql.ENUM(
    "manual",
    "document_confirmed",
    "document_auto_created",
    "system_migrated",
    name="liabilitysourcetype",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        source_type_enum.create(bind, checkfirst=True)

    source_type_column = (
        source_type_enum if bind.dialect.name == "postgresql" else sa.String(length=50)
    )

    op.add_column(
        "liabilities",
        sa.Column(
            "source_type",
            source_type_column,
            nullable=False,
            server_default="manual",
        ),
    )
    op.create_index("ix_liabilities_source_type", "liabilities", ["source_type"])

    if bind.dialect.name == "postgresql":
        op.execute(
            sa.text(
                """
                UPDATE liabilities
                SET source_type = CASE
                    WHEN source_document_id IS NOT NULL THEN 'document_confirmed'::liabilitysourcetype
                    WHEN linked_loan_id IS NOT NULL THEN 'system_migrated'::liabilitysourcetype
                    ELSE 'manual'::liabilitysourcetype
                END
                """
            )
        )
    else:
        op.execute(
            sa.text(
                """
                UPDATE liabilities
                SET source_type = CASE
                    WHEN source_document_id IS NOT NULL THEN 'document_confirmed'
                    WHEN linked_loan_id IS NOT NULL THEN 'system_migrated'
                    ELSE 'manual'
                END
                """
            )
        )


def downgrade() -> None:
    op.drop_index("ix_liabilities_source_type", table_name="liabilities")
    op.drop_column("liabilities", "source_type")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        source_type_enum.drop(bind, checkfirst=True)
