"""Add is_archived and archived_at columns to documents table

Revision ID: add_document_archival
Revises: add_performance_indexes
Create Date: 2026-03-05
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_document_archival'
down_revision = 'add_performance_indexes'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('documents', sa.Column('is_archived', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('documents', sa.Column('archived_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('documents', 'archived_at')
    op.drop_column('documents', 'is_archived')
