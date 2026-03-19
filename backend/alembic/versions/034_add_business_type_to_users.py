"""Add business_type column to users for self-employed sub-type.

Revision ID: 034_add_business_type
Revises: 033
Create Date: 2026-03-15
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '034_add_business_type'
down_revision = '033'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum type
    selfemployedtype = sa.Enum(
        'freiberufler', 'gewerbetreibende', 'neue_selbstaendige', 'land_forstwirtschaft',
        name='selfemployedtype',
    )
    selfemployedtype.create(op.get_bind(), checkfirst=True)

    # Add nullable column (only relevant for self_employed/mixed users)
    op.add_column('users', sa.Column(
        'business_type',
        sa.Enum('freiberufler', 'gewerbetreibende', 'neue_selbstaendige', 'land_forstwirtschaft',
                name='selfemployedtype', create_type=False),
        nullable=True,
    ))


def downgrade() -> None:
    op.drop_column('users', 'business_type')

    # Drop enum type
    sa.Enum(name='selfemployedtype').drop(op.get_bind(), checkfirst=True)
