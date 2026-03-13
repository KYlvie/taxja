"""Add property_id and is_system_generated to transactions table

Revision ID: 003a
Revises: 003_add_property_expense_categories
Create Date: 2026-03-07 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '003a'
down_revision = '003_add_property_expense_categories'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add property_id column to transactions table
    op.add_column(
        'transactions',
        sa.Column('property_id', postgresql.UUID(as_uuid=True), nullable=True)
    )
    
    # Add is_system_generated column to transactions table
    op.add_column(
        'transactions',
        sa.Column('is_system_generated', sa.Boolean(), nullable=False, server_default='false')
    )
    
    # Add foreign key constraint to properties table
    op.create_foreign_key(
        'fk_transactions_property_id',
        'transactions',
        'properties',
        ['property_id'],
        ['id'],
        ondelete='SET NULL'
    )
    
    # Create index on property_id for better query performance
    op.create_index('ix_transactions_property_id', 'transactions', ['property_id'])


def downgrade() -> None:
    # Drop index
    op.drop_index('ix_transactions_property_id', table_name='transactions')
    
    # Drop foreign key constraint
    op.drop_constraint('fk_transactions_property_id', 'transactions', type_='foreignkey')
    
    # Drop columns
    op.drop_column('transactions', 'is_system_generated')
    op.drop_column('transactions', 'property_id')
