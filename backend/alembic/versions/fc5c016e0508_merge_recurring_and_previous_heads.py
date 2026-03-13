"""merge_recurring_and_previous_heads

Revision ID: fc5c016e0508
Revises: 012, 35954ae63c9d
Create Date: 2026-03-08 19:32:00.229577

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fc5c016e0508'
down_revision = ('012', '35954ae63c9d')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
