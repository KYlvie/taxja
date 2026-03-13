"""Add property table for rental property asset management

Revision ID: 002
Revises: 001
Create Date: 2026-03-07 14:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create property_type enum
    property_type_enum = postgresql.ENUM('rental', 'owner_occupied', 'mixed_use', name='propertytype')
    property_type_enum.create(op.get_bind())
    
    # Create property_status enum
    property_status_enum = postgresql.ENUM('active', 'sold', 'archived', name='propertystatus')
    property_status_enum.create(op.get_bind())
    
    # Create properties table
    op.create_table(
        'properties',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', sa.Integer(), nullable=False),
        
        # Property classification
        sa.Column('property_type', postgresql.ENUM('rental', 'owner_occupied', 'mixed_use', name='propertytype'), nullable=False, server_default='rental'),
        sa.Column('rental_percentage', sa.Numeric(precision=5, scale=2), nullable=False, server_default='100.00'),
        
        # Address fields
        sa.Column('address', sa.String(length=500), nullable=False),
        sa.Column('street', sa.String(length=255), nullable=False),
        sa.Column('city', sa.String(length=100), nullable=False),
        sa.Column('postal_code', sa.String(length=10), nullable=False),
        
        # Purchase information
        sa.Column('purchase_date', sa.Date(), nullable=False),
        sa.Column('purchase_price', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('building_value', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('land_value', sa.Numeric(precision=12, scale=2), nullable=True),
        
        # Purchase costs (for owner-occupied tracking and capital gains calculations)
        sa.Column('grunderwerbsteuer', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('notary_fees', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('registry_fees', sa.Numeric(precision=12, scale=2), nullable=True),
        
        # Building details
        sa.Column('construction_year', sa.Integer(), nullable=True),
        sa.Column('depreciation_rate', sa.Numeric(precision=5, scale=4), nullable=False, server_default='0.02'),
        
        # Status
        sa.Column('status', postgresql.ENUM('active', 'sold', 'archived', name='propertystatus'), nullable=False, server_default='active'),
        sa.Column('sale_date', sa.Date(), nullable=True),
        
        # Document references
        sa.Column('kaufvertrag_document_id', sa.Integer(), nullable=True),
        sa.Column('mietvertrag_document_id', sa.Integer(), nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        
        # Primary key
        sa.PrimaryKeyConstraint('id'),
        
        # Foreign keys
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['kaufvertrag_document_id'], ['documents.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['mietvertrag_document_id'], ['documents.id'], ondelete='SET NULL'),
        
        # Check constraints
        sa.CheckConstraint('rental_percentage >= 0 AND rental_percentage <= 100', name='check_rental_percentage_range'),
        sa.CheckConstraint('purchase_price > 0 AND purchase_price <= 100000000', name='check_purchase_price_range'),
        sa.CheckConstraint('building_value > 0 AND building_value <= purchase_price', name='check_building_value_range'),
        sa.CheckConstraint('depreciation_rate >= 0.001 AND depreciation_rate <= 0.10', name='check_depreciation_rate_range'),
        sa.CheckConstraint("construction_year IS NULL OR (construction_year >= 1800 AND construction_year <= EXTRACT(YEAR FROM CURRENT_DATE))", name='check_construction_year_range'),
        sa.CheckConstraint('sale_date IS NULL OR sale_date >= purchase_date', name='check_sale_date_after_purchase'),
        sa.CheckConstraint("status != 'sold' OR sale_date IS NOT NULL", name='check_sold_has_sale_date'),
    )
    
    # Create indexes
    op.create_index('ix_properties_user_id', 'properties', ['user_id'])
    op.create_index('ix_properties_status', 'properties', ['status'])
    op.create_index('ix_properties_user_status', 'properties', ['user_id', 'status'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_properties_user_status', table_name='properties')
    op.drop_index('ix_properties_status', table_name='properties')
    op.drop_index('ix_properties_user_id', table_name='properties')
    
    # Drop table
    op.drop_table('properties')
    
    # Drop enums
    property_status_enum = postgresql.ENUM('active', 'sold', 'archived', name='propertystatus')
    property_status_enum.drop(op.get_bind())
    
    property_type_enum = postgresql.ENUM('rental', 'owner_occupied', 'mixed_use', name='propertytype')
    property_type_enum.drop(op.get_bind())
