"""add loan contract document id

Revision ID: 011
Revises: 010
Create Date: 2026-03-08

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '011'
down_revision = '010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add loan_contract_document_id to property_loans table"""
    op.add_column(
        'property_loans',
        sa.Column('loan_contract_document_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_property_loans_loan_contract_document',
        'property_loans',
        'documents',
        ['loan_contract_document_id'],
        ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    """Remove loan_contract_document_id from property_loans table"""
    op.drop_constraint('fk_property_loans_loan_contract_document', 'property_loans', type_='foreignkey')
    op.drop_column('property_loans', 'loan_contract_document_id')
