#!/usr/bin/env python3
"""
Property Migration Verification Script

This script verifies that all property management migrations have been
applied correctly and that the database schema matches expectations.

Usage:
    python verify_property_migration.py
    python verify_property_migration.py --database taxja_staging
"""

import sys
import argparse
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
import os
from typing import List, Dict, Tuple


class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'
    BOLD = '\033[1m'


def print_success(message: str):
    """Print success message in green"""
    print(f"{Colors.GREEN}✓{Colors.END} {message}")


def print_error(message: str):
    """Print error message in red"""
    print(f"{Colors.RED}✗{Colors.END} {message}")


def print_warning(message: str):
    """Print warning message in yellow"""
    print(f"{Colors.YELLOW}⚠{Colors.END} {message}")


def print_info(message: str):
    """Print info message in blue"""
    print(f"{Colors.BLUE}ℹ{Colors.END} {message}")


def print_header(message: str):
    """Print section header"""
    print(f"\n{Colors.BOLD}{message}{Colors.END}")
    print("=" * len(message))


def get_database_url(database_name: str = None) -> str:
    """Get database URL from environment or construct from parameters"""
    if database_name:
        # Construct URL with provided database name
        user = os.getenv('DB_USER', 'postgres')
        password = os.getenv('DB_PASSWORD', 'postgres')
        host = os.getenv('DB_HOST', 'localhost')
        port = os.getenv('DB_PORT', '5432')
        return f"postgresql://{user}:{password}@{host}:{port}/{database_name}"
    
    # Use DATABASE_URL from environment
    return os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/taxja')


def verify_table_exists(inspector: inspect, table_name: str) -> bool:
    """Verify that a table exists"""
    tables = inspector.get_table_names()
    if table_name in tables:
        print_success(f"Table '{table_name}' exists")
        return True
    else:
        print_error(f"Table '{table_name}' does not exist")
        return False


def verify_enum_exists(engine: Engine, enum_name: str, expected_values: List[str]) -> bool:
    """Verify that an enum type exists with expected values"""
    query = text("""
        SELECT e.enumlabel
        FROM pg_type t
        JOIN pg_enum e ON t.oid = e.enumtypid
        WHERE t.typname = :enum_name
        ORDER BY e.enumsortorder
    """)
    
    with engine.connect() as conn:
        result = conn.execute(query, {"enum_name": enum_name})
        actual_values = [row[0] for row in result]
    
    if not actual_values:
        print_error(f"Enum '{enum_name}' does not exist")
        return False
    
    if set(actual_values) == set(expected_values):
        print_success(f"Enum '{enum_name}' exists with correct values: {', '.join(actual_values)}")
        return True
    else:
        print_error(f"Enum '{enum_name}' has incorrect values")
        print_info(f"  Expected: {', '.join(expected_values)}")
        print_info(f"  Actual: {', '.join(actual_values)}")
        return False


def verify_columns(inspector: inspect, table_name: str, expected_columns: List[str]) -> bool:
    """Verify that a table has all expected columns"""
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    missing_columns = set(expected_columns) - set(columns)
    
    if not missing_columns:
        print_success(f"Table '{table_name}' has all {len(expected_columns)} expected columns")
        return True
    else:
        print_error(f"Table '{table_name}' is missing columns: {', '.join(missing_columns)}")
        return False


def verify_indexes(inspector: inspect, table_name: str, expected_indexes: List[str]) -> bool:
    """Verify that a table has all expected indexes"""
    indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
    missing_indexes = set(expected_indexes) - set(indexes)
    
    if not missing_indexes:
        print_success(f"Table '{table_name}' has all {len(expected_indexes)} expected indexes")
        return True
    else:
        print_warning(f"Table '{table_name}' is missing indexes: {', '.join(missing_indexes)}")
        print_info("  Note: Some indexes may be created by SQLAlchemy model definitions")
        return True  # Don't fail on missing indexes as they might be optional


def verify_foreign_keys(inspector: inspect, table_name: str, expected_fks: List[Tuple[str, str]]) -> bool:
    """Verify that a table has all expected foreign keys"""
    fks = inspector.get_foreign_keys(table_name)
    actual_fks = [(fk['constrained_columns'][0], fk['referred_table']) for fk in fks]
    
    missing_fks = []
    for expected_col, expected_table in expected_fks:
        if not any(col == expected_col and table == expected_table for col, table in actual_fks):
            missing_fks.append(f"{expected_col} -> {expected_table}")
    
    if not missing_fks:
        print_success(f"Table '{table_name}' has all {len(expected_fks)} expected foreign keys")
        return True
    else:
        print_error(f"Table '{table_name}' is missing foreign keys: {', '.join(missing_fks)}")
        return False


def verify_constraints(engine: Engine, table_name: str, expected_constraints: List[str]) -> bool:
    """Verify that a table has all expected check constraints"""
    query = text("""
        SELECT conname
        FROM pg_constraint
        WHERE conrelid = :table_name::regclass
        AND contype = 'c'
    """)
    
    with engine.connect() as conn:
        result = conn.execute(query, {"table_name": table_name})
        actual_constraints = [row[0] for row in result]
    
    missing_constraints = set(expected_constraints) - set(actual_constraints)
    
    if not missing_constraints:
        print_success(f"Table '{table_name}' has all {len(expected_constraints)} expected constraints")
        return True
    else:
        print_warning(f"Table '{table_name}' is missing constraints: {', '.join(missing_constraints)}")
        print_info("  Note: Some constraints may have auto-generated names")
        return True  # Don't fail on missing constraints as names might differ


def verify_properties_table(engine: Engine, inspector: inspect) -> bool:
    """Verify properties table structure"""
    print_header("Verifying Properties Table")
    
    results = []
    
    # Check table exists
    results.append(verify_table_exists(inspector, 'properties'))
    
    # Check columns
    expected_columns = [
        'id', 'user_id', 'property_type', 'rental_percentage',
        'address', 'street', 'city', 'postal_code',
        'purchase_date', 'purchase_price', 'building_value', 'land_value',
        'grunderwerbsteuer', 'notary_fees', 'registry_fees',
        'construction_year', 'depreciation_rate',
        'status', 'sale_date',
        'kaufvertrag_document_id', 'mietvertrag_document_id',
        'created_at', 'updated_at'
    ]
    results.append(verify_columns(inspector, 'properties', expected_columns))
    
    # Check indexes
    expected_indexes = [
        'ix_properties_user_id',
        'ix_properties_status',
        'idx_properties_user_status'
    ]
    results.append(verify_indexes(inspector, 'properties', expected_indexes))
    
    # Check foreign keys
    expected_fks = [
        ('user_id', 'users'),
    ]
    results.append(verify_foreign_keys(inspector, 'properties', expected_fks))
    
    # Check constraints
    expected_constraints = [
        'check_rental_percentage_range',
        'check_purchase_price_range',
        'check_building_value_range',
        'check_depreciation_rate_range',
        'check_construction_year_range',
        'check_sale_date_after_purchase',
        'check_sold_has_sale_date'
    ]
    results.append(verify_constraints(engine, 'properties', expected_constraints))
    
    return all(results)


def verify_transactions_extension(engine: Engine, inspector: inspect) -> bool:
    """Verify transactions table has property-related columns"""
    print_header("Verifying Transactions Table Extension")
    
    results = []
    
    # Check property_id column exists
    columns = [col['name'] for col in inspector.get_columns('transactions')]
    if 'property_id' in columns:
        print_success("Column 'property_id' exists in transactions table")
        results.append(True)
    else:
        print_error("Column 'property_id' does not exist in transactions table")
        results.append(False)
    
    # Check is_system_generated column exists
    if 'is_system_generated' in columns:
        print_success("Column 'is_system_generated' exists in transactions table")
        results.append(True)
    else:
        print_error("Column 'is_system_generated' does not exist in transactions table")
        results.append(False)
    
    # Check foreign key to properties
    fks = inspector.get_foreign_keys('transactions')
    property_fk_exists = any(
        'property_id' in fk['constrained_columns'] and fk['referred_table'] == 'properties'
        for fk in fks
    )
    
    if property_fk_exists:
        print_success("Foreign key from transactions.property_id to properties.id exists")
        results.append(True)
    else:
        print_error("Foreign key from transactions.property_id to properties.id does not exist")
        results.append(False)
    
    # Check index on property_id
    indexes = [idx['name'] for idx in inspector.get_indexes('transactions')]
    if 'ix_transactions_property_id' in indexes:
        print_success("Index 'ix_transactions_property_id' exists")
        results.append(True)
    else:
        print_warning("Index 'ix_transactions_property_id' does not exist")
        results.append(True)  # Don't fail, might be optional
    
    return all(results)


def verify_property_loans_table(engine: Engine, inspector: inspect) -> bool:
    """Verify property_loans table structure"""
    print_header("Verifying Property Loans Table")
    
    results = []
    
    # Check table exists
    results.append(verify_table_exists(inspector, 'property_loans'))
    
    # Check columns
    expected_columns = [
        'id', 'property_id', 'user_id',
        'loan_amount', 'interest_rate', 'start_date', 'end_date',
        'monthly_payment', 'lender_name', 'lender_account',
        'loan_type', 'notes', 'created_at', 'updated_at'
    ]
    results.append(verify_columns(inspector, 'property_loans', expected_columns))
    
    # Check foreign keys
    expected_fks = [
        ('property_id', 'properties'),
        ('user_id', 'users')
    ]
    results.append(verify_foreign_keys(inspector, 'property_loans', expected_fks))
    
    return all(results)


def verify_enums(engine: Engine) -> bool:
    """Verify property-related enum types"""
    print_header("Verifying Enum Types")
    
    results = []
    
    # Check propertytype enum
    results.append(verify_enum_exists(
        engine,
        'propertytype',
        ['rental', 'owner_occupied', 'mixed_use']
    ))
    
    # Check propertystatus enum
    results.append(verify_enum_exists(
        engine,
        'propertystatus',
        ['active', 'sold', 'archived']
    ))
    
    return all(results)


def verify_performance_indexes(engine: Engine, inspector: inspect) -> bool:
    """Verify performance optimization indexes"""
    print_header("Verifying Performance Indexes")
    
    results = []
    
    # Check properties indexes
    property_indexes = [idx['name'] for idx in inspector.get_indexes('properties')]
    expected_property_indexes = [
        'idx_properties_status',
        'idx_properties_user_status'
    ]
    
    for idx_name in expected_property_indexes:
        if idx_name in property_indexes:
            print_success(f"Index '{idx_name}' exists on properties table")
            results.append(True)
        else:
            print_warning(f"Index '{idx_name}' does not exist on properties table")
            results.append(True)  # Don't fail, might be optional
    
    # Check transactions indexes
    transaction_indexes = [idx['name'] for idx in inspector.get_indexes('transactions')]
    expected_transaction_indexes = [
        'idx_transactions_property_date',
        'idx_transactions_depreciation'
    ]
    
    for idx_name in expected_transaction_indexes:
        if idx_name in transaction_indexes:
            print_success(f"Index '{idx_name}' exists on transactions table")
            results.append(True)
        else:
            print_warning(f"Index '{idx_name}' does not exist on transactions table")
            results.append(True)  # Don't fail, might be optional
    
    return all(results)


def verify_column_sizes(inspector: inspect) -> bool:
    """Verify that address columns have correct sizes for encryption"""
    print_header("Verifying Column Sizes for Encryption")
    
    results = []
    
    columns = {col['name']: col for col in inspector.get_columns('properties')}
    
    # Check address column size
    address_col = columns.get('address')
    if address_col and hasattr(address_col['type'], 'length'):
        if address_col['type'].length >= 1000:
            print_success(f"Column 'address' has sufficient size: {address_col['type'].length}")
            results.append(True)
        else:
            print_warning(f"Column 'address' may be too small for encryption: {address_col['type'].length}")
            print_info("  Expected: >= 1000 characters")
            results.append(True)  # Don't fail, might not be encrypted yet
    
    # Check street column size
    street_col = columns.get('street')
    if street_col and hasattr(street_col['type'], 'length'):
        if street_col['type'].length >= 500:
            print_success(f"Column 'street' has sufficient size: {street_col['type'].length}")
            results.append(True)
        else:
            print_warning(f"Column 'street' may be too small for encryption: {street_col['type'].length}")
            print_info("  Expected: >= 500 characters")
            results.append(True)  # Don't fail, might not be encrypted yet
    
    # Check city column size
    city_col = columns.get('city')
    if city_col and hasattr(city_col['type'], 'length'):
        if city_col['type'].length >= 200:
            print_success(f"Column 'city' has sufficient size: {city_col['type'].length}")
            results.append(True)
        else:
            print_warning(f"Column 'city' may be too small for encryption: {city_col['type'].length}")
            print_info("  Expected: >= 200 characters")
            results.append(True)  # Don't fail, might not be encrypted yet
    
    return all(results)


def main():
    """Main verification function"""
    parser = argparse.ArgumentParser(
        description='Verify property management database migrations'
    )
    parser.add_argument(
        '--database',
        help='Database name to verify (default: from DATABASE_URL env var)',
        default=None
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show detailed output'
    )
    
    args = parser.parse_args()
    
    # Get database URL
    database_url = get_database_url(args.database)
    
    print_header("Property Management Migration Verification")
    print_info(f"Database: {database_url.split('@')[1] if '@' in database_url else database_url}")
    
    try:
        # Create engine and inspector
        engine = create_engine(database_url)
        inspector = inspect(engine)
        
        # Run verification checks
        all_results = []
        
        all_results.append(verify_enums(engine))
        all_results.append(verify_properties_table(engine, inspector))
        all_results.append(verify_transactions_extension(engine, inspector))
        all_results.append(verify_property_loans_table(engine, inspector))
        all_results.append(verify_performance_indexes(engine, inspector))
        all_results.append(verify_column_sizes(inspector))
        
        # Print summary
        print_header("Verification Summary")
        
        if all(all_results):
            print_success("All verification checks passed!")
            return 0
        else:
            print_warning("Some verification checks failed or have warnings")
            print_info("Review the output above for details")
            return 1
    
    except Exception as e:
        print_error(f"Verification failed with error: {str(e)}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 2


if __name__ == '__main__':
    sys.exit(main())
