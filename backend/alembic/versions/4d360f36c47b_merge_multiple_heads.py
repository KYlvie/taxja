"""merge_multiple_heads

Revision ID: 4d360f36c47b
Revises: 022, 030_perf_indexes, 031_bao_retention, 032_add_vat_type
Create Date: 2026-03-15 19:23:45.019457

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4d360f36c47b'
down_revision = ('022', '030_perf_indexes', '031_bao_retention', '032_add_vat_type')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
