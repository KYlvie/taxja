"""Update existing plan features and quotas in the database.

Run this after deploying the feature gate hierarchy changes to ensure
DB plan data matches the new feature assignments:
- Free: OCR_SCANNING + MULTI_LANGUAGE + 3 OCR scans/month
- Plus: bank_import, property_management, recurring_suggestions added
- Pro: all features (unchanged, but ensures completeness)

Usage:
    python scripts/update_plan_features.py
"""
import sys
import os
from pathlib import Path

backend_dir = Path(__file__).parent.parent
os.chdir(backend_dir)
sys.path.insert(0, str(backend_dir))

from sqlalchemy import text
from app.db.base import SessionLocal


def update_plans():
    db = SessionLocal()
    try:
        # Update Free plan: add ocr_scanning, multi_language, 3 OCR scans
        db.execute(text("""
            UPDATE plans
            SET features = '{"basic_tax_calc": true, "transaction_entry": true, "ocr_scanning": true, "multi_language": true}',
                quotas = '{"transactions": 30, "ocr_scans": 3, "ai_conversations": 0}'
            WHERE plan_type = 'free'
        """))
        print("  ✓ Updated Free plan: +ocr_scanning, +multi_language, ocr_scans=3")

        # Update Plus plan: ensure all Plus features are listed
        db.execute(text("""
            UPDATE plans
            SET features = '{"basic_tax_calc": true, "transaction_entry": true, "unlimited_transactions": true, "ocr_scanning": true, "full_tax_calc": true, "multi_language": true, "vat_calc": true, "svs_calc": true, "bank_import": true, "property_management": true, "recurring_suggestions": true}',
                quotas = '{"transactions": -1, "ocr_scans": 20, "ai_conversations": 0}'
            WHERE plan_type = 'plus'
        """))
        print("  ✓ Updated Plus plan: all Plus features complete")

        # Update Pro plan: ensure all features are listed
        db.execute(text("""
            UPDATE plans
            SET features = '{"basic_tax_calc": true, "transaction_entry": true, "unlimited_transactions": true, "ocr_scanning": true, "unlimited_ocr": true, "full_tax_calc": true, "multi_language": true, "vat_calc": true, "svs_calc": true, "bank_import": true, "property_management": true, "recurring_suggestions": true, "ai_assistant": true, "e1_generation": true, "advanced_reports": true, "priority_support": true, "api_access": true}',
                quotas = '{"transactions": -1, "ocr_scans": -1, "ai_conversations": -1}'
            WHERE plan_type = 'pro'
        """))
        print("  ✓ Updated Pro plan: all features complete")

        db.commit()
        print("\n✅ All plans updated successfully!")
        print("\nNote: Feature access is now hierarchy-based (Pro ⊇ Plus ⊇ Free).")
        print("The DB features JSON is kept in sync but the code uses plan level as authority.")
        return True

    except Exception as e:
        db.rollback()
        print(f"\n❌ Error updating plans: {e}")
        return False
    finally:
        db.close()


if __name__ == "__main__":
    print("🔄 Updating plan features and quotas...\n")
    if update_plans():
        sys.exit(0)
    else:
        sys.exit(1)
