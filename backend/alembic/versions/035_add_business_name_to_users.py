"""Add business_name column to users for self-employed company name.

Revision ID: 035_add_business_name
Revises: 034_add_business_type
Create Date: 2026-03-15
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '035_add_business_name'
down_revision = '034_add_business_type'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column(
        'business_name',
        sa.String(255),
        nullable=True,
    ))


def downgrade() -> None:
    op.drop_column('users', 'business_name')
