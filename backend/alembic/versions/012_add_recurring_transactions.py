"""add recurring transactions table

Revision ID: 012
Revises: 011
Create Date: 2026-03-08

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '012'
down_revision = '011'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add recurring transactions table and enums"""
    
    # Create RecurrenceFrequency enum (if not exists)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE recurrencefrequency AS ENUM (
                'monthly', 'quarterly', 'annually', 'weekly', 'biweekly'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Create RecurringTransactionType enum (if not exists)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE recurringtransactiontype AS ENUM (
                'rental_income', 'loan_interest', 'depreciation', 'manual'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Create recurring_transactions table
    op.create_table(
        'recurring_transactions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('recurring_type', sa.Enum(
            'rental_income', 'loan_interest', 'depreciation', 'manual',
            name='recurringtransactiontype'
        ), nullable=False),
        sa.Column('property_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('loan_id', sa.Integer(), nullable=True),
        sa.Column('description', sa.String(length=500), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('transaction_type', sa.String(length=20), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=False),
        sa.Column('frequency', sa.Enum(
            'monthly', 'quarterly', 'annually', 'weekly', 'biweekly',
            name='recurrencefrequency'
        ), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('day_of_month', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('paused_at', sa.DateTime(), nullable=True),
        sa.Column('last_generated_date', sa.Date(), nullable=True),
        sa.Column('next_generation_date', sa.Date(), nullable=True),
        sa.Column('notes', sa.String(length=1000), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['property_id'], ['properties.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['loan_id'], ['property_loans.id'], ondelete='CASCADE'),
        sa.CheckConstraint('amount > 0', name='check_amount_positive'),
        sa.CheckConstraint(
            "transaction_type IN ('income', 'expense')",
            name='check_transaction_type_valid'
        ),
        sa.CheckConstraint(
            'end_date IS NULL OR end_date >= start_date',
            name='check_end_date_after_start'
        ),
        sa.CheckConstraint(
            'day_of_month IS NULL OR (day_of_month >= 1 AND day_of_month <= 31)',
            name='check_day_of_month_range'
        ),
        sa.CheckConstraint(
            "(recurring_type = 'rental_income' AND property_id IS NOT NULL) OR "
            "(recurring_type = 'loan_interest' AND loan_id IS NOT NULL) OR "
            "(recurring_type = 'depreciation' AND property_id IS NOT NULL) OR "
            "(recurring_type = 'manual')",
            name='check_source_entity_required'
        ),
    )
    
    # Create indexes
    op.create_index('ix_recurring_transactions_id', 'recurring_transactions', ['id'])
    op.create_index('ix_recurring_transactions_user_id', 'recurring_transactions', ['user_id'])
    op.create_index('ix_recurring_transactions_recurring_type', 'recurring_transactions', ['recurring_type'])
    op.create_index('ix_recurring_transactions_property_id', 'recurring_transactions', ['property_id'])
    op.create_index('ix_recurring_transactions_loan_id', 'recurring_transactions', ['loan_id'])
    op.create_index('ix_recurring_transactions_is_active', 'recurring_transactions', ['is_active'])
    op.create_index('ix_recurring_transactions_next_generation_date', 'recurring_transactions', ['next_generation_date'])


def downgrade() -> None:
    """Remove recurring transactions table and enums"""
    
    # Drop indexes
    op.drop_index('ix_recurring_transactions_next_generation_date', table_name='recurring_transactions')
    op.drop_index('ix_recurring_transactions_is_active', table_name='recurring_transactions')
    op.drop_index('ix_recurring_transactions_loan_id', table_name='recurring_transactions')
    op.drop_index('ix_recurring_transactions_property_id', table_name='recurring_transactions')
    op.drop_index('ix_recurring_transactions_recurring_type', table_name='recurring_transactions')
    op.drop_index('ix_recurring_transactions_user_id', table_name='recurring_transactions')
    op.drop_index('ix_recurring_transactions_id', table_name='recurring_transactions')
    
    # Drop table
    op.drop_table('recurring_transactions')
    
    # Drop enums
    op.execute('DROP TYPE recurringtransactiontype')
    op.execute('DROP TYPE recurrencefrequency')
