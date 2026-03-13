"""add_property_performance_indexes

Revision ID: 006a
Revises: 006
Create Date: 2026-03-07

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '006a'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade():
    """Add performance indexes for property and transaction queries"""
    
    # Property indexes
    # Note: idx_properties_user_id already exists from model definition (index=True)
    # We'll create it conditionally or skip if it exists
    
    # Index for filtering properties by status
    op.create_index(
        'idx_properties_status',
        'properties',
        ['status'],
        unique=False
    )
    
    # Composite index for filtering properties by user and status
    op.create_index(
        'idx_properties_user_status',
        'properties',
        ['user_id', 'status'],
        unique=False
    )
    
    # Transaction indexes for property-related queries
    # Note: idx_transactions_property_id already exists from model definition (index=True)
    
    # Composite index for finding transactions by property and date range
    op.create_index(
        'idx_transactions_property_date',
        'transactions',
        ['property_id', 'transaction_date'],
        unique=False
    )
    
    # Index for finding depreciation transactions (system-generated)
    op.create_index(
        'idx_transactions_depreciation',
        'transactions',
        ['is_system_generated'],
        unique=False
    )


def downgrade():
    """Remove property performance indexes"""
    
    # Drop transaction indexes
    op.drop_index('idx_transactions_depreciation', table_name='transactions')
    op.drop_index('idx_transactions_property_date', table_name='transactions')
    
    # Drop property indexes
    op.drop_index('idx_properties_user_status', table_name='properties')
    op.drop_index('idx_properties_status', table_name='properties')
