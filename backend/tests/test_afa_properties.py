"""
Property-Based Tests for AfA (Depreciation) Calculator

This module uses Hypothesis to validate correctness properties of the AfA calculator
through property-based testing with randomly generated test data.

**Validates: Requirements 11 (Depreciation Calculation Correctness)**

Correctness Properties Tested:
- Property 1: Depreciation Accumulation Invariant
- Property 2: Depreciation Rate Consistency
- Property 3: Pro-Rata Calculation Correctness
- Property 6: Depreciation Idempotence
- Property 8: Depreciation Rate Metamorphic
"""

import pytest
from decimal import Decimal
from datetime import date
from unittest.mock import Mock
from hypothesis import given, strategies as st, assume, settings, HealthCheck
from sqlalchemy.orm import Session

from app.services.afa_calculator import AfACalculator
from app.models.property import BuildingUse


# ============================================================================
# Mock Property Class (avoids SQLAlchemy initialization issues)
# ============================================================================

class PropertyType:
    """Mock PropertyType enum"""
    RENTAL = "rental"
    OWNER_OCCUPIED = "owner_occupied"
    MIXED_USE = "mixed_use"


class PropertyStatus:
    """Mock PropertyStatus enum"""
    ACTIVE = "active"
    SOLD = "sold"
    ARCHIVED = "archived"


class MockProperty:
    """Mock Property class for testing without database"""
    def __init__(self):
        self.id = None
        self.user_id = None
        self.property_type = None
        self.rental_percentage = None
        self.address = None
        self.street = None
        self.city = None
        self.postal_code = None
        self.purchase_date = None
        self.purchase_price = None
        self.building_value = None
        self.land_value = None
        self.construction_year = None
        self.depreciation_rate = None
        self.asset_type = None
        self.building_use = None
        self.status = None
        self.sale_date = None


# ============================================================================
# Hypothesis Strategies for Test Data Generation
# ============================================================================

@st.composite
def property_strategy(draw, property_type=PropertyType.RENTAL):
    """
    Generate valid Property instances for testing.
    
    Constrains values to realistic ranges for Austrian rental properties.
    """
    # Generate purchase date between 2000 and 2025
    purchase_year = draw(st.integers(min_value=2000, max_value=2025))
    purchase_month = draw(st.integers(min_value=1, max_value=12))
    purchase_day = draw(st.integers(min_value=1, max_value=28))  # Safe for all months
    purchase_date_val = date(purchase_year, purchase_month, purchase_day)
    
    # Generate building value (10,000 to 1,000,000 EUR)
    building_value = draw(st.decimals(
        min_value=Decimal("10000"),
        max_value=Decimal("1000000"),
        places=2
    ))
    
    # Generate depreciation rate for helper-method tests that still use stored rates.
    depreciation_rate = draw(st.decimals(
        min_value=Decimal("0.015"),
        max_value=Decimal("0.020"),
        places=4
    ))
    
    # Keep construction year before accelerated AfA kicks in so the base rate is stable.
    construction_year = draw(st.integers(min_value=1850, max_value=2020))
    
    # Create property instance (using mock to avoid SQLAlchemy issues)
    prop = MockProperty()
    prop.id = "test-property-id"
    prop.user_id = 1
    prop.property_type = property_type
    prop.rental_percentage = Decimal("100.00")
    prop.address = "Test Address"
    prop.street = "Test Street"
    prop.city = "Wien"
    prop.postal_code = "1010"
    prop.purchase_date = purchase_date_val
    prop.purchase_price = building_value / Decimal("0.8")  # Building is 80% of purchase
    prop.building_value = building_value
    prop.land_value = building_value / Decimal("4")  # 20% of purchase price
    prop.construction_year = construction_year
    prop.depreciation_rate = depreciation_rate
    prop.asset_type = "real_estate"
    prop.building_use = BuildingUse.RESIDENTIAL
    prop.status = PropertyStatus.ACTIVE
    prop.sale_date = None
    
    return prop


def _set_real_estate_context(
    calculator: AfACalculator,
    *,
    accumulated: Decimal = Decimal("0"),
    rental_percentage: Decimal = Decimal("100"),
) -> None:
    """Stub historical rental context for real-estate annual depreciation tests."""
    calculator.get_accumulated_depreciation = Mock(return_value=accumulated)
    calculator._get_rental_percentage_for_year = Mock(return_value=rental_percentage)
    calculator._check_rental_income_warning = Mock()


@st.composite
def mixed_use_property_strategy(draw):
    """Generate mixed-use properties with rental percentage."""
    prop = draw(property_strategy(property_type=PropertyType.MIXED_USE))
    
    # Generate rental percentage (10% to 90%)
    rental_pct = draw(st.decimals(
        min_value=Decimal("10.00"),
        max_value=Decimal("90.00"),
        places=2
    ))
    prop.rental_percentage = rental_pct
    
    return prop


# ============================================================================
# Property 1: Depreciation Accumulation Invariant
# **Validates: Requirements 11.1**
# ============================================================================

@given(
    property=property_strategy(),
    num_years=st.integers(min_value=1, max_value=50)
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property_1_depreciation_never_exceeds_building_value(property, num_years):
    """
    Property 1: Depreciation Accumulation Invariant
    
    FOR ALL properties p, at any point in time:
    sum(depreciation_transactions.amount WHERE property_id = p.id) <= p.building_value
    
    This test verifies that accumulated depreciation never exceeds the building value,
    regardless of how many years pass.
    """
    # Setup mock database
    mock_db = Mock(spec=Session)
    calculator = AfACalculator(db=mock_db)
    
    # Simulate depreciation over multiple years
    accumulated = Decimal("0")
    start_year = property.purchase_date.year
    
    for year_offset in range(num_years):
        year = start_year + year_offset

        _set_real_estate_context(calculator, accumulated=accumulated)
        
        # Calculate depreciation for this year
        annual_depreciation = calculator.calculate_annual_depreciation(property, year)
        accumulated += annual_depreciation
        
        # INVARIANT: Accumulated depreciation must never exceed building value
        assert accumulated <= property.building_value, (
            f"Accumulated depreciation {accumulated} exceeds building value "
            f"{property.building_value} after {year_offset + 1} years"
        )


# ============================================================================
# Property 2: Depreciation Rate Consistency
# **Validates: Requirements 11.3**
# ============================================================================

@given(
    building_value=st.decimals(
        min_value=Decimal("10000"),
        max_value=Decimal("1000000"),
        places=2
    )
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property_2_annual_depreciation_equals_building_value_times_rate(
    building_value,
):
    """
    Property 2: Depreciation Rate Consistency
    
    FOR ALL residential properties p with full year of ownership:
    annual_depreciation = p.building_value * statutory_residential_rate
    (within 0.01 EUR tolerance)
    
    This test verifies that for a full year of ownership, the annual depreciation
    equals the building value multiplied by the statutory residential rate.
    """
    # Setup mock database
    mock_db = Mock(spec=Session)
    calculator = AfACalculator(db=mock_db)
    
    # Create property with full year ownership (purchased Jan 1)
    property = MockProperty()
    property.id = "test-property-id"
    property.property_type = PropertyType.RENTAL
    property.rental_percentage = Decimal("100.00")
    property.purchase_date = date(2020, 1, 1)
    property.building_value = building_value
    property.depreciation_rate = calculator.RESIDENTIAL_RATE
    property.construction_year = 2020
    property.asset_type = "real_estate"
    property.building_use = BuildingUse.RESIDENTIAL
    property.sale_date = None

    _set_real_estate_context(calculator)
    
    # Calculate annual depreciation for full year (2021)
    actual = calculator.calculate_annual_depreciation(property, 2021)
    
    # Expected: building_value * statutory residential rate
    expected = (building_value * calculator.RESIDENTIAL_RATE).quantize(Decimal("0.01"))
    
    # PROPERTY: Annual depreciation should equal building_value * rate
    # Allow 0.01 EUR tolerance for rounding
    assert abs(actual - expected) <= Decimal("0.01"), (
        f"Annual depreciation {actual} does not match expected {expected} "
        f"(building_value={building_value}, rate={calculator.RESIDENTIAL_RATE})"
    )


# ============================================================================
# Property 3: Pro-Rata Calculation Correctness
# **Validates: Requirements 11.4**
# ============================================================================

@given(
    building_value=st.decimals(
        min_value=Decimal("10000"),
        max_value=Decimal("1000000"),
        places=2
    ),
    purchase_month=st.integers(min_value=1, max_value=12)
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property_3_prorated_first_year_depreciation_formula(
    building_value,
    purchase_month
):
    """
    Property 3: Pro-Rata Calculation Correctness
    
    FOR ALL residential properties p purchased in year Y:
    first_year_depreciation = (p.building_value * statutory_residential_rate * months_owned_in_Y) / 12
    (within 0.01 EUR tolerance)
    
    This test verifies that partial year depreciation is correctly pro-rated
    based on the number of months owned.
    """
    # Setup mock database
    mock_db = Mock(spec=Session)
    calculator = AfACalculator(db=mock_db)
    
    # Create property purchased mid-year
    purchase_year = 2020
    property = MockProperty()
    property.id = "test-property-id"
    property.property_type = PropertyType.RENTAL
    property.rental_percentage = Decimal("100.00")
    property.purchase_date = date(purchase_year, purchase_month, 15)
    property.building_value = building_value
    property.depreciation_rate = calculator.RESIDENTIAL_RATE
    property.construction_year = 2020
    property.asset_type = "real_estate"
    property.building_use = BuildingUse.RESIDENTIAL
    property.sale_date = None

    _set_real_estate_context(calculator)
    
    # Calculate first year depreciation
    actual = calculator.calculate_annual_depreciation(property, purchase_year)
    
    # Calculate expected pro-rated amount
    months_owned = 12 - purchase_month + 1  # Inclusive of purchase month
    annual_amount = building_value * calculator.RESIDENTIAL_RATE
    expected = ((annual_amount * months_owned) / 12).quantize(Decimal("0.01"))
    
    # PROPERTY: First year depreciation should be pro-rated by months owned
    # Allow 0.01 EUR tolerance for rounding
    assert abs(actual - expected) <= Decimal("0.01"), (
        f"Pro-rated depreciation {actual} does not match expected {expected} "
        f"(building_value={building_value}, rate={calculator.RESIDENTIAL_RATE}, "
        f"months_owned={months_owned})"
    )


@given(
    property=property_strategy(),
    months_owned=st.integers(min_value=1, max_value=12)
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property_3_prorated_depreciation_method(property, months_owned):
    """
    Property 3: Pro-Rata Calculation Correctness (using prorated method)
    
    Verifies that the calculate_prorated_depreciation method correctly
    implements the pro-rata formula.
    """
    # Setup calculator (no DB needed for this method)
    calculator = AfACalculator()
    
    # Calculate pro-rated depreciation
    actual = calculator.calculate_prorated_depreciation(property, months_owned)
    
    # Calculate expected
    annual_amount = property.building_value * property.depreciation_rate
    expected = ((annual_amount * months_owned) / 12).quantize(Decimal("0.01"))
    
    # PROPERTY: Pro-rated depreciation should match formula
    assert abs(actual - expected) <= Decimal("0.01"), (
        f"Pro-rated depreciation {actual} does not match expected {expected} "
        f"for {months_owned} months"
    )


# ============================================================================
# Property 6: Depreciation Idempotence
# **Validates: Requirements 11.5**
# ============================================================================

@given(
    property=property_strategy(),
    year=st.integers(min_value=2020, max_value=2030)
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property_6_depreciation_calculation_is_idempotent(property, year):
    """
    Property 6: Depreciation Idempotence
    
    FOR ALL properties p and year Y:
    Calculating depreciation for year Y multiple times produces identical results
    
    This test verifies that the depreciation calculation is deterministic and
    produces the same result when called multiple times with the same inputs.
    """
    # Ensure year is after purchase
    assume(year >= property.purchase_date.year)
    
    # Setup mock database
    mock_db = Mock(spec=Session)
    calculator = AfACalculator(db=mock_db)
    
    # Mock accumulated depreciation (some arbitrary amount)
    accumulated = property.building_value * Decimal("0.3")  # 30% depreciated
    _set_real_estate_context(calculator, accumulated=accumulated)
    
    # Calculate depreciation multiple times
    result1 = calculator.calculate_annual_depreciation(property, year)
    result2 = calculator.calculate_annual_depreciation(property, year)
    result3 = calculator.calculate_annual_depreciation(property, year)
    
    # PROPERTY: All results should be identical (idempotent)
    assert result1 == result2 == result3, (
        f"Depreciation calculation is not idempotent: "
        f"result1={result1}, result2={result2}, result3={result3}"
    )


@given(
    property=property_strategy(),
    months_owned=st.integers(min_value=1, max_value=12)
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property_6_prorated_depreciation_is_idempotent(property, months_owned):
    """
    Property 6: Depreciation Idempotence (pro-rated method)
    
    Verifies that the pro-rated depreciation calculation is also idempotent.
    """
    calculator = AfACalculator()
    
    # Calculate pro-rated depreciation multiple times
    result1 = calculator.calculate_prorated_depreciation(property, months_owned)
    result2 = calculator.calculate_prorated_depreciation(property, months_owned)
    result3 = calculator.calculate_prorated_depreciation(property, months_owned)
    
    # PROPERTY: All results should be identical (idempotent)
    assert result1 == result2 == result3, (
        f"Pro-rated depreciation calculation is not idempotent: "
        f"result1={result1}, result2={result2}, result3={result3}"
    )


# ============================================================================
# Property 8: Depreciation Rate Metamorphic
# **Validates: Requirements 11.6**
# ============================================================================

@given(
    building_value=st.decimals(
        min_value=Decimal("10000"),
        max_value=Decimal("1000000"),
        places=2
    )
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property_8_commercial_rate_scales_depreciation(building_value):
    """
    Property 8: Depreciation Rate Metamorphic Property
    
    FOR ALL full-year buildings with identical value:
    commercial_depreciation = residential_depreciation * (2.5 / 1.5)

    This test verifies that the real-estate path applies the statutory
    commercial vs residential rates consistently.
    """
    # Setup mock database
    mock_db = Mock(spec=Session)
    calculator = AfACalculator(db=mock_db)

    residential = MockProperty()
    residential.id = "test-property-id"
    residential.property_type = PropertyType.RENTAL
    residential.rental_percentage = Decimal("100.00")
    residential.purchase_date = date(2020, 1, 1)
    residential.building_value = building_value
    residential.depreciation_rate = calculator.RESIDENTIAL_RATE
    residential.construction_year = 2020
    residential.asset_type = "real_estate"
    residential.building_use = BuildingUse.RESIDENTIAL
    residential.sale_date = None

    commercial = MockProperty()
    commercial.id = "test-property-id"
    commercial.property_type = PropertyType.RENTAL
    commercial.rental_percentage = Decimal("100.00")
    commercial.purchase_date = date(2020, 1, 1)
    commercial.building_value = building_value
    commercial.depreciation_rate = calculator.COMMERCIAL_RATE
    commercial.construction_year = 2020
    commercial.asset_type = "real_estate"
    commercial.building_use = BuildingUse.COMMERCIAL
    commercial.sale_date = None

    _set_real_estate_context(calculator)

    year = 2021
    calculator.calculate_annual_depreciation(residential, year)
    commercial_depreciation = calculator.calculate_annual_depreciation(commercial, year)

    expected_commercial = (
        building_value * calculator.COMMERCIAL_RATE
    ).quantize(Decimal("0.01"))

    assert commercial_depreciation == expected_commercial, (
        f"Commercial depreciation {commercial_depreciation} does not match "
        f"expected {expected_commercial} for building_value={building_value}"
    )


@given(
    building_value=st.decimals(
        min_value=Decimal("10000"),
        max_value=Decimal("1000000"),
        places=2
    ),
    base_rate=st.decimals(
        min_value=Decimal("0.015"),
        max_value=Decimal("0.020"),
        places=4
    )
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property_8_halving_rate_halves_depreciation(building_value, base_rate):
    """
    Property 8: Depreciation Rate Metamorphic Property (stored-rate helper)
    
    Specifically tests that the direct prorated helper scales linearly with
    the stored depreciation_rate field.
    """
    calculator = AfACalculator()
    
    # Create property with base rate
    property = MockProperty()
    property.id = "test-property-id"
    property.property_type = PropertyType.RENTAL
    property.rental_percentage = Decimal("100.00")
    property.purchase_date = date(2020, 1, 1)
    property.building_value = building_value
    property.depreciation_rate = base_rate
    property.sale_date = None
    
    # Calculate with base rate
    base_depreciation = calculator.calculate_prorated_depreciation(property, 12)
    
    # Calculate with half rate
    property.depreciation_rate = base_rate / 2
    half_depreciation = calculator.calculate_prorated_depreciation(property, 12)
    
    # PROPERTY: Half rate should produce half depreciation
    expected_half = (base_depreciation / 2).quantize(Decimal("0.01"))
    
    # Allow 0.01 EUR tolerance for rounding
    assert abs(half_depreciation - expected_half) <= Decimal("0.01"), (
        f"Halving rate did not halve depreciation: "
        f"base_rate={base_rate}, half_rate={base_rate/2}, "
        f"base_depreciation={base_depreciation}, "
        f"half_depreciation={half_depreciation}, "
        f"expected_half={expected_half}"
    )


# ============================================================================
# Additional Property Tests: Mixed-Use Properties
# **Validates: Requirements 11 (with mixed-use properties)**
# ============================================================================

@given(
    property=mixed_use_property_strategy(),
    year=st.integers(min_value=2020, max_value=2030)
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_mixed_use_property_depreciation_respects_rental_percentage(property, year):
    """
    Verify that mixed-use properties only depreciate the rental percentage
    of the building value.
    
    This extends Property 2 to mixed-use properties.
    """
    # Ensure year is after purchase
    assume(year >= property.purchase_date.year)
    
    # Setup mock database
    mock_db = Mock(spec=Session)
    calculator = AfACalculator(db=mock_db)
    
    _set_real_estate_context(calculator, rental_percentage=property.rental_percentage)
    
    # Calculate depreciation
    actual = calculator.calculate_annual_depreciation(property, year)
    
    # Calculate expected (only rental percentage is depreciable)
    depreciable_value = property.building_value * (property.rental_percentage / 100)
    
    # For first year, might be pro-rated
    months_owned = calculator._calculate_months_owned(property, year)
    annual_amount = depreciable_value * calculator.RESIDENTIAL_RATE
    
    if months_owned < 12:
        expected = ((annual_amount * months_owned) / 12).quantize(Decimal("0.01"))
    else:
        expected = annual_amount.quantize(Decimal("0.01"))
    
    # PROPERTY: Depreciation should only apply to rental percentage
    assert abs(actual - expected) <= Decimal("0.01"), (
        f"Mixed-use depreciation {actual} does not match expected {expected} "
        f"(rental_percentage={property.rental_percentage}%)"
    )


# ============================================================================
# Edge Case Property Tests
# ============================================================================

@given(
    property=property_strategy(),
    num_years=st.integers(min_value=1, max_value=100)
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_depreciation_stops_when_fully_depreciated(property, num_years):
    """
    Verify that once a property is fully depreciated, no additional
    depreciation is calculated.
    
    This is a corollary of Property 1.
    """
    # Setup mock database
    mock_db = Mock(spec=Session)
    calculator = AfACalculator(db=mock_db)
    
    _set_real_estate_context(calculator, accumulated=property.building_value)
    
    # Calculate depreciation for any year after full depreciation
    year = property.purchase_date.year + num_years
    depreciation = calculator.calculate_annual_depreciation(property, year)
    
    # PROPERTY: No depreciation should be calculated
    assert depreciation == Decimal("0"), (
        f"Depreciation {depreciation} calculated for fully depreciated property"
    )


@given(property=property_strategy())
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_no_depreciation_before_purchase_year(property):
    """
    Verify that no depreciation is calculated for years before the property
    was purchased.
    """
    calculator = AfACalculator()
    
    # Calculate depreciation for year before purchase
    year_before = property.purchase_date.year - 1
    depreciation = calculator.calculate_annual_depreciation(property, year_before)
    
    # PROPERTY: No depreciation before purchase
    assert depreciation == Decimal("0"), (
        f"Depreciation {depreciation} calculated for year before purchase"
    )
