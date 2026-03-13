"""Complete database fix for monetization system"""
import sys
import os
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))
os.chdir(backend_dir)

from sqlalchemy import text
from app.db.base import SessionLocal

def complete_database_fix():
    """Fix all database issues in one go"""
    print("="*60)
    print("COMPLETE DATABASE FIX")
    print("="*60)
    
    db = SessionLocal()
    
    try:
        # Step 1: Fix plantype enum values
        print("\n1. Fixing plantype enum values...")
        db.execute(text("UPDATE plans SET plan_type = UPPER(plan_type::text)::plantype WHERE plan_type::text IN ('free', 'plus', 'pro')"))
        db.commit()
        print("   ✅ Enum values fixed")
        
        # Step 2: Add cancel_at_period_end if missing
        print("\n2. Checking cancel_at_period_end column...")
        result = db.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'subscriptions' 
            AND column_name = 'cancel_at_period_end'
        """)).fetchone()
        
        if not result:
            print("   Adding cancel_at_period_end column...")
            db.execute(text("""
                ALTER TABLE subscriptions 
                ADD COLUMN cancel_at_period_end BOOLEAN DEFAULT FALSE NOT NULL
            """))
            db.commit()
            print("   ✅ Column added")
        else:
            print("   ✅ Column already exists")
        
        # Step 3: Verify plans exist
        print("\n3. Checking subscription plans...")
        plans_count = db.execute(text("SELECT COUNT(*) FROM plans")).scalar()
        
        if plans_count == 0:
            print("   No plans found, creating them...")
            
            # Free Plan
            db.execute(text("""
                INSERT INTO plans (plan_type, name, monthly_price, yearly_price, features, quotas)
                VALUES (
                    'FREE',
                    'Free',
                    0.00,
                    0.00,
                    '{"basic_tax_calc": true, "transaction_entry": true}'::jsonb,
                    '{"transactions": 50, "ocr_scans": 0, "ai_conversations": 0}'::jsonb
                )
            """))
            
            # Plus Plan
            db.execute(text("""
                INSERT INTO plans (plan_type, name, monthly_price, yearly_price, features, quotas)
                VALUES (
                    'PLUS',
                    'Plus',
                    4.90,
                    49.00,
                    '{"basic_tax_calc": true, "transaction_entry": true, "unlimited_transactions": true, "ocr_scanning": true, "full_tax_calc": true, "multi_language": true, "vat_calc": true, "svs_calc": true}'::jsonb,
                    '{"transactions": -1, "ocr_scans": 20, "ai_conversations": 0}'::jsonb
                )
            """))
            
            # Pro Plan
            db.execute(text("""
                INSERT INTO plans (plan_type, name, monthly_price, yearly_price, features, quotas)
                VALUES (
                    'PRO',
                    'Pro',
                    9.90,
                    99.00,
                    '{"basic_tax_calc": true, "transaction_entry": true, "unlimited_transactions": true, "ocr_scanning": true, "unlimited_ocr": true, "full_tax_calc": true, "multi_language": true, "vat_calc": true, "svs_calc": true, "ai_assistant": true, "e1_generation": true, "advanced_reports": true, "priority_support": true, "api_access": true}'::jsonb,
                    '{"transactions": -1, "ocr_scans": -1, "ai_conversations": -1}'::jsonb
                )
            """))
            
            db.commit()
            print("   ✅ Created 3 plans")
        else:
            print(f"   ✅ Found {plans_count} plans")
        
        # Step 4: Verify database state
        print("\n4. Verifying database state...")
        
        # Check plans
        plans = db.execute(text("""
            SELECT plan_type, name, monthly_price 
            FROM plans 
            ORDER BY monthly_price
        """)).fetchall()
        
        print("   Plans:")
        for plan_type, name, price in plans:
            print(f"     - {name} ({plan_type}): €{price}/month")
        
        # Check subscription table structure
        columns = db.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'subscriptions'
            ORDER BY ordinal_position
        """)).fetchall()
        
        print(f"\n   Subscription table has {len(columns)} columns")
        
        print("\n" + "="*60)
        print("✅ DATABASE FIX COMPLETE")
        print("="*60)
        
        print("\nNext steps:")
        print("  1. Run: python backend/scripts/test_subscription_flow.py")
        print("  2. Run: python backend/scripts/quick_test.py")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        db.rollback()
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


if __name__ == "__main__":
    try:
        success = complete_database_fix()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
