"""Add vat_type field to transactions

Revision ID: 032_add_vat_type
Revises: 031_bao_retention
Create Date: 2026-03-15
"""
from alembic import op
import sqlalchemy as sa

revision = "032_add_vat_type"
down_revision = None  # Adjust to actual head
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create the VatType enum
    vat_type_enum = sa.Enum(
        "domestic", "intra_community", "reverse_charge", "import", "exempt",
        name="vattype",
    )
    vat_type_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "transactions",
        sa.Column("vat_type", vat_type_enum, nullable=True, server_default="domestic"),
    )


def downgrade() -> None:
    op.drop_column("transactions", "vat_type")
    sa.Enum(name="vattype").drop(op.get_bind(), checkfirst=True)
