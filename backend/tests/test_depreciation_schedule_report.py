"""
Tests for depreciation schedule report generation with future projections.

Tests the PropertyReportService.generate_depreciation_schedule() method
to ensure it correctly generates historical and future depreciation schedules.
"""
import pytest
from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.models.property import Property, PropertyType, PropertyStatus
from app.models.user import User
from app.services.property_report_service import PropertyReportService


@pytest.fixture
def test_user(db):
    """Create a test user"""
    user = User(
        email="landlord@test.com",
        hashed_password="hashed_password",
        name="Test Landlord",
        user_type="landlord"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def active_property(db, test_user):
    """Create an active rental property purchased 3 years ago"""
    property = Property(
        id=uuid4(),
        user_id=test_user.id,
        property_type=PropertyType.RENTAL,
        rental_percentage=Decimal("100.00"),
        street="Teststraße 123",
        city="Wien",
        postal_code="1010",
        address="Teststraße 123, 1010 Wien",
        purchase_date=date(2023, 1, 1),
        purchase_price=Decimal("300000.00"),
        building_value=Decimal("240000.00"),
        construction_year=2000,
        depreciation_rate=Decimal("0.02"),
        status=PropertyStatus.ACTIVE
    )
    db.add(property)
    db.commit()
    db.refresh(property)
    return property


@pytest.fixture
def sold_property(db, test_user):
    """Create a sold property"""
    property = Property(
        id=uuid4(),
        user_id=test_user.id,
        property_type=PropertyType.RENTAL,
        rental_percentage=Decimal("100.00"),
        street="Verkauftstraße 456",
        city="Wien",
        postal_code="1020",
        address="Verkauftstraße 456, 1020 Wien",
        purchase_date=date(2020, 1, 1),
        purchase_price=Decimal("200000.00"),
        building_value=Decimal("160000.00"),
        construction_year=1990,
        depreciation_rate=Decimal("0.02"),
        status=PropertyStatus.SOLD,
        sale_date=date(2024, 12, 31)
    )
    db.add(property)
    db.commit()
    db.refresh(property)
    return property


class TestDepreciationScheduleReport:
    """Test depreciation schedule report generation"""

    def test_generate_schedule_with_historical_only(self, db, active_property):
        """Test generating schedule with only historical data (no future projections)"""
        report_service = PropertyReportService(db)
        
        result = report_service.generate_depreciation_schedule(
            str(active_property.id),
            include_future=False
        )
        
        # Verify property details
        assert result["property"]["id"] == str(active_property.id)
        assert result["property"]["address"] == "Teststraße 123, 1010 Wien"
        assert result["property"]["building_value"] == 240000.00
        assert result["property"]["depreciation_rate"] == 0.02
        assert result["property"]["status"] == "active"
        
        # Verify schedule contains only historical years (2023, 2024, 2025, 2026)
        schedule = result["schedule"]
        current_year = date.today().year
        expected_years = current_year - 2023 + 1  # From 2023 to current year inclusive
        assert len(schedule) == expected_years
        
        # All entries should be historical (not projected)
        for entry in schedule:
            assert entry["is_projected"] is False
        
        # Verify summary
        summary = result["summary"]
        assert summary["years_elapsed"] == expected_years
        assert summary["years_projected"] == 0
        assert summary["total_depreciation"] == 240000.00
        assert summary["accumulated_depreciation"] > 0
        assert summary["remaining_value"] < 240000.00

    def test_generate_schedule_with_future_projections(self, db, active_property):
        """Test generating schedule with future depreciation projections"""
        report_service = PropertyReportService(db)
        
        result = report_service.generate_depreciation_schedule(
            str(active_property.id),
            include_future=True,
            future_years=10
        )
        
        # Verify schedule contains both historical and future entries
        schedule = result["schedule"]
        current_year = date.today().year
        expected_historical = current_year - 2023 + 1
        
        assert len(schedule) > expected_historical  # Should have future entries
        
        # Verify historical entries
        historical_entries = [e for e in schedule if not e["is_projected"]]
        assert len(historical_entries) == expected_historical
        
        # Verify future entries
        future_entries = [e for e in schedule if e["is_projected"]]
        assert len(future_entries) > 0
        assert len(future_entries) <= 10  # Should not exceed requested future_years
        
        # Verify future years are sequential and after current year
        for i, entry in enumerate(future_entries):
            assert entry["year"] == current_year + 1 + i
            assert entry["is_projected"] is True
            assert entry["annual_depreciation"] > 0
        
        # Verify summary
        summary = result["summary"]
        assert summary["years_elapsed"] == expected_historical
        assert summary["years_projected"] == len(future_entries)
        assert summary["years_remaining"] is not None
        assert summary["years_remaining"] > 0

    def test_depreciation_stops_at_building_value(self, db, active_property):
        """Test that future projections stop when building value is fully depreciated"""
        report_service = PropertyReportService(db)
        
        # Request 50 years of projections (more than needed to fully depreciate)
        result = report_service.generate_depreciation_schedule(
            str(active_property.id),
            include_future=True,
            future_years=50
        )
        
        schedule = result["schedule"]
        
        # Find the last entry
        last_entry = schedule[-1]
        
        # Verify accumulated depreciation does not exceed building value
        assert last_entry["accumulated_depreciation"] <= 240000.00
        
        # Verify remaining value is zero or very close to zero
        assert last_entry["remaining_value"] <= 0.01
        
        # Verify fully_depreciated_year is set
        summary = result["summary"]
        if last_entry["remaining_value"] == 0:
            assert summary["fully_depreciated_year"] == last_entry["year"]

    def test_sold_property_no_future_projections(self, db, sold_property):
        """Test that sold properties do not generate future projections"""
        report_service = PropertyReportService(db)
        
        result = report_service.generate_depreciation_schedule(
            str(sold_property.id),
            include_future=True,
            future_years=10
        )
        
        schedule = result["schedule"]
        
        # All entries should be historical (no projections for sold properties)
        for entry in schedule:
            assert entry["is_projected"] is False
            assert entry["year"] <= 2024  # Sale year
        
        # Verify summary
        summary = result["summary"]
        assert summary["years_projected"] == 0
        assert summary["years_remaining"] is None  # No future depreciation for sold property

    def test_annual_depreciation_consistency(self, db, active_property):
        """Test that annual depreciation amounts are consistent in projections"""
        report_service = PropertyReportService(db)
        
        result = report_service.generate_depreciation_schedule(
            str(active_property.id),
            include_future=True,
            future_years=5
        )
        
        schedule = result["schedule"]
        
        # Get future entries (full year depreciation)
        future_entries = [e for e in schedule if e["is_projected"]]
        
        if len(future_entries) > 1:
            # All future full-year entries should have same annual depreciation
            # (until approaching building value limit)
            expected_annual = 240000.00 * 0.02  # building_value * rate
            
            for entry in future_entries[:-1]:  # Exclude last entry (might be partial)
                # Allow small rounding differences
                assert abs(entry["annual_depreciation"] - expected_annual) < 0.01

    def test_accumulated_depreciation_increases_monotonically(self, db, active_property):
        """Test that accumulated depreciation increases monotonically"""
        report_service = PropertyReportService(db)
        
        result = report_service.generate_depreciation_schedule(
            str(active_property.id),
            include_future=True,
            future_years=10
        )
        
        schedule = result["schedule"]
        
        # Verify accumulated depreciation increases each year
        for i in range(1, len(schedule)):
            assert schedule[i]["accumulated_depreciation"] >= schedule[i-1]["accumulated_depreciation"]
        
        # Verify remaining value decreases each year
        for i in range(1, len(schedule)):
            assert schedule[i]["remaining_value"] <= schedule[i-1]["remaining_value"]

    def test_years_remaining_calculation(self, db, active_property):
        """Test that years_remaining is calculated correctly"""
        report_service = PropertyReportService(db)
        
        result = report_service.generate_depreciation_schedule(
            str(active_property.id),
            include_future=True,
            future_years=10
        )
        
        summary = result["summary"]
        
        # Calculate expected years remaining
        remaining_value = summary["remaining_value"]
        annual_depreciation = 240000.00 * 0.02
        expected_years = remaining_value / annual_depreciation
        
        # Verify years_remaining is close to expected
        assert summary["years_remaining"] is not None
        assert abs(summary["years_remaining"] - expected_years) < 0.2  # Allow small difference

    def test_property_not_found(self, db):
        """Test that ValueError is raised for non-existent property"""
        report_service = PropertyReportService(db)
        
        with pytest.raises(ValueError, match="Property .* not found"):
            report_service.generate_depreciation_schedule(str(uuid4()))

    def test_future_years_parameter_limits(self, db, active_property):
        """Test that future_years parameter is respected"""
        report_service = PropertyReportService(db)
        
        # Test with 5 future years
        result_5 = report_service.generate_depreciation_schedule(
            str(active_property.id),
            include_future=True,
            future_years=5
        )
        
        # Test with 15 future years
        result_15 = report_service.generate_depreciation_schedule(
            str(active_property.id),
            include_future=True,
            future_years=15
        )
        
        # Verify different number of projected years
        future_5 = [e for e in result_5["schedule"] if e["is_projected"]]
        future_15 = [e for e in result_15["schedule"] if e["is_projected"]]
        
        assert len(future_5) <= 5
        assert len(future_15) <= 15
        assert len(future_15) > len(future_5)

    def test_mixed_use_property_depreciation(self, db, test_user):
        """Test depreciation schedule for mixed-use property (partial rental)"""
        # Create mixed-use property (50% rental)
        property = Property(
            id=uuid4(),
            user_id=test_user.id,
            property_type=PropertyType.MIXED_USE,
            rental_percentage=Decimal("50.00"),
            street="Gemischtstraße 789",
            city="Wien",
            postal_code="1030",
            address="Gemischtstraße 789, 1030 Wien",
            purchase_date=date(2024, 1, 1),
            purchase_price=Decimal("400000.00"),
            building_value=Decimal("320000.00"),
            construction_year=2010,
            depreciation_rate=Decimal("0.02"),
            status=PropertyStatus.ACTIVE
        )
        db.add(property)
        db.commit()
        
        report_service = PropertyReportService(db)
        
        result = report_service.generate_depreciation_schedule(
            str(property.id),
            include_future=True,
            future_years=5
        )
        
        # Verify depreciation is calculated on 50% of building value
        expected_annual = 320000.00 * 0.50 * 0.02  # building_value * rental_pct * rate
        
        future_entries = [e for e in result["schedule"] if e["is_projected"]]
        if future_entries:
            # Check first future entry (full year)
            assert abs(future_entries[0]["annual_depreciation"] - expected_annual) < 0.01
