"""Add unified liabilities table and liability links.

Revision ID: 062_add_liabilities_table
Revises: 061_canonical_line_items
Create Date: 2026-03-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "062_add_liabilities_table"
down_revision = "061_canonical_line_items"
branch_labels = None
depends_on = None


liability_type_enum = postgresql.ENUM(
    "property_loan",
    "business_loan",
    "owner_loan",
    "family_loan",
    "other_liability",
    name="liabilitytype",
    create_type=False,
)

report_category_enum = postgresql.ENUM(
    "darlehen_und_kredite",
    "sonstige_verbindlichkeiten",
    name="liabilityreportcategory",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        liability_type_enum.create(bind, checkfirst=True)
        report_category_enum.create(bind, checkfirst=True)

    op.create_table(
        "liabilities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "liability_type",
            liability_type_enum if bind.dialect.name == "postgresql" else sa.String(length=50),
            nullable=False,
        ),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="EUR"),
        sa.Column("lender_name", sa.String(length=255), nullable=False),
        sa.Column("principal_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("outstanding_balance", sa.Numeric(12, 2), nullable=False),
        sa.Column("interest_rate", sa.Numeric(8, 6), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("monthly_payment", sa.Numeric(12, 2), nullable=True),
        sa.Column("tax_relevant", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("tax_relevance_reason", sa.String(length=500), nullable=True),
        sa.Column(
            "report_category",
            report_category_enum if bind.dialect.name == "postgresql" else sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "linked_property_id",
            postgresql.UUID(as_uuid=True) if bind.dialect.name == "postgresql" else sa.String(length=36),
            sa.ForeignKey("properties.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "linked_loan_id",
            sa.Integer(),
            sa.ForeignKey("property_loans.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "source_document_id",
            sa.Integer(),
            sa.ForeignKey("documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_liabilities_user_id", "liabilities", ["user_id"])
    op.create_index("ix_liabilities_liability_type", "liabilities", ["liability_type"])
    op.create_index("ix_liabilities_tax_relevant", "liabilities", ["tax_relevant"])
    op.create_index("ix_liabilities_linked_property_id", "liabilities", ["linked_property_id"])
    op.create_index("ix_liabilities_linked_loan_id", "liabilities", ["linked_loan_id"])
    op.create_index("ix_liabilities_source_document_id", "liabilities", ["source_document_id"])
    op.create_index("ix_liabilities_is_active", "liabilities", ["is_active"])

    op.add_column(
        "recurring_transactions",
        sa.Column(
            "liability_id",
            sa.Integer(),
            sa.ForeignKey("liabilities.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_recurring_transactions_liability_id", "recurring_transactions", ["liability_id"])

    op.add_column(
        "transactions",
        sa.Column(
            "liability_id",
            sa.Integer(),
            sa.ForeignKey("liabilities.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_transactions_liability_id", "transactions", ["liability_id"])

    liability_type_literal = (
        "'property_loan'::liabilitytype" if bind.dialect.name == "postgresql" else "'property_loan'"
    )
    report_category_literal = (
        "'darlehen_und_kredite'::liabilityreportcategory"
        if bind.dialect.name == "postgresql"
        else "'darlehen_und_kredite'"
    )

    op.execute(
        sa.text(
            f"""
            INSERT INTO liabilities (
                user_id,
                liability_type,
                display_name,
                currency,
                lender_name,
                principal_amount,
                outstanding_balance,
                interest_rate,
                start_date,
                end_date,
                monthly_payment,
                tax_relevant,
                tax_relevance_reason,
                report_category,
                linked_property_id,
                linked_loan_id,
                source_document_id,
                is_active,
                notes,
                created_at,
                updated_at
            )
            SELECT
                pl.user_id,
                {liability_type_literal},
                COALESCE(pl.lender_name, 'Property loan') || ' mortgage',
                'EUR',
                COALESCE(pl.lender_name, 'Unknown lender'),
                pl.loan_amount,
                pl.loan_amount,
                pl.interest_rate,
                pl.start_date,
                pl.end_date,
                pl.monthly_payment,
                true,
                'Property loan linked to rental/property financing',
                {report_category_literal},
                pl.property_id,
                pl.id,
                pl.loan_contract_document_id,
                CASE
                    WHEN pl.end_date IS NULL OR pl.end_date >= CURRENT_DATE THEN true
                    ELSE false
                END,
                pl.notes,
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            FROM property_loans pl
            """
        )
    )

    transaction_type_literal = (
        "'LIABILITY_DRAWDOWN'::transactiontype"
        if bind.dialect.name == "postgresql"
        else "'LIABILITY_DRAWDOWN'"
    )
    op.execute(
        sa.text(
            f"""
            INSERT INTO transactions (
                user_id,
                property_id,
                liability_id,
                type,
                amount,
                transaction_date,
                description,
                is_deductible,
                classification_confidence,
                reviewed,
                locked,
                is_system_generated,
                import_source,
                is_recurring,
                recurring_is_active,
                created_at,
                updated_at
            )
            SELECT
                l.user_id,
                l.linked_property_id,
                l.id,
                {transaction_type_literal},
                l.outstanding_balance,
                l.start_date,
                'Opening balance - ' || l.display_name,
                false,
                1.00,
                true,
                true,
                true,
                'liability_migration',
                false,
                false,
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            FROM liabilities l
            WHERE l.linked_loan_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1
                  FROM transactions t
                  WHERE t.liability_id = l.id
                    AND t.type = {transaction_type_literal}
              )
            """
        )
    )

    op.execute(
        sa.text(
            """
            UPDATE recurring_transactions rt
            SET liability_id = l.id
            FROM liabilities l
            WHERE rt.loan_id = l.linked_loan_id
              AND rt.liability_id IS NULL
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_transactions_liability_id", table_name="transactions")
    op.drop_column("transactions", "liability_id")

    op.drop_index("ix_recurring_transactions_liability_id", table_name="recurring_transactions")
    op.drop_column("recurring_transactions", "liability_id")

    op.drop_index("ix_liabilities_is_active", table_name="liabilities")
    op.drop_index("ix_liabilities_source_document_id", table_name="liabilities")
    op.drop_index("ix_liabilities_linked_loan_id", table_name="liabilities")
    op.drop_index("ix_liabilities_linked_property_id", table_name="liabilities")
    op.drop_index("ix_liabilities_tax_relevant", table_name="liabilities")
    op.drop_index("ix_liabilities_liability_type", table_name="liabilities")
    op.drop_index("ix_liabilities_user_id", table_name="liabilities")
    op.drop_table("liabilities")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        report_category_enum.drop(bind, checkfirst=True)
        liability_type_enum.drop(bind, checkfirst=True)
