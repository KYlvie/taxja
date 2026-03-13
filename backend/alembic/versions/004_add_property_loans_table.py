"""add_property_loans_table

Revision ID: 004
Revises: 003
Create Date: 2026-03-07

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003a'
branch_labels = None
depends_on = None


def upgrade():
    """Create property_loans table"""
    op.create_table(
        'property_loans',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('property_id', UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('loan_amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('interest_rate', sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('monthly_payment', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('lender_name', sa.String(length=255), nullable=False),
        sa.Column('lender_account', sa.String(length=100), nullable=True),
        sa.Column('loan_type', sa.String(length=50), nullable=True),
        sa.Column('notes', sa.String(length=1000), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['property_id'], ['properties.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.CheckConstraint('loan_amount > 0', name='check_loan_amount_positive'),
        sa.CheckConstraint('interest_rate >= 0 AND interest_rate <= 0.20', name='check_interest_rate_range'),
        sa.CheckConstraint('monthly_payment > 0', name='check_monthly_payment_positive'),
        sa.CheckConstraint('end_date IS NULL OR end_date >= start_date', name='check_end_date_after_start')
    )
    
    # Create indexes
    op.create_index('ix_property_loans_id', 'property_loans', ['id'])
    op.create_index('ix_property_loans_property_id', 'property_loans', ['property_id'])
    op.create_index('ix_property_loans_user_id', 'property_loans', ['user_id'])


def downgrade():
    """Drop property_loans table"""
    op.drop_index('ix_property_loans_user_id', table_name='property_loans')
    op.drop_index('ix_property_loans_property_id', table_name='property_loans')
    op.drop_index('ix_property_loans_id', table_name='property_loans')
    op.drop_table('property_loans')
