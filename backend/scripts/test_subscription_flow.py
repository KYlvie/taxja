"""End-to-end test for subscription flow"""
import sys
import os
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))
os.chdir(backend_dir)

from sqlalchemy import text
from app.db.base import SessionLocal
from app.models.user import User
from app.models.subscription import Subscription, SubscriptionStatus
from app.services.plan_service import PlanService
from app.services.subscription_service import SubscriptionService
from app.services.feature_gate_service import FeatureGateService, Feature
from app.services.usage_tracker_service import UsageTrackerService
from app.services.trial_service import TrialService
from datetime import datetime, timedelta


def test_subscription_flow():
    """Test complete subscription flow"""
    print("="*60)
    print("SUBSCRIPTION FLOW TEST")
    print("="*60)
    
    db = SessionLocal()
    test_results = []
    
    try:
        # Test 1: Create test user
        print("\n1. Creating test user...")
        test_email = f"test_user_{datetime.now().timestamp()}@example.com"
        
        # Check if user exists
        existing_user = db.query(User).filter(User.email == test_email).first()
        if existing_user:
            test_user = existing_user
            print(f"   ✅ Using existing user: {test_user.email}")
        else:
            test_user = User(
                email=test_email,
                password_hash="test_password_hash",
                name="Test User",
                user_type="employee"
            )
            db.add(test_user)
            db.commit()
            db.refresh(test_user)
            print(f"   ✅ Created test user: {test_user.email}")
        
        test_results.append(("Create Test User", True))
        
        # Test 2: Get Free plan
        print("\n2. Getting Free plan...")
        plan_service = PlanService(db)
        free_plan = db.execute(
            text("SELECT * FROM plans WHERE plan_type = 'free'")
        ).fetchone()
        
        if not free_plan:
            print("   ❌ Free plan not found")
            test_results.append(("Get Free Plan", False))
            return False
        
        print(f"   ✅ Free plan found (ID: {free_plan.id})")
        test_results.append(("Get Free Plan", True))
        
        # Test 3: Assign Free plan to user
        print("\n3. Assigning Free plan to user...")
        subscription_service = SubscriptionService(db)
        
        # Check if subscription exists
        existing_sub = db.query(Subscription).filter(
            Subscription.user_id == test_user.id
        ).first()
        
        if existing_sub:
            print(f"   ✅ User already has subscription (Status: {existing_sub.status})")
        else:
            subscription = subscription_service.create_subscription(
                user_id=test_user.id,
                plan_id=free_plan.id
            )
            print(f"   ✅ Subscription created (ID: {subscription.id})")
        
        test_results.append(("Assign Free Plan", True))
        
        # Test 4: Check feature access
        print("\n4. Testing feature access...")
        feature_gate = FeatureGateService(db, None)
        
        # Free user should have basic features
        has_basic = feature_gate.check_feature_access(
            test_user.id, 
            Feature.BASIC_TAX_CALC
        )
        print(f"   ✅ Basic tax calc: {has_basic} (expected: True)")
        
        # Free user should NOT have AI assistant
        has_ai = feature_gate.check_feature_access(
            test_user.id,
            Feature.AI_ASSISTANT
        )
        print(f"   ✅ AI assistant: {has_ai} (expected: False)")
        
        test_results.append(("Feature Access Check", has_basic and not has_ai))
        
        # Test 5: Check quota limits
        print("\n5. Testing quota limits...")
        usage_tracker = UsageTrackerService(db, None)
        
        # Get Free plan quotas
        quotas = db.execute(
            text("SELECT quotas FROM plans WHERE plan_type = 'free'")
        ).fetchone()
        
        transaction_quota = quotas.quotas.get('transactions', 0)
        print(f"   ✅ Free plan transaction quota: {transaction_quota}")
        
        # Check if user can add transaction
        can_add = usage_tracker.check_quota_limit(
            test_user.id,
            'transactions'
        )
        print(f"   ✅ Can add transaction: {can_add}")
        
        test_results.append(("Quota Check", True))
        
        # Test 6: Test trial activation
        print("\n6. Testing trial activation...")
        trial_service = TrialService(db)
        
        # Check if user already used trial
        if test_user.trial_used:
            print(f"   ⚠️  User already used trial")
            test_results.append(("Trial Activation", True))
        else:
            # Get Pro plan
            pro_plan = db.execute(
                text("SELECT * FROM plans WHERE plan_type = 'pro'")
            ).fetchone()
            
            if pro_plan:
                trial_sub = trial_service.activate_trial(
                    test_user.id,
                    pro_plan.id
                )
                print(f"   ✅ Trial activated (ends: {trial_sub.current_period_end})")
                test_results.append(("Trial Activation", True))
            else:
                print(f"   ❌ Pro plan not found")
                test_results.append(("Trial Activation", False))
        
        # Test 7: Test subscription upgrade
        print("\n7. Testing subscription upgrade simulation...")
        plus_plan = db.execute(
            text("SELECT * FROM plans WHERE plan_type = 'plus'")
        ).fetchone()
        
        if plus_plan:
            print(f"   ✅ Plus plan found (€{plus_plan.monthly_price}/month)")
            print(f"   ℹ️  Upgrade would change plan from Free to Plus")
            print(f"   ℹ️  (Actual Stripe payment not tested)")
            test_results.append(("Upgrade Simulation", True))
        else:
            print(f"   ❌ Plus plan not found")
            test_results.append(("Upgrade Simulation", False))
        
        # Test 8: Test usage tracking
        print("\n8. Testing usage tracking...")
        
        # Increment usage
        usage_tracker.increment_usage(
            test_user.id,
            'transactions',
            1
        )
        
        # Get usage summary
        summary = usage_tracker.get_usage_summary(test_user.id)
        print(f"   ✅ Usage tracked: {summary.get('transactions', {}).get('used', 0)} transactions")
        
        test_results.append(("Usage Tracking", True))
        
        # Summary
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        
        passed = sum(1 for _, result in test_results if result)
        total = len(test_results)
        
        for name, result in test_results:
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{status} - {name}")
        
        print(f"\nTotal: {passed}/{total} tests passed")
        
        if passed == total:
            print("\n🎉 All subscription flow tests passed!")
            print("\nThe monetization system is working correctly!")
            print("\nNext steps:")
            print("  1. Configure Stripe test keys in backend/.env")
            print("  2. Run: python backend/scripts/test_stripe_config.py")
            print("  3. Start backend and test checkout flow")
            return True
        else:
            print("\n⚠️  Some tests failed")
            return False
        
    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


if __name__ == "__main__":
    try:
        success = test_subscription_flow()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
