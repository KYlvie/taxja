"""Add performance indexes for 100K users scale

Revision ID: 030_perf_indexes
Revises: None (standalone, safe to run anytime)
"""
from alembic import op

revision = "030_perf_indexes"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # =========================================================================
    # Composite indexes for high-frequency queries
    # =========================================================================

    # transactions: dashboard summary, list by user+year (most common query)
    op.execute("""
        CREATE INDEX IF NOT EXISTS
        ix_transactions_user_date
        ON transactions (user_id, transaction_date DESC)
    """)

    # transactions: filter by user + type (income vs expense aggregation)
    op.execute("""
        CREATE INDEX IF NOT EXISTS
        ix_transactions_user_type
        ON transactions (user_id, type)
    """)

    # transactions: tax year queries (extract year from date)
    op.execute("""
        CREATE INDEX IF NOT EXISTS
        ix_transactions_user_year
        ON transactions (user_id, EXTRACT(YEAR FROM transaction_date))
    """)

    # transactions: deductible expense queries
    op.execute("""
        CREATE INDEX IF NOT EXISTS
        ix_transactions_user_deductible
        ON transactions (user_id, is_deductible)
        WHERE is_deductible = true
    """)

    # transactions: property-related queries (landlord users)
    op.execute("""
        CREATE INDEX IF NOT EXISTS
        ix_transactions_property
        ON transactions (property_id, transaction_date DESC)
        WHERE property_id IS NOT NULL
    """)

    # documents: list by user + upload date
    op.execute("""
        CREATE INDEX IF NOT EXISTS
        ix_documents_user_uploaded
        ON documents (user_id, uploaded_at DESC)
    """)

    # chat_messages: history by user + timestamp
    op.execute("""
        CREATE INDEX IF NOT EXISTS
        ix_chat_messages_user_time
        ON chat_messages (user_id, created_at DESC)
    """)

    # recurring_transactions: due date lookup for auto-generation
    op.execute("""
        CREATE INDEX IF NOT EXISTS
        ix_recurring_next_date
        ON recurring_transactions (next_occurrence, is_active)
        WHERE is_active = true
    """)

    # usage_records: current period lookup
    op.execute("""
        CREATE INDEX IF NOT EXISTS
        ix_usage_records_user_period
        ON usage_records (user_id, resource_type, period_start, period_end)
    """)

    # subscriptions: user lookup
    op.execute("""
        CREATE INDEX IF NOT EXISTS
        ix_subscriptions_user_status
        ON subscriptions (user_id, status)
    """)

    # audit_logs: user activity lookup
    op.execute("""
        CREATE INDEX IF NOT EXISTS
        ix_audit_logs_user_time
        ON audit_logs (user_id, created_at DESC)
    """)

    # users: account status for admin queries and cleanup tasks
    op.execute("""
        CREATE INDEX IF NOT EXISTS
        ix_users_deletion_pending
        ON users (scheduled_deletion_at)
        WHERE account_status = 'deletion_pending'
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_transactions_user_date")
    op.execute("DROP INDEX IF EXISTS ix_transactions_user_type")
    op.execute("DROP INDEX IF EXISTS ix_transactions_user_year")
    op.execute("DROP INDEX IF EXISTS ix_transactions_user_deductible")
    op.execute("DROP INDEX IF EXISTS ix_transactions_property")
    op.execute("DROP INDEX IF EXISTS ix_documents_user_uploaded")
    op.execute("DROP INDEX IF EXISTS ix_chat_messages_user_time")
    op.execute("DROP INDEX IF EXISTS ix_recurring_next_date")
    op.execute("DROP INDEX IF EXISTS ix_usage_records_user_period")
    op.execute("DROP INDEX IF EXISTS ix_subscriptions_user_status")
    op.execute("DROP INDEX IF EXISTS ix_audit_logs_user_time")
    op.execute("DROP INDEX IF EXISTS ix_users_deletion_pending")
