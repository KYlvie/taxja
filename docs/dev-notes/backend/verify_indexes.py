"""Verify that the properties table has the required indexes"""
from sqlalchemy import create_engine, inspect
import os
from dotenv import load_dotenv

load_dotenv()

engine = create_engine(os.getenv('DATABASE_URL'))
inspector = inspect(engine)

try:
    indexes = inspector.get_indexes('properties')
    
    print("Indexes on properties table:")
    for idx in indexes:
        print(f"  - {idx['name']}: {idx['column_names']}")
    
    # Check for required indexes
    required_indexes = {
        'ix_properties_user_id': ['user_id'],
        'ix_properties_status': ['status'],
        'ix_properties_user_status': ['user_id', 'status']
    }
    
    found_indexes = {idx['name']: idx['column_names'] for idx in indexes}
    
    print("\nVerification:")
    all_present = True
    for name, columns in required_indexes.items():
        if name in found_indexes and found_indexes[name] == columns:
            print(f"  ✓ {name} - PRESENT")
        else:
            print(f"  ✗ {name} - MISSING")
            all_present = False
    
    if all_present:
        print("\n✓ All required indexes are present!")
    else:
        print("\n✗ Some required indexes are missing!")
        
except Exception as e:
    print(f"Error: {e}")
    print("\nNote: This might mean the properties table doesn't exist yet.")
    print("Run 'alembic upgrade head' to apply migrations.")
