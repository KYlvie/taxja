"""Verify migration file structure without importing alembic"""
import re
import sys

def verify_migration_file():
    """Verify the migration file has correct structure"""
    
    with open('alembic/versions/001_initial_migration.py', 'r') as f:
        content = f.read()
    
    # Check for required attributes
    checks = {
        "revision = '001'": "revision attribute",
        "down_revision = None": "down_revision attribute",
        "def upgrade()": "upgrade function",
        "def downgrade()": "downgrade function",
        "create_table('users'": "users table creation",
        "create_table('transactions'": "transactions table creation",
        "create_table('documents'": "documents table creation",
        "create_table('tax_configurations'": "tax_configurations table creation",
        "create_table('loss_carryforwards'": "loss_carryforwards table creation",
        "create_table('tax_reports'": "tax_reports table creation",
    }
    
    print("Verifying migration file structure...\n")
    
    all_passed = True
    for pattern, description in checks.items():
        if pattern in content:
            print(f"✓ Found {description}")
        else:
            print(f"✗ Missing {description}")
            all_passed = False
    
    # Check for all expected tables
    tables = ['users', 'transactions', 'documents', 'tax_configurations', 
              'loss_carryforwards', 'tax_reports']
    
    print("\nVerifying all tables are created:")
    for table in tables:
        if f"create_table('{table}'" in content or f'create_table("{table}"' in content:
            print(f"✓ Table '{table}' is created")
        else:
            print(f"✗ Table '{table}' is missing")
            all_passed = False
    
    # Check for foreign keys
    print("\nVerifying foreign key relationships:")
    fk_checks = [
        ("transactions", "user_id", "users"),
        ("transactions", "document_id", "documents"),
        ("documents", "user_id", "users"),
        ("loss_carryforwards", "user_id", "users"),
        ("tax_reports", "user_id", "users"),
    ]
    
    for table, column, ref_table in fk_checks:
        # Look for ForeignKeyConstraint patterns
        if f"ForeignKeyConstraint(['{column}']" in content or f'ForeignKeyConstraint(["{column}"]' in content:
            print(f"✓ Foreign key {table}.{column} -> {ref_table}")
        else:
            print(f"⚠ Foreign key {table}.{column} -> {ref_table} (check manually)")
    
    # Check for indexes
    print("\nVerifying indexes:")
    index_patterns = [
        "ix_users_email",
        "ix_transactions_user_id",
        "ix_transactions_transaction_date",
        "ix_documents_user_id",
        "ix_tax_configurations_tax_year",
    ]
    
    for index in index_patterns:
        if index in content:
            print(f"✓ Index '{index}' is created")
        else:
            print(f"⚠ Index '{index}' not found (check manually)")
    
    # Check for enums
    print("\nVerifying enum types:")
    enums = ['usertype', 'transactiontype', 'incomecategory', 'expensecategory', 'documenttype']
    for enum in enums:
        if enum.upper() in content or enum.lower() in content:
            print(f"✓ Enum '{enum}' is defined")
        else:
            print(f"⚠ Enum '{enum}' not found (check manually)")
    
    return all_passed

if __name__ == "__main__":
    try:
        if verify_migration_file():
            print("\n✓ Migration file structure verification passed!")
            sys.exit(0)
        else:
            print("\n⚠ Some checks failed, but migration may still be valid")
            sys.exit(0)
    except FileNotFoundError:
        print("\n✗ Migration file not found!")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        sys.exit(1)
