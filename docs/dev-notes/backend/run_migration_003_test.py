"""Automated test runner for migration 003

This script:
1. Applies migration 003 (if not already applied)
2. Runs validation tests
3. Runs unit tests
"""
import subprocess
import sys
import os


def run_command(cmd, description):
    """Run a command and handle errors"""
    print(f"\n{'=' * 80}")
    print(f"{description}")
    print(f"{'=' * 80}")
    print(f"Command: {cmd}\n")
    
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    
    if result.returncode != 0:
        print(f"\n❌ FAILED: {description}")
        return False
    
    print(f"\n✅ SUCCESS: {description}")
    return True


def main():
    """Main test runner"""
    print("=" * 80)
    print("MIGRATION 003 TEST SUITE")
    print("Testing: Add property_id to transactions")
    print("=" * 80)
    
    # Change to backend directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # Step 1: Check current migration status
    if not run_command(
        "alembic current",
        "Step 1: Check current migration status"
    ):
        print("\n⚠ WARNING: Could not check migration status")
    
    # Step 2: Apply migration 003 (if needed)
    print("\n" + "=" * 80)
    print("Step 2: Applying migration 003 (if not already applied)")
    print("=" * 80)
    result = subprocess.run(
        "alembic upgrade 003",
        shell=True,
        capture_output=True,
        text=True
    )
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    
    if result.returncode != 0:
        if "Target database is not up to date" in result.stdout or "already at" in result.stdout:
            print("✓ Migration 003 already applied")
        else:
            print("❌ FAILED: Could not apply migration")
            return False
    else:
        print("✅ Migration 003 applied successfully")
    
    # Step 3: Run migration validation tests
    if not run_command(
        "python test_migration_003.py",
        "Step 3: Run migration validation tests"
    ):
        return False
    
    # Step 4: Run unit tests
    if not run_command(
        "pytest tests/test_transaction_property_link.py -v",
        "Step 4: Run unit tests for transaction-property linking"
    ):
        return False
    
    # Final summary
    print("\n" + "=" * 80)
    print("🎉 ALL TESTS PASSED!")
    print("=" * 80)
    print("\nMigration 003 Summary:")
    print("✓ Migration applied successfully")
    print("✓ Database schema validated")
    print("✓ Unit tests passed")
    print("\nThe following changes were made:")
    print("  • Added property_id column to transactions table (UUID, nullable)")
    print("  • Added is_system_generated column to transactions table (boolean, default false)")
    print("  • Added foreign key constraint: transactions.property_id -> properties.id")
    print("  • Added index on property_id for query performance")
    print("  • Configured ON DELETE SET NULL for property deletion")
    print("=" * 80)
    
    return True


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
