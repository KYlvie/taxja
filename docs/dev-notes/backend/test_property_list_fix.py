"""
Test script to verify PropertyListItem address field fix
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from app.db.base import SessionLocal
from app.models.property import Property
from app.schemas.property import PropertyListItem

def test_property_list_serialization():
    """Test that PropertyListItem can serialize Property objects with address field"""
    db: Session = SessionLocal()
    
    try:
        # Get a property from database
        property = db.query(Property).filter(
            Property.id == "c278b5d8-2c8c-4eaf-85a4-6577da6d64a5"
        ).first()
        
        if not property:
            print("❌ Property not found in database")
            return False
        
        print(f"✅ Found property: {property.id}")
        print(f"   Street: {property.street}")
        print(f"   City: {property.city}")
        print(f"   Postal Code: {property.postal_code}")
        print(f"   Address (hybrid property): {property.address}")
        
        # Try to serialize to PropertyListItem
        try:
            list_item = PropertyListItem.model_validate(property)
            print(f"\n✅ PropertyListItem serialization successful!")
            print(f"   ID: {list_item.id}")
            print(f"   Street: {list_item.street}")
            print(f"   City: {list_item.city}")
            print(f"   Postal Code: {list_item.postal_code}")
            print(f"   Address (computed): {list_item.address}")
            print(f"   Status: {list_item.status}")
            
            # Convert to dict to verify JSON serialization
            dict_data = list_item.model_dump()
            print(f"\n✅ JSON serialization successful!")
            print(f"   Address in dict: {dict_data['address']}")
            
            return True
            
        except Exception as e:
            print(f"\n❌ PropertyListItem serialization failed!")
            print(f"   Error: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
            
    finally:
        db.close()

if __name__ == "__main__":
    print("=" * 60)
    print("Testing PropertyListItem Address Field Fix")
    print("=" * 60)
    
    success = test_property_list_serialization()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ All tests passed!")
    else:
        print("❌ Tests failed!")
    print("=" * 60)
    
    sys.exit(0 if success else 1)
