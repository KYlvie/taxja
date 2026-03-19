"""Add explicit recurring template link to transactions

Revision ID: 020
Revises: 019
Create Date: 2026-03-14 12:30:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    column_names = {column["name"] for column in inspector.get_columns("transactions")}
    if "source_recurring_id" not in column_names:
        op.add_column(
            "transactions",
            sa.Column("source_recurring_id", sa.Integer(), nullable=True),
        )

    fk_names = {fk["name"] for fk in inspector.get_foreign_keys("transactions")}
    fk_name = "fk_transactions_source_recurring_id"
    if fk_name not in fk_names:
        op.create_foreign_key(
            fk_name,
            "transactions",
            "recurring_transactions",
            ["source_recurring_id"],
            ["id"],
            ondelete="SET NULL",
        )

    index_names = {index["name"] for index in inspector.get_indexes("transactions")}
    index_name = "ix_transactions_source_recurring_id"
    if index_name not in index_names:
        op.create_index(
            index_name,
            "transactions",
            ["source_recurring_id"],
            if_not_exists=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    index_names = {index["name"] for index in inspector.get_indexes("transactions")}
    index_name = "ix_transactions_source_recurring_id"
    if index_name in index_names:
        op.drop_index(index_name, table_name="transactions")

    fk_names = {fk["name"] for fk in inspector.get_foreign_keys("transactions")}
    fk_name = "fk_transactions_source_recurring_id"
    if fk_name in fk_names:
        op.drop_constraint(fk_name, "transactions", type_="foreignkey")

    column_names = {column["name"] for column in inspector.get_columns("transactions")}
    if "source_recurring_id" in column_names:
        op.drop_column("transactions", "source_recurring_id")
