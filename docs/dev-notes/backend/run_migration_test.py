#!/usr/bin/env python
"""
Automated migration test runner for migration 002
Applies migration, tests it, downgrades, tests downgrade, then re-applies
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    print("\n" + "="*70)
    print("MIGRATION 002 AUTOMATED TEST RUNNER")
    print("="*70)
    
    try:
        from alembic.config import Config
        from alembic import command
        from test_migration_002 import test_migration_upgrade, test_migration_downgrade
        
        cfg = Config("alembic.ini")
        
        # Step 1: Check current state
        print("\n[Step 1/6] Checking current migration state...")
        command.current(cfg)
        
        # Step 2: Upgrade to head
        print("\n[Step 2/6] Applying migration 002 (upgrade to head)...")
        command.upgrade(cfg, "head")
        print("✓ Migration applied")
        
        # Step 3: Test upgrade
        print("\n[Step 3/6] Testing upgrade state...")
        if not test_migration_upgrade():
            print("\n✗ Upgrade test failed!")
            return 1
        
        # Step 4: Downgrade
        print("\n[Step 4/6] Testing downgrade (rolling back one revision)...")
        command.downgrade(cfg, "-1")
        print("✓ Downgrade executed")
        
        # Step 5: Test downgrade
        print("\n[Step 5/6] Testing downgrade state...")
        if not test_migration_downgrade():
            print("\n✗ Downgrade test failed!")
            # Try to restore
            print("\nAttempting to restore database state...")
            command.upgrade(cfg, "head")
            return 1
        
        # Step 6: Re-upgrade
        print("\n[Step 6/6] Restoring database (re-applying migration)...")
        command.upgrade(cfg, "head")
        print("✓ Database restored to head")
        
        # Final verification
        print("\n[Final Verification] Confirming database state...")
        if not test_migration_upgrade():
            print("\n✗ Final verification failed!")
            return 1
        
        print("\n" + "="*70)
        print("✓✓✓ ALL TESTS PASSED ✓✓✓")
        print("="*70)
        print("\nMigration 002 has been successfully tested:")
        print("  ✓ Upgrade creates all required database objects")
        print("  ✓ Downgrade removes all objects cleanly")
        print("  ✓ Re-upgrade restores everything correctly")
        print("  ✓ Migration is fully reversible")
        print("\nTask 1.2 acceptance criteria met:")
        print("  ✓ Migration file created")
        print("  ✓ Migration includes all Property model fields")
        print("  ✓ Migration includes foreign key constraint to users table")
        print("  ✓ Migration includes indexes on user_id and status")
        print("  ✓ Migration tested with upgrade and downgrade")
        print("\n✅ Task 1.2 is COMPLETE")
        
        return 0
        
    except ImportError as e:
        print(f"\n✗ Import error: {e}")
        print("\nPlease ensure:")
        print("  1. You're in the backend directory")
        print("  2. Dependencies are installed: pip install -r requirements.txt")
        print("  3. Database is running: docker-compose up -d postgres")
        return 1
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        
        # Try to restore database state
        try:
            print("\nAttempting to restore database state...")
            from alembic.config import Config
            from alembic import command
            cfg = Config("alembic.ini")
            command.upgrade(cfg, "head")
            print("✓ Database restored")
        except:
            print("✗ Could not restore database state")
            print("Please manually run: alembic upgrade head")
        
        return 1


if __name__ == "__main__":
    sys.exit(main())
