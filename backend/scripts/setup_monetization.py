"""Setup script for monetization system - install dependencies and run migrations"""
import subprocess
import sys
import os
from pathlib import Path

def run_command(cmd, cwd=None):
    """Run a shell command and return success status"""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print(f"Error: {result.stderr}")
            return False
        if result.stdout:
            print(result.stdout)
        return True
    except Exception as e:
        print(f"Failed to run command: {e}")
        return False

def run_migrations():
    """Run alembic migrations using Python API"""
    try:
        from alembic.config import Config
        from alembic import command
        
        backend_dir = Path(__file__).parent.parent
        alembic_cfg = Config(str(backend_dir / "alembic.ini"))
        
        # Run upgrade to revision 010 (monetization tables)
        command.upgrade(alembic_cfg, "010")
        return True
    except Exception as e:
        print(f"Migration error: {e}")
        return False

def main():
    """Main setup function"""
    backend_dir = Path(__file__).parent.parent
    
    print("=" * 60)
    print("MONETIZATION SYSTEM SETUP")
    print("=" * 60)
    
    # Step 1: Install stripe
    print("\n1. Installing stripe package...")
    if not run_command(f"{sys.executable} -m pip install stripe==8.0.0", cwd=backend_dir):
        print("❌ Failed to install stripe")
        return False
    print("✅ Stripe installed")
    
    # Step 2: Run migrations
    print("\n2. Running database migrations...")
    os.chdir(backend_dir)
    if not run_migrations():
        print("❌ Failed to run migrations")
        return False
    print("✅ Migrations completed")
    
    # Step 3: Seed plans
    print("\n3. Seeding subscription plans...")
    if not run_command(f"{sys.executable} scripts/seed_plans.py", cwd=backend_dir):
        print("❌ Failed to seed plans")
        return False
    print("✅ Plans seeded")
    
    print("\n" + "=" * 60)
    print("✅ SETUP COMPLETE!")
    print("=" * 60)
    print("\nNext step: Run quick_test.py to verify installation")
    print(f"  {sys.executable} scripts/quick_test.py")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
