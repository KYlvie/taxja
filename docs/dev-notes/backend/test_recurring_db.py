"""Test recurring transactions directly from database"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.recurring_transaction import RecurringTransaction
from app.models.user import User

# Database connection
DATABASE_URL = "postgresql://taxja:taxja_password@localhost:5432/taxja"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

db = SessionLocal()

try:
    # Get user
    user = db.query(User).filter(User.email == "ylvie.khoo@hotmail.com").first()
    if not user:
        print("User not found!")
        exit(1)
    
    print(f"User found: {user.email} (ID: {user.id})")
    
    # Get recurring transactions
    recurring_txns = db.query(RecurringTransaction).filter(
        RecurringTransaction.user_id == user.id
    ).all()
    
    print(f"\nTotal recurring transactions: {len(recurring_txns)}")
    
    if recurring_txns:
        for txn in recurring_txns:
            print(f"\n- ID: {txn.id}")
            print(f"  Type: {txn.recurring_type}")
            print(f"  Description: {txn.description}")
            print(f"  Amount: {txn.amount}")
            print(f"  Frequency: {txn.frequency}")
            print(f"  Active: {txn.is_active}")
    else:
        print("\nNo recurring transactions found for this user.")
        print("This is expected if you haven't created any yet.")
    
finally:
    db.close()
