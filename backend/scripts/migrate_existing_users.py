"""Migrate existing users to Free plan"""
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta

backend_dir = Path(__file__).parent.parent
os.chdir(backend_dir)
sys.path.insert(0, str(backend_dir))

from sqlalchemy import text
from app.db.base import SessionLocal
from app.models.user import User
from app.models.plan import Plan, PlanType
from app.models.subscription import Subscription, SubscriptionStatus

def migrate_users():
    """Migrate all existing users to Free plan"""
    db = SessionLocal()
    
    try:
        print("=" * 60)
        print("USER MIGRATION TO FREE PLAN")
        print("=" * 60)
        
        # Get Free plan
        free_plan = db.query(Plan).filter(Plan.plan_type == PlanType.FREE).first()
        if not free_plan:
            print("❌ Free plan not found. Run seed_plans_sql.py first.")
            return False
        
        print(f"\n✓ Free plan found (ID: {free_plan.id})")
        
        # Get all users without subscriptions
        users_without_sub = (
            db.query(User)
            .outerjoin(Subscription)
            .filter(Subscription.id == None)
            .all()
        )
        
        print(f"\n✓ Found {len(users_without_sub)} users without subscriptions")
        
        if len(users_without_sub) == 0:
            print("\n✅ All users already have subscriptions")
            return True
        
        # Create subscriptions for users
        created_count = 0
        for user in users_without_sub:
            subscription = Subscription(
                user_id=user.id,
                plan_id=free_plan.id,
                status=SubscriptionStatus.ACTIVE,
                current_period_start=datetime.utcnow(),
                current_period_end=datetime.utcnow() + timedelta(days=365)  # 1 year
            )
            db.add(subscription)
            created_count += 1
            
            if created_count % 100 == 0:
                print(f"  Processed {created_count} users...")
        
        db.commit()
        
        print(f"\n✅ Created {created_count} Free plan subscriptions")
        
        # Verify
        total_subs = db.query(Subscription).count()
        total_users = db.query(User).count()
        
        print(f"\n📊 Summary:")
        print(f"  Total users: {total_users}")
        print(f"  Total subscriptions: {total_subs}")
        print(f"  Coverage: {total_subs/total_users*100:.1f}%")
        
        print("\n" + "=" * 60)
        print("✅ MIGRATION COMPLETE")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    success = migrate_users()
    sys.exit(0 if success else 1)
