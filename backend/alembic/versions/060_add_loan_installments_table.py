"""Add loan_installments table for principal and interest breakdowns.

Revision ID: 060_add_loan_installments
Revises: 059_extended_txn_types
Create Date: 2026-03-21
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "060_add_loan_installments"
down_revision = "059_extended_txn_types"
branch_labels = None
depends_on = None


loan_installment_source = postgresql.ENUM(
    "estimated",
    "manual",
    "bank_statement",
    "zinsbescheinigung",
    name="loaninstallmentsource",
    create_type=False,
)

loan_installment_status = postgresql.ENUM(
    "scheduled",
    "posted",
    "reconciled",
    "overridden",
    name="loaninstallmentstatus",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    loan_installment_source.create(bind, checkfirst=True)
    loan_installment_status.create(bind, checkfirst=True)

    op.create_table(
        "loan_installments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("loan_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("actual_payment_date", sa.Date(), nullable=True),
        sa.Column("tax_year", sa.Integer(), nullable=False),
        sa.Column("scheduled_payment", sa.Numeric(12, 2), nullable=False),
        sa.Column("principal_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("interest_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("remaining_balance_after", sa.Numeric(12, 2), nullable=False),
        sa.Column("source", loan_installment_source, nullable=False),
        sa.Column("status", loan_installment_status, nullable=False),
        sa.Column("source_document_id", sa.Integer(), nullable=True),
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("scheduled_payment > 0", name="check_installment_payment_positive"),
        sa.CheckConstraint("principal_amount >= 0", name="check_installment_principal_non_negative"),
        sa.CheckConstraint("interest_amount >= 0", name="check_installment_interest_non_negative"),
        sa.CheckConstraint(
            "remaining_balance_after >= 0",
            name="check_installment_remaining_balance_non_negative",
        ),
        sa.ForeignKeyConstraint(["loan_id"], ["property_loans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("loan_id", "due_date", name="uq_loan_installments_loan_due_date"),
    )
    op.create_index(op.f("ix_loan_installments_id"), "loan_installments", ["id"], unique=False)
    op.create_index(op.f("ix_loan_installments_loan_id"), "loan_installments", ["loan_id"], unique=False)
    op.create_index(op.f("ix_loan_installments_user_id"), "loan_installments", ["user_id"], unique=False)
    op.create_index(op.f("ix_loan_installments_due_date"), "loan_installments", ["due_date"], unique=False)
    op.create_index(op.f("ix_loan_installments_tax_year"), "loan_installments", ["tax_year"], unique=False)
    op.create_index(
        op.f("ix_loan_installments_source_document_id"),
        "loan_installments",
        ["source_document_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_loan_installments_source_document_id"), table_name="loan_installments")
    op.drop_index(op.f("ix_loan_installments_tax_year"), table_name="loan_installments")
    op.drop_index(op.f("ix_loan_installments_due_date"), table_name="loan_installments")
    op.drop_index(op.f("ix_loan_installments_user_id"), table_name="loan_installments")
    op.drop_index(op.f("ix_loan_installments_loan_id"), table_name="loan_installments")
    op.drop_index(op.f("ix_loan_installments_id"), table_name="loan_installments")
    op.drop_table("loan_installments")

    bind = op.get_bind()
    loan_installment_status.drop(bind, checkfirst=True)
    loan_installment_source.drop(bind, checkfirst=True)
