"""Fix subscription table - add missing cancel_at_period_end column"""
import sys
import os
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))
os.chdir(backend_dir)

from sqlalchemy import text
from app.db.base import SessionLocal

def fix_subscription_table():
    """Add missing cancel_at_period_end column to subscriptions table"""
    print("="*60)
    print("FIX SUBSCRIPTION TABLE")
    print("="*60)
    
    db = SessionLocal()
    
    try:
        # Check if column exists
        print("\n1. Checking if cancel_at_period_end column exists...")
        result = db.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'subscriptions' 
            AND column_name = 'cancel_at_period_end'
        """)).fetchone()
        
        if result:
            print("   ✅ Column already exists")
            return True
        
        print("   ⚠️  Column missing, adding it now...")
        
        # Add the column
        print("\n2. Adding cancel_at_period_end column...")
        db.execute(text("""
            ALTER TABLE subscriptions 
            ADD COLUMN cancel_at_period_end BOOLEAN DEFAULT FALSE NOT NULL
        """))
        db.commit()
        print("   ✅ Column added successfully")
        
        # Verify
        print("\n3. Verifying column was added...")
        result = db.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'subscriptions' 
            AND column_name = 'cancel_at_period_end'
        """)).fetchone()
        
        if result:
            print("   ✅ Verification successful")
        else:
            print("   ❌ Verification failed")
            return False
        
        # Show all columns
        print("\n4. Current subscription table columns:")
        columns = db.execute(text("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'subscriptions'
            ORDER BY ordinal_position
        """)).fetchall()
        
        for col_name, data_type, is_nullable in columns:
            nullable = "NULL" if is_nullable == "YES" else "NOT NULL"
            print(f"   - {col_name:30} {data_type:20} {nullable}")
        
        print("\n" + "="*60)
        print("✅ SUBSCRIPTION TABLE FIXED")
        print("="*60)
        
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
        success = fix_subscription_table()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
