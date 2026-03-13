"""Unit tests for DeductionCalculator"""
import pytest
from decimal import Decimal
from backend.app.services.deduction_calculator import (
    DeductionCalculator,
    FamilyInfo,
    DeductionResult
)


class TestCommutingAllowance:
    """Tests for commuting allowance calculation"""
    def test_distance_below_20km_kleines_not_eligible(self):
        """Test that distances below 20km are not eligible for Kleines Pendlerpauschale"""
        calculator = DeductionCalculator()
        result = calculator.calculate_commuting_allowance(
            distance_km=15,
            public_transport_available=True
        )

        assert result.amount == Decimal('0.00')
        assert "not eligible" in result.note.lower()

    def test_distance_below_2km_grosses_not_eligible(self):
        """Test that distances below 2km are not eligible for Großes Pendlerpauschale"""
        calculator = DeductionCalculator()
        result = calculator.calculate_commuting_allowance(
            distance_km=1,
            public_transport_available=False
        )

        assert result.amount == Decimal('0.00')
        assert "not eligible" in result.note.lower()

    def test_large_allowance_2_to_20km(self):
        """Test large commuting allowance for 2-20km without public transport"""
        calculator = DeductionCalculator()
        result = calculator.calculate_commuting_allowance(
            distance_km=10,
            public_transport_available=False
        )

        # Base: €31/month * 12 = €372
        # Pendlereuro: 10km * €6 = €60
        # Total: €432
        expected_base = Decimal('31.00') * Decimal('12')
        expected_pendler = Decimal('10') * Decimal('6.00')
        expected_total = expected_base + expected_pendler

        assert result.amount == expected_total
        assert result.breakdown['type'] == 'Großes Pendlerpauschale'
        assert result.breakdown['base_monthly'] == Decimal('31.00')
        assert result.breakdown['distance_bracket'] == '2-20km'
        assert result.breakdown['public_transport_available'] is False

    def test_small_allowance_20_to_40km(self):
        """Test small commuting allowance for 20-40km with public transport"""
        calculator = DeductionCalculator()
        result = calculator.calculate_commuting_allowance(
            distance_km=25,
            public_transport_available=True
        )

        # Base: €58/month * 12 = €696
        # Pendlereuro: 25km * €6 = €150
        # Total: €846
        expected_base = Decimal('58.00') * Decimal('12')
        expected_pendler = Decimal('25') * Decimal('6.00')
        expected_total = expected_base + expected_pendler

        assert result.amount == expected_total
        assert result.breakdown['type'] == 'Kleines Pendlerpauschale'
        assert result.breakdown['distance_km'] == 25
        assert result.breakdown['base_monthly'] == Decimal('58.00')
        assert result.breakdown['pendler_euro'] == Decimal('150.00')

    def test_small_allowance_40_to_60km(self):
        """Test small commuting allowance for 40-60km with public transport"""
        calculator = DeductionCalculator()
        result = calculator.calculate_commuting_allowance(
            distance_km=50,
            public_transport_available=True
        )

        # Base: €113/month * 12 = €1,356
        # Pendlereuro: 50km * €6 = €300
        # Total: €1,656
        expected_base = Decimal('113.00') * Decimal('12')
        expected_pendler = Decimal('50') * Decimal('6.00')
        expected_total = expected_base + expected_pendler

        assert result.amount == expected_total
        assert result.breakdown['base_monthly'] == Decimal('113.00')
        assert result.breakdown['distance_bracket'] == '40-60km'

    def test_small_allowance_above_60km(self):
        """Test small commuting allowance for 60km+ with public transport"""
        calculator = DeductionCalculator()
        result = calculator.calculate_commuting_allowance(
            distance_km=75,
            public_transport_available=True
        )

        # Base: €168/month * 12 = €2,016
        # Pendlereuro: 75km * €6 = €450
        # Total: €2,466
        expected_base = Decimal('168.00') * Decimal('12')
        expected_pendler = Decimal('75') * Decimal('6.00')
        expected_total = expected_base + expected_pendler

        assert result.amount == expected_total
        assert result.breakdown['base_monthly'] == Decimal('168.00')
        assert result.breakdown['distance_bracket'] == '60km+'

    def test_large_allowance_20_to_40km(self):
        """Test large commuting allowance for 20-40km without public transport"""
        calculator = DeductionCalculator()
        result = calculator.calculate_commuting_allowance(
            distance_km=30,
            public_transport_available=False
        )

        # Base: €123/month * 12 = €1,476
        # Pendlereuro: 30km * €6 = €180
        # Total: €1,656
        expected_base = Decimal('123.00') * Decimal('12')
        expected_pendler = Decimal('30') * Decimal('6.00')
        expected_total = expected_base + expected_pendler

        assert result.amount == expected_total
        assert result.breakdown['type'] == 'Großes Pendlerpauschale'
        assert result.breakdown['base_monthly'] == Decimal('123.00')
        assert result.breakdown['distance_bracket'] == '20-40km'
        assert result.breakdown['public_transport_available'] is False

    def test_large_allowance_40_to_60km(self):
        """Test large commuting allowance for 40-60km without public transport"""
        calculator = DeductionCalculator()
        result = calculator.calculate_commuting_allowance(
            distance_km=45,
            public_transport_available=False
        )

        # Base: €214/month * 12 = €2,568
        # Pendlereuro: 45km * €6 = €270
        # Total: €2,838
        expected_base = Decimal('214.00') * Decimal('12')
        expected_pendler = Decimal('45') * Decimal('6.00')
        expected_total = expected_base + expected_pendler

        assert result.amount == expected_total
        assert result.breakdown['base_monthly'] == Decimal('214.00')
        assert result.breakdown['distance_bracket'] == '40-60km'

    def test_large_allowance_above_60km(self):
        """Test large commuting allowance for 60km+ without public transport"""
        calculator = DeductionCalculator()
        result = calculator.calculate_commuting_allowance(
            distance_km=80,
            public_transport_available=False
        )

        # Base: €306/month * 12 = €3,672
        # Pendlereuro: 80km * €6 = €480
        # Total: €4,152
        expected_base = Decimal('306.00') * Decimal('12')
        expected_pendler = Decimal('80') * Decimal('6.00')
        expected_total = expected_base + expected_pendler

        assert result.amount == expected_total
        assert result.breakdown['base_monthly'] == Decimal('306.00')
        assert result.breakdown['distance_bracket'] == '60km+'

    def test_exact_boundary_20km(self):
        """Test exact boundary at 20km"""
        calculator = DeductionCalculator()
        result = calculator.calculate_commuting_allowance(
            distance_km=20,
            public_transport_available=True
        )

        # Should be eligible at exactly 20km
        assert result.amount > Decimal('0.00')
        assert result.breakdown['distance_bracket'] == '20-40km'

    def test_exact_boundary_40km(self):
        """Test exact boundary at 40km"""
        calculator = DeductionCalculator()
        result = calculator.calculate_commuting_allowance(
            distance_km=40,
            public_transport_available=True
        )

        # Should use 40-60km bracket
        assert result.breakdown['distance_bracket'] == '40-60km'
        assert result.breakdown['base_monthly'] == Decimal('113.00')

    def test_exact_boundary_60km(self):
        """Test exact boundary at 60km"""
        calculator = DeductionCalculator()
        result = calculator.calculate_commuting_allowance(
            distance_km=60,
            public_transport_available=True
        )

        # Should use 60km+ bracket
        assert result.breakdown['distance_bracket'] == '60km+'
        assert result.breakdown['base_monthly'] == Decimal('168.00')


class TestHomeOfficeDeduction:
    """Tests for home office deduction"""

    def test_home_office_flat_rate(self):
        """Test home office deduction returns €300 flat rate"""
        calculator = DeductionCalculator()
        result = calculator.calculate_home_office_deduction()

        assert result.amount == Decimal('300.00')
        assert result.breakdown['type'] == 'Home Office Deduction'
        assert result.breakdown['annual_amount'] == Decimal('300.00')
        assert '€300' in result.note


class TestFamilyDeductions:
    """Tests for family deductions"""

    def test_no_children_no_single_parent(self):
        """Test family deduction with no children and not single parent"""
        calculator = DeductionCalculator()
        family_info = FamilyInfo(num_children=0, is_single_parent=False)
        result = calculator.calculate_family_deductions(family_info)

        assert result.amount == Decimal('0.00')
        assert result.breakdown['num_children'] == 0
        assert result.breakdown['is_single_parent'] is False

    def test_one_child_not_single_parent(self):
        """Test family deduction with one child, not single parent"""
        calculator = DeductionCalculator()
        family_info = FamilyInfo(num_children=1, is_single_parent=False)
        result = calculator.calculate_family_deductions(family_info)

        # €70.90/month * 12 months = €850.80
        expected = Decimal('70.90') * Decimal('12')

        assert result.amount == expected
        assert result.breakdown['child_deduction'] == expected
        assert result.breakdown['single_parent_deduction'] == Decimal('0.00')

    def test_two_children_not_single_parent(self):
        """Test family deduction with two children, not single parent"""
        calculator = DeductionCalculator()
        family_info = FamilyInfo(num_children=2, is_single_parent=False)
        result = calculator.calculate_family_deductions(family_info)

        # €70.90/month * 12 months * 2 children = €1,701.60
        expected = Decimal('70.90') * Decimal('12') * Decimal('2')

        assert result.amount == expected
        assert result.breakdown['num_children'] == 2

    def test_one_child_single_parent(self):
        """Test family deduction with one child and single parent"""
        calculator = DeductionCalculator()
        family_info = FamilyInfo(num_children=1, is_single_parent=True)
        result = calculator.calculate_family_deductions(family_info)

        # Child: €70.90/month * 12 = €850.80
        # Single parent: €612.00
        child_deduction = Decimal('70.90') * Decimal('12')
        single_parent_deduction = Decimal('612.00')
        expected = child_deduction + single_parent_deduction

        assert result.amount == expected
        assert result.breakdown['child_deduction'] == child_deduction
        assert result.breakdown['single_parent_deduction'] == single_parent_deduction
        assert result.breakdown['is_single_parent'] is True

    def test_three_children_single_parent(self):
        """Test family deduction with three children and single parent"""
        calculator = DeductionCalculator()
        family_info = FamilyInfo(num_children=3, is_single_parent=True)
        result = calculator.calculate_family_deductions(family_info)

        # Child: €70.90/month * 12 * 3 = €2,552.40
        # Single parent: €612.00
        child_deduction = Decimal('70.90') * Decimal('12') * Decimal('3')
        single_parent_deduction = Decimal('612.00')
        expected = child_deduction + single_parent_deduction

        assert result.amount == expected
        assert result.breakdown['num_children'] == 3


class TestSingleParentDeduction:
    """Tests for single parent deduction"""

    def test_single_parent_deduction(self):
        """Test single parent deduction returns €612 (2026)"""
        calculator = DeductionCalculator()
        result = calculator.calculate_single_parent_deduction()

        assert result.amount == Decimal('612.00')
        assert result.breakdown['annual_amount'] == Decimal('612.00')
        assert '612' in result.note


class TestTotalDeductions:
    """Tests for total deductions calculation"""

    def test_no_deductions(self):
        """Test total deductions with no eligible deductions"""
        calculator = DeductionCalculator()
        result = calculator.calculate_total_deductions()

        assert result.amount == Decimal('0.00')
        assert len(result.breakdown) == 0

    def test_only_commuting(self):
        """Test total deductions with only commuting allowance"""
        calculator = DeductionCalculator()
        result = calculator.calculate_total_deductions(
            commuting_distance_km=30,
            public_transport_available=True
        )

        # Should match commuting allowance calculation
        expected = Decimal('58.00') * Decimal('12') + Decimal('30') * Decimal('6.00')

        assert result.amount == expected
        assert 'commuting_allowance' in result.breakdown
        assert 'home_office' not in result.breakdown
        assert 'family_deductions' not in result.breakdown

    def test_only_home_office(self):
        """Test total deductions with only home office"""
        calculator = DeductionCalculator()
        result = calculator.calculate_total_deductions(
            home_office_eligible=True
        )

        assert result.amount == Decimal('300.00')
        assert 'home_office' in result.breakdown

    def test_only_family(self):
        """Test total deductions with only family deductions"""
        calculator = DeductionCalculator()
        family_info = FamilyInfo(num_children=2, is_single_parent=True)
        result = calculator.calculate_total_deductions(
            family_info=family_info
        )

        # 2 children + single parent
        expected = Decimal('70.90') * Decimal('12') * Decimal('2') + Decimal('612.00')

        assert result.amount == expected
        assert 'family_deductions' in result.breakdown

    def test_all_deductions_combined(self):
        """Test total deductions with all types combined"""
        calculator = DeductionCalculator()
        family_info = FamilyInfo(num_children=2, is_single_parent=True)
        result = calculator.calculate_total_deductions(
            commuting_distance_km=50,
            public_transport_available=False,
            home_office_eligible=True,
            family_info=family_info
        )

        # Commuting: €214/month * 12 + 50km * €6 = €2,568 + €300 = €2,868
        # Home office: €300
        # Family: €70.90 * 12 * 2 + €612 = €1,701.60 + €612 = €2,313.60
        commuting = Decimal('214.00') * Decimal('12') + Decimal('50') * Decimal('6.00')
        home_office = Decimal('300.00')
        family = Decimal('70.90') * Decimal('12') * Decimal('2') + Decimal('612.00')
        expected = commuting + home_office + family

        assert result.amount == expected
        assert 'commuting_allowance' in result.breakdown
        assert 'home_office' in result.breakdown
        assert 'family_deductions' in result.breakdown
        assert result.breakdown['commuting_amount'] == commuting
        assert result.breakdown['home_office_amount'] == home_office
        assert result.breakdown['family_amount'] == family

    def test_commuting_below_threshold_excluded(self):
        """Test that commuting below 20km is excluded from total"""
        calculator = DeductionCalculator()
        result = calculator.calculate_total_deductions(
            commuting_distance_km=15,
            public_transport_available=True,
            home_office_eligible=True
        )

        # Only home office should be included
        assert result.amount == Decimal('300.00')
        assert 'commuting_allowance' not in result.breakdown


class TestDeductionResultStructure:
    """Tests for DeductionResult data structure"""

    def test_result_has_required_fields(self):
        """Test that DeductionResult has all required fields"""
        calculator = DeductionCalculator()
        result = calculator.calculate_home_office_deduction()

        assert hasattr(result, 'amount')
        assert hasattr(result, 'breakdown')
        assert hasattr(result, 'note')
        assert isinstance(result.amount, Decimal)
        assert isinstance(result.breakdown, dict)

    def test_amount_precision(self):
        """Test that all amounts are rounded to 2 decimal places"""
        calculator = DeductionCalculator()

        # Test commuting
        commuting = calculator.calculate_commuting_allowance(25, True)
        assert commuting.amount == commuting.amount.quantize(Decimal('0.01'))

        # Test home office
        home_office = calculator.calculate_home_office_deduction()
        assert home_office.amount == home_office.amount.quantize(Decimal('0.01'))

        # Test family
        family_info = FamilyInfo(num_children=1, is_single_parent=True)
        family = calculator.calculate_family_deductions(family_info)
        assert family.amount == family.amount.quantize(Decimal('0.01'))


class TestEdgeCases:
    """Tests for edge cases and boundary conditions"""

    def test_zero_children(self):
        """Test family deduction with zero children"""
        calculator = DeductionCalculator()
        family_info = FamilyInfo(num_children=0, is_single_parent=False)
        result = calculator.calculate_family_deductions(family_info)

        assert result.amount == Decimal('0.00')

    def test_large_number_of_children(self):
        """Test family deduction with many children"""
        calculator = DeductionCalculator()
        family_info = FamilyInfo(num_children=5, is_single_parent=False)
        result = calculator.calculate_family_deductions(family_info)

        expected = Decimal('70.90') * Decimal('12') * Decimal('5')
        assert result.amount == expected

    def test_very_long_commute(self):
        """Test commuting allowance with very long distance"""
        calculator = DeductionCalculator()
        result = calculator.calculate_commuting_allowance(
            distance_km=150,
            public_transport_available=False
        )

        # Base: €306/month * 12 = €3,672
        # Pendlereuro: 150km * €6 = €900
        # Total: €4,572
        expected = Decimal('306.00') * Decimal('12') + Decimal('150') * Decimal('6.00')

        assert result.amount == expected


# ============================================================================
# PROPERTY-BASED TESTS FOR COMMUTING ALLOWANCE
# ============================================================================
# Property 12: Commuting allowance calculation correctness
# Validates: Requirements 29.2
# ============================================================================

from hypothesis import given, strategies as st, assume
from hypothesis import settings


class TestCommutingAllowanceProperties:
    """
    Property-based tests for commuting allowance calculation.

    These tests validate the correctness properties of the Pendlerpauschale
    calculation according to Austrian tax law (Requirement 29.2).
    """

    @given(
        distance_km=st.integers(min_value=0, max_value=200),
        public_transport_available=st.booleans()
    )
    @settings(max_examples=50)
    def test_property_non_negative_result(self, distance_km, public_transport_available):
        """
        Property: Commuting allowance result is always non-negative.

        For any valid input, the calculated allowance must be >= 0.
        """
        calculator = DeductionCalculator()
        result = calculator.calculate_commuting_allowance(
            distance_km=distance_km,
            public_transport_available=public_transport_available
        )

        assert result.amount >= Decimal('0.00'), \
            f"Allowance must be non-negative, got {result.amount} for {distance_km}km"

    @given(
        distance_km=st.integers(min_value=0, max_value=19)
    )
    @settings(max_examples=25)
    def test_property_below_20km_kleines_returns_zero(self, distance_km):
        """
        Property: Distances below 20km always return zero for Kleines Pendlerpauschale.

        Austrian tax law requires minimum 20km distance for Kleines Pendlerpauschale.
        """
        calculator = DeductionCalculator()

        result = calculator.calculate_commuting_allowance(
            distance_km=distance_km,
            public_transport_available=True
        )

        assert result.amount == Decimal('0.00'), \
            f"Distance {distance_km}km should return €0 for Kleines, got {result.amount}"
        assert result.note is not None, \
            "Should provide explanation for zero allowance"

    @given(
        distance_km=st.integers(min_value=0, max_value=1)
    )
    @settings(max_examples=10)
    def test_property_below_2km_grosses_returns_zero(self, distance_km):
        """
        Property: Distances below 2km always return zero for Großes Pendlerpauschale.

        Austrian tax law requires minimum 2km distance for Großes Pendlerpauschale.
        """
        calculator = DeductionCalculator()

        result = calculator.calculate_commuting_allowance(
            distance_km=distance_km,
            public_transport_available=False
        )

        assert result.amount == Decimal('0.00'), \
            f"Distance {distance_km}km should return €0 for Großes, got {result.amount}"
        assert result.note is not None, \
            "Should provide explanation for zero allowance"

    @given(
        distance_km=st.integers(min_value=2, max_value=19)
    )
    @settings(max_examples=25)
    def test_property_2_to_19km_grosses_returns_positive(self, distance_km):
        """
        Property: Distances 2-19km return positive for Großes Pendlerpauschale.

        The 2-20km bracket (€31/month) applies when no public transport is available.
        """
        calculator = DeductionCalculator()

        result = calculator.calculate_commuting_allowance(
            distance_km=distance_km,
            public_transport_available=False
        )

        assert result.amount > Decimal('0.00'), \
            f"Distance {distance_km}km should return positive for Großes, got {result.amount}"
        assert result.breakdown['base_monthly'] == Decimal('31.00')
        assert result.breakdown['distance_bracket'] == '2-20km'

    @given(
        distance_km=st.integers(min_value=20, max_value=200)
    )
    @settings(max_examples=50)
    def test_property_above_20km_returns_positive(self, distance_km):
        """
        Property: Distances >= 20km always return positive allowance.

        Any distance meeting the minimum threshold should receive some allowance.
        """
        calculator = DeductionCalculator()

        # Test both public transport scenarios
        for public_transport in [True, False]:
            result = calculator.calculate_commuting_allowance(
                distance_km=distance_km,
                public_transport_available=public_transport
            )

            assert result.amount > Decimal('0.00'), \
                f"Distance {distance_km}km should return positive allowance, got {result.amount}"

    @given(
        distance_km=st.integers(min_value=20, max_value=200)
    )
    @settings(max_examples=50)
    def test_property_monotonicity_with_distance(self, distance_km):
        """
        Property: Allowance increases monotonically with distance.

        For any distance d1 < d2, allowance(d1) <= allowance(d2).
        This holds because Pendlereuro increases linearly with distance.
        """
        calculator = DeductionCalculator()

        # Test both public transport scenarios
        for public_transport in [True, False]:
            result1 = calculator.calculate_commuting_allowance(
                distance_km=distance_km,
                public_transport_available=public_transport
            )

            # Test with a slightly larger distance
            if distance_km < 200:
                result2 = calculator.calculate_commuting_allowance(
                    distance_km=distance_km + 1,
                    public_transport_available=public_transport
                )

                assert result2.amount >= result1.amount, \
                    f"Allowance should increase with distance: " \
                    f"{distance_km}km={result1.amount} vs {distance_km+1}km={result2.amount}"

    @given(
        distance_km=st.integers(min_value=20, max_value=200)
    )
    @settings(max_examples=50)
    def test_property_pendlereuro_component(self, distance_km):
        """
        Property: Pendlereuro component is always distance * €6.

        The Pendlereuro is calculated as €6 per km per year, regardless of
        public transport availability or distance bracket.
        """
        calculator = DeductionCalculator()

        for public_transport in [True, False]:
            result = calculator.calculate_commuting_allowance(
                distance_km=distance_km,
                public_transport_available=public_transport
            )

            expected_pendlereuro = Decimal(str(distance_km)) * Decimal('6.00')
            actual_pendlereuro = result.breakdown['pendler_euro']

            assert actual_pendlereuro == expected_pendlereuro, \
                f"Pendlereuro should be {expected_pendlereuro}, got {actual_pendlereuro}"

    @given(
        distance_km=st.integers(min_value=20, max_value=200)
    )
    @settings(max_examples=50)
    def test_property_base_plus_pendlereuro(self, distance_km):
        """
        Property: Total allowance = base annual + Pendlereuro.

        The total allowance is always the sum of the base monthly amount
        (times 12) plus the Pendlereuro component.
        """
        calculator = DeductionCalculator()

        for public_transport in [True, False]:
            result = calculator.calculate_commuting_allowance(
                distance_km=distance_km,
                public_transport_available=public_transport
            )

            base_annual = result.breakdown['base_annual']
            pendler_euro = result.breakdown['pendler_euro']
            expected_total = base_annual + pendler_euro

            assert result.amount == expected_total.quantize(Decimal('0.01')), \
                f"Total should equal base_annual + pendler_euro: " \
                f"{result.amount} != {base_annual} + {pendler_euro}"

    @given(
        distance_km=st.integers(min_value=20, max_value=200)
    )
    @settings(max_examples=50)
    def test_property_large_allowance_greater_than_small(self, distance_km):
        """
        Property: Large allowance (no public transport) >= Small allowance for all brackets.

        With corrected Großes Pendlerpauschale values, the large allowance is always
        greater than or equal to the small allowance at every distance bracket,
        compensating for the lack of public transport.
        """
        calculator = DeductionCalculator()

        result_small = calculator.calculate_commuting_allowance(
            distance_km=distance_km,
            public_transport_available=True
        )

        result_large = calculator.calculate_commuting_allowance(
            distance_km=distance_km,
            public_transport_available=False
        )

        assert result_large.amount >= result_small.amount, \
            f"For {distance_km}km, large allowance ({result_large.amount}) should be >= " \
            f"small allowance ({result_small.amount})"

    @given(
        distance_km=st.integers(min_value=20, max_value=39)
    )
    @settings(max_examples=25)
    def test_property_bracket_20_40km(self, distance_km):
        """
        Property: Distances 20-39km use the 20-40km bracket.

        Base monthly amounts:
        - Small: €58/month
        - Large: €123/month
        """
        calculator = DeductionCalculator()

        result_small = calculator.calculate_commuting_allowance(
            distance_km=distance_km,
            public_transport_available=True
        )
        result_large = calculator.calculate_commuting_allowance(
            distance_km=distance_km,
            public_transport_available=False
        )

        assert result_small.breakdown['base_monthly'] == Decimal('58.00'), \
            f"Small allowance base should be €58 for {distance_km}km"
        assert result_large.breakdown['base_monthly'] == Decimal('123.00'), \
            f"Large allowance base should be €123 for {distance_km}km"
        assert result_small.breakdown['distance_bracket'] == '20-40km'
        assert result_large.breakdown['distance_bracket'] == '20-40km'

    @given(
        distance_km=st.integers(min_value=40, max_value=59)
    )
    @settings(max_examples=25)
    def test_property_bracket_40_60km(self, distance_km):
        """
        Property: Distances 40-59km use the 40-60km bracket.

        Base monthly amounts:
        - Small: €113/month
        - Large: €214/month
        """
        calculator = DeductionCalculator()

        result_small = calculator.calculate_commuting_allowance(
            distance_km=distance_km,
            public_transport_available=True
        )
        result_large = calculator.calculate_commuting_allowance(
            distance_km=distance_km,
            public_transport_available=False
        )

        assert result_small.breakdown['base_monthly'] == Decimal('113.00'), \
            f"Small allowance base should be €113 for {distance_km}km"
        assert result_large.breakdown['base_monthly'] == Decimal('214.00'), \
            f"Large allowance base should be €214 for {distance_km}km"
        assert result_small.breakdown['distance_bracket'] == '40-60km'
        assert result_large.breakdown['distance_bracket'] == '40-60km'

    @given(
        distance_km=st.integers(min_value=60, max_value=200)
    )
    @settings(max_examples=25)
    def test_property_bracket_60km_plus(self, distance_km):
        """
        Property: Distances 60km+ use the 60km+ bracket.

        Base monthly amounts:
        - Small: €168/month
        - Large: €306/month
        """
        calculator = DeductionCalculator()

        result_small = calculator.calculate_commuting_allowance(
            distance_km=distance_km,
            public_transport_available=True
        )
        result_large = calculator.calculate_commuting_allowance(
            distance_km=distance_km,
            public_transport_available=False
        )

        assert result_small.breakdown['base_monthly'] == Decimal('168.00'), \
            f"Small allowance base should be €168 for {distance_km}km"
        assert result_large.breakdown['base_monthly'] == Decimal('306.00'), \
            f"Large allowance base should be €306 for {distance_km}km"
        assert result_small.breakdown['distance_bracket'] == '60km+'
        assert result_large.breakdown['distance_bracket'] == '60km+'

    @given(
        distance_km=st.integers(min_value=20, max_value=200),
        public_transport_available=st.booleans()
    )
    @settings(max_examples=50)
    def test_property_result_structure_completeness(self, distance_km, public_transport_available):
        """
        Property: Result structure contains all required fields.

        Every valid calculation must return a complete DeductionResult with
        amount, breakdown, and appropriate metadata.
        """
        calculator = DeductionCalculator()
        result = calculator.calculate_commuting_allowance(
            distance_km=distance_km,
            public_transport_available=public_transport_available
        )

        # Check result structure
        assert hasattr(result, 'amount')
        assert hasattr(result, 'breakdown')
        assert isinstance(result.amount, Decimal)
        assert isinstance(result.breakdown, dict)

        # For eligible distances, check breakdown completeness
        if distance_km >= 20:
            assert 'type' in result.breakdown
            assert 'distance_km' in result.breakdown
            assert 'distance_bracket' in result.breakdown
            assert 'base_monthly' in result.breakdown
            assert 'base_annual' in result.breakdown
            assert 'pendler_euro' in result.breakdown
            assert 'public_transport_available' in result.breakdown

            # Verify breakdown values are correct types
            assert isinstance(result.breakdown['distance_km'], int)
            assert isinstance(result.breakdown['base_monthly'], Decimal)
            assert isinstance(result.breakdown['base_annual'], Decimal)
            assert isinstance(result.breakdown['pendler_euro'], Decimal)
            assert isinstance(result.breakdown['public_transport_available'], bool)

    @given(
        distance_km=st.integers(min_value=20, max_value=200),
        public_transport_available=st.booleans()
    )
    @settings(max_examples=200)
    def test_property_decimal_precision(self, distance_km, public_transport_available):
        """
        Property: All monetary amounts have exactly 2 decimal places.

        Tax calculations must be precise to the cent (€0.01).
        """
        calculator = DeductionCalculator()
        result = calculator.calculate_commuting_allowance(
            distance_km=distance_km,
            public_transport_available=public_transport_available
        )

        # Check main amount
        assert result.amount == result.amount.quantize(Decimal('0.01')), \
            f"Amount {result.amount} should have exactly 2 decimal places"

        # Check breakdown amounts
        if distance_km >= 20:
            assert result.breakdown['base_monthly'] == \
                result.breakdown['base_monthly'].quantize(Decimal('0.01'))
            assert result.breakdown['base_annual'] == \
                result.breakdown['base_annual'].quantize(Decimal('0.01'))
            assert result.breakdown['pendler_euro'] == \
                result.breakdown['pendler_euro'].quantize(Decimal('0.01'))

    @given(
        distance_km=st.integers(min_value=20, max_value=200),
        public_transport_available=st.booleans()
    )
    @settings(max_examples=200)
    def test_property_idempotence(self, distance_km, public_transport_available):
        """
        Property: Calling the function multiple times with same inputs yields same result.

        The calculation should be deterministic and stateless.
        """
        calculator = DeductionCalculator()

        result1 = calculator.calculate_commuting_allowance(
            distance_km=distance_km,
            public_transport_available=public_transport_available
        )

        result2 = calculator.calculate_commuting_allowance(
            distance_km=distance_km,
            public_transport_available=public_transport_available
        )

        assert result1.amount == result2.amount, \
            "Multiple calls with same inputs should return same amount"
        assert result1.breakdown == result2.breakdown, \
            "Multiple calls with same inputs should return same breakdown"

    @given(
        distance_km=st.integers(min_value=20, max_value=200)
    )
    @settings(max_examples=200)
    def test_property_allowance_type_consistency(self, distance_km):
        """
        Property: Allowance type matches public transport availability.

        - Public transport available → "Kleines Pendlerpauschale"
        - Public transport not available → "Großes Pendlerpauschale"
        """
        calculator = DeductionCalculator()

        result_small = calculator.calculate_commuting_allowance(
            distance_km=distance_km,
            public_transport_available=True
        )
        result_large = calculator.calculate_commuting_allowance(
            distance_km=distance_km,
            public_transport_available=False
        )

        assert result_small.breakdown['type'] == 'Kleines Pendlerpauschale', \
            "Public transport available should use Kleines Pendlerpauschale"
        assert result_large.breakdown['type'] == 'Großes Pendlerpauschale', \
            "Public transport not available should use Großes Pendlerpauschale"

        assert result_small.breakdown['public_transport_available'] is True
        assert result_large.breakdown['public_transport_available'] is False

    @given(
        distance_km=st.integers(min_value=20, max_value=200)
    )
    @settings(max_examples=100)
    def test_property_base_annual_equals_monthly_times_12(self, distance_km):
        """
        Property: Base annual amount = base monthly amount * 12.

        The annual base is always exactly 12 times the monthly base.
        """
        calculator = DeductionCalculator()

        for public_transport in [True, False]:
            result = calculator.calculate_commuting_allowance(
                distance_km=distance_km,
                public_transport_available=public_transport
            )

            expected_annual = result.breakdown['base_monthly'] * Decimal('12')
            actual_annual = result.breakdown['base_annual']

            assert actual_annual == expected_annual.quantize(Decimal('0.01')), \
                f"Base annual should be monthly * 12: {actual_annual} != {expected_annual}"

    @given(
        distance1=st.integers(min_value=20, max_value=39),
        distance2=st.integers(min_value=40, max_value=59),
        distance3=st.integers(min_value=60, max_value=200)
    )
    @settings(max_examples=25)
    def test_property_bracket_transitions(self, distance1, distance2, distance3):
        """
        Property: Allowance increases at bracket boundaries.

        When transitioning from one bracket to the next, the allowance
        should increase (due to higher base amount).
        """
        calculator = DeductionCalculator()

        for public_transport in [True, False]:
            result1 = calculator.calculate_commuting_allowance(
                distance_km=distance1,
                public_transport_available=public_transport
            )
            result2 = calculator.calculate_commuting_allowance(
                distance_km=distance2,
                public_transport_available=public_transport
            )
            result3 = calculator.calculate_commuting_allowance(
                distance_km=distance3,
                public_transport_available=public_transport
            )

            # Allowance should increase across brackets
            assert result2.amount > result1.amount, \
                f"40-60km bracket should have higher allowance than 20-40km"
            assert result3.amount > result2.amount, \
                f"60km+ bracket should have higher allowance than 40-60km"
