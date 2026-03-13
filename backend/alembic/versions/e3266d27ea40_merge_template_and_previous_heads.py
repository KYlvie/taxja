"""merge template and previous heads

Revision ID: e3266d27ea40
Revises: 013, fc5c016e0508
Create Date: 2026-03-08 20:28:56.095656

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e3266d27ea40'
down_revision = ('013', 'fc5c016e0508')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
