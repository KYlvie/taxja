"""
Unit tests for AfA (Depreciation) Calculator Service
"""

import pytest
from decimal import Decimal
from datetime import date
from unittest.mock import Mock, MagicMock
from sqlalchemy.orm import Session

from app.services.afa_calculator import AfACalculator
from app.models.property import Property, PropertyType, PropertyStatus
from app.models.transaction import Transaction, TransactionType, ExpenseCategory


@pytest.fixture
def mock_db():
    """Create a mock database session"""
    return Mock(spec=Session)


@pytest.fixture
def calculator(mock_db):
    """Create AfA calculator with mock database"""
    return AfACalculator(db=mock_db)


@pytest.fixture
def sample_property():
    """Create a sample rental property"""
    prop = Property()
    prop.id = "550e8400-e29b-41d4-a716-446655440000"
    prop.user_id = 1
    prop.property_type = PropertyType.RENTAL
    prop.rental_percentage = Decimal("100.00")
    prop.address = "Hauptstraße 123, 1010 Wien"
    prop.street = "Hauptstraße 123"
    prop.city = "Wien"
    prop.postal_code = "1010"
    prop.purchase_date = date(2020, 6, 15)
    prop.purchase_price = Decimal("350000.00")
    prop.building_value = Decimal("280000.00")
    prop.land_value = Decimal("70000.00")
    prop.construction_year = 1985
    prop.depreciation_rate = Decimal("0.0150")
    prop.asset_type = "real_estate"
    prop.status = PropertyStatus.ACTIVE
    prop.sale_date = None
    return prop


def _set_real_estate_context(
    calculator: AfACalculator,
    accumulated: Decimal = Decimal("0"),
    rental_percentage: Decimal = Decimal("100"),
):
    """Stub accumulated depreciation and rental history for real-estate tests."""
    calculator.get_accumulated_depreciation = Mock(return_value=accumulated)
    calculator._get_rental_percentage_for_year = Mock(return_value=rental_percentage)


class TestDetermineDepreciationRate:
    """Test depreciation rate determination based on construction year"""
    
    def test_pre_1915_building_gets_1_5_percent(self, calculator):
        """Residential buildings constructed before 1915 use 1.5%."""
        rate = calculator.determine_depreciation_rate(1900)
        assert rate == Decimal("0.015")
    
    def test_1915_building_gets_1_5_percent(self, calculator):
        """The old 1915 cutoff no longer applies for residential buildings."""
        rate = calculator.determine_depreciation_rate(1915)
        assert rate == Decimal("0.015")
    
    def test_post_1915_building_gets_1_5_percent(self, calculator):
        """Residential buildings constructed after 1915 still use 1.5%."""
        rate = calculator.determine_depreciation_rate(1985)
        assert rate == Decimal("0.015")
    
    def test_unknown_construction_year_defaults_to_1_5_percent(self, calculator):
        """Unknown residential construction year defaults to 1.5%."""
        rate = calculator.determine_depreciation_rate(None)
        assert rate == Decimal("0.015")
    
    def test_edge_case_1914(self, calculator):
        """1914 should get 1.5% rate (before 1915)"""
        rate = calculator.determine_depreciation_rate(1914)
        assert rate == Decimal("0.015")


class TestCalculateAnnualDepreciation:
    """Test annual depreciation calculation"""
    
    def test_full_year_depreciation(self, calculator, sample_property, mock_db):
        """Calculate depreciation for a full year of ownership"""
        _set_real_estate_context(calculator)
        
        # Calculate for year 2021 (full year)
        depreciation = calculator.calculate_annual_depreciation(sample_property, 2021)
        
        # Expected: 280,000 * 0.015 = 4,200.00
        assert depreciation == Decimal("4200.00")
    
    def test_partial_first_year_depreciation(self, calculator, sample_property, mock_db):
        """Calculate pro-rated depreciation for first year (purchased mid-year)"""
        _set_real_estate_context(calculator)
        
        # Property purchased June 15, 2020 - owned for 7 months (Jun-Dec)
        depreciation = calculator.calculate_annual_depreciation(sample_property, 2020)
        
        # Expected: (280,000 * 0.015 * 7) / 12 = 2,450.00
        assert depreciation == Decimal("2450.00")
    
    def test_no_depreciation_before_purchase(self, calculator, sample_property, mock_db):
        """No depreciation for years before property was purchased"""
        _set_real_estate_context(calculator)
        depreciation = calculator.calculate_annual_depreciation(sample_property, 2019)
        assert depreciation == Decimal("0")
    
    def test_no_depreciation_after_sale(self, calculator, sample_property, mock_db):
        """No depreciation for years after property was sold"""
        sample_property.sale_date = date(2023, 12, 31)
        _set_real_estate_context(calculator)
        depreciation = calculator.calculate_annual_depreciation(sample_property, 2024)
        assert depreciation == Decimal("0")
    
    def test_stops_at_building_value_limit(self, calculator, sample_property, mock_db):
        """Depreciation stops when accumulated equals building value"""
        _set_real_estate_context(calculator, accumulated=Decimal("280000.00"))
        
        depreciation = calculator.calculate_annual_depreciation(sample_property, 2025)
        assert depreciation == Decimal("0")
    
    def test_respects_remaining_depreciable_value(self, calculator, sample_property, mock_db):
        """Depreciation limited to remaining depreciable value"""
        _set_real_estate_context(calculator, accumulated=Decimal("278000.00"))
        
        depreciation = calculator.calculate_annual_depreciation(sample_property, 2025)
        
        # Expected: min(4200, 2000) = 2000.00
        assert depreciation == Decimal("2000.00")
    
    def test_mixed_use_property_depreciation(self, calculator, sample_property, mock_db):
        """Mixed-use property depreciates only rental percentage"""
        sample_property.property_type = PropertyType.MIXED_USE
        sample_property.rental_percentage = Decimal("50.00")
        _set_real_estate_context(calculator, rental_percentage=Decimal("50"))
        
        depreciation = calculator.calculate_annual_depreciation(sample_property, 2021)
        
        # Expected: 280,000 * 0.50 * 0.015 = 2,100.00
        assert depreciation == Decimal("2100.00")
    
    def test_owner_occupied_no_depreciation(self, calculator, sample_property, mock_db):
        """Owner-occupied properties are not depreciable"""
        sample_property.property_type = PropertyType.OWNER_OCCUPIED
        _set_real_estate_context(calculator, rental_percentage=Decimal("0"))
        depreciation = calculator.calculate_annual_depreciation(sample_property, 2021)
        assert depreciation == Decimal("0")
    
    def test_requires_database_session(self, sample_property):
        """Should raise error if no database session provided"""
        calculator_no_db = AfACalculator(db=None)
        
        with pytest.raises(ValueError, match="Database session required"):
            calculator_no_db.calculate_annual_depreciation(sample_property, 2021)


class TestCalculateProratedDepreciation:
    """Test pro-rated depreciation calculation"""
    
    def test_prorated_for_6_months(self, calculator, sample_property):
        """Calculate pro-rated depreciation for 6 months"""
        depreciation = calculator.calculate_prorated_depreciation(sample_property, 6)
        
        # Expected: (280,000 * 0.015 * 6) / 12 = 2,100.00
        assert depreciation == Decimal("2100.00")
    
    def test_prorated_for_1_month(self, calculator, sample_property):
        """Calculate pro-rated depreciation for 1 month"""
        depreciation = calculator.calculate_prorated_depreciation(sample_property, 1)
        
        # Expected: (280,000 * 0.015 * 1) / 12 = 350.00
        assert depreciation == Decimal("350.00")
    
    def test_prorated_for_12_months_equals_annual(self, calculator, sample_property):
        """Pro-rated for 12 months should equal full annual depreciation"""
        depreciation = calculator.calculate_prorated_depreciation(sample_property, 12)
        
        # Expected: (280,000 * 0.015 * 12) / 12 = 4,200.00
        assert depreciation == Decimal("4200.00")
    
    def test_prorated_mixed_use_property(self, calculator, sample_property):
        """Pro-rated depreciation for mixed-use property"""
        sample_property.property_type = PropertyType.MIXED_USE
        sample_property.rental_percentage = Decimal("60.00")
        
        depreciation = calculator.calculate_prorated_depreciation(sample_property, 6)
        
        # Expected: (280,000 * 0.60 * 0.015 * 6) / 12 = 1,260.00
        assert depreciation == Decimal("1260.00")
    
    def test_prorated_owner_occupied_no_depreciation(self, calculator, sample_property):
        """Owner-occupied properties have no pro-rated depreciation"""
        sample_property.property_type = PropertyType.OWNER_OCCUPIED
        
        depreciation = calculator.calculate_prorated_depreciation(sample_property, 6)
        assert depreciation == Decimal("0")


class TestGetAccumulatedDepreciation:
    """Test accumulated depreciation query"""
    
    def test_get_accumulated_all_years(self, calculator, mock_db):
        """Get accumulated depreciation from purchase year through a target year."""
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        sample = Property()
        sample.id = "550e8400-e29b-41d4-a716-446655440000"
        sample.asset_type = "real_estate"
        sample.property_type = PropertyType.RENTAL
        sample.purchase_date = date(2020, 6, 15)
        sample.building_value = Decimal("280000.00")
        sample.depreciation_rate = Decimal("0.0150")
        sample.construction_year = 1985
        sample.sale_date = None
        mock_query.first.return_value = sample
        mock_db.query.return_value = mock_query
        calculator._get_rental_percentage_for_year = Mock(return_value=Decimal("100"))
        
        property_id = "550e8400-e29b-41d4-a716-446655440000"
        accumulated = calculator.get_accumulated_depreciation(property_id, up_to_year=2023)
        
        assert accumulated == Decimal("15050.00")
    
    def test_get_accumulated_up_to_year(self, calculator, mock_db):
        """Get accumulated depreciation up to specific year"""
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        sample = Property()
        sample.id = "550e8400-e29b-41d4-a716-446655440000"
        sample.asset_type = "real_estate"
        sample.property_type = PropertyType.RENTAL
        sample.purchase_date = date(2020, 6, 15)
        sample.building_value = Decimal("280000.00")
        sample.depreciation_rate = Decimal("0.0150")
        sample.construction_year = 1985
        sample.sale_date = None
        mock_query.first.return_value = sample
        mock_db.query.return_value = mock_query
        calculator._get_rental_percentage_for_year = Mock(side_effect=[
            Decimal("100"),
            Decimal("100"),
            Decimal("50"),
            Decimal("50"),
        ])
        
        property_id = "550e8400-e29b-41d4-a716-446655440000"
        accumulated = calculator.get_accumulated_depreciation(property_id, up_to_year=2023)
        
        # 2020: 2450.00, 2021: 4200.00, 2022: 2100.00, 2023: 2100.00
        assert accumulated == Decimal("10850.00")
    
    def test_get_accumulated_no_transactions(self, calculator, mock_db):
        """Return zero when there is no property or no rental history."""
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        mock_db.query.return_value = mock_query
        
        property_id = "550e8400-e29b-41d4-a716-446655440000"
        accumulated = calculator.get_accumulated_depreciation(property_id)
        
        assert accumulated == Decimal("0")
    
    def test_requires_database_session(self):
        """Should raise error if no database session provided"""
        calculator_no_db = AfACalculator(db=None)
        
        with pytest.raises(ValueError, match="Database session required"):
            calculator_no_db.get_accumulated_depreciation("some-id")


class TestCalculateMonthsOwned:
    """Test months owned calculation"""
    
    def test_full_year_ownership(self, calculator, sample_property):
        """Property owned for full year returns 12 months"""
        sample_property.purchase_date = date(2020, 1, 1)
        months = calculator._calculate_months_owned(sample_property, 2021)
        assert months == 12
    
    def test_partial_first_year(self, calculator, sample_property):
        """Property purchased mid-year"""
        sample_property.purchase_date = date(2020, 6, 15)
        months = calculator._calculate_months_owned(sample_property, 2020)
        # June to December = 7 months
        assert months == 7
    
    def test_partial_last_year(self, calculator, sample_property):
        """Property sold mid-year"""
        sample_property.purchase_date = date(2020, 1, 1)
        sample_property.sale_date = date(2023, 6, 30)
        months = calculator._calculate_months_owned(sample_property, 2023)
        # January to June = 6 months
        assert months == 6
    
    def test_purchased_in_december(self, calculator, sample_property):
        """Property purchased in December"""
        sample_property.purchase_date = date(2020, 12, 15)
        months = calculator._calculate_months_owned(sample_property, 2020)
        # Only December = 1 month
        assert months == 1
    
    def test_sold_in_january(self, calculator, sample_property):
        """Property sold in January"""
        sample_property.purchase_date = date(2020, 1, 1)
        sample_property.sale_date = date(2023, 1, 15)
        months = calculator._calculate_months_owned(sample_property, 2023)
        # Only January = 1 month
        assert months == 1


class TestRoundingPrecision:
    """Test that all calculations round to 2 decimal places"""
    
    def test_annual_depreciation_rounds_to_2_decimals(self, calculator, sample_property, mock_db):
        """Annual depreciation should round to 2 decimal places"""
        sample_property.asset_type = "equipment"
        sample_property.depreciation_rate = Decimal("0.0173")
        calculator.get_accumulated_depreciation = Mock(return_value=Decimal("0"))
        depreciation = calculator.calculate_annual_depreciation(sample_property, 2021)
        
        # Check that result has exactly 2 decimal places
        assert depreciation == depreciation.quantize(Decimal("0.01"))
    
    def test_prorated_depreciation_rounds_to_2_decimals(self, calculator, sample_property):
        """Pro-rated depreciation should round to 2 decimal places"""
        depreciation = calculator.calculate_prorated_depreciation(sample_property, 7)
        
        # Check that result has exactly 2 decimal places
        assert depreciation == depreciation.quantize(Decimal("0.01"))


class TestEdgeCases:
    """Test edge cases and boundary conditions"""
    
    def test_zero_building_value(self, calculator, sample_property, mock_db):
        """Handle property with zero building value"""
        sample_property.building_value = Decimal("0")
        _set_real_estate_context(calculator)
        
        depreciation = calculator.calculate_annual_depreciation(sample_property, 2021)
        assert depreciation == Decimal("0")
    
    def test_very_high_depreciation_rate(self, calculator, sample_property, mock_db):
        """Non-real-estate assets use the stored depreciation rate."""
        sample_property.asset_type = "equipment"
        sample_property.depreciation_rate = Decimal("0.10")
        calculator.get_accumulated_depreciation = Mock(return_value=Decimal("0"))
        
        depreciation = calculator.calculate_annual_depreciation(sample_property, 2021)
        
        # Expected: 280,000 * 0.10 = 28,000.00
        assert depreciation == Decimal("28000.00")
    
    def test_very_low_depreciation_rate(self, calculator, sample_property, mock_db):
        """Non-real-estate assets use the stored depreciation rate."""
        sample_property.asset_type = "equipment"
        sample_property.depreciation_rate = Decimal("0.001")
        calculator.get_accumulated_depreciation = Mock(return_value=Decimal("0"))
        
        depreciation = calculator.calculate_annual_depreciation(sample_property, 2021)
        
        # Expected: 280,000 * 0.001 = 280.00
        assert depreciation == Decimal("280.00")
