"""Test admin API endpoints"""
import sys
import os
from pathlib import Path

backend_dir = Path(__file__).parent.parent
os.chdir(backend_dir)
sys.path.insert(0, str(backend_dir))

from sqlalchemy import text
from app.db.base import SessionLocal

def test_admin_endpoints():
    """Test that admin endpoints can be imported"""
    print("=" * 60)
    print("ADMIN API TEST")
    print("=" * 60)
    
    try:
        # Test import
        print("\n1. Testing admin endpoint import...")
        from app.api.v1.endpoints import admin
        print("   ✅ Admin endpoints imported successfully")
        
        # Test router
        print("\n2. Testing admin router...")
        assert hasattr(admin, 'router'), "Router not found"
        print(f"   ✅ Router found with {len(admin.router.routes)} routes")
        
        # List all routes
        print("\n3. Admin API routes:")
        for route in admin.router.routes:
            if hasattr(route, 'methods') and hasattr(route, 'path'):
                methods = ', '.join(route.methods)
                print(f"   - {methods:10} {route.path}")
        
        # Test database connection
        print("\n4. Testing database connection...")
        db = SessionLocal()
        try:
            count = db.execute(text("SELECT COUNT(*) FROM plans")).scalar()
            print(f"   ✅ Database connected, {count} plans found")
        finally:
            db.close()
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
        print("\nAdmin API is ready to use!")
        print("\nExample endpoints:")
        print("  GET  /api/v1/admin/subscriptions")
        print("  GET  /api/v1/admin/analytics/revenue")
        print("  POST /api/v1/admin/subscriptions/{user_id}/grant-trial")
        print("\nStart the server to test:")
        print("  uvicorn app.main:app --reload")
        print("\nThen visit:")
        print("  http://localhost:8000/docs")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_admin_endpoints()
    sys.exit(0 if success else 1)
