"""Add telearbeit_days and employer_telearbeit_pauschale to users.

Revision ID: 044_telearbeit
Revises: 043
Create Date: 2026-03-16
"""

from alembic import op
import sqlalchemy as sa


revision = "044_telearbeit"
down_revision = "043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("telearbeit_days", sa.Integer(), nullable=True))
    op.add_column(
        "users",
        sa.Column("employer_telearbeit_pauschale", sa.Numeric(10, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "employer_telearbeit_pauschale")
    op.drop_column("users", "telearbeit_days")
