"""add_historical_import_tables

Revision ID: 005
Revises: 004
Create Date: 2026-03-07

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY


# revision identifiers, used by Alembic.
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade():
    """Create historical import tables"""
    
    # Create historical_import_sessions table
    op.create_table(
        'historical_import_sessions',
        sa.Column('id', UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.Enum('ACTIVE', 'COMPLETED', 'FAILED', name='importsessionstatus'), nullable=False, server_default='ACTIVE'),
        sa.Column('tax_years', ARRAY(sa.Integer()), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('total_documents', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('successful_imports', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failed_imports', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('transactions_created', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('properties_created', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('properties_linked', sa.Integer(), nullable=False, server_default='0'),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )
    
    # Create indexes for historical_import_sessions
    op.create_index('ix_historical_import_sessions_user_id', 'historical_import_sessions', ['user_id'])
    op.create_index('ix_historical_import_sessions_status', 'historical_import_sessions', ['status'])
    
    # Create historical_import_uploads table
    op.create_table(
        'historical_import_uploads',
        sa.Column('id', UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('session_id', UUID(as_uuid=True), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('document_type', sa.Enum('E1_FORM', 'BESCHEID', 'KAUFVERTRAG', 'SALDENLISTE', name='historicaldocumenttype'), nullable=False),
        sa.Column('tax_year', sa.Integer(), nullable=False),
        sa.Column('status', sa.Enum('UPLOADED', 'PROCESSING', 'EXTRACTED', 'REVIEW_REQUIRED', 'APPROVED', 'REJECTED', 'FAILED', name='importstatus'), nullable=False, server_default='UPLOADED'),
        sa.Column('ocr_task_id', sa.String(length=255), nullable=True),
        sa.Column('extraction_confidence', sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column('extracted_data', JSONB, nullable=True),
        sa.Column('edited_data', JSONB, nullable=True),
        sa.Column('transactions_created', ARRAY(sa.Integer()), nullable=False, server_default='{}'),
        sa.Column('properties_created', ARRAY(UUID(as_uuid=True)), nullable=False, server_default='{}'),
        sa.Column('properties_linked', ARRAY(UUID(as_uuid=True)), nullable=False, server_default='{}'),
        sa.Column('requires_review', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('reviewed_by', sa.Integer(), nullable=True),
        sa.Column('approval_notes', sa.Text(), nullable=True),
        sa.Column('errors', JSONB, nullable=False, server_default='[]'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['session_id'], ['historical_import_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ondelete='SET NULL'),
    )
    
    # Create indexes for historical_import_uploads
    op.create_index('ix_historical_import_uploads_session_id', 'historical_import_uploads', ['session_id'])
    op.create_index('ix_historical_import_uploads_user_id', 'historical_import_uploads', ['user_id'])
    op.create_index('ix_historical_import_uploads_document_id', 'historical_import_uploads', ['document_id'])
    op.create_index('ix_historical_import_uploads_document_type', 'historical_import_uploads', ['document_type'])
    op.create_index('ix_historical_import_uploads_tax_year', 'historical_import_uploads', ['tax_year'])
    op.create_index('ix_historical_import_uploads_status', 'historical_import_uploads', ['status'])
    
    # Create import_conflicts table
    op.create_table(
        'import_conflicts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', UUID(as_uuid=True), nullable=False),
        sa.Column('upload_id_1', UUID(as_uuid=True), nullable=False),
        sa.Column('upload_id_2', UUID(as_uuid=True), nullable=False),
        sa.Column('conflict_type', sa.String(length=100), nullable=False),
        sa.Column('field_name', sa.String(length=255), nullable=False),
        sa.Column('value_1', sa.String(length=500), nullable=True),
        sa.Column('value_2', sa.String(length=500), nullable=True),
        sa.Column('resolution', sa.String(length=100), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_by', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['session_id'], ['historical_import_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['upload_id_1'], ['historical_import_uploads.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['upload_id_2'], ['historical_import_uploads.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['resolved_by'], ['users.id'], ondelete='SET NULL'),
    )
    
    # Create indexes for import_conflicts
    op.create_index('ix_import_conflicts_id', 'import_conflicts', ['id'])
    op.create_index('ix_import_conflicts_session_id', 'import_conflicts', ['session_id'])
    
    # Create import_metrics table
    op.create_table(
        'import_metrics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('upload_id', UUID(as_uuid=True), nullable=False),
        sa.Column('document_type', sa.Enum('E1_FORM', 'BESCHEID', 'KAUFVERTRAG', 'SALDENLISTE', name='historicaldocumenttype'), nullable=False),
        sa.Column('extraction_confidence', sa.Numeric(precision=3, scale=2), nullable=False),
        sa.Column('fields_extracted', sa.Integer(), nullable=False),
        sa.Column('fields_total', sa.Integer(), nullable=False),
        sa.Column('extraction_time_ms', sa.Integer(), nullable=False),
        sa.Column('field_accuracies', JSONB, nullable=False, server_default='{}'),
        sa.Column('fields_corrected', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('corrections', JSONB, nullable=False, server_default='[]'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['upload_id'], ['historical_import_uploads.id'], ondelete='CASCADE'),
    )
    
    # Create indexes for import_metrics
    op.create_index('ix_import_metrics_id', 'import_metrics', ['id'])
    op.create_index('ix_import_metrics_upload_id', 'import_metrics', ['upload_id'], unique=True)
    op.create_index('ix_import_metrics_document_type', 'import_metrics', ['document_type'])


def downgrade():
    """Drop historical import tables"""
    
    # Drop import_metrics table
    op.drop_index('ix_import_metrics_document_type', table_name='import_metrics')
    op.drop_index('ix_import_metrics_upload_id', table_name='import_metrics')
    op.drop_index('ix_import_metrics_id', table_name='import_metrics')
    op.drop_table('import_metrics')
    
    # Drop import_conflicts table
    op.drop_index('ix_import_conflicts_session_id', table_name='import_conflicts')
    op.drop_index('ix_import_conflicts_id', table_name='import_conflicts')
    op.drop_table('import_conflicts')
    
    # Drop historical_import_uploads table
    op.drop_index('ix_historical_import_uploads_status', table_name='historical_import_uploads')
    op.drop_index('ix_historical_import_uploads_tax_year', table_name='historical_import_uploads')
    op.drop_index('ix_historical_import_uploads_document_type', table_name='historical_import_uploads')
    op.drop_index('ix_historical_import_uploads_document_id', table_name='historical_import_uploads')
    op.drop_index('ix_historical_import_uploads_user_id', table_name='historical_import_uploads')
    op.drop_index('ix_historical_import_uploads_session_id', table_name='historical_import_uploads')
    op.drop_table('historical_import_uploads')
    
    # Drop historical_import_sessions table
    op.drop_index('ix_historical_import_sessions_status', table_name='historical_import_sessions')
    op.drop_index('ix_historical_import_sessions_user_id', table_name='historical_import_sessions')
    op.drop_table('historical_import_sessions')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS importstatus')
    op.execute('DROP TYPE IF EXISTS historicaldocumenttype')
    op.execute('DROP TYPE IF EXISTS importsessionstatus')
