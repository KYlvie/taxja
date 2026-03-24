"""Add BAO retention fields and ImmoESt property fields

Revision ID: 031_bao_retention
Revises: 030_add_performance_indexes_100k
Create Date: 2026-03-15
"""
from alembic import op
import sqlalchemy as sa

revision = "031_bao_retention"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # BAO §132 retention expiry on users table
    op.add_column("users", sa.Column("bao_retention_expiry", sa.DateTime(), nullable=True))

    # ImmoESt fields on properties table
    op.add_column("properties", sa.Column("sale_price", sa.Numeric(12, 2), nullable=True))
    op.add_column("properties", sa.Column("hauptwohnsitz", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("properties", sa.Column("selbst_errichtet", sa.Boolean(), nullable=False, server_default=sa.text("false")))


def downgrade() -> None:
    op.drop_column("properties", "selbst_errichtet")
    op.drop_column("properties", "hauptwohnsitz")
    op.drop_column("properties", "sale_price")
    op.drop_column("users", "bao_retention_expiry")
