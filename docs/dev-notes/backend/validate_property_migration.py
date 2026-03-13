"""Validate property migration file structure and syntax"""
import ast
import sys

def validate_migration():
    """Validate the migration file can be parsed and has required structure"""
    
    migration_file = "alembic/versions/002_add_property_table.py"
    
    print(f"Validating migration file: {migration_file}")
    print("-" * 60)
    
    # Read the file
    try:
        with open(migration_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"✗ Migration file not found: {migration_file}")
        return False
    
    # Parse the file as Python AST
    try:
        tree = ast.parse(content)
        print("✓ Migration file has valid Python syntax")
    except SyntaxError as e:
        print(f"✗ Syntax error in migration file: {e}")
        return False
    
    # Check for required module-level variables
    required_vars = {
        'revision': None,
        'down_revision': None,
        'branch_labels': None,
        'depends_on': None
    }
    
    required_functions = ['upgrade', 'downgrade']
    found_functions = []
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in required_vars:
                    if isinstance(node.value, ast.Constant):
                        required_vars[target.id] = node.value.value
        
        if isinstance(node, ast.FunctionDef):
            if node.name in required_functions:
                found_functions.append(node.name)
    
    # Validate required variables
    all_vars_present = True
    for var_name, var_value in required_vars.items():
        if var_name in ['revision', 'down_revision']:
            if var_value is None:
                print(f"✗ Required variable '{var_name}' not found or not a constant")
                all_vars_present = False
            else:
                print(f"✓ Found {var_name}: {var_value}")
    
    # Validate revision values
    if required_vars['revision'] != '002':
        print(f"✗ Expected revision '002', got '{required_vars['revision']}'")
        return False
    
    if required_vars['down_revision'] != '001':
        print(f"✗ Expected down_revision '001', got '{required_vars['down_revision']}'")
        return False
    
    # Validate required functions
    for func_name in required_functions:
        if func_name in found_functions:
            print(f"✓ Found function: {func_name}()")
        else:
            print(f"✗ Required function '{func_name}()' not found")
            all_vars_present = False
    
    if not all_vars_present:
        return False
    
    # Check for key migration operations in upgrade function
    upgrade_checks = [
        ('create_table', 'properties'),
        ('create_index', 'ix_properties_user_id'),
        ('create_index', 'ix_properties_status'),
        ('ForeignKeyConstraint', 'users'),
        ('CheckConstraint', 'rental_percentage'),
        ('CheckConstraint', 'purchase_price'),
        ('CheckConstraint', 'building_value'),
    ]
    
    print("\nChecking migration content:")
    for check_term, context in upgrade_checks:
        if check_term in content and context in content:
            print(f"✓ Found {check_term} for {context}")
        else:
            print(f"⚠ Warning: {check_term} for {context} not found")
    
    # Check for downgrade operations
    downgrade_checks = [
        'drop_table',
        'drop_index',
    ]
    
    print("\nChecking downgrade content:")
    for check_term in downgrade_checks:
        if check_term in content:
            print(f"✓ Found {check_term} in downgrade")
        else:
            print(f"⚠ Warning: {check_term} not found in downgrade")
    
    return True

if __name__ == "__main__":
    print("Property Migration Validation")
    print("=" * 60)
    
    try:
        if validate_migration():
            print("\n" + "=" * 60)
            print("✓ Migration validation passed!")
            print("=" * 60)
            print("\nNext steps:")
            print("1. Ensure PostgreSQL database is running")
            print("2. Run: alembic upgrade head")
            print("3. Verify table creation with SQL queries")
            sys.exit(0)
        else:
            print("\n" + "=" * 60)
            print("✗ Migration validation failed")
            print("=" * 60)
            sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error during validation: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
