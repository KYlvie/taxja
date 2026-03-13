"""Run migration 010 to create monetization tables"""
import sys
import os
from pathlib import Path

# Change to backend directory
backend_dir = Path(__file__).parent.parent
os.chdir(backend_dir)
sys.path.insert(0, str(backend_dir))

from sqlalchemy import text
from app.db.base import SessionLocal

def check_table_exists(table_name):
    """Check if a table exists"""
    db = SessionLocal()
    try:
        result = db.execute(text(
            f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{table_name}')"
        )).scalar()
        return result
    finally:
        db.close()

def run_migration_010():
    """Run migration 010 SQL directly"""
    db = SessionLocal()
    try:
        # Check if tables already exist
        if check_table_exists('plans'):
            print("✅ Plans table already exists")
            return True
        
        print("Creating monetization tables...")
        
        # Create plantype enum
        db.execute(text("""
            DO $$ BEGIN
                CREATE TYPE plantype AS ENUM ('free', 'plus', 'pro');
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
        """))
        
        # Create billingcycle enum
        db.execute(text("""
            DO $$ BEGIN
                CREATE TYPE billingcycle AS ENUM ('monthly', 'yearly');
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
        """))
        
        # Create subscriptionstatus enum
        db.execute(text("""
            DO $$ BEGIN
                CREATE TYPE subscriptionstatus AS ENUM ('active', 'canceled', 'past_due', 'trialing');
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
        """))
        
        # Create resourcetype enum
        db.execute(text("""
            DO $$ BEGIN
                CREATE TYPE resourcetype AS ENUM ('transactions', 'documents', 'api_calls', 'storage_mb');
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
        """))
        
        # Create plans table
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
        
        # Create subscriptions table
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
        
        # Create usage_records table
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
        
        # Create payment_events table
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
        
        # Add subscription fields to users table if they don't exist
        db.execute(text("""
            DO $$ BEGIN
                ALTER TABLE users ADD COLUMN subscription_id INTEGER REFERENCES subscriptions(id) ON DELETE SET NULL;
            EXCEPTION
                WHEN duplicate_column THEN null;
            END $$;
        """))
        
        db.execute(text("""
            DO $$ BEGIN
                ALTER TABLE users ADD COLUMN trial_used BOOLEAN NOT NULL DEFAULT FALSE;
            EXCEPTION
                WHEN duplicate_column THEN null;
            END $$;
        """))
        
        db.execute(text("""
            DO $$ BEGIN
                ALTER TABLE users ADD COLUMN trial_end_date TIMESTAMP;
            EXCEPTION
                WHEN duplicate_column THEN null;
            END $$;
        """))
        
        # Create indexes
        db.execute(text("CREATE INDEX IF NOT EXISTS ix_subscriptions_user_id ON subscriptions(user_id)"))
        db.execute(text("CREATE INDEX IF NOT EXISTS ix_subscriptions_status ON subscriptions(status)"))
        db.execute(text("CREATE INDEX IF NOT EXISTS ix_usage_records_user_id ON usage_records(user_id)"))
        db.execute(text("CREATE INDEX IF NOT EXISTS ix_usage_records_period ON usage_records(period_start, period_end)"))
        db.execute(text("CREATE INDEX IF NOT EXISTS ix_users_subscription_id ON users(subscription_id)"))
        db.execute(text("CREATE INDEX IF NOT EXISTS ix_users_trial_end_date ON users(trial_end_date)"))
        
        db.commit()
        print("✅ Monetization tables created successfully")
        return True
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error creating tables: {e}")
        return False
    finally:
        db.close()

if __name__ == "__main__":
    print("=" * 60)
    print("CREATING MONETIZATION TABLES")
    print("=" * 60)
    
    if run_migration_010():
        print("\n✅ Migration 010 completed successfully")
        sys.exit(0)
    else:
        print("\n❌ Migration 010 failed")
        sys.exit(1)
