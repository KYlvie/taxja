"""Seed subscription plans for testing"""
import sys
import os
from pathlib import Path

# Add parent directory to path and change to backend directory
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))
os.chdir(backend_dir)

from app.db.base import SessionLocal
from app.models.plan import Plan, PlanType

def seed_plans():
    """Seed the database with subscription plans"""
    db = SessionLocal()
    
    try:
        # Check if plans already exist
        existing_plans = db.query(Plan).count()
        if existing_plans > 0:
            print(f"⚠️  Plans already exist ({existing_plans} plans). Skipping seed.")
            return
        
        plans = [
            Plan(
                plan_type=PlanType.FREE,
                name="Free",
                monthly_price=0,
                yearly_price=0,
                features={
                    "basic_tax_calc": True,
                    "transaction_entry": True,
                },
                quotas={
                    "transactions": 50,
                    "ocr_scans": 0,
                    "ai_conversations": 0,
                }
            ),
            Plan(
                plan_type=PlanType.PLUS,
                name="Plus",
                monthly_price=4.90,
                yearly_price=49.00,
                features={
                    "basic_tax_calc": True,
                    "transaction_entry": True,
                    "unlimited_transactions": True,
                    "ocr_scanning": True,
                    "full_tax_calc": True,
                    "multi_language": True,
                    "vat_calc": True,
                    "svs_calc": True,
                },
                quotas={
                    "transactions": -1,  # unlimited
                    "ocr_scans": 20,
                    "ai_conversations": 0,
                }
            ),
            Plan(
                plan_type=PlanType.PRO,
                name="Pro",
                monthly_price=9.90,
                yearly_price=99.00,
                features={
                    "basic_tax_calc": True,
                    "transaction_entry": True,
                    "unlimited_transactions": True,
                    "ocr_scanning": True,
                    "unlimited_ocr": True,
                    "full_tax_calc": True,
                    "multi_language": True,
                    "vat_calc": True,
                    "svs_calc": True,
                    "ai_assistant": True,
                    "e1_generation": True,
                    "advanced_reports": True,
                    "priority_support": True,
                    "api_access": True,
                },
                quotas={
                    "transactions": -1,  # unlimited
                    "ocr_scans": -1,  # unlimited
                    "ai_conversations": -1,  # unlimited
                }
            ),
        ]
        
        for plan in plans:
            db.add(plan)
            print(f"  ✓ Created {plan.name} plan (€{plan.monthly_price}/month)")
        
        db.commit()
        print("\n✅ Plans seeded successfully!")
        print("\nCreated plans:")
        print("  1. Free - €0/month (50 transactions)")
        print("  2. Plus - €4.90/month (unlimited transactions, 20 OCR scans)")
        print("  3. Pro - €9.90/month (unlimited everything)")
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ Error seeding plans: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    print("🌱 Seeding subscription plans...\n")
    seed_plans()
