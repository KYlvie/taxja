"""Add performance indexes

Revision ID: add_performance_indexes
Revises: add_chat_messages
Create Date: 2026-03-04

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_performance_indexes'
down_revision = 'add_chat_messages'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add indexes for common query patterns"""
    
    # Transaction indexes
    op.create_index(
        'ix_transactions_user_id_date',
        'transactions',
        ['user_id', 'transaction_date'],
        unique=False
    )
    op.create_index(
        'ix_transactions_type_category',
        'transactions',
        ['type', 'income_category', 'expense_category'],
        unique=False
    )
    op.create_index(
        'ix_transactions_is_deductible',
        'transactions',
        ['user_id', 'is_deductible'],
        unique=False,
        postgresql_where=sa.text('is_deductible = true')
    )
    
    # Document indexes
    op.create_index(
        'ix_documents_user_id_type',
        'documents',
        ['user_id', 'document_type'],
        unique=False
    )
    op.create_index(
        'ix_documents_user_id_uploaded',
        'documents',
        ['user_id', 'uploaded_at'],
        unique=False
    )
    
    # User indexes (email already has unique constraint)
    op.create_index(
        'ix_users_user_type',
        'users',
        ['user_type'],
        unique=False
    )


def downgrade() -> None:
    """Remove performance indexes"""
    
    # Transaction indexes
    op.drop_index('ix_transactions_user_id_date', table_name='transactions')
    op.drop_index('ix_transactions_type_category', table_name='transactions')
    op.drop_index('ix_transactions_is_deductible', table_name='transactions')
    
    # Document indexes
    op.drop_index('ix_documents_user_id_type', table_name='documents')
    op.drop_index('ix_documents_user_id_uploaded', table_name='documents')
    
    # User indexes
    op.drop_index('ix_users_user_type', table_name='users')
