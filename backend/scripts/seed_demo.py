#!/usr/bin/env python3
"""
Seed demo data script for Taxja

Usage:
    python scripts/seed_demo.py [--clear]

Options:
    --clear     Clear existing demo data before seeding
"""

import sys
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.demo_data import seed_demo_data
from app.models.user import User
from app.models.transaction import Transaction
from app.models.document import Document


def clear_demo_data(db: Session):
    """Clear existing demo data"""
    print("Clearing existing demo data...")
    
    # Delete demo users and their related data (cascade will handle transactions/documents)
    demo_emails = [
        "employee@demo.taxja.at",
        "selfemployed@demo.taxja.at",
        "landlord@demo.taxja.at",
        "mixed@demo.taxja.at"
    ]
    
    deleted_count = db.query(User).filter(User.email.in_(demo_emails)).delete(synchronize_session=False)
    db.commit()
    
    print(f"Deleted {deleted_count} demo users and their related data")


def main():
    parser = argparse.ArgumentParser(description="Seed demo data for Taxja")
    parser.add_argument("--clear", action="store_true", help="Clear existing demo data before seeding")
    args = parser.parse_args()

    db = SessionLocal()
    
    try:
        if args.clear:
            clear_demo_data(db)
        
        print("\nSeeding demo data...")
        seed_demo_data(db)
        
        print("\n✅ Demo data seeded successfully!")
        print("\nYou can now log in with any of the demo accounts:")
        print("  - employee@demo.taxja.at")
        print("  - selfemployed@demo.taxja.at")
        print("  - landlord@demo.taxja.at")
        print("  - mixed@demo.taxja.at")
        print("\nPassword for all accounts: Demo2026!")
        
    except Exception as e:
        print(f"\n❌ Error seeding demo data: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
