"""Add persisted tax profile fields to users.

Revision ID: 055_add_user_tax_profile_fields
Revises: 025, 054, 4d360f36c47b
Create Date: 2026-03-19
"""
from alembic import op
import sqlalchemy as sa


revision = "055_add_user_tax_profile_fields"
down_revision = ("025", "054", "4d360f36c47b")
branch_labels = None
depends_on = None


vat_status_enum = sa.Enum(
    "regelbesteuert",
    "kleinunternehmer",
    "pauschaliert",
    "unknown",
    name="vatstatus",
)
gewinnermittlungsart_enum = sa.Enum(
    "bilanzierung",
    "ea_rechnung",
    "pauschal",
    "unknown",
    name="gewinnermittlungsart",
)


def upgrade() -> None:
    bind = op.get_bind()
    vat_status_enum.create(bind, checkfirst=True)
    gewinnermittlungsart_enum.create(bind, checkfirst=True)

    op.add_column("users", sa.Column("vat_status", vat_status_enum, nullable=True))
    op.add_column(
        "users",
        sa.Column("gewinnermittlungsart", gewinnermittlungsart_enum, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "gewinnermittlungsart")
    op.drop_column("users", "vat_status")

    bind = op.get_bind()
    gewinnermittlungsart_enum.drop(bind, checkfirst=True)
    vat_status_enum.drop(bind, checkfirst=True)
