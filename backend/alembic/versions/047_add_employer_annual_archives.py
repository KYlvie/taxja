"""Add employer annual payroll archive tables

Revision ID: 047_employer_annual_archives
Revises: 046_employer_months
Create Date: 2026-03-17
"""
from alembic import op
import sqlalchemy as sa


revision = '047_employer_annual_archives'
down_revision = '046_employer_months'
branch_labels = None
depends_on = None


employer_annual_archive_status = sa.Enum(
    'PENDING_CONFIRMATION',
    'ARCHIVED',
    name='employerannualarchivestatus',
)


def upgrade() -> None:
    employer_annual_archive_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'employer_annual_archives',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('tax_year', sa.Integer(), nullable=False),
        sa.Column(
            'status',
            employer_annual_archive_status,
            nullable=False,
            server_default='PENDING_CONFIRMATION',
        ),
        sa.Column('source_type', sa.String(length=30), nullable=True),
        sa.Column('archive_signal', sa.String(length=50), nullable=True),
        sa.Column('confidence', sa.Numeric(3, 2), nullable=True),
        sa.Column('employer_name', sa.String(length=255), nullable=True),
        sa.Column('gross_income', sa.Numeric(12, 2), nullable=True),
        sa.Column('withheld_tax', sa.Numeric(12, 2), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('confirmed_at', sa.DateTime(), nullable=True),
        sa.Column('last_signal_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'tax_year', name='uq_employer_annual_archive_user_year'),
    )
    op.create_index(
        op.f('ix_employer_annual_archives_id'),
        'employer_annual_archives',
        ['id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_employer_annual_archives_status'),
        'employer_annual_archives',
        ['status'],
        unique=False,
    )
    op.create_index(
        op.f('ix_employer_annual_archives_tax_year'),
        'employer_annual_archives',
        ['tax_year'],
        unique=False,
    )
    op.create_index(
        op.f('ix_employer_annual_archives_user_id'),
        'employer_annual_archives',
        ['user_id'],
        unique=False,
    )

    op.create_table(
        'employer_annual_archive_documents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('annual_archive_id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('relation_type', sa.String(length=30), nullable=False, server_default='supporting'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['annual_archive_id'], ['employer_annual_archives.id']),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'annual_archive_id',
            'document_id',
            name='uq_employer_annual_archive_document',
        ),
    )
    op.create_index(
        op.f('ix_employer_annual_archive_documents_annual_archive_id'),
        'employer_annual_archive_documents',
        ['annual_archive_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_employer_annual_archive_documents_document_id'),
        'employer_annual_archive_documents',
        ['document_id'],
        unique=False,
    )

    op.alter_column('employer_annual_archives', 'status', server_default=None)
    op.alter_column('employer_annual_archive_documents', 'relation_type', server_default=None)


def downgrade() -> None:
    op.drop_index(
        op.f('ix_employer_annual_archive_documents_document_id'),
        table_name='employer_annual_archive_documents',
    )
    op.drop_index(
        op.f('ix_employer_annual_archive_documents_annual_archive_id'),
        table_name='employer_annual_archive_documents',
    )
    op.drop_table('employer_annual_archive_documents')

    op.drop_index(op.f('ix_employer_annual_archives_user_id'), table_name='employer_annual_archives')
    op.drop_index(op.f('ix_employer_annual_archives_tax_year'), table_name='employer_annual_archives')
    op.drop_index(op.f('ix_employer_annual_archives_status'), table_name='employer_annual_archives')
    op.drop_index(op.f('ix_employer_annual_archives_id'), table_name='employer_annual_archives')
    op.drop_table('employer_annual_archives')

    employer_annual_archive_status.drop(op.get_bind(), checkfirst=True)
