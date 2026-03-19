"""Add tax_form_templates table for storing BMF PDF form templates

Revision ID: 033
Revises: 032
Create Date: 2026-03-15
"""
from alembic import op
import sqlalchemy as sa

revision = '033'
down_revision = '032_add_vat_type'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table('tax_form_templates'):
        return

    # Create TaxFormType enum
    taxformtype = sa.Enum(
        'E1', 'E1a', 'E1b', 'L1', 'L1k', 'K1', 'U1', 'UVA',
        name='taxformtype'
    )
    taxformtype.create(bind, checkfirst=True)

    op.create_table(
        'tax_form_templates',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('tax_year', sa.Integer(), nullable=False, index=True),
        sa.Column('form_type', sa.String(length=10), nullable=False),
        sa.Column('display_name', sa.String(200), nullable=True),
        sa.Column('pdf_template', sa.LargeBinary(), nullable=False),
        sa.Column('field_mapping', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('original_filename', sa.String(255), nullable=True),
        sa.Column('file_size_bytes', sa.Integer(), nullable=True),
        sa.Column('page_count', sa.Integer(), nullable=True),
        sa.Column('source_url', sa.String(500), nullable=True),
        sa.Column('bmf_version', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('tax_year', 'form_type', name='uq_tax_form_template_year_type'),
    )


def downgrade():
    op.drop_table('tax_form_templates')
    sa.Enum(name='taxformtype').drop(op.get_bind(), checkfirst=True)
