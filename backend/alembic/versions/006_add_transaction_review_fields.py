"""Add reviewed and locked fields to transactions

Revision ID: 006
Revises: 005
Create Date: 2024-01-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add reviewed field to transactions table
    op.add_column('transactions', sa.Column('reviewed', sa.Boolean(), nullable=False, server_default='false'))
    
    # Add locked field to transactions table
    op.add_column('transactions', sa.Column('locked', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    # Remove locked field from transactions table
    op.drop_column('transactions', 'locked')
    
    # Remove reviewed field from transactions table
    op.drop_column('transactions', 'reviewed')
