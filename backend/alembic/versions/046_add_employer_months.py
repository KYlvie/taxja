"""Add employer_months and employer_month_documents tables

Revision ID: 046_employer_months
Revises: 045_employer_profile
Create Date: 2026-03-17
"""
from alembic import op
import sqlalchemy as sa


revision = '046_employer_months'
down_revision = '045_employer_profile'
branch_labels = None
depends_on = None


employer_month_status = sa.Enum(
    'UNKNOWN',
    'PAYROLL_DETECTED',
    'MISSING_CONFIRMATION',
    'NO_PAYROLL_CONFIRMED',
    'ARCHIVED_YEAR_ONLY',
    name='employermonthstatus',
)


def upgrade() -> None:
    employer_month_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'employer_months',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('year_month', sa.String(length=7), nullable=False),
        sa.Column('status', employer_month_status, nullable=False, server_default='UNKNOWN'),
        sa.Column('source_type', sa.String(length=30), nullable=True),
        sa.Column('payroll_signal', sa.String(length=50), nullable=True),
        sa.Column('confidence', sa.Numeric(3, 2), nullable=True),
        sa.Column('employee_count', sa.Integer(), nullable=True),
        sa.Column('gross_wages', sa.Numeric(12, 2), nullable=True),
        sa.Column('net_paid', sa.Numeric(12, 2), nullable=True),
        sa.Column('employer_social_cost', sa.Numeric(12, 2), nullable=True),
        sa.Column('lohnsteuer', sa.Numeric(12, 2), nullable=True),
        sa.Column('db_amount', sa.Numeric(12, 2), nullable=True),
        sa.Column('dz_amount', sa.Numeric(12, 2), nullable=True),
        sa.Column('kommunalsteuer', sa.Numeric(12, 2), nullable=True),
        sa.Column('special_payments', sa.Numeric(12, 2), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('confirmed_at', sa.DateTime(), nullable=True),
        sa.Column('last_signal_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'year_month', name='uq_employer_month_user_month'),
    )
    op.create_index(op.f('ix_employer_months_id'), 'employer_months', ['id'], unique=False)
    op.create_index(op.f('ix_employer_months_status'), 'employer_months', ['status'], unique=False)
    op.create_index(op.f('ix_employer_months_user_id'), 'employer_months', ['user_id'], unique=False)
    op.create_index(op.f('ix_employer_months_year_month'), 'employer_months', ['year_month'], unique=False)

    op.create_table(
        'employer_month_documents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('employer_month_id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('relation_type', sa.String(length=30), nullable=False, server_default='supporting'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id']),
        sa.ForeignKeyConstraint(['employer_month_id'], ['employer_months.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('employer_month_id', 'document_id', name='uq_employer_month_document'),
    )
    op.create_index(
        op.f('ix_employer_month_documents_document_id'),
        'employer_month_documents',
        ['document_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_employer_month_documents_employer_month_id'),
        'employer_month_documents',
        ['employer_month_id'],
        unique=False,
    )

    op.alter_column('employer_months', 'status', server_default=None)
    op.alter_column('employer_month_documents', 'relation_type', server_default=None)


def downgrade() -> None:
    op.drop_index(op.f('ix_employer_month_documents_employer_month_id'), table_name='employer_month_documents')
    op.drop_index(op.f('ix_employer_month_documents_document_id'), table_name='employer_month_documents')
    op.drop_table('employer_month_documents')

    op.drop_index(op.f('ix_employer_months_year_month'), table_name='employer_months')
    op.drop_index(op.f('ix_employer_months_user_id'), table_name='employer_months')
    op.drop_index(op.f('ix_employer_months_status'), table_name='employer_months')
    op.drop_index(op.f('ix_employer_months_id'), table_name='employer_months')
    op.drop_table('employer_months')

    employer_month_status.drop(op.get_bind(), checkfirst=True)
