"""Reset database: drop schema, create tables from models, seed data, create admin."""
import subprocess
import sys
from datetime import datetime


def main():
    from sqlalchemy import text, inspect
    from app.db.base import engine, Base, SessionLocal

    # Import ALL models so Base.metadata is complete
    from app.models.user import User, UserType
    from app.models.transaction import Transaction
    from app.models.document import Document
    from app.models.tax_configuration import TaxConfiguration
    from app.models.tax_report import TaxReport
    from app.models.classification_correction import ClassificationCorrection
    from app.models.loss_carryforward import LossCarryforward
    try:
        from app.models.chat_message import ChatMessage
    except Exception:
        pass
    try:
        from app.models.property import Property
    except Exception:
        pass
    try:
        from app.models.property_loan import PropertyLoan
    except Exception:
        pass
    try:
        from app.models.recurring_transaction import RecurringTransaction
    except Exception:
        pass
    try:
        from app.models.notification import Notification
    except Exception:
        pass
    try:
        from app.models.subscription import Subscription, Plan, UsageRecord, PaymentEvent
    except Exception:
        pass
    try:
        from app.models.uat_feedback import UATFeedback, UATSession
    except Exception:
        pass
    try:
        from app.models.dismissed_suggestion import DismissedSuggestion
    except Exception:
        pass
    try:
        from app.models.audit_log import AuditLog
    except Exception:
        pass

    # Step 1: Drop and recreate public schema
    print("=== Step 1: DROP SCHEMA public CASCADE ===")
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.execute(text("GRANT ALL ON SCHEMA public TO PUBLIC"))
    print("Done.")

    # Step 2: Create all tables from SQLAlchemy models
    print("\n=== Step 2: Creating tables from models ===")
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"Created {len(tables)} tables: {', '.join(sorted(tables))}")

    # Step 3: Stamp alembic version to head (so future migrations work)
    print("\n=== Step 3: Stamping alembic version to head ===")
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)"
        ))
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "stamp", "head"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print("Alembic stamped to head.")
    else:
        print("Alembic stamp output:", result.stdout, result.stderr)

    # Step 4: Create admin user
    print("\n=== Step 4: Creating admin user ===")
    from app.core.security import get_password_hash
    db = SessionLocal()
    try:
        admin = User(
            email="admin@taxja.at",
            password_hash=get_password_hash("Admin123!"),
            name="Admin",
            user_type=UserType.SELF_EMPLOYED,
            is_admin=True,
            language="zh",
            account_status="active",
            email_verified=True,
            disclaimer_accepted_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(admin)
        db.commit()
        print("Admin created: admin@taxja.at / Admin123!")
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        raise
    finally:
        db.close()

    # Step 5: Seed tax configurations
    print("\n=== Step 5: Seeding tax configs ===")
    from app.db.seed_tax_config import seed_tax_configs
    seed_tax_configs()

    print("\n=== All done! ===")
    print("Login: admin@taxja.at / Admin123!")


if __name__ == "__main__":
    main()
