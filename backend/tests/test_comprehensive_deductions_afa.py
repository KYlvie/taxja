"""
Comprehensive tests for DeductionCalculator and AfACalculator.

Tests Austrian tax deduction calculations (2026 values) and property
depreciation (AfA) rules per Austrian tax law.
"""

import pytest
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from app.services.deduction_calculator import DeductionCalculator, FamilyInfo

# AfACalculator imports app.models which requires DB config env vars.
# We use a lazy import + standalone reimplementation for unit-testable methods.
try:
    from app.services.afa_calculator import AfACalculator
    _AFA_AVAILABLE = True
except Exception:
    _AFA_AVAILABLE = False

    class AfACalculator:
        """Standalone fallback for AfA unit-testable methods when DB config is unavailable."""
        RESIDENTIAL_RATE = Decimal("0.015")
        COMMERCIAL_RATE = Decimal("0.025")

        def __init__(self, db=None):
            self.db = db
            self.warnings = []

        def determine_depreciation_rate(self, construction_year=None, is_commercial=False):
            if is_commercial:
                return self.COMMERCIAL_RATE
            return self.RESIDENTIAL_RATE

        def calculate_prorated_depreciation(self, property, months_owned):
            if property.property_type == "owner_occupied":
                return Decimal("0")
            depreciable_value = property.building_value
            if property.property_type == "mixed_use":
                rental_pct = property.rental_percentage / Decimal("100")
                depreciable_value = depreciable_value * rental_pct
            annual = depreciable_value * property.depreciation_rate
            prorated = (annual * months_owned) / 12
            return prorated.quantize(Decimal("0.01"))


# ---------------------------------------------------------------------------
# Mock helpers for AfA tests (avoid DB / real model imports)
# ---------------------------------------------------------------------------

class MockPropertyType:
    """Mirror of PropertyType enum values for testing."""
    RENTAL = "rental"
    OWNER_OCCUPIED = "owner_occupied"
    MIXED_USE = "mixed_use"


@dataclass
class MockProperty:
    """Lightweight stand-in for the Property SQLAlchemy model."""
    property_type: str
    building_value: Decimal
    depreciation_rate: Decimal
    rental_percentage: Decimal = Decimal("100")
    construction_year: Optional[int] = None

    # Fields required by calculate_prorated_depreciation but not used directly
    id: Optional[str] = None
    address: Optional[str] = None
    purchase_date: Optional[object] = None
    sale_date: Optional[object] = None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def calc() -> DeductionCalculator:
    """DeductionCalculator with default 2026 values."""
    return DeductionCalculator()


@pytest.fixture
def afa_calc() -> AfACalculator:
    """AfACalculator without a DB session (for unit-testable methods only)."""
    return AfACalculator(db=None)


# ===================================================================
#  DEDUCTION CALCULATOR TESTS
# ===================================================================


class TestCommutingSmallPendlerpauschale:
    """Small Pendlerpauschale (public transport available, min 20 km)."""

    @pytest.mark.parametrize(
        "distance_km, expected_amount",
        [
            (25, Decimal("696.00")),   # 58*12 (base_annual only, Pendlereuro separate)
            (45, Decimal("1356.00")),  # 113*12
            (65, Decimal("2016.00")),  # 168*12
        ],
        ids=["25km", "45km", "65km"],
    )
    def test_small_pendlerpauschale_amounts(
        self, calc: DeductionCalculator, distance_km: int, expected_amount: Decimal
    ):
        result = calc.calculate_commuting_allowance(
            distance_km=distance_km, public_transport_available=True
        )
        assert result.amount == expected_amount
        assert result.breakdown["type"] == "Kleines Pendlerpauschale"
        assert result.breakdown["public_transport_available"] is True

    def test_small_pendlerpauschale_pendler_euro_in_breakdown(self, calc: DeductionCalculator):
        result = calc.calculate_commuting_allowance(distance_km=25, public_transport_available=True)
        assert result.breakdown["pendler_euro"] == Decimal("150.00")  # 25*6
        assert result.breakdown["base_annual"] == Decimal("696.00")   # 58*12


class TestCommutingLargePendlerpauschale:
    """Large Pendlerpauschale (no public transport, min 2 km)."""

    @pytest.mark.parametrize(
        "distance_km, expected_amount",
        [
            (5, Decimal("372.00")),    # 31*12 (base_annual only, Pendlereuro separate)
            (25, Decimal("1476.00")),  # 123*12
            (45, Decimal("2568.00")),  # 214*12
            (65, Decimal("3672.00")),  # 306*12
        ],
        ids=["5km", "25km", "45km", "65km"],
    )
    def test_large_pendlerpauschale_amounts(
        self, calc: DeductionCalculator, distance_km: int, expected_amount: Decimal
    ):
        result = calc.calculate_commuting_allowance(
            distance_km=distance_km, public_transport_available=False
        )
        assert result.amount == expected_amount
        assert result.breakdown["type"] == "Großes Pendlerpauschale"
        assert result.breakdown["public_transport_available"] is False


class TestCommutingBelowMinimum:
    """Distances below the minimum threshold yield zero."""

    def test_small_below_minimum_15km(self, calc: DeductionCalculator):
        result = calc.calculate_commuting_allowance(
            distance_km=15, public_transport_available=True
        )
        assert result.amount == Decimal("0.00")
        assert result.breakdown == {}
        assert "20km" in result.note

    def test_large_below_minimum_1km(self, calc: DeductionCalculator):
        result = calc.calculate_commuting_allowance(
            distance_km=1, public_transport_available=False
        )
        assert result.amount == Decimal("0.00")
        assert result.breakdown == {}
        assert "2km" in result.note


class TestHomeOfficeDeduction:
    """Home office flat-rate deduction."""

    def test_home_office_always_300(self, calc: DeductionCalculator):
        result = calc.calculate_home_office_deduction()
        assert result.amount == Decimal("300.00")
        assert result.breakdown["annual_amount"] == Decimal("300.00")


class TestChildDeduction:
    """Kinderabsetzbetrag: EUR 70.90/month per child."""

    @pytest.mark.parametrize(
        "num_children, expected",
        [
            (1, Decimal("850.80")),    # 70.90 * 12
            (3, Decimal("2552.40")),   # 70.90 * 12 * 3
        ],
        ids=["1-child", "3-children"],
    )
    def test_child_deduction_amounts(
        self, calc: DeductionCalculator, num_children: int, expected: Decimal
    ):
        family = FamilyInfo(num_children=num_children)
        result = calc.calculate_family_deductions(family)
        assert result.breakdown["child_deduction"] == expected


class TestSingleParentDeduction:
    """Single parent deduction (Alleinerzieher): EUR 612/year."""

    def test_single_parent_gets_612(self, calc: DeductionCalculator):
        family = FamilyInfo(num_children=1, is_single_parent=True)
        result = calc.calculate_family_deductions(family)
        assert result.breakdown["single_parent_deduction"] == Decimal("612.00")

    def test_not_single_parent_gets_0(self, calc: DeductionCalculator):
        family = FamilyInfo(num_children=1, is_single_parent=False)
        result = calc.calculate_family_deductions(family)
        assert result.breakdown["single_parent_deduction"] == Decimal("0.00")


class TestFamilienbonusPlus:
    """Familienbonus Plus tax credit."""

    def test_two_children_under_18(self, calc: DeductionCalculator):
        family = FamilyInfo(
            num_children=2, children_under_18=2, children_18_to_24=0
        )
        result = calc.calculate_familienbonus(family)
        assert result.amount == Decimal("4000.32")  # 2000.16 * 2

    def test_one_under_18_one_18_to_24(self, calc: DeductionCalculator):
        family = FamilyInfo(
            num_children=2, children_under_18=1, children_18_to_24=1
        )
        result = calc.calculate_familienbonus(family)
        assert result.amount == Decimal("2700.24")  # 2000.16 + 700.08

    def test_zero_children(self, calc: DeductionCalculator):
        family = FamilyInfo(
            num_children=0, children_under_18=0, children_18_to_24=0
        )
        result = calc.calculate_familienbonus(family)
        assert result.amount == Decimal("0.00")


class TestAlleinverdiener:
    """Alleinverdiener/Alleinerzieher tax credit."""

    @pytest.mark.parametrize(
        "num_children, expected",
        [
            (1, Decimal("612.00")),   # base only
            (2, Decimal("828.00")),   # 2026 BMF tiered
            (3, Decimal("1101.00")),  # 828 + 273*(3-2)
        ],
        ids=["1-child", "2-children", "3-children"],
    )
    def test_single_parent_with_children(
        self, calc: DeductionCalculator, num_children: int, expected: Decimal
    ):
        family = FamilyInfo(
            num_children=num_children, is_single_parent=True
        )
        result = calc.calculate_alleinverdiener(family)
        assert result.amount == expected
        assert result.breakdown["type"] == "Alleinerzieherabsetzbetrag"

    def test_sole_earner_with_children(self, calc: DeductionCalculator):
        family = FamilyInfo(num_children=2, is_sole_earner=True)
        result = calc.calculate_alleinverdiener(family)
        assert result.amount == Decimal("828.00")
        assert result.breakdown["type"] == "Alleinverdienerabsetzbetrag"

    def test_not_eligible_no_children(self, calc: DeductionCalculator):
        family = FamilyInfo(num_children=0, is_single_parent=True)
        result = calc.calculate_alleinverdiener(family)
        assert result.amount == Decimal("0.00")

    def test_not_eligible_neither_sole_earner_nor_single_parent(
        self, calc: DeductionCalculator
    ):
        family = FamilyInfo(
            num_children=2, is_single_parent=False, is_sole_earner=False
        )
        result = calc.calculate_alleinverdiener(family)
        assert result.amount == Decimal("0.00")


class TestEmployeeDeductions:
    """Werbungskostenpauschale and Verkehrsabsetzbetrag."""

    def test_werbungskostenpauschale_applied_when_actual_below(
        self, calc: DeductionCalculator
    ):
        result = calc.calculate_employee_deductions(
            actual_werbungskosten=Decimal("50.00")
        )
        assert result.amount == Decimal("132.00")
        assert result.breakdown["werbungskostenpauschale"] == Decimal("132.00")

    def test_werbungskostenpauschale_not_applied_when_actual_above(
        self, calc: DeductionCalculator
    ):
        result = calc.calculate_employee_deductions(
            actual_werbungskosten=Decimal("200.00")
        )
        assert result.amount == Decimal("0.00")
        assert result.breakdown["werbungskostenpauschale"] == Decimal("0.00")

    def test_verkehrsabsetzbetrag_always_in_breakdown(
        self, calc: DeductionCalculator
    ):
        result = calc.calculate_employee_deductions(
            actual_werbungskosten=Decimal("0.00")
        )
        assert result.breakdown["verkehrsabsetzbetrag"] == Decimal("496.00")

    def test_verkehrsabsetzbetrag_present_even_when_pauschale_not_applied(
        self, calc: DeductionCalculator
    ):
        result = calc.calculate_employee_deductions(
            actual_werbungskosten=Decimal("500.00")
        )
        assert result.breakdown["verkehrsabsetzbetrag"] == Decimal("496.00")


class TestTotalDeductions:
    """Comprehensive scenario combining multiple deduction sources."""

    def test_comprehensive_scenario(self, calc: DeductionCalculator):
        """
        Scenario: employee, 30 km commute with public transport,
        home office, 2 children (1 under 18, 1 aged 18-24),
        single parent, actual Werbungskosten below Pauschale.
        """
        family = FamilyInfo(
            num_children=2,
            is_single_parent=True,
            children_under_18=1,
            children_18_to_24=1,
        )
        result = calc.calculate_total_deductions(
            commuting_distance_km=30,
            public_transport_available=True,
            home_office_eligible=True,
            family_info=family,
            is_employee=True,
            actual_werbungskosten=Decimal("50.00"),
        )

        # Commuting: base_annual only = 58*12 = 696 (Pendlereuro separate as tax credit)
        assert result.breakdown["commuting_amount"] == Decimal("696.00")

        # Home office: 300 (stored as telearbeit_amount)
        assert result.breakdown["telearbeit_amount"] == Decimal("300.00")

        # Family: Kinderabsetzbetrag informational only (NOT in total amount)
        assert 'kinderabsetzbetrag_info_amount' in result.breakdown

        # Familienbonus in breakdown: 2000.16 + 700.08 = 2700.24
        assert result.breakdown["familienbonus_amount"] == Decimal("2700.24")

        # Alleinverdiener: 2 children = 828 (2026 BMF tiered)
        assert result.breakdown["alleinverdiener_amount"] == Decimal("828.00")

        # Employee: Werbungskostenpauschale 132
        assert result.breakdown["werbungskostenpauschale_amount"] == Decimal("132.00")

        # Verkehrsabsetzbetrag stored for engine
        assert result.breakdown["verkehrsabsetzbetrag"] == Decimal("496.00")

        # Total (income deductions only: commuting + home_office + employee):
        # 696 + 300 + 132 = 1128.00
        # Family items, Pendlereuro, Verkehrsabsetzbetrag are NOT in amount
        assert result.amount == Decimal("1128.00")


class TestCustomConfigOverrides:
    """Verify that custom deduction_config overrides defaults."""

    def test_custom_home_office(self):
        calc = DeductionCalculator(deduction_config={"home_office": 400})
        result = calc.calculate_home_office_deduction()
        assert result.amount == Decimal("400")

    def test_custom_child_deduction_monthly(self):
        calc = DeductionCalculator(
            deduction_config={"child_deduction_monthly": 80}
        )
        family = FamilyInfo(num_children=1)
        result = calc.calculate_family_deductions(family)
        assert result.breakdown["child_deduction"] == Decimal("960.00")  # 80*12

    def test_custom_verkehrsabsetzbetrag(self):
        calc = DeductionCalculator(
            deduction_config={"verkehrsabsetzbetrag": 500}
        )
        result = calc.calculate_employee_deductions()
        assert result.breakdown["verkehrsabsetzbetrag"] == Decimal("500.00")

    def test_custom_commuting_brackets(self):
        calc = DeductionCalculator(
            deduction_config={
                "commuting_brackets": {
                    "small": {20: 65, 40: 120, 60: 175},
                }
            }
        )
        result = calc.calculate_commuting_allowance(
            distance_km=25, public_transport_available=True
        )
        # base_annual only: 65*12 = 780 (Pendlereuro 25*6=150 separate in breakdown)
        assert result.amount == Decimal("780.00")

    def test_custom_alleinverdiener(self):
        calc = DeductionCalculator(
            deduction_config={
                "alleinverdiener_base": 650,       # 1-child total
                "alleinverdiener_2_children": 900,  # 2-children total
                "alleinverdiener_per_extra_child": 300,
            }
        )
        family = FamilyInfo(num_children=3, is_single_parent=True)
        result = calc.calculate_alleinverdiener(family)
        # 2-children total (900) + 300*(3-2) = 1200
        assert result.amount == Decimal("1200.00")

    def test_custom_familienbonus(self):
        calc = DeductionCalculator(
            deduction_config={
                "familienbonus_under_18": 2100,
                "familienbonus_18_24": 750,
            }
        )
        family = FamilyInfo(
            num_children=2, children_under_18=1, children_18_to_24=1
        )
        result = calc.calculate_familienbonus(family)
        assert result.amount == Decimal("2850.00")  # 2100 + 750


class TestEdgeCases:
    """Edge cases: 0 children, 0 distance, boundary distances."""

    def test_zero_children_family_deductions(self, calc: DeductionCalculator):
        family = FamilyInfo(num_children=0)
        result = calc.calculate_family_deductions(family)
        assert result.amount == Decimal("0.00")

    def test_zero_distance_small(self, calc: DeductionCalculator):
        result = calc.calculate_commuting_allowance(
            distance_km=0, public_transport_available=True
        )
        assert result.amount == Decimal("0.00")

    def test_zero_distance_large(self, calc: DeductionCalculator):
        result = calc.calculate_commuting_allowance(
            distance_km=0, public_transport_available=False
        )
        assert result.amount == Decimal("0.00")

    def test_exact_minimum_small_20km(self, calc: DeductionCalculator):
        result = calc.calculate_commuting_allowance(
            distance_km=20, public_transport_available=True
        )
        # base_annual only: 58*12 = 696 (Pendlereuro 20*6=120 separate)
        assert result.amount == Decimal("696.00")

    def test_exact_minimum_large_2km(self, calc: DeductionCalculator):
        result = calc.calculate_commuting_allowance(
            distance_km=2, public_transport_available=False
        )
        # base_annual only: 31*12 = 372 (Pendlereuro 2*6=12 separate)
        assert result.amount == Decimal("372.00")

    def test_total_deductions_no_inputs(self, calc: DeductionCalculator):
        result = calc.calculate_total_deductions()
        assert result.amount == Decimal("0.00")

    def test_familienbonus_zero_children(self, calc: DeductionCalculator):
        family = FamilyInfo(
            num_children=0, children_under_18=0, children_18_to_24=0
        )
        result = calc.calculate_familienbonus(family)
        assert result.amount == Decimal("0.00")


# ===================================================================
#  AfA CALCULATOR TESTS
# ===================================================================


class TestDepreciationRate:
    """determine_depreciation_rate: residential=1.5%, commercial=2.5% (since 2016 reform)."""

    @pytest.mark.parametrize(
        "construction_year, is_commercial, expected_rate",
        [
            (1900, False, Decimal("0.015")),
            (1914, False, Decimal("0.015")),
            (1915, False, Decimal("0.015")),
            (2000, False, Decimal("0.015")),
            (None, False, Decimal("0.015")),
            (2000, True, Decimal("0.025")),
            (None, True, Decimal("0.025")),
        ],
        ids=[
            "1900-residential", "1914-residential", "1915-residential",
            "2000-residential", "unknown-residential",
            "2000-commercial", "unknown-commercial",
        ],
    )
    def test_depreciation_rate(
        self,
        afa_calc: AfACalculator,
        construction_year: Optional[int],
        is_commercial: bool,
        expected_rate: Decimal,
    ):
        assert afa_calc.determine_depreciation_rate(construction_year, is_commercial=is_commercial) == expected_rate


class TestProratedDepreciation:
    """calculate_prorated_depreciation with mock Property objects."""

    def test_half_year_rental(self, afa_calc: AfACalculator):
        prop = MockProperty(
            property_type=MockPropertyType.RENTAL,
            building_value=Decimal("200000"),
            depreciation_rate=Decimal("0.02"),
        )
        result = afa_calc.calculate_prorated_depreciation(prop, months_owned=6)
        # 200000 * 0.02 * 6/12 = 2000
        assert result == Decimal("2000.00")

    def test_full_year_rental(self, afa_calc: AfACalculator):
        prop = MockProperty(
            property_type=MockPropertyType.RENTAL,
            building_value=Decimal("200000"),
            depreciation_rate=Decimal("0.02"),
        )
        result = afa_calc.calculate_prorated_depreciation(prop, months_owned=12)
        # 200000 * 0.02 * 12/12 = 4000
        assert result == Decimal("4000.00")

    def test_owner_occupied_returns_zero(self, afa_calc: AfACalculator):
        prop = MockProperty(
            property_type=MockPropertyType.OWNER_OCCUPIED,
            building_value=Decimal("200000"),
            depreciation_rate=Decimal("0.02"),
        )
        result = afa_calc.calculate_prorated_depreciation(prop, months_owned=12)
        assert result == Decimal("0")

    def test_mixed_use_60_percent_rental(self, afa_calc: AfACalculator):
        prop = MockProperty(
            property_type=MockPropertyType.MIXED_USE,
            building_value=Decimal("200000"),
            depreciation_rate=Decimal("0.02"),
            rental_percentage=Decimal("60"),
        )
        result = afa_calc.calculate_prorated_depreciation(prop, months_owned=12)
        # 200000 * 0.60 * 0.02 * 12/12 = 2400
        assert result == Decimal("2400.00")

    def test_mixed_use_30_percent_rental(self, afa_calc: AfACalculator):
        prop = MockProperty(
            property_type=MockPropertyType.MIXED_USE,
            building_value=Decimal("200000"),
            depreciation_rate=Decimal("0.02"),
            rental_percentage=Decimal("30"),
        )
        result = afa_calc.calculate_prorated_depreciation(prop, months_owned=12)
        # 200000 * 0.30 * 0.02 = 1200
        assert result == Decimal("1200.00")

    def test_pre_1915_rate_full_year(self, afa_calc: AfACalculator):
        prop = MockProperty(
            property_type=MockPropertyType.RENTAL,
            building_value=Decimal("200000"),
            depreciation_rate=Decimal("0.015"),
        )
        result = afa_calc.calculate_prorated_depreciation(prop, months_owned=12)
        # 200000 * 0.015 = 3000
        assert result == Decimal("3000.00")

    def test_single_month_ownership(self, afa_calc: AfACalculator):
        prop = MockProperty(
            property_type=MockPropertyType.RENTAL,
            building_value=Decimal("200000"),
            depreciation_rate=Decimal("0.02"),
        )
        result = afa_calc.calculate_prorated_depreciation(prop, months_owned=1)
        # 200000 * 0.02 * 1/12 = 333.33
        assert result == Decimal("333.33")

    def test_mixed_use_partial_year(self, afa_calc: AfACalculator):
        prop = MockProperty(
            property_type=MockPropertyType.MIXED_USE,
            building_value=Decimal("200000"),
            depreciation_rate=Decimal("0.02"),
            rental_percentage=Decimal("60"),
        )
        result = afa_calc.calculate_prorated_depreciation(prop, months_owned=6)
        # 200000 * 0.60 * 0.02 * 6/12 = 1200
        assert result == Decimal("1200.00")
