"""Add employer_mode and employer_region to users

Revision ID: 045_employer_profile
Revises: 044_telearbeit
Create Date: 2026-03-17
"""
from alembic import op
import sqlalchemy as sa

revision = '045_employer_profile'
down_revision = '044_telearbeit'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('employer_mode', sa.String(length=20), nullable=False, server_default='none'),
    )
    op.add_column(
        'users',
        sa.Column('employer_region', sa.String(length=100), nullable=True),
    )
    op.alter_column('users', 'employer_mode', server_default=None)


def downgrade() -> None:
    op.drop_column('users', 'employer_region')
    op.drop_column('users', 'employer_mode')
