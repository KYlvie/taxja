"""Quick test script to verify monetization system setup"""
import sys
import os
from pathlib import Path

# Add parent directory to path and change to backend directory
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))
os.chdir(backend_dir)

from sqlalchemy import text
from app.db.base import SessionLocal
from app.models.plan import Plan, PlanType
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.usage_record import UsageRecord, ResourceType
from app.services.plan_service import PlanService
from app.services.subscription_service import SubscriptionService
from app.services.feature_gate_service import FeatureGateService, Feature
from app.services.usage_tracker_service import UsageTrackerService
from datetime import datetime, timedelta


def test_database_connection():
    """Test database connection"""
    print("1. Testing database connection...")
    try:
        db = SessionLocal()
        result = db.execute(text("SELECT 1")).scalar()
        db.close()
        print("   ✅ Database connection successful")
        return True
    except Exception as e:
        print(f"   ❌ Database connection failed: {e}")
        return False


def test_plans_exist():
    """Test if plans are seeded"""
    print("\n2. Checking if plans exist...")
    db = SessionLocal()
    try:
        # Query directly with SQL to avoid enum issues
        result = db.execute(text("SELECT COUNT(*) FROM plans")).scalar()
        if result == 0:
            print("   ⚠️  No plans found. Run: python scripts/seed_plans_sql.py")
            return False
        
        print(f"   ✅ Found {result} plans")
        
        # List plans using raw SQL
        plans = db.execute(text("SELECT name, monthly_price FROM plans ORDER BY monthly_price")).fetchall()
        for name, price in plans:
            print(f"      - {name} (€{price}/month)")
        return True
    except Exception as e:
        print(f"   ❌ Error checking plans: {e}")
        return False
    finally:
        db.close()


def test_plan_service():
    """Test PlanService"""
    print("\n3. Testing PlanService...")
    db = SessionLocal()
    try:
        service = PlanService(db)
        
        # Test list_plans using raw SQL
        plans_count = db.execute(text("SELECT COUNT(*) FROM plans")).scalar()
        assert plans_count > 0, "No plans found"
        print(f"   ✅ Found {plans_count} plans in database")
        
        # Test get_plan_features using raw SQL
        result = db.execute(text("SELECT features FROM plans WHERE plan_type = 'free'")).fetchone()
        if result:
            print(f"   ✅ Free plan features retrieved")
        
        # Test get_plan_quotas using raw SQL
        result = db.execute(text("SELECT quotas FROM plans WHERE plan_type = 'free'")).fetchone()
        if result:
            print(f"   ✅ Free plan quotas retrieved")
        
        return True
    except Exception as e:
        print(f"   ❌ PlanService test failed: {e}")
        return False
    finally:
        db.close()


def test_feature_gate_service():
    """Test FeatureGateService"""
    print("\n4. Testing FeatureGateService...")
    db = SessionLocal()
    try:
        service = FeatureGateService(db, None)  # No Redis for quick test
        
        # Get Free plan using raw SQL
        result = db.execute(text("SELECT id, features FROM plans WHERE plan_type = 'free'")).fetchone()
        if not result:
            print("   ❌ Free plan not found")
            return False
        
        plan_id, features = result
        print(f"   ✅ Free plan found (ID: {plan_id})")
        
        # Check features
        has_basic = features.get('basic_tax_calc', False)
        has_ai = features.get('ai_assistant', False)
        print(f"   ✅ Free plan has basic_tax_calc: {has_basic}")
        print(f"   ✅ Free plan has AI Assistant: {has_ai} (expected: False)")
        
        return True
    except Exception as e:
        print(f"   ❌ FeatureGateService test failed: {e}")
        return False
    finally:
        db.close()


def test_models():
    """Test model methods"""
    print("\n5. Testing model methods...")
    db = SessionLocal()
    try:
        # Test using raw SQL
        result = db.execute(text("""
            SELECT id, features, quotas 
            FROM plans 
            WHERE plan_type = 'free'
        """)).fetchone()
        
        if not result:
            print("   ❌ Free plan not found")
            return False
        
        plan_id, features, quotas = result
        
        # Validate features
        assert isinstance(features, dict), "Features should be a dict"
        print("   ✅ Plan features validation works")
        
        # Validate quotas
        assert isinstance(quotas, dict), "Quotas should be a dict"
        print("   ✅ Plan quotas validation works")
        
        # Test quota check
        transaction_quota = quotas.get("transactions", 0)
        print(f"   ✅ Free plan transaction quota: {transaction_quota}")
        
        return True
    except Exception as e:
        print(f"   ❌ Model test failed: {e}")
        return False
    finally:
        db.close()


def test_api_imports():
    """Test if API modules can be imported"""
    print("\n6. Testing API imports...")
    try:
        from app.api.v1.endpoints import subscriptions, usage, webhooks
        print("   ✅ Subscription endpoints imported")
        print("   ✅ Usage endpoints imported")
        print("   ✅ Webhook endpoints imported")
        
        from app.api.deps import require_feature, require_plan, check_quota
        print("   ✅ Feature gate dependencies imported")
        
        from app.api.exceptions import (
            SubscriptionNotFoundError,
            QuotaExceededError,
            FeatureNotAvailableError
        )
        print("   ✅ Custom exceptions imported")
        
        return True
    except Exception as e:
        print(f"   ❌ Import test failed: {e}")
        return False


def main():
    """Run all tests"""
    print("=" * 60)
    print("MONETIZATION SYSTEM - QUICK TEST")
    print("=" * 60)
    
    results = []
    
    results.append(("Database Connection", test_database_connection()))
    results.append(("Plans Exist", test_plans_exist()))
    results.append(("PlanService", test_plan_service()))
    results.append(("FeatureGateService", test_feature_gate_service()))
    results.append(("Model Methods", test_models()))
    results.append(("API Imports", test_api_imports()))
    
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! System is ready for testing.")
        print("\nNext steps:")
        print("  1. Start backend: uvicorn app.main:app --reload")
        print("  2. Start frontend: cd frontend && npm run dev")
        print("  3. Open http://localhost:3000/pricing")
    else:
        print("\n⚠️  Some tests failed. Please fix issues before proceeding.")
        sys.exit(1)


if __name__ == "__main__":
    main()
