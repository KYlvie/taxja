"""Add asset disposal differentiation fields.

- Extend propertystatus enum with 'scrapped' and 'withdrawn' values.
- Add disposal_reason column to properties table.
- Backfill disposal_reason = 'sold' for existing sold properties.

Revision ID: 064_add_asset_disposal_fields
Revises: 063_add_liability_source_type
Create Date: 2026-03-22
"""

from alembic import op
import sqlalchemy as sa


revision = "064_add_asset_disposal_fields"
down_revision = "063_add_liability_source_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Extend the propertystatus enum with new values.
    # PostgreSQL ALTER TYPE ... ADD VALUE cannot run inside a transaction,
    # so we use autocommit execution via raw connection.
    op.execute("ALTER TYPE propertystatus ADD VALUE IF NOT EXISTS 'scrapped'")
    op.execute("ALTER TYPE propertystatus ADD VALUE IF NOT EXISTS 'withdrawn'")

    # Add disposal_reason column
    op.add_column(
        "properties",
        sa.Column("disposal_reason", sa.String(30), nullable=True),
    )

    # Backfill: set disposal_reason = 'sold' for existing sold properties
    op.execute(
        "UPDATE properties SET disposal_reason = 'sold' WHERE status = 'sold'"
    )


def downgrade() -> None:
    op.drop_column("properties", "disposal_reason")
    # Note: PostgreSQL does not support removing values from an enum type.
    # To fully downgrade the enum, a more complex migration with type
    # recreation would be needed. Leaving the enum values in place is safe.
