#!/usr/bin/env python3
"""
Validation script for migration 006_add_property_performance_indexes.py

This script validates the migration syntax without requiring a database connection.
"""
import sys
import ast


def validate_migration():
    """Validate the migration file syntax and structure"""
    migration_file = "alembic/versions/006_add_property_performance_indexes.py"
    
    print(f"Validating migration file: {migration_file}")
    print("-" * 60)
    
    try:
        # Read the migration file
        with open(migration_file, 'r') as f:
            content = f.read()
        
        # Parse the Python syntax
        tree = ast.parse(content)
        print("✓ Python syntax is valid")
        
        # Check for required functions
        functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        
        if 'upgrade' in functions:
            print("✓ upgrade() function found")
        else:
            print("✗ upgrade() function missing")
            return False
        
        if 'downgrade' in functions:
            print("✓ downgrade() function found")
        else:
            print("✗ downgrade() function missing")
            return False
        
        # Check for required variables
        module_vars = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        if isinstance(node.value, ast.Constant):
                            module_vars[target.id] = node.value.value
        
        required_vars = ['revision', 'down_revision']
        for var in required_vars:
            if var in module_vars:
                print(f"✓ {var} = '{module_vars[var]}'")
            else:
                print(f"✗ {var} variable missing")
                return False
        
        # Check revision chain
        if module_vars.get('revision') == '006' and module_vars.get('down_revision') == '005':
            print("✓ Revision chain is correct (006 -> 005)")
        else:
            print("✗ Revision chain may be incorrect")
        
        # Count index operations
        index_creates = content.count('op.create_index')
        index_drops = content.count('op.drop_index')
        
        print(f"✓ Found {index_creates} CREATE INDEX operations")
        print(f"✓ Found {index_drops} DROP INDEX operations")
        
        if index_creates == index_drops:
            print("✓ Number of CREATE and DROP operations match")
        else:
            print("⚠ Warning: CREATE and DROP operations don't match")
        
        # Check for expected index names
        expected_indexes = [
            'idx_properties_status',
            'idx_properties_user_status',
            'idx_transactions_property_date',
            'idx_transactions_depreciation'
        ]
        
        print("\nExpected indexes:")
        for idx_name in expected_indexes:
            if idx_name in content:
                print(f"  ✓ {idx_name}")
            else:
                print(f"  ✗ {idx_name} not found")
                return False
        
        print("\n" + "=" * 60)
        print("✓ Migration validation PASSED")
        print("=" * 60)
        return True
        
    except SyntaxError as e:
        print(f"✗ Syntax error: {e}")
        return False
    except FileNotFoundError:
        print(f"✗ Migration file not found: {migration_file}")
        return False
    except Exception as e:
        print(f"✗ Validation error: {e}")
        return False


if __name__ == "__main__":
    success = validate_migration()
    sys.exit(0 if success else 1)
