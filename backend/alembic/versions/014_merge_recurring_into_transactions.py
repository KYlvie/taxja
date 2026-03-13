"""Add recurring fields to transactions table and asset_type to properties

Revision ID: 014
Revises: e3266d27ea40
Create Date: 2026-03-10
"""
from alembic import op
import sqlalchemy as sa

revision = '014'
down_revision = 'e3266d27ea40'
branch_labels = None
depends_on = None


def upgrade():
    # === Part 1: Add recurring fields to transactions ===
    op.add_column('transactions', sa.Column('is_recurring', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('transactions', sa.Column('recurring_frequency', sa.String(20), nullable=True))
    op.add_column('transactions', sa.Column('recurring_start_date', sa.Date(), nullable=True))
    op.add_column('transactions', sa.Column('recurring_end_date', sa.Date(), nullable=True))
    op.add_column('transactions', sa.Column('recurring_day_of_month', sa.Integer(), nullable=True))
    op.add_column('transactions', sa.Column('recurring_is_active', sa.Boolean(), server_default='true', nullable=False))
    op.add_column('transactions', sa.Column('recurring_next_date', sa.Date(), nullable=True))
    op.add_column('transactions', sa.Column('recurring_last_generated', sa.Date(), nullable=True))
    op.add_column('transactions', sa.Column('parent_recurring_id', sa.Integer(), nullable=True))
    
    # Index for recurring queries
    op.create_index('ix_transactions_is_recurring', 'transactions', ['is_recurring'])
    op.create_index('ix_transactions_parent_recurring_id', 'transactions', ['parent_recurring_id'])
    op.create_index('ix_transactions_recurring_next_date', 'transactions', ['recurring_next_date'])
    
    # Self-referential FK: generated transactions point back to the recurring "template" transaction
    op.create_foreign_key(
        'fk_transactions_parent_recurring',
        'transactions', 'transactions',
        ['parent_recurring_id'], ['id'],
        ondelete='SET NULL'
    )

    # === Part 2: Add asset_type and sub_category to properties ===
    op.add_column('properties', sa.Column('asset_type', sa.String(50), server_default='real_estate', nullable=False))
    op.add_column('properties', sa.Column('sub_category', sa.String(100), nullable=True))
    op.add_column('properties', sa.Column('name', sa.String(255), nullable=True))
    op.add_column('properties', sa.Column('useful_life_years', sa.Integer(), nullable=True))
    op.add_column('properties', sa.Column('business_use_percentage', sa.Numeric(5, 2), server_default='100', nullable=False))
    op.add_column('properties', sa.Column('supplier', sa.String(255), nullable=True))
    op.add_column('properties', sa.Column('accumulated_depreciation', sa.Numeric(12, 2), server_default='0', nullable=False))
    
    op.create_index('ix_properties_asset_type', 'properties', ['asset_type'])

    # Migrate existing recurring_transactions data into transactions
    # This is done via a Python script after migration, not in the migration itself


def downgrade():
    # Remove asset fields from properties
    op.drop_index('ix_properties_asset_type', table_name='properties')
    op.drop_column('properties', 'accumulated_depreciation')
    op.drop_column('properties', 'supplier')
    op.drop_column('properties', 'business_use_percentage')
    op.drop_column('properties', 'useful_life_years')
    op.drop_column('properties', 'name')
    op.drop_column('properties', 'sub_category')
    op.drop_column('properties', 'asset_type')

    # Remove recurring fields from transactions
    op.drop_constraint('fk_transactions_parent_recurring', 'transactions', type_='foreignkey')
    op.drop_index('ix_transactions_recurring_next_date', table_name='transactions')
    op.drop_index('ix_transactions_parent_recurring_id', table_name='transactions')
    op.drop_index('ix_transactions_is_recurring', table_name='transactions')
    op.drop_column('transactions', 'parent_recurring_id')
    op.drop_column('transactions', 'recurring_last_generated')
    op.drop_column('transactions', 'recurring_next_date')
    op.drop_column('transactions', 'recurring_is_active')
    op.drop_column('transactions', 'recurring_day_of_month')
    op.drop_column('transactions', 'recurring_end_date')
    op.drop_column('transactions', 'recurring_start_date')
    op.drop_column('transactions', 'recurring_frequency')
    op.drop_column('transactions', 'is_recurring')
