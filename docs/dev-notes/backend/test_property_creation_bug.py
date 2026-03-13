"""
Test to reproduce property creation validation error.
Run with: python backend/test_property_creation_bug.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.schemas.property import PropertyCreate, PropertyType
from datetime import date
from decimal import Decimal

def test_property_validation():
    """Test property creation with minimal data."""
    print("=" * 80)
    print("Testing Property Creation Validation")
    print("=" * 80)
    
    # Test 1: Valid data
    print("\nTest 1: Valid property data")
    try:
        valid_data = PropertyCreate(
            property_type=PropertyType.RENTAL,
            street="Therneberg 51",
            city="Altenmarkt a.d.Triesting",
            postal_code="2571",
            purchase_date=date(2026, 3, 9),
            purchase_price=Decimal("218400.00"),
        )
        print("✅ Valid data accepted")
        print(f"   Address fields: street={valid_data.street}, city={valid_data.city}, postal_code={valid_data.postal_code}")
    except Exception as e:
        print(f"❌ Validation failed: {e}")
    
    # Test 2: Missing required fields
    print("\nTest 2: Missing required fields (empty dict)")
    try:
        invalid_data = PropertyCreate(**{})
        print("❌ Should have failed validation!")
    except Exception as e:
        print(f"✅ Validation error (expected):")
        print(f"   {e}")
    
    # Test 3: Missing city
    print("\nTest 3: Missing city field")
    try:
        missing_city = PropertyCreate(
            property_type=PropertyType.RENTAL,
            street="Therneberg 51",
            postal_code="2571",
            purchase_date=date(2026, 3, 9),
            purchase_price=Decimal("218400.00"),
        )
        print("❌ Should have failed validation!")
    except Exception as e:
        print(f"✅ Validation error (expected):")
        print(f"   {e}")

if __name__ == "__main__":
    test_property_validation()
