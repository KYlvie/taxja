"""Tests for Property Pydantic schemas"""
import pytest
from datetime import date, timedelta
from decimal import Decimal
from pydantic import ValidationError
from app.schemas.property import PropertyCreate, PropertyUpdate
from app.models.property import PropertyType, PropertyStatus


class TestPropertyCreate:
    """Test PropertyCreate schema validation"""

    def test_valid_property_creation(self):
        """Test creating a valid property"""
        data = {
            "street": "Hauptstraße 123",
            "city": "Wien",
            "postal_code": "1010",
            "purchase_date": date(2020, 6, 15),
            "purchase_price": Decimal("350000.00"),
            "building_value": Decimal("280000.00"),
            "construction_year": 1985,
        }
        property_create = PropertyCreate(**data)
        
        assert property_create.street == "Hauptstraße 123"
        assert property_create.city == "Wien"
        assert property_create.postal_code == "1010"
        assert property_create.purchase_price == Decimal("350000.00")
        assert property_create.building_value == Decimal("280000.00")
        assert property_create.depreciation_rate == Decimal("0.0200")  # Auto-determined

    def test_auto_calculate_building_value(self):
        """Test building_value auto-calculation (80% of purchase_price)"""
        data = {
            "street": "Teststraße 1",
            "city": "Graz",
            "postal_code": "8010",
            "purchase_date": date(2021, 1, 1),
            "purchase_price": Decimal("500000.00"),
        }
        property_create = PropertyCreate(**data)
        
        # Should be 80% of purchase_price
        assert property_create.building_value == Decimal("400000.00")

    def test_auto_determine_depreciation_rate_pre_1915(self):
        """Test depreciation rate auto-determination for pre-1915 buildings"""
        data = {
            "street": "Altbau 1",
            "city": "Salzburg",
            "postal_code": "5020",
            "purchase_date": date(2022, 1, 1),
            "purchase_price": Decimal("300000.00"),
            "construction_year": 1900,
        }
        property_create = PropertyCreate(**data)
        
        # Pre-1915 buildings get 1.5% depreciation rate
        assert property_create.depreciation_rate == Decimal("0.0150")

    def test_auto_determine_depreciation_rate_post_1915(self):
        """Test depreciation rate auto-determination for 1915+ buildings"""
        data = {
            "street": "Neubau 1",
            "city": "Linz",
            "postal_code": "4020",
            "purchase_date": date(2022, 1, 1),
            "purchase_price": Decimal("400000.00"),
            "construction_year": 2000,
        }
        property_create = PropertyCreate(**data)
        
        # 1915+ buildings get 2.0% depreciation rate
        assert property_create.depreciation_rate == Decimal("0.0200")

    def test_purchase_date_in_future_rejected(self):
        """Test that future purchase dates are rejected"""
        future_date = date.today() + timedelta(days=30)
        data = {
            "street": "Future Street",
            "city": "Wien",
            "postal_code": "1010",
            "purchase_date": future_date,
            "purchase_price": Decimal("300000.00"),
        }
        
        with pytest.raises(ValidationError) as exc_info:
            PropertyCreate(**data)
        
        assert "cannot be in the future" in str(exc_info.value)

    def test_purchase_price_zero_rejected(self):
        """Test that zero purchase price is rejected"""
        data = {
            "street": "Test Street",
            "city": "Wien",
            "postal_code": "1010",
            "purchase_date": date(2020, 1, 1),
            "purchase_price": Decimal("0"),
        }
        
        with pytest.raises(ValidationError) as exc_info:
            PropertyCreate(**data)
        
        assert "greater than 0" in str(exc_info.value)

    def test_purchase_price_exceeds_max_rejected(self):
        """Test that purchase price > 100M is rejected"""
        data = {
            "street": "Expensive Street",
            "city": "Wien",
            "postal_code": "1010",
            "purchase_date": date(2020, 1, 1),
            "purchase_price": Decimal("150000000.00"),
        }
        
        with pytest.raises(ValidationError) as exc_info:
            PropertyCreate(**data)
        
        assert "100,000,000" in str(exc_info.value) or "100000000" in str(exc_info.value)

    def test_building_value_exceeds_purchase_price_rejected(self):
        """Test that building_value > purchase_price is rejected"""
        data = {
            "street": "Test Street",
            "city": "Wien",
            "postal_code": "1010",
            "purchase_date": date(2020, 1, 1),
            "purchase_price": Decimal("300000.00"),
            "building_value": Decimal("350000.00"),
        }
        
        with pytest.raises(ValidationError) as exc_info:
            PropertyCreate(**data)
        
        assert "cannot exceed purchase price" in str(exc_info.value)

    def test_depreciation_rate_below_min_rejected(self):
        """Test that depreciation rate < 0.1% is rejected"""
        data = {
            "street": "Test Street",
            "city": "Wien",
            "postal_code": "1010",
            "purchase_date": date(2020, 1, 1),
            "purchase_price": Decimal("300000.00"),
            "depreciation_rate": Decimal("0.0005"),
        }
        
        with pytest.raises(ValidationError) as exc_info:
            PropertyCreate(**data)
        
        assert "0.001" in str(exc_info.value) or "0.1%" in str(exc_info.value)

    def test_depreciation_rate_above_max_rejected(self):
        """Test that depreciation rate > 10% is rejected"""
        data = {
            "street": "Test Street",
            "city": "Wien",
            "postal_code": "1010",
            "purchase_date": date(2020, 1, 1),
            "purchase_price": Decimal("300000.00"),
            "depreciation_rate": Decimal("0.15"),
        }
        
        with pytest.raises(ValidationError) as exc_info:
            PropertyCreate(**data)
        
        assert "0.10" in str(exc_info.value) or "10%" in str(exc_info.value)

    def test_empty_address_fields_rejected(self):
        """Test that empty address fields are rejected"""
        data = {
            "street": "  ",  # Empty after strip
            "city": "Wien",
            "postal_code": "1010",
            "purchase_date": date(2020, 1, 1),
            "purchase_price": Decimal("300000.00"),
        }
        
        with pytest.raises(ValidationError) as exc_info:
            PropertyCreate(**data)
        
        assert "cannot be empty" in str(exc_info.value)

    def test_rental_property_must_have_100_percent(self):
        """Test that rental properties must have rental_percentage = 100"""
        data = {
            "property_type": PropertyType.RENTAL,
            "rental_percentage": Decimal("50.00"),
            "street": "Test Street",
            "city": "Wien",
            "postal_code": "1010",
            "purchase_date": date(2020, 1, 1),
            "purchase_price": Decimal("300000.00"),
        }
        
        with pytest.raises(ValidationError) as exc_info:
            PropertyCreate(**data)
        
        assert "must have rental_percentage = 100" in str(exc_info.value)

    def test_owner_occupied_must_have_0_percent(self):
        """Test that owner-occupied properties must have rental_percentage = 0"""
        data = {
            "property_type": PropertyType.OWNER_OCCUPIED,
            "rental_percentage": Decimal("50.00"),
            "street": "Test Street",
            "city": "Wien",
            "postal_code": "1010",
            "purchase_date": date(2020, 1, 1),
            "purchase_price": Decimal("300000.00"),
        }
        
        with pytest.raises(ValidationError) as exc_info:
            PropertyCreate(**data)
        
        assert "must have rental_percentage = 0" in str(exc_info.value)

    def test_mixed_use_requires_percentage_between_0_and_100(self):
        """Test that mixed-use properties require percentage between 0 and 100 (exclusive)"""
        # Test with 0%
        data = {
            "property_type": PropertyType.MIXED_USE,
            "rental_percentage": Decimal("0.00"),
            "street": "Test Street",
            "city": "Wien",
            "postal_code": "1010",
            "purchase_date": date(2020, 1, 1),
            "purchase_price": Decimal("300000.00"),
        }
        
        with pytest.raises(ValidationError) as exc_info:
            PropertyCreate(**data)
        
        assert "between 0 and 100 (exclusive)" in str(exc_info.value)

    def test_construction_year_in_future_rejected(self):
        """Test that future construction years are rejected"""
        future_year = date.today().year + 5
        data = {
            "street": "Test Street",
            "city": "Wien",
            "postal_code": "1010",
            "purchase_date": date(2020, 1, 1),
            "purchase_price": Decimal("300000.00"),
            "construction_year": future_year,
        }
        
        with pytest.raises(ValidationError) as exc_info:
            PropertyCreate(**data)
        
        assert "cannot be in the future" in str(exc_info.value)


class TestPropertyUpdate:
    """Test PropertyUpdate schema validation"""

    def test_valid_property_update(self):
        """Test updating property with valid data"""
        data = {
            "street": "New Street 456",
            "depreciation_rate": Decimal("0.025"),
        }
        property_update = PropertyUpdate(**data)
        
        assert property_update.street == "New Street 456"
        assert property_update.depreciation_rate == Decimal("0.0250")

    def test_update_status_to_sold_requires_sale_date(self):
        """Test that updating status to 'sold' requires sale_date"""
        data = {
            "status": PropertyStatus.SOLD,
        }
        
        with pytest.raises(ValidationError) as exc_info:
            PropertyUpdate(**data)
        
        assert "sale_date is required" in str(exc_info.value)

    def test_update_status_to_sold_with_sale_date(self):
        """Test updating status to 'sold' with sale_date"""
        data = {
            "status": PropertyStatus.SOLD,
            "sale_date": date(2025, 12, 31),
        }
        property_update = PropertyUpdate(**data)
        
        assert property_update.status == PropertyStatus.SOLD
        assert property_update.sale_date == date(2025, 12, 31)

    def test_partial_update(self):
        """Test that partial updates work (all fields optional)"""
        data = {
            "city": "Salzburg",
        }
        property_update = PropertyUpdate(**data)
        
        assert property_update.city == "Salzburg"
        assert property_update.street is None
        assert property_update.depreciation_rate is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
