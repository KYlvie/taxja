"""Add subscription tables for monetization system

Revision ID: 010
Revises: 009
Create Date: 2026-03-15 10:00:00.000000

This migration creates the subscription system tables:
- plans: Subscription plan definitions (Free, Plus, Pro)
- subscriptions: User subscription records
- usage_records: Resource usage tracking
- payment_events: Stripe webhook event logs
- Extends users table with subscription fields

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '010'
down_revision = '009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create subscription system tables"""
    
    # Create enum types
    op.execute("""
        CREATE TYPE plantype AS ENUM ('free', 'plus', 'pro')
    """)
    
    op.execute("""
        CREATE TYPE billingcycle AS ENUM ('monthly', 'yearly')
    """)
    
    op.execute("""
        CREATE TYPE subscriptionstatus AS ENUM (
            'active', 'past_due', 'canceled', 'trialing'
        )
    """)
    
    op.execute("""
        CREATE TYPE resourcetype AS ENUM (
            'transactions', 'ocr_scans', 'ai_conversations'
        )
    """)
    
    # Create plans table
    op.create_table(
        'plans',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('plan_type', sa.Enum(
            'free', 'plus', 'pro',
            name='plantype'
        ), nullable=False, unique=True),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('monthly_price', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('yearly_price', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('features', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('quotas', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for plans
    op.create_index('idx_plans_plan_type', 'plans', ['plan_type'])
    
    # Create subscriptions table
    op.create_table(
        'subscriptions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('plan_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.Enum(
            'active', 'past_due', 'canceled', 'trialing',
            name='subscriptionstatus'
        ), nullable=False),
        sa.Column('billing_cycle', sa.Enum(
            'monthly', 'yearly',
            name='billingcycle'
        ), nullable=True),
        sa.Column('stripe_subscription_id', sa.String(length=255), nullable=True, unique=True),
        sa.Column('stripe_customer_id', sa.String(length=255), nullable=True),
        sa.Column('current_period_start', sa.DateTime(), nullable=True),
        sa.Column('current_period_end', sa.DateTime(), nullable=True),
        sa.Column('cancel_at_period_end', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['plan_id'], ['plans.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for subscriptions
    op.create_index('idx_subscriptions_user_id', 'subscriptions', ['user_id'])
    op.create_index('idx_subscriptions_plan_id', 'subscriptions', ['plan_id'])
    op.create_index('idx_subscriptions_status', 'subscriptions', ['status'])
    op.create_index('idx_subscriptions_stripe_subscription_id', 'subscriptions', ['stripe_subscription_id'])
    op.create_index('idx_subscriptions_stripe_customer_id', 'subscriptions', ['stripe_customer_id'])
    op.create_index('idx_subscriptions_period_end', 'subscriptions', ['current_period_end'])
    
    # Create usage_records table
    op.create_table(
        'usage_records',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('resource_type', sa.Enum(
            'transactions', 'ocr_scans', 'ai_conversations',
            name='resourcetype'
        ), nullable=False),
        sa.Column('count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('period_start', sa.DateTime(), nullable=False),
        sa.Column('period_end', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for usage_records
    op.create_index('idx_usage_records_user_id', 'usage_records', ['user_id'])
    op.create_index('idx_usage_records_resource_type', 'usage_records', ['resource_type'])
    op.create_index('idx_usage_records_period', 'usage_records', ['period_start', 'period_end'])
    op.create_index('idx_usage_records_user_resource_period', 'usage_records', 
                    ['user_id', 'resource_type', 'period_start', 'period_end'])
    
    # Create payment_events table
    op.create_table(
        'payment_events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('stripe_event_id', sa.String(length=255), nullable=False, unique=True),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('processed_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for payment_events
    op.create_index('idx_payment_events_stripe_event_id', 'payment_events', ['stripe_event_id'])
    op.create_index('idx_payment_events_event_type', 'payment_events', ['event_type'])
    op.create_index('idx_payment_events_user_id', 'payment_events', ['user_id'])
    op.create_index('idx_payment_events_processed_at', 'payment_events', [sa.text('processed_at DESC')])
    
    # Extend users table with subscription fields
    op.add_column('users', sa.Column('subscription_id', sa.Integer(), nullable=True))
    op.add_column('users', sa.Column('trial_used', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('users', sa.Column('trial_end_date', sa.DateTime(), nullable=True))
    
    # Add foreign key constraint for subscription_id
    op.create_foreign_key(
        'fk_users_subscription_id',
        'users', 'subscriptions',
        ['subscription_id'], ['id'],
        ondelete='SET NULL'
    )
    
    # Create index for users.subscription_id
    op.create_index('idx_users_subscription_id', 'users', ['subscription_id'])
    op.create_index('idx_users_trial_end_date', 'users', ['trial_end_date'])


def downgrade() -> None:
    """Drop subscription system tables"""
    
    # Drop indexes from users table
    op.drop_index('idx_users_trial_end_date', table_name='users')
    op.drop_index('idx_users_subscription_id', table_name='users')
    
    # Drop foreign key constraint from users table
    op.drop_constraint('fk_users_subscription_id', 'users', type_='foreignkey')
    
    # Drop columns from users table
    op.drop_column('users', 'trial_end_date')
    op.drop_column('users', 'trial_used')
    op.drop_column('users', 'subscription_id')
    
    # Drop indexes from payment_events
    op.drop_index('idx_payment_events_processed_at', table_name='payment_events')
    op.drop_index('idx_payment_events_user_id', table_name='payment_events')
    op.drop_index('idx_payment_events_event_type', table_name='payment_events')
    op.drop_index('idx_payment_events_stripe_event_id', table_name='payment_events')
    
    # Drop payment_events table
    op.drop_table('payment_events')
    
    # Drop indexes from usage_records
    op.drop_index('idx_usage_records_user_resource_period', table_name='usage_records')
    op.drop_index('idx_usage_records_period', table_name='usage_records')
    op.drop_index('idx_usage_records_resource_type', table_name='usage_records')
    op.drop_index('idx_usage_records_user_id', table_name='usage_records')
    
    # Drop usage_records table
    op.drop_table('usage_records')
    
    # Drop indexes from subscriptions
    op.drop_index('idx_subscriptions_period_end', table_name='subscriptions')
    op.drop_index('idx_subscriptions_stripe_customer_id', table_name='subscriptions')
    op.drop_index('idx_subscriptions_stripe_subscription_id', table_name='subscriptions')
    op.drop_index('idx_subscriptions_status', table_name='subscriptions')
    op.drop_index('idx_subscriptions_plan_id', table_name='subscriptions')
    op.drop_index('idx_subscriptions_user_id', table_name='subscriptions')
    
    # Drop subscriptions table
    op.drop_table('subscriptions')
    
    # Drop indexes from plans
    op.drop_index('idx_plans_plan_type', table_name='plans')
    
    # Drop plans table
    op.drop_table('plans')
    
    # Drop enum types
    op.execute('DROP TYPE resourcetype')
    op.execute('DROP TYPE subscriptionstatus')
    op.execute('DROP TYPE billingcycle')
    op.execute('DROP TYPE plantype')
