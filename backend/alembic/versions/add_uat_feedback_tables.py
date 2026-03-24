"""Add UAT feedback tables

Revision ID: add_uat_feedback
Revises: [previous_revision]
Create Date: 2026-03-08

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_uat_feedback'
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade():
    # Create enum types (with checkfirst to avoid duplicates)
    feedback_category_enum = postgresql.ENUM(
        'usability',
        'functionality',
        'value',
        'bug_report',
        'feature_request',
        name='feedbackcategory',
        create_type=False
    )
    feedback_category_enum.create(op.get_bind(), checkfirst=True)
    
    feedback_severity_enum = postgresql.ENUM(
        'critical',
        'high',
        'medium',
        'low',
        name='feedbackseverity',
        create_type=False
    )
    feedback_severity_enum.create(op.get_bind(), checkfirst=True)
    
    test_scenario_enum = postgresql.ENUM(
        'property_registration',
        'historical_backfill',
        'transaction_linking',
        'property_metrics',
        'report_generation',
        'multi_property',
        'property_archival',
        'general',
        name='testscenario',
        create_type=False
    )
    test_scenario_enum.create(op.get_bind(), checkfirst=True)
    
    # Create uat_feedback table
    op.create_table(
        'uat_feedback',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('test_scenario', postgresql.ENUM(
            'property_registration',
            'historical_backfill',
            'transaction_linking',
            'property_metrics',
            'report_generation',
            'multi_property',
            'property_archival',
            'general',
            name='testscenario',
            create_type=False
        ), nullable=False),
        sa.Column('category', postgresql.ENUM(
            'usability',
            'functionality',
            'value',
            'bug_report',
            'feature_request',
            name='feedbackcategory',
            create_type=False
        ), nullable=False),
        sa.Column('rating', sa.Integer(), nullable=True),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('severity', postgresql.ENUM(
            'critical',
            'high',
            'medium',
            'low',
            name='feedbackseverity',
            create_type=False
        ), nullable=True),
        sa.Column('steps_to_reproduce', sa.Text(), nullable=True),
        sa.Column('expected_result', sa.Text(), nullable=True),
        sa.Column('actual_result', sa.Text(), nullable=True),
        sa.Column('browser_info', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('resolved', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_uat_feedback_id', 'uat_feedback', ['id'])
    op.create_index('ix_uat_feedback_user_id', 'uat_feedback', ['user_id'])
    op.create_index('ix_uat_feedback_test_scenario', 'uat_feedback', ['test_scenario'])
    op.create_index('ix_uat_feedback_category', 'uat_feedback', ['category'])
    op.create_index('ix_uat_feedback_severity', 'uat_feedback', ['severity'])
    op.create_index('ix_uat_feedback_resolved', 'uat_feedback', ['resolved'])
    
    # Create uat_metrics table
    op.create_table(
        'uat_metrics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('test_scenario', postgresql.ENUM(
            'property_registration',
            'historical_backfill',
            'transaction_linking',
            'property_metrics',
            'report_generation',
            'multi_property',
            'property_archival',
            'general',
            name='testscenario',
            create_type=False
        ), nullable=False),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('duration_seconds', sa.Float(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_uat_metrics_id', 'uat_metrics', ['id'])
    op.create_index('ix_uat_metrics_user_id', 'uat_metrics', ['user_id'])
    op.create_index('ix_uat_metrics_test_scenario', 'uat_metrics', ['test_scenario'])
    op.create_index('ix_uat_metrics_success', 'uat_metrics', ['success'])


def downgrade():
    # Drop tables
    op.drop_index('ix_uat_metrics_success', table_name='uat_metrics')
    op.drop_index('ix_uat_metrics_test_scenario', table_name='uat_metrics')
    op.drop_index('ix_uat_metrics_user_id', table_name='uat_metrics')
    op.drop_index('ix_uat_metrics_id', table_name='uat_metrics')
    op.drop_table('uat_metrics')
    
    op.drop_index('ix_uat_feedback_resolved', table_name='uat_feedback')
    op.drop_index('ix_uat_feedback_severity', table_name='uat_feedback')
    op.drop_index('ix_uat_feedback_category', table_name='uat_feedback')
    op.drop_index('ix_uat_feedback_test_scenario', table_name='uat_feedback')
    op.drop_index('ix_uat_feedback_user_id', table_name='uat_feedback')
    op.drop_index('ix_uat_feedback_id', table_name='uat_feedback')
    op.drop_table('uat_feedback')
    
    # Drop enum types
    sa.Enum(name='testscenario').drop(op.get_bind())
    sa.Enum(name='feedbackseverity').drop(op.get_bind())
    sa.Enum(name='feedbackcategory').drop(op.get_bind())
