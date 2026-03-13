#!/usr/bin/env python
"""
Simple script to apply migration 003
Use this if alembic command is not available in your PATH
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    print("\n" + "="*70)
    print("APPLYING MIGRATION 003: add_property_id_to_transactions")
    print("="*70)
    
    try:
        from alembic.config import Config
        from alembic import command
        
        cfg = Config("alembic.ini")
        
        # Show current state
        print("\nCurrent migration state:")
        command.current(cfg)
        
        # Apply migration
        print("\nApplying migration to head...")
        command.upgrade(cfg, "head")
        
        print("\n✓ Migration applied successfully!")
        
        # Show new state
        print("\nNew migration state:")
        command.current(cfg)
        
        print("\n" + "="*70)
        print("Next steps:")
        print("  1. Run tests: python test_migration_003.py")
        print("="*70)
        
        return 0
        
    except Exception as e:
        print(f"\n✗ Error applying migration: {e}")
        import traceback
        traceback.print_exc()
        
        print("\nTroubleshooting:")
        print("  1. Ensure PostgreSQL is running: docker-compose up -d postgres")
        print("  2. Check .env file has correct database credentials")
        print("  3. Ensure dependencies installed: pip install -r requirements.txt")
        
        return 1


if __name__ == "__main__":
    sys.exit(main())
