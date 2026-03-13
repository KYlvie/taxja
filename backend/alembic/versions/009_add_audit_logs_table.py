"""Add audit logs table

Revision ID: 009
Revises: 008
Create Date: 2026-03-08 12:00:00.000000

This migration creates the audit_logs table for tracking all property-related operations.

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create audit_logs table"""
    
    # Create enum types
    op.execute("""
        CREATE TYPE auditoperationtype AS ENUM (
            'create', 'update', 'delete', 'archive',
            'link_transaction', 'unlink_transaction',
            'backfill_depreciation', 'generate_depreciation'
        )
    """)
    
    op.execute("""
        CREATE TYPE auditentitytype AS ENUM (
            'property', 'transaction', 'property_loan'
        )
    """)
    
    # Create audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('operation_type', sa.Enum(
            'create', 'update', 'delete', 'archive',
            'link_transaction', 'unlink_transaction',
            'backfill_depreciation', 'generate_depreciation',
            name='auditoperationtype'
        ), nullable=False),
        sa.Column('entity_type', sa.Enum(
            'property', 'transaction', 'property_loan',
            name='auditentitytype'
        ), nullable=False),
        sa.Column('entity_id', sa.String(length=100), nullable=False),
        sa.Column('details', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('idx_audit_user_id', 'audit_logs', ['user_id'])
    op.create_index('idx_audit_operation_type', 'audit_logs', ['operation_type'])
    op.create_index('idx_audit_entity_type', 'audit_logs', ['entity_type'])
    op.create_index('idx_audit_entity_id', 'audit_logs', ['entity_id'])
    op.create_index('idx_audit_created_at_desc', 'audit_logs', [sa.text('created_at DESC')])
    op.create_index('idx_audit_user_entity', 'audit_logs', ['user_id', 'entity_type', 'entity_id'])
    op.create_index('idx_audit_entity_operation', 'audit_logs', ['entity_type', 'entity_id', 'operation_type'])


def downgrade() -> None:
    """Drop audit_logs table"""
    
    # Drop indexes
    op.drop_index('idx_audit_entity_operation', table_name='audit_logs')
    op.drop_index('idx_audit_user_entity', table_name='audit_logs')
    op.drop_index('idx_audit_created_at_desc', table_name='audit_logs')
    op.drop_index('idx_audit_entity_id', table_name='audit_logs')
    op.drop_index('idx_audit_entity_type', table_name='audit_logs')
    op.drop_index('idx_audit_operation_type', table_name='audit_logs')
    op.drop_index('idx_audit_user_id', table_name='audit_logs')
    
    # Drop table
    op.drop_table('audit_logs')
    
    # Drop enum types
    op.execute('DROP TYPE auditentitytype')
    op.execute('DROP TYPE auditoperationtype')
