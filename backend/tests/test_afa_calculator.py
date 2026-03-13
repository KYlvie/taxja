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
    prop.depreciation_rate = Decimal("0.0200")
    prop.status = PropertyStatus.ACTIVE
    prop.sale_date = None
    return prop


class TestDetermineDepreciationRate:
    """Test depreciation rate determination based on construction year"""
    
    def test_pre_1915_building_gets_1_5_percent(self, calculator):
        """Buildings constructed before 1915 should get 1.5% depreciation rate"""
        rate = calculator.determine_depreciation_rate(1900)
        assert rate == Decimal("0.015")
    
    def test_1915_building_gets_2_percent(self, calculator):
        """Buildings constructed in 1915 should get 2.0% depreciation rate"""
        rate = calculator.determine_depreciation_rate(1915)
        assert rate == Decimal("0.020")
    
    def test_post_1915_building_gets_2_percent(self, calculator):
        """Buildings constructed after 1915 should get 2.0% depreciation rate"""
        rate = calculator.determine_depreciation_rate(1985)
        assert rate == Decimal("0.020")
    
    def test_unknown_construction_year_defaults_to_2_percent(self, calculator):
        """Unknown construction year should default to 2.0% depreciation rate"""
        rate = calculator.determine_depreciation_rate(None)
        assert rate == Decimal("0.020")
    
    def test_edge_case_1914(self, calculator):
        """1914 should get 1.5% rate (before 1915)"""
        rate = calculator.determine_depreciation_rate(1914)
        assert rate == Decimal("0.015")


class TestCalculateAnnualDepreciation:
    """Test annual depreciation calculation"""
    
    def test_full_year_depreciation(self, calculator, sample_property, mock_db):
        """Calculate depreciation for a full year of ownership"""
        # Mock accumulated depreciation query to return 0
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = Decimal("0")
        mock_db.query.return_value = mock_query
        
        # Calculate for year 2021 (full year)
        depreciation = calculator.calculate_annual_depreciation(sample_property, 2021)
        
        # Expected: 280,000 * 0.02 = 5,600.00
        assert depreciation == Decimal("5600.00")
    
    def test_partial_first_year_depreciation(self, calculator, sample_property, mock_db):
        """Calculate pro-rated depreciation for first year (purchased mid-year)"""
        # Mock accumulated depreciation query to return 0
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = Decimal("0")
        mock_db.query.return_value = mock_query
        
        # Property purchased June 15, 2020 - owned for 7 months (Jun-Dec)
        depreciation = calculator.calculate_annual_depreciation(sample_property, 2020)
        
        # Expected: (280,000 * 0.02 * 7) / 12 = 3,266.67
        assert depreciation == Decimal("3266.67")
    
    def test_no_depreciation_before_purchase(self, calculator, sample_property, mock_db):
        """No depreciation for years before property was purchased"""
        depreciation = calculator.calculate_annual_depreciation(sample_property, 2019)
        assert depreciation == Decimal("0")
    
    def test_no_depreciation_after_sale(self, calculator, sample_property, mock_db):
        """No depreciation for years after property was sold"""
        sample_property.sale_date = date(2023, 12, 31)
        depreciation = calculator.calculate_annual_depreciation(sample_property, 2024)
        assert depreciation == Decimal("0")
    
    def test_stops_at_building_value_limit(self, calculator, sample_property, mock_db):
        """Depreciation stops when accumulated equals building value"""
        # Mock accumulated depreciation to be at building value
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = Decimal("280000.00")
        mock_db.query.return_value = mock_query
        
        depreciation = calculator.calculate_annual_depreciation(sample_property, 2025)
        assert depreciation == Decimal("0")
    
    def test_respects_remaining_depreciable_value(self, calculator, sample_property, mock_db):
        """Depreciation limited to remaining depreciable value"""
        # Mock accumulated depreciation close to building value
        # Accumulated: 278,000, Remaining: 2,000
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = Decimal("278000.00")
        mock_db.query.return_value = mock_query
        
        depreciation = calculator.calculate_annual_depreciation(sample_property, 2025)
        
        # Expected: min(5600, 2000) = 2000.00
        assert depreciation == Decimal("2000.00")
    
    def test_mixed_use_property_depreciation(self, calculator, sample_property, mock_db):
        """Mixed-use property depreciates only rental percentage"""
        sample_property.property_type = PropertyType.MIXED_USE
        sample_property.rental_percentage = Decimal("50.00")
        
        # Mock accumulated depreciation query to return 0
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = Decimal("0")
        mock_db.query.return_value = mock_query
        
        depreciation = calculator.calculate_annual_depreciation(sample_property, 2021)
        
        # Expected: 280,000 * 0.50 * 0.02 = 2,800.00
        assert depreciation == Decimal("2800.00")
    
    def test_owner_occupied_no_depreciation(self, calculator, sample_property, mock_db):
        """Owner-occupied properties are not depreciable"""
        sample_property.property_type = PropertyType.OWNER_OCCUPIED
        
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
        
        # Expected: (280,000 * 0.02 * 6) / 12 = 2,800.00
        assert depreciation == Decimal("2800.00")
    
    def test_prorated_for_1_month(self, calculator, sample_property):
        """Calculate pro-rated depreciation for 1 month"""
        depreciation = calculator.calculate_prorated_depreciation(sample_property, 1)
        
        # Expected: (280,000 * 0.02 * 1) / 12 = 466.67
        assert depreciation == Decimal("466.67")
    
    def test_prorated_for_12_months_equals_annual(self, calculator, sample_property):
        """Pro-rated for 12 months should equal full annual depreciation"""
        depreciation = calculator.calculate_prorated_depreciation(sample_property, 12)
        
        # Expected: (280,000 * 0.02 * 12) / 12 = 5,600.00
        assert depreciation == Decimal("5600.00")
    
    def test_prorated_mixed_use_property(self, calculator, sample_property):
        """Pro-rated depreciation for mixed-use property"""
        sample_property.property_type = PropertyType.MIXED_USE
        sample_property.rental_percentage = Decimal("60.00")
        
        depreciation = calculator.calculate_prorated_depreciation(sample_property, 6)
        
        # Expected: (280,000 * 0.60 * 0.02 * 6) / 12 = 1,680.00
        assert depreciation == Decimal("1680.00")
    
    def test_prorated_owner_occupied_no_depreciation(self, calculator, sample_property):
        """Owner-occupied properties have no pro-rated depreciation"""
        sample_property.property_type = PropertyType.OWNER_OCCUPIED
        
        depreciation = calculator.calculate_prorated_depreciation(sample_property, 6)
        assert depreciation == Decimal("0")


class TestGetAccumulatedDepreciation:
    """Test accumulated depreciation query"""
    
    def test_get_accumulated_all_years(self, calculator, mock_db):
        """Get total accumulated depreciation across all years"""
        # Mock query to return sum of depreciation transactions
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = Decimal("28000.00")
        mock_db.query.return_value = mock_query
        
        property_id = "550e8400-e29b-41d4-a716-446655440000"
        accumulated = calculator.get_accumulated_depreciation(property_id)
        
        assert accumulated == Decimal("28000.00")
    
    def test_get_accumulated_up_to_year(self, calculator, mock_db):
        """Get accumulated depreciation up to specific year"""
        # Mock query to return sum up to 2023
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = Decimal("16800.00")
        mock_db.query.return_value = mock_query
        
        property_id = "550e8400-e29b-41d4-a716-446655440000"
        accumulated = calculator.get_accumulated_depreciation(property_id, up_to_year=2023)
        
        assert accumulated == Decimal("16800.00")
    
    def test_get_accumulated_no_transactions(self, calculator, mock_db):
        """Return zero if no depreciation transactions exist"""
        # Mock query to return None (no transactions)
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = None
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
        # Mock accumulated depreciation
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = Decimal("0")
        mock_db.query.return_value = mock_query
        
        # Use a rate that produces many decimal places
        sample_property.depreciation_rate = Decimal("0.0173")
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
        
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = Decimal("0")
        mock_db.query.return_value = mock_query
        
        depreciation = calculator.calculate_annual_depreciation(sample_property, 2021)
        assert depreciation == Decimal("0")
    
    def test_very_high_depreciation_rate(self, calculator, sample_property, mock_db):
        """Handle property with maximum depreciation rate (10%)"""
        sample_property.depreciation_rate = Decimal("0.10")
        
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = Decimal("0")
        mock_db.query.return_value = mock_query
        
        depreciation = calculator.calculate_annual_depreciation(sample_property, 2021)
        
        # Expected: 280,000 * 0.10 = 28,000.00
        assert depreciation == Decimal("28000.00")
    
    def test_very_low_depreciation_rate(self, calculator, sample_property, mock_db):
        """Handle property with minimum depreciation rate (0.1%)"""
        sample_property.depreciation_rate = Decimal("0.001")
        
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = Decimal("0")
        mock_db.query.return_value = mock_query
        
        depreciation = calculator.calculate_annual_depreciation(sample_property, 2021)
        
        # Expected: 280,000 * 0.001 = 280.00
        assert depreciation == Decimal("280.00")
