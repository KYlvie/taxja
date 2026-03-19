"""Add building_use and eco_standard columns to properties.

building_use: residential (1.5% AfA) vs commercial (2.5% AfA) per §8 Abs 1 EStG.
eco_standard: enables extended 3× AfA for 3 years on 2024-2026 residential builds.

Revision ID: 043
Revises: 042
"""
from alembic import op
import sqlalchemy as sa

revision = "043"
down_revision = "042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add building_use enum column with default 'residential'
    building_use_enum = sa.Enum("residential", "commercial", name="buildinguse")
    building_use_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "properties",
        sa.Column(
            "building_use",
            building_use_enum,
            nullable=False,
            server_default="residential",
        ),
    )

    # Add eco_standard boolean
    op.add_column(
        "properties",
        sa.Column(
            "eco_standard",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("properties", "eco_standard")
    op.drop_column("properties", "building_use")

    building_use_enum = sa.Enum("residential", "commercial", name="buildinguse")
    building_use_enum.drop(op.get_bind(), checkfirst=True)
