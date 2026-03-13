"""
Test script to verify PropertyDetailResponse fix
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from app.db.base import SessionLocal
from app.models.property import Property
from app.schemas.property import PropertyDetailResponse, PropertyMetrics
from decimal import Decimal

def test_property_detail_serialization():
    """Test that PropertyDetailResponse can serialize Property objects"""
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
        print(f"   Street (hybrid): {property.street}")
        print(f"   City (hybrid): {property.city}")
        print(f"   Postal Code: {property.postal_code}")
        print(f"   Address (hybrid): {property.address}")
        
        # Try to serialize to PropertyDetailResponse
        try:
            # Method 1: Using model_validate (correct way)
            detail_response = PropertyDetailResponse.model_validate(property)
            print(f"\n✅ PropertyDetailResponse serialization successful!")
            print(f"   ID: {detail_response.id}")
            print(f"   Street: {detail_response.street}")
            print(f"   City: {detail_response.city}")
            print(f"   Postal Code: {detail_response.postal_code}")
            print(f"   Address: {detail_response.address}")
            print(f"   Status: {detail_response.status}")
            
            # Add mock metrics
            detail_response.metrics = PropertyMetrics(
                property_id=property.id,
                accumulated_depreciation=Decimal("0"),
                remaining_depreciable_value=Decimal("280000"),
                annual_depreciation=Decimal("5600"),
                total_rental_income=Decimal("0"),
                total_expenses=Decimal("0"),
                net_rental_income=Decimal("0"),
                years_remaining=Decimal("50.0"),
                warnings=[]
            )
            
            # Convert to dict to verify JSON serialization
            dict_data = detail_response.model_dump()
            print(f"\n✅ JSON serialization successful!")
            print(f"   Address in dict: {dict_data['address']}")
            print(f"   Street in dict: {dict_data['street']}")
            print(f"   City in dict: {dict_data['city']}")
            print(f"   Metrics in dict: {dict_data.get('metrics', {}).get('property_id')}")
            
            return True
            
        except Exception as e:
            print(f"\n❌ PropertyDetailResponse serialization failed!")
            print(f"   Error: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
            
    finally:
        db.close()

if __name__ == "__main__":
    print("=" * 60)
    print("Testing PropertyDetailResponse Fix")
    print("=" * 60)
    
    success = test_property_detail_serialization()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ All tests passed!")
    else:
        print("❌ Tests failed!")
    print("=" * 60)
    
    sys.exit(0 if success else 1)
