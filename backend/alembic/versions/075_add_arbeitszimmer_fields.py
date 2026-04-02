"""Add Arbeitszimmer (home-office room) fields to users table.

Enables percentage-based deduction for tenants with a dedicated home office room.
The ratio arbeitszimmer_m2 / nutzflaeche_m2 determines the deductible share of
rent, utilities, and maintenance expenses (§20 Abs.1 Z 2 lit.d EStG).

Revision ID: 075_add_arbeitszimmer_fields
Revises: 074_add_semi_annual_frequency
Create Date: 2026-03-28 20:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "075_add_arbeitszimmer_fields"
down_revision = "075_add_rent_adjustment_document_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("arbeitszimmer_m2", sa.Numeric(6, 2), nullable=True))
    op.add_column("users", sa.Column("nutzflaeche_m2", sa.Numeric(6, 2), nullable=True))
    op.add_column("users", sa.Column("arbeitszimmer_mittelpunkt", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "arbeitszimmer_mittelpunkt")
    op.drop_column("users", "nutzflaeche_m2")
    op.drop_column("users", "arbeitszimmer_m2")
