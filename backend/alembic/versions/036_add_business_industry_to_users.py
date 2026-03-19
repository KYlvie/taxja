"""Add business_industry column to users for industry-specific deductibility.

Revision ID: 036_add_business_industry
Revises: 035_add_business_name
Create Date: 2026-03-15
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '036_add_business_industry'
down_revision = '035_add_business_name'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column(
        'business_industry',
        sa.String(50),
        nullable=True,
    ))


def downgrade() -> None:
    op.drop_column('users', 'business_industry')
