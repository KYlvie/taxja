"""
Test script for property tax validation warnings.

This script tests the warning system that alerts users when rental properties
have no rental income, which could be questioned by the Austrian tax office.
"""
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy.orm import Session

from app.db.base import SessionLocal
from app.models.property import Property, PropertyType, PropertyStatus
from app.services.afa_calculator import AfACalculator


def test_property_warnings():
    """Test property tax validation warnings for properties without rental income."""
    db: Session = SessionLocal()
    
    try:
        # Test user_id (ylvie.khoo@hotmail.com)
        user_id = 11
        current_year = 2026
        
        print("=" * 80)
        print("Property Tax Validation Warnings Test")
        print("=" * 80)
        print()
        
        # Get all active properties for user
        properties = db.query(Property).filter(
            Property.user_id == user_id,
            Property.status == PropertyStatus.ACTIVE
        ).all()
        
        if not properties:
            print(f"❌ No active properties found for user_id={user_id}")
            return
        
        print(f"Found {len(properties)} active property(ies) for user_id={user_id}")
        print()
        
        # Test each property
        afa_calculator = AfACalculator(db=db)
        
        for property in properties:
            print("-" * 80)
            print(f"Property: {property.address}")
            print(f"  ID: {property.id}")
            print(f"  Type: {property.property_type.value}")
            print(f"  Purchase Date: {property.purchase_date}")
            print(f"  Building Value: €{property.building_value:,.2f}")
            print(f"  Depreciation Rate: {property.depreciation_rate * 100:.2f}%")
            print()
            
            # Calculate depreciation for current year (this triggers warning check)
            afa_calculator.clear_warnings()
            depreciation = afa_calculator.calculate_annual_depreciation(property, current_year)
            warnings = afa_calculator.get_warnings()
            
            print(f"  Annual Depreciation ({current_year}): €{depreciation:,.2f}")
            print()
            
            if warnings:
                print(f"  ⚠️  {len(warnings)} Warning(s) Found:")
                print()
                for i, warning in enumerate(warnings, 1):
                    print(f"  Warning #{i}:")
                    print(f"    Level: {warning['level'].upper()}")
                    print(f"    Type: {warning['type']}")
                    print(f"    Year: {warning['year']}")
                    print(f"    Months Vacant: {warning['months_vacant']}")
                    print()
                    print(f"    German Message:")
                    print(f"      {warning['message_de']}")
                    print()
                    print(f"    English Message:")
                    print(f"      {warning['message_en']}")
                    print()
                    print(f"    Chinese Message:")
                    print(f"      {warning['message_zh']}")
                    print()
            else:
                print("  ✅ No warnings - property has rental income or is owner-occupied")
                print()
        
        print("=" * 80)
        print("Test completed successfully!")
        print("=" * 80)
        
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    test_property_warnings()
