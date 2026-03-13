"""Initial migration: create all tables

Revision ID: 001
Revises: 
Create Date: 2026-03-04 09:26:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('tax_number', sa.String(length=500), nullable=True),
        sa.Column('vat_number', sa.String(length=500), nullable=True),
        sa.Column('address', sa.String(length=1000), nullable=True),
        sa.Column('user_type', sa.Enum('EMPLOYEE', 'SELF_EMPLOYED', 'LANDLORD', 'MIXED', name='usertype'), nullable=False),
        sa.Column('family_info', sa.JSON(), nullable=True),
        sa.Column('commuting_info', sa.JSON(), nullable=True),
        sa.Column('home_office_eligible', sa.Boolean(), nullable=True),
        sa.Column('language', sa.String(length=5), nullable=True),
        sa.Column('two_factor_enabled', sa.Boolean(), nullable=True),
        sa.Column('two_factor_secret', sa.String(length=500), nullable=True),
        sa.Column('disclaimer_accepted_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('last_login', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)

    # Create tax_configurations table
    op.create_table(
        'tax_configurations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tax_year', sa.Integer(), nullable=False),
        sa.Column('tax_brackets', sa.JSON(), nullable=False),
        sa.Column('exemption_amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('vat_rates', sa.JSON(), nullable=False),
        sa.Column('svs_rates', sa.JSON(), nullable=False),
        sa.Column('deduction_config', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tax_configurations_id'), 'tax_configurations', ['id'], unique=False)
    op.create_index(op.f('ix_tax_configurations_tax_year'), 'tax_configurations', ['tax_year'], unique=True)

    # Create documents table
    op.create_table(
        'documents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('document_type', sa.Enum('PAYSLIP', 'RECEIPT', 'INVOICE', 'RENTAL_CONTRACT', 'BANK_STATEMENT', 'PROPERTY_TAX', 'LOHNZETTEL', 'SVS_NOTICE', 'OTHER', name='documenttype'), nullable=False),
        sa.Column('file_path', sa.String(length=500), nullable=False),
        sa.Column('file_name', sa.String(length=255), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('mime_type', sa.String(length=100), nullable=True),
        sa.Column('ocr_result', sa.JSON(), nullable=True),
        sa.Column('raw_text', sa.Text(), nullable=True),
        sa.Column('confidence_score', sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column('transaction_id', sa.Integer(), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(), nullable=False),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_documents_document_type'), 'documents', ['document_type'], unique=False)
    op.create_index(op.f('ix_documents_id'), 'documents', ['id'], unique=False)
    op.create_index(op.f('ix_documents_user_id'), 'documents', ['user_id'], unique=False)

    # Create transactions table
    op.create_table(
        'transactions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('type', sa.Enum('INCOME', 'EXPENSE', name='transactiontype'), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('transaction_date', sa.Date(), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('income_category', sa.Enum('EMPLOYMENT', 'RENTAL', 'SELF_EMPLOYMENT', 'CAPITAL_GAINS', name='incomecategory'), nullable=True),
        sa.Column('expense_category', sa.Enum('OFFICE_SUPPLIES', 'EQUIPMENT', 'TRAVEL', 'MARKETING', 'PROFESSIONAL_SERVICES', 'INSURANCE', 'MAINTENANCE', 'PROPERTY_TAX', 'LOAN_INTEREST', 'DEPRECIATION', 'GROCERIES', 'UTILITIES', 'COMMUTING', 'HOME_OFFICE', 'OTHER', name='expensecategory'), nullable=True),
        sa.Column('is_deductible', sa.Boolean(), nullable=True),
        sa.Column('deduction_reason', sa.String(length=500), nullable=True),
        sa.Column('vat_rate', sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column('vat_amount', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('document_id', sa.Integer(), nullable=True),
        sa.Column('classification_confidence', sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column('needs_review', sa.Boolean(), nullable=True),
        sa.Column('import_source', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_transactions_id'), 'transactions', ['id'], unique=False)
    op.create_index(op.f('ix_transactions_transaction_date'), 'transactions', ['transaction_date'], unique=False)
    op.create_index(op.f('ix_transactions_type'), 'transactions', ['type'], unique=False)
    op.create_index(op.f('ix_transactions_user_id'), 'transactions', ['user_id'], unique=False)

    # Add foreign key from documents to transactions (circular reference handled)
    op.create_foreign_key('fk_documents_transaction_id', 'documents', 'transactions', ['transaction_id'], ['id'])

    # Create loss_carryforwards table
    op.create_table(
        'loss_carryforwards',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('loss_year', sa.Integer(), nullable=False),
        sa.Column('loss_amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('used_amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('remaining_amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'loss_year', name='uq_user_loss_year')
    )
    op.create_index(op.f('ix_loss_carryforwards_id'), 'loss_carryforwards', ['id'], unique=False)
    op.create_index(op.f('ix_loss_carryforwards_loss_year'), 'loss_carryforwards', ['loss_year'], unique=False)
    op.create_index(op.f('ix_loss_carryforwards_user_id'), 'loss_carryforwards', ['user_id'], unique=False)

    # Create tax_reports table
    op.create_table(
        'tax_reports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('tax_year', sa.Integer(), nullable=False),
        sa.Column('income_summary', sa.JSON(), nullable=False),
        sa.Column('expense_summary', sa.JSON(), nullable=False),
        sa.Column('tax_calculation', sa.JSON(), nullable=False),
        sa.Column('deductions', sa.JSON(), nullable=False),
        sa.Column('net_income', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('pdf_file_path', sa.String(length=500), nullable=True),
        sa.Column('xml_file_path', sa.String(length=500), nullable=True),
        sa.Column('generated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tax_reports_id'), 'tax_reports', ['id'], unique=False)
    op.create_index(op.f('ix_tax_reports_tax_year'), 'tax_reports', ['tax_year'], unique=False)
    op.create_index(op.f('ix_tax_reports_user_id'), 'tax_reports', ['user_id'], unique=False)


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_index(op.f('ix_tax_reports_user_id'), table_name='tax_reports')
    op.drop_index(op.f('ix_tax_reports_tax_year'), table_name='tax_reports')
    op.drop_index(op.f('ix_tax_reports_id'), table_name='tax_reports')
    op.drop_table('tax_reports')

    op.drop_index(op.f('ix_loss_carryforwards_user_id'), table_name='loss_carryforwards')
    op.drop_index(op.f('ix_loss_carryforwards_loss_year'), table_name='loss_carryforwards')
    op.drop_index(op.f('ix_loss_carryforwards_id'), table_name='loss_carryforwards')
    op.drop_table('loss_carryforwards')

    # Drop foreign key from documents to transactions
    op.drop_constraint('fk_documents_transaction_id', 'documents', type_='foreignkey')

    op.drop_index(op.f('ix_transactions_user_id'), table_name='transactions')
    op.drop_index(op.f('ix_transactions_type'), table_name='transactions')
    op.drop_index(op.f('ix_transactions_transaction_date'), table_name='transactions')
    op.drop_index(op.f('ix_transactions_id'), table_name='transactions')
    op.drop_table('transactions')

    op.drop_index(op.f('ix_documents_user_id'), table_name='documents')
    op.drop_index(op.f('ix_documents_id'), table_name='documents')
    op.drop_index(op.f('ix_documents_document_type'), table_name='documents')
    op.drop_table('documents')

    op.drop_index(op.f('ix_tax_configurations_tax_year'), table_name='tax_configurations')
    op.drop_index(op.f('ix_tax_configurations_id'), table_name='tax_configurations')
    op.drop_table('tax_configurations')

    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')

    # Drop enums
    sa.Enum(name='usertype').drop(op.get_bind())
    sa.Enum(name='transactiontype').drop(op.get_bind())
    sa.Enum(name='incomecategory').drop(op.get_bind())
    sa.Enum(name='expensecategory').drop(op.get_bind())
    sa.Enum(name='documenttype').drop(op.get_bind())
