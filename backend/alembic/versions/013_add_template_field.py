"""add template field to recurring transactions

Revision ID: 013
Revises: 012
Create Date: 2026-03-08

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '013'
down_revision = '012'
branch_labels = None
depends_on = None


def upgrade():
    # Add template field
    op.add_column('recurring_transactions', 
        sa.Column('template', sa.String(length=50), nullable=True)
    )
    
    # Add new recurring transaction types - must be done in separate transaction
    # Use raw SQL with COMMIT to add enum values
    connection = op.get_bind()
    connection.execute(sa.text("COMMIT"))
    connection.execute(sa.text("ALTER TYPE recurringtransactiontype ADD VALUE IF NOT EXISTS 'other_income'"))
    connection.execute(sa.text("ALTER TYPE recurringtransactiontype ADD VALUE IF NOT EXISTS 'other_expense'"))
    connection.execute(sa.text("BEGIN"))
    
    # Update constraint to allow new types
    op.drop_constraint('check_source_entity_required', 'recurring_transactions', type_='check')
    op.create_check_constraint(
        'check_source_entity_required',
        'recurring_transactions',
        """
        (recurring_type = 'rental_income' AND property_id IS NOT NULL) OR
        (recurring_type = 'loan_interest' AND loan_id IS NOT NULL) OR
        (recurring_type = 'depreciation' AND property_id IS NOT NULL) OR
        (recurring_type IN ('other_income', 'other_expense', 'manual'))
        """
    )


def downgrade():
    # Remove template field
    op.drop_column('recurring_transactions', 'template')
    
    # Restore old constraint
    op.drop_constraint('check_source_entity_required', 'recurring_transactions', type_='check')
    op.create_check_constraint(
        'check_source_entity_required',
        'recurring_transactions',
        """
        (recurring_type = 'rental_income' AND property_id IS NOT NULL) OR
        (recurring_type = 'loan_interest' AND loan_id IS NOT NULL) OR
        (recurring_type = 'depreciation' AND property_id IS NOT NULL) OR
        (recurring_type = 'manual')
        """
    )
    
    # Note: Cannot remove enum values in PostgreSQL without recreating the type
    # This would require more complex migration with data preservation
