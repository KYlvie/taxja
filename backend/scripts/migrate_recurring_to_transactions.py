"""
Migrate data from recurring_transactions table into transactions table with is_recurring=true.
This is a one-time migration script for the recurring merge (Task 12).

Usage:
    cd backend
    python scripts/migrate_recurring_to_transactions.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from app.core.config import settings


def migrate():
    engine = create_engine(settings.DATABASE_URL)
    with engine.connect() as conn:
        # Check if recurring_transactions table exists
        result = conn.execute(text(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'recurring_transactions')"
        ))
        if not result.scalar():
            print("recurring_transactions table does not exist. Nothing to migrate.")
            return

        # Get all recurring transactions
        rows = conn.execute(text("SELECT * FROM recurring_transactions")).fetchall()
        if not rows:
            print("No recurring transactions to migrate.")
            return

        print(f"Found {len(rows)} recurring transactions to migrate.")

        # Map recurring_type -> (transaction type, category)
        type_map = {
            "rental_income": ("INCOME", "RENTAL"),
            "loan_interest": ("EXPENSE", "LOAN_INTEREST"),
            "depreciation": ("EXPENSE", "DEPRECIATION"),
            "other_income": ("INCOME", "RENTAL"),  # fallback to RENTAL since no OTHER_INCOME enum
            "other_expense": ("EXPENSE", "OTHER"),
            "manual": None,
        }

        migrated = 0
        for row in rows:
            row_dict = row._mapping

            # Determine type and category
            rt = row_dict["recurring_type"]
            if rt == "manual":
                txn_type = row_dict["transaction_type"].upper()
                category = row_dict["category"].upper()
            elif rt in type_map and type_map[rt]:
                txn_type, category = type_map[rt]
            else:
                txn_type = row_dict["transaction_type"].upper()
                category = row_dict["category"].upper()

            # Build income_category / expense_category
            income_cat = category if txn_type == "INCOME" else None
            expense_cat = category if txn_type == "EXPENSE" else None

            # Insert into transactions
            conn.execute(text("""
                INSERT INTO transactions (
                    user_id, type, amount, transaction_date, description,
                    income_category, expense_category,
                    is_deductible, property_id,
                    is_recurring, recurring_frequency,
                    recurring_start_date, recurring_end_date,
                    recurring_day_of_month, recurring_is_active,
                    recurring_next_date, recurring_last_generated,
                    import_source, created_at, updated_at
                ) VALUES (
                    :user_id, CAST(:txn_type AS transactiontype), :amount, :start_date, :description,
                    CAST(:income_cat AS incomecategory), CAST(:expense_cat AS expensecategory),
                    :is_deductible, :property_id,
                    true, :frequency,
                    :start_date, :end_date,
                    :day_of_month, :is_active,
                    :next_date, :last_generated,
                    'migrated_recurring', :created_at, :updated_at
                )
            """), {
                "user_id": row_dict["user_id"],
                "txn_type": txn_type,
                "amount": row_dict["amount"],
                "start_date": row_dict["start_date"],
                "description": row_dict["description"],
                "income_cat": income_cat,
                "expense_cat": expense_cat,
                "is_deductible": txn_type == "EXPENSE",
                "property_id": row_dict.get("property_id"),
                "frequency": row_dict["frequency"],
                "end_date": row_dict.get("end_date"),
                "day_of_month": row_dict.get("day_of_month"),
                "is_active": row_dict.get("is_active", True),
                "next_date": row_dict.get("next_generation_date"),
                "last_generated": row_dict.get("last_generated_date"),
                "created_at": row_dict["created_at"],
                "updated_at": row_dict["updated_at"],
            })
            migrated += 1

        conn.commit()
        print(f"Successfully migrated {migrated} recurring transactions into transactions table.")


if __name__ == "__main__":
    migrate()
