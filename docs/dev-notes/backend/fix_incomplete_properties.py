"""
Fix incomplete property records in database.
Run with: python -m backend.fix_incomplete_properties
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.db.base import SessionLocal
from app.models.property import Property
from sqlalchemy import inspect

def fix_incomplete_properties():
    """Check and fix properties with missing encrypted fields."""
    print("=" * 80)
    print("Checking for Incomplete Property Records")
    print("=" * 80)
    
    db = SessionLocal()
    
    try:
        properties = db.query(Property).all()
        print(f"\nFound {len(properties)} properties in database\n")
        
        issues_found = 0
        
        for prop in properties:
            print(f"Property ID: {prop.id}")
            print(f"  User ID: {prop.user_id}")
            
            # Check encrypted fields
            has_issues = False
            
            try:
                address = prop.address
                if not address or address.strip() == "":
                    print(f"  ❌ Missing or empty address")
                    has_issues = True
                else:
                    print(f"  ✅ Address: {address}")
            except Exception as e:
                print(f"  ❌ Error reading address: {e}")
                has_issues = True
            
            try:
                street = prop.street
                if not street or street.strip() == "":
                    print(f"  ❌ Missing or empty street")
                    has_issues = True
                else:
                    print(f"  ✅ Street: {street}")
            except Exception as e:
                print(f"  ❌ Error reading street: {e}")
                has_issues = True
            
            try:
                city = prop.city
                if not city or city.strip() == "":
                    print(f"  ❌ Missing or empty city")
                    has_issues = True
                else:
                    print(f"  ✅ City: {city}")
            except Exception as e:
                print(f"  ❌ Error reading city: {e}")
                has_issues = True
            
            # Check postal_code (not encrypted)
            if not prop.postal_code or prop.postal_code.strip() == "":
                print(f"  ❌ Missing or empty postal_code")
                has_issues = True
            else:
                print(f"  ✅ Postal Code: {prop.postal_code}")
            
            if has_issues:
                issues_found += 1
                print(f"\n  🔧 Fixing property {prop.id}...")
                
                # Fix missing fields with defaults
                if not prop.street or prop.street.strip() == "":
                    prop.street = "Unbekannt"
                    print(f"     Set street to 'Unbekannt'")
                
                if not prop.city or prop.city.strip() == "":
                    prop.city = "Unbekannt"
                    print(f"     Set city to 'Unbekannt'")
                
                if not prop.postal_code or prop.postal_code.strip() == "":
                    prop.postal_code = "0000"
                    print(f"     Set postal_code to '0000'")
                
                # Rebuild address
                prop.address = f"{prop.street}, {prop.postal_code} {prop.city}"
                print(f"     Rebuilt address: {prop.address}")
                
                db.commit()
                print(f"  ✅ Fixed property {prop.id}")
            
            print()
        
        print("=" * 80)
        if issues_found > 0:
            print(f"Fixed {issues_found} properties with missing fields")
        else:
            print("All properties are complete!")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    fix_incomplete_properties()
