"""Create credit billing tables: credit_balances, credit_ledger,
credit_cost_configs, topup_purchases, credit_topup_packages.

Plan extension fields (monthly_credits, overage_price_per_credit) were
already added in migration 052.

Revision ID: 053
Revises: 052
Create Date: 2026-03-21
"""
import sqlalchemy as sa
from alembic import op

revision = "053"
down_revision = "052"
branch_labels = None
depends_on = None

# Enum definitions
credit_operation_enum = sa.Enum(
    "deduction",
    "refund",
    "monthly_reset",
    "topup",
    "topup_expiry",
    "overage_settlement",
    "admin_adjustment",
    "migration",
    name="creditoperation",
)

credit_source_enum = sa.Enum(
    "plan",
    "topup",
    "overage",
    "mixed",
    name="creditsource",
)

credit_ledger_status_enum = sa.Enum(
    "settled",
    "reserved",
    "reversed",
    "failed",
    name="creditledgerstatus",
)


def upgrade() -> None:
    # ── credit_balances ──────────────────────────────────────────────
    op.create_table(
        "credit_balances",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
            index=True,
        ),
        sa.Column("plan_balance", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("topup_balance", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "overage_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "overage_credits_used", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "has_unpaid_overage",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "unpaid_overage_periods", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        # CHECK constraints
        sa.CheckConstraint(
            "plan_balance >= 0",
            name="ck_credit_balances_plan_balance_non_negative",
        ),
        sa.CheckConstraint(
            "topup_balance >= 0",
            name="ck_credit_balances_topup_balance_non_negative",
        ),
        sa.CheckConstraint(
            "overage_credits_used >= 0",
            name="ck_credit_balances_overage_credits_used_non_negative",
        ),
        sa.CheckConstraint(
            "unpaid_overage_periods >= 0",
            name="ck_credit_balances_unpaid_overage_periods_non_negative",
        ),
    )

    # ── credit_ledger ────────────────────────────────────────────────
    op.create_table(
        "credit_ledger",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("operation", credit_operation_enum, nullable=False),
        sa.Column("operation_detail", sa.String(100), nullable=True),
        sa.Column(
            "status",
            credit_ledger_status_enum,
            nullable=False,
            server_default="settled",
            index=True,
        ),
        sa.Column("credit_amount", sa.Integer(), nullable=False),
        sa.Column(
            "source",
            credit_source_enum,
            nullable=False,
            server_default="plan",
        ),
        sa.Column("plan_balance_after", sa.Integer(), nullable=False),
        sa.Column("topup_balance_after", sa.Integer(), nullable=False),
        sa.Column(
            "is_overage",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("overage_portion", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("context_type", sa.String(50), nullable=True),
        sa.Column("context_id", sa.Integer(), nullable=True),
        sa.Column("reference_id", sa.String(255), nullable=True),
        sa.Column("reservation_id", sa.String(255), nullable=True),
        sa.Column("reason", sa.String(200), nullable=True),
        sa.Column("pricing_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        # CHECK constraints
        sa.CheckConstraint(
            "credit_amount != 0",
            name="ck_credit_ledger_amount_nonzero",
        ),
        sa.CheckConstraint(
            "plan_balance_after >= 0",
            name="ck_credit_ledger_plan_balance_after_non_negative",
        ),
        sa.CheckConstraint(
            "topup_balance_after >= 0",
            name="ck_credit_ledger_topup_balance_after_non_negative",
        ),
        sa.CheckConstraint(
            "overage_portion >= 0",
            name="ck_credit_ledger_overage_portion_non_negative",
        ),
    )

    # Composite indexes for credit_ledger
    op.create_index(
        "ix_credit_ledger_user_created",
        "credit_ledger",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_credit_ledger_user_operation",
        "credit_ledger",
        ["user_id", "operation"],
    )
    op.create_index(
        "ix_credit_ledger_context",
        "credit_ledger",
        ["context_type", "context_id"],
    )

    # Partial unique index for refund idempotency
    op.create_index(
        "uq_credit_ledger_refund_key",
        "credit_ledger",
        ["user_id", "reference_id"],
        unique=True,
        postgresql_where=sa.text(
            "operation = 'refund' AND reference_id IS NOT NULL"
        ),
    )

    # ── credit_cost_configs ──────────────────────────────────────────
    op.create_table(
        "credit_cost_configs",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "operation",
            sa.String(50),
            nullable=False,
            unique=True,
            index=True,
        ),
        sa.Column("credit_cost", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(200), nullable=True),
        sa.Column("pricing_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # ── topup_purchases ──────────────────────────────────────────────
    op.create_table(
        "topup_purchases",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("credits_purchased", sa.Integer(), nullable=False),
        sa.Column("credits_remaining", sa.Integer(), nullable=False),
        sa.Column("price_paid", sa.Numeric(10, 2), nullable=False),
        sa.Column("stripe_payment_id", sa.String(255), nullable=True),
        sa.Column(
            "purchased_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column(
            "is_expired",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # ── credit_topup_packages ────────────────────────────────────────
    op.create_table(
        "credit_topup_packages",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("credits", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("stripe_price_id", sa.String(255), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table("credit_topup_packages")
    op.drop_table("topup_purchases")
    op.drop_table("credit_cost_configs")

    # Drop indexes before dropping credit_ledger table
    op.drop_index("uq_credit_ledger_refund_key", table_name="credit_ledger")
    op.drop_index("ix_credit_ledger_context", table_name="credit_ledger")
    op.drop_index("ix_credit_ledger_user_operation", table_name="credit_ledger")
    op.drop_index("ix_credit_ledger_user_created", table_name="credit_ledger")
    op.drop_table("credit_ledger")

    op.drop_table("credit_balances")

    # Drop enums
    credit_ledger_status_enum.drop(op.get_bind(), checkfirst=True)
    credit_source_enum.drop(op.get_bind(), checkfirst=True)
    credit_operation_enum.drop(op.get_bind(), checkfirst=True)
