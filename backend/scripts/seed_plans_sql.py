"""Seed subscription plans using raw SQL"""
import sys
import os
from pathlib import Path

backend_dir = Path(__file__).parent.parent
os.chdir(backend_dir)
sys.path.insert(0, str(backend_dir))

from sqlalchemy import text
from app.db.base import SessionLocal

def seed_plans():
    """Seed plans using raw SQL"""
    db = SessionLocal()
    try:
        # Check if plans exist
        count = db.execute(text("SELECT COUNT(*) FROM plans")).scalar()
        if count > 0:
            print(f"⚠️  Plans already exist ({count} plans). Skipping seed.")
            return True
        
        print("🌱 Seeding subscription plans...")
        
        # Insert Free plan
        db.execute(text("""
            INSERT INTO plans (plan_type, name, monthly_price, yearly_price, features, quotas)
            VALUES (
                'free',
                'Free',
                0,
                0,
                '{"basic_tax_calc": true, "transaction_entry": true}',
                '{"transactions": 50, "ocr_scans": 0, "ai_conversations": 0}'
            )
        """))
        print("  ✓ Created Free plan (€0/month)")
        
        # Insert Plus plan
        db.execute(text("""
            INSERT INTO plans (plan_type, name, monthly_price, yearly_price, features, quotas)
            VALUES (
                'plus',
                'Plus',
                4.90,
                49.00,
                '{"basic_tax_calc": true, "transaction_entry": true, "unlimited_transactions": true, "ocr_scanning": true, "full_tax_calc": true, "multi_language": true, "vat_calc": true, "svs_calc": true}',
                '{"transactions": -1, "ocr_scans": 20, "ai_conversations": 0}'
            )
        """))
        print("  ✓ Created Plus plan (€4.9/month)")
        
        # Insert Pro plan
        db.execute(text("""
            INSERT INTO plans (plan_type, name, monthly_price, yearly_price, features, quotas)
            VALUES (
                'pro',
                'Pro',
                9.90,
                99.00,
                '{"basic_tax_calc": true, "transaction_entry": true, "unlimited_transactions": true, "ocr_scanning": true, "unlimited_ocr": true, "full_tax_calc": true, "multi_language": true, "vat_calc": true, "svs_calc": true, "ai_assistant": true, "e1_generation": true, "advanced_reports": true, "priority_support": true, "api_access": true}',
                '{"transactions": -1, "ocr_scans": -1, "ai_conversations": -1}'
            )
        """))
        print("  ✓ Created Pro plan (€9.9/month)")
        
        db.commit()
        print("\n✅ Successfully seeded 3 subscription plans")
        return True
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ Error seeding plans: {e}")
        return False
    finally:
        db.close()

if __name__ == "__main__":
    if seed_plans():
        sys.exit(0)
    else:
        sys.exit(1)
