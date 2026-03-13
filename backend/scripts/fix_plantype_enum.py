"""Fix plantype enum to match model definition"""
import sys
import os
from pathlib import Path

backend_dir = Path(__file__).parent.parent
os.chdir(backend_dir)
sys.path.insert(0, str(backend_dir))

from sqlalchemy import text
from app.db.base import SessionLocal

def fix_enum():
    """Fix the plantype enum"""
    db = SessionLocal()
    try:
        print("Fixing plantype enum...")
        
        # Drop dependent tables first
        db.execute(text("DROP TABLE IF EXISTS subscriptions CASCADE"))
        db.execute(text("DROP TABLE IF EXISTS usage_records CASCADE"))
        db.execute(text("DROP TABLE IF EXISTS payment_events CASCADE"))
        db.execute(text("DROP TABLE IF EXISTS plans CASCADE"))
        
        # Drop the existing enum
        db.execute(text("DROP TYPE IF EXISTS plantype CASCADE"))
        db.execute(text("DROP TYPE IF EXISTS billingcycle CASCADE"))
        db.execute(text("DROP TYPE IF EXISTS subscriptionstatus CASCADE"))
        db.execute(text("DROP TYPE IF EXISTS resourcetype CASCADE"))
        
        # Recreate enums with correct values
        db.execute(text("CREATE TYPE plantype AS ENUM ('free', 'plus', 'pro')"))
        db.execute(text("CREATE TYPE billingcycle AS ENUM ('monthly', 'yearly')"))
        db.execute(text("CREATE TYPE subscriptionstatus AS ENUM ('active', 'canceled', 'past_due', 'trialing')"))
        db.execute(text("CREATE TYPE resourcetype AS ENUM ('transactions', 'documents', 'api_calls', 'storage_mb')"))
        
        # Recreate tables
        db.execute(text("""
            CREATE TABLE plans (
                id SERIAL PRIMARY KEY,
                plan_type plantype NOT NULL UNIQUE,
                name VARCHAR(100) NOT NULL,
                monthly_price NUMERIC(10, 2) NOT NULL,
                yearly_price NUMERIC(10, 2) NOT NULL,
                features JSONB NOT NULL DEFAULT '{}',
                quotas JSONB NOT NULL DEFAULT '{}',
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        db.execute(text("""
            CREATE TABLE subscriptions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                plan_id INTEGER NOT NULL REFERENCES plans(id),
                status subscriptionstatus NOT NULL DEFAULT 'active',
                billing_cycle billingcycle NOT NULL DEFAULT 'monthly',
                current_period_start TIMESTAMP NOT NULL,
                current_period_end TIMESTAMP NOT NULL,
                stripe_subscription_id VARCHAR(255),
                stripe_customer_id VARCHAR(255),
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id)
            )
        """))
        
        db.execute(text("""
            CREATE TABLE usage_records (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                resource_type resourcetype NOT NULL,
                amount INTEGER NOT NULL,
                period_start TIMESTAMP NOT NULL,
                period_end TIMESTAMP NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        db.execute(text("""
            CREATE TABLE payment_events (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                stripe_event_id VARCHAR(255) NOT NULL UNIQUE,
                event_type VARCHAR(100) NOT NULL,
                payload JSONB NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        # Create indexes
        db.execute(text("CREATE INDEX ix_subscriptions_user_id ON subscriptions(user_id)"))
        db.execute(text("CREATE INDEX ix_subscriptions_status ON subscriptions(status)"))
        db.execute(text("CREATE INDEX ix_usage_records_user_id ON usage_records(user_id)"))
        db.execute(text("CREATE INDEX ix_usage_records_period ON usage_records(period_start, period_end)"))
        
        db.commit()
        print("✅ Enum and tables fixed successfully")
        return True
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error: {e}")
        return False
    finally:
        db.close()

if __name__ == "__main__":
    if fix_enum():
        sys.exit(0)
    else:
        sys.exit(1)
