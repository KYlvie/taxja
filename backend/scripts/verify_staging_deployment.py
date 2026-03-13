#!/usr/bin/env python3
"""
Staging Deployment Verification Script
Verifies that the Property Asset Management feature is correctly deployed to staging
"""

import sys
import requests
from sqlalchemy import create_engine, text
from typing import Dict, List, Tuple
import os
from datetime import datetime

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://taxja:taxja_password@localhost:5432/taxja")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

# Colors for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'


def print_header(text: str):
    """Print a formatted header"""
    print(f"\n{BLUE}{'=' * 60}{RESET}")
    print(f"{BLUE}{text.center(60)}{RESET}")
    print(f"{BLUE}{'=' * 60}{RESET}\n")


def print_success(text: str):
    """Print success message"""
    print(f"{GREEN}✓ {text}{RESET}")


def print_error(text: str):
    """Print error message"""
    print(f"{RED}✗ {text}{RESET}")


def print_warning(text: str):
    """Print warning message"""
    print(f"{YELLOW}⚠ {text}{RESET}")


def print_info(text: str):
    """Print info message"""
    print(f"  {text}")


def verify_database_schema() -> Tuple[bool, List[str]]:
    """Verify database schema changes"""
    print_header("Database Schema Verification")
    
    errors = []
    
    try:
        engine = create_engine(DATABASE_URL)
        
        with engine.connect() as conn:
            # Check properties table exists
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'properties'
                );
            """))
            if result.scalar():
                print_success("Properties table exists")
            else:
                print_error("Properties table not found")
                errors.append("Properties table missing")
            
            # Check property enums
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM pg_type 
                    WHERE typname = 'propertytype'
                );
            """))
            if result.scalar():
                print_success("PropertyType enum exists")
            else:
                print_error("PropertyType enum not found")
                errors.append("PropertyType enum missing")
            
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM pg_type 
                    WHERE typname = 'propertystatus'
                );
            """))
            if result.scalar():
                print_success("PropertyStatus enum exists")
            else:
                print_error("PropertyStatus enum not found")
                errors.append("PropertyStatus enum missing")
            
            # Check property_id column in transactions
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_name = 'transactions' 
                    AND column_name = 'property_id'
                );
            """))
            if result.scalar():
                print_success("Transactions.property_id column exists")
            else:
                print_error("Transactions.property_id column not found")
                errors.append("Transactions.property_id column missing")
            
            # Check property_loans table
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'property_loans'
                );
            """))
            if result.scalar():
                print_success("Property_loans table exists")
            else:
                print_warning("Property_loans table not found (optional)")
            
            # Check audit_logs table
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'audit_logs'
                );
            """))
            if result.scalar():
                print_success("Audit_logs table exists")
            else:
                print_error("Audit_logs table not found")
                errors.append("Audit_logs table missing")
            
            # Check indexes
            indexes_to_check = [
                'idx_properties_user_id',
                'idx_properties_status',
                'idx_properties_user_status',
                'idx_transactions_property_id'
            ]
            
            for index_name in indexes_to_check:
                result = conn.execute(text(f"""
                    SELECT EXISTS (
                        SELECT FROM pg_indexes 
                        WHERE indexname = '{index_name}'
                    );
                """))
                if result.scalar():
                    print_success(f"Index {index_name} exists")
                else:
                    print_warning(f"Index {index_name} not found")
            
            # Check constraints
            result = conn.execute(text("""
                SELECT COUNT(*) 
                FROM information_schema.table_constraints 
                WHERE table_name = 'properties' 
                AND constraint_type = 'CHECK';
            """))
            check_count = result.scalar()
            if check_count >= 5:
                print_success(f"Properties table has {check_count} check constraints")
            else:
                print_warning(f"Properties table has only {check_count} check constraints (expected >= 5)")
            
            # Check foreign keys
            result = conn.execute(text("""
                SELECT COUNT(*) 
                FROM information_schema.table_constraints 
                WHERE table_name = 'properties' 
                AND constraint_type = 'FOREIGN KEY';
            """))
            fk_count = result.scalar()
            if fk_count >= 1:
                print_success(f"Properties table has {fk_count} foreign key(s)")
            else:
                print_error("Properties table missing foreign keys")
                errors.append("Foreign keys missing")
        
        return len(errors) == 0, errors
        
    except Exception as e:
        print_error(f"Database connection failed: {str(e)}")
        return False, [str(e)]


def verify_api_endpoints() -> Tuple[bool, List[str]]:
    """Verify API endpoints are accessible"""
    print_header("API Endpoints Verification")
    
    errors = []
    
    try:
        # Check health endpoint
        response = requests.get(f"{BACKEND_URL}/health", timeout=5)
        if response.status_code == 200:
            print_success("Health endpoint accessible")
        else:
            print_error(f"Health endpoint returned {response.status_code}")
            errors.append(f"Health check failed: {response.status_code}")
        
        # Check API docs
        response = requests.get(f"{BACKEND_URL}/docs", timeout=5)
        if response.status_code == 200:
            print_success("API documentation accessible")
        else:
            print_warning(f"API docs returned {response.status_code}")
        
        # Check OpenAPI schema for property endpoints
        response = requests.get(f"{BACKEND_URL}/openapi.json", timeout=5)
        if response.status_code == 200:
            openapi_spec = response.json()
            paths = openapi_spec.get("paths", {})
            
            property_endpoints = [
                "/api/v1/properties",
                "/api/v1/properties/{property_id}",
            ]
            
            for endpoint in property_endpoints:
                if endpoint in paths:
                    print_success(f"Endpoint {endpoint} defined in OpenAPI spec")
                else:
                    print_error(f"Endpoint {endpoint} not found in OpenAPI spec")
                    errors.append(f"Endpoint {endpoint} missing")
        else:
            print_warning("Could not fetch OpenAPI spec")
        
        return len(errors) == 0, errors
        
    except requests.exceptions.ConnectionError:
        print_error("Could not connect to backend API")
        return False, ["Backend API not accessible"]
    except Exception as e:
        print_error(f"API verification failed: {str(e)}")
        return False, [str(e)]


def verify_migrations() -> Tuple[bool, List[str]]:
    """Verify migration state"""
    print_header("Migration State Verification")
    
    errors = []
    
    try:
        engine = create_engine(DATABASE_URL)
        
        with engine.connect() as conn:
            # Check alembic_version table
            result = conn.execute(text("""
                SELECT version_num 
                FROM alembic_version 
                LIMIT 1;
            """))
            version = result.scalar()
            
            if version:
                print_success(f"Current migration version: {version}")
                print_info("Expected: Migration 009 or later for property feature")
            else:
                print_error("No migration version found")
                errors.append("Migration version not found")
        
        return len(errors) == 0, errors
        
    except Exception as e:
        print_error(f"Migration verification failed: {str(e)}")
        return False, [str(e)]


def verify_data_integrity() -> Tuple[bool, List[str]]:
    """Verify data integrity"""
    print_header("Data Integrity Verification")
    
    errors = []
    
    try:
        engine = create_engine(DATABASE_URL)
        
        with engine.connect() as conn:
            # Check for orphaned property_id references
            result = conn.execute(text("""
                SELECT COUNT(*) 
                FROM transactions 
                WHERE property_id IS NOT NULL 
                AND property_id NOT IN (SELECT id FROM properties);
            """))
            orphaned_count = result.scalar()
            
            if orphaned_count == 0:
                print_success("No orphaned property_id references in transactions")
            else:
                print_error(f"Found {orphaned_count} orphaned property_id references")
                errors.append(f"{orphaned_count} orphaned references")
            
            # Check for properties without users
            result = conn.execute(text("""
                SELECT COUNT(*) 
                FROM properties 
                WHERE user_id NOT IN (SELECT id FROM users);
            """))
            orphaned_properties = result.scalar()
            
            if orphaned_properties == 0:
                print_success("All properties have valid user references")
            else:
                print_error(f"Found {orphaned_properties} properties without valid users")
                errors.append(f"{orphaned_properties} invalid user references")
            
            # Check constraint violations (should be 0)
            result = conn.execute(text("""
                SELECT COUNT(*) 
                FROM properties 
                WHERE building_value > purchase_price;
            """))
            constraint_violations = result.scalar()
            
            if constraint_violations == 0:
                print_success("No constraint violations found")
            else:
                print_error(f"Found {constraint_violations} constraint violations")
                errors.append(f"{constraint_violations} constraint violations")
        
        return len(errors) == 0, errors
        
    except Exception as e:
        print_error(f"Data integrity check failed: {str(e)}")
        return False, [str(e)]


def print_summary(results: Dict[str, Tuple[bool, List[str]]]):
    """Print verification summary"""
    print_header("Verification Summary")
    
    total_checks = len(results)
    passed_checks = sum(1 for success, _ in results.values() if success)
    
    print(f"Total Checks: {total_checks}")
    print(f"Passed: {GREEN}{passed_checks}{RESET}")
    print(f"Failed: {RED}{total_checks - passed_checks}{RESET}")
    print()
    
    if passed_checks == total_checks:
        print_success("All verification checks passed!")
        print_info("Staging deployment is successful.")
        return 0
    else:
        print_error("Some verification checks failed!")
        print()
        print("Failed checks:")
        for check_name, (success, errors) in results.items():
            if not success:
                print(f"\n{RED}{check_name}:{RESET}")
                for error in errors:
                    print(f"  - {error}")
        print()
        print_info("Please review the errors above and fix before proceeding.")
        return 1


def main():
    """Main verification function"""
    print_header("Property Asset Management - Staging Deployment Verification")
    print_info(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print_info(f"Database: {DATABASE_URL.split('@')[-1]}")  # Hide credentials
    print_info(f"Backend: {BACKEND_URL}")
    
    results = {}
    
    # Run all verification checks
    results["Database Schema"] = verify_database_schema()
    results["API Endpoints"] = verify_api_endpoints()
    results["Migration State"] = verify_migrations()
    results["Data Integrity"] = verify_data_integrity()
    
    # Print summary and exit
    exit_code = print_summary(results)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
