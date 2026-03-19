"""Add user_classification_rules and transaction_line_items tables.

Revision ID: 039_user_rules_line_items
Revises: 038_cls_method
Create Date: 2026-03-16
"""
from alembic import op
import sqlalchemy as sa

revision = "039_user_rules_line_items"
down_revision = "038_cls_method"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Per-user classification rules
    op.create_table(
        "user_classification_rules",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("normalized_description", sa.String(300), nullable=False, index=True),
        sa.Column("original_description", sa.String(500), nullable=True),
        sa.Column("txn_type", sa.String(20), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("hit_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("confidence", sa.Numeric(3, 2), nullable=False, server_default="1.00"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "user_id", "normalized_description", "txn_type",
            name="uq_user_description_type",
        ),
    )

    # 2. Transaction line items
    op.create_table(
        "transaction_line_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "transaction_id", sa.Integer(),
            sa.ForeignKey("transactions.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("is_deductible", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deduction_reason", sa.String(500), nullable=True),
        sa.Column("vat_rate", sa.Numeric(5, 4), nullable=True),
        sa.Column("vat_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("classification_method", sa.String(20), nullable=True),
        sa.Column("classification_confidence", sa.Numeric(3, 2), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("transaction_line_items")
    op.drop_table("user_classification_rules")
