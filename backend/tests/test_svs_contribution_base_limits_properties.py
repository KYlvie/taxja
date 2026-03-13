"""
Property-based tests for SVS contribution base limits

**Validates: Requirements 28.4, 28.5, 28.6**

Property 10: SVS contribution base limits
- GSVG: contribution base >= €551.10/month (if annual income >= €6,613.20)
- All types: contribution base <= €8,085/month
- Contribution amount = base × dynamic rate
- GSVG returns €0 when annual income < €6,613.20
- Neue Selbständige minimum contribution €160.81/month
"""

import pytest
from hypothesis import given, strategies as st, assume, settings, HealthCheck
from decimal import Decimal
from backend.app.services.svs_calculator import SVSCalculator, UserType, SVSResult


# Custom strategies for generating test data
def decimal_strategy(min_value=0, max_value=1000000, places=2):
    """Generate Decimal values with specified precision"""
    return st.decimals(
        min_value=Decimal(str(min_value)),
        max_value=Decimal(str(max_value)),
        allow_nan=False,
        allow_infinity=False,
        places=places
    )


@pytest.fixture
def svs_calculator():
    """Create an SVS calculator instance"""
    return SVSCalculator()


class TestProperty10SVSContributionBaseLimits:
    """
    **Property 10: SVS contribution base limits**
    **Validates: Requirements 28.4, 28.5, 28.6**
    
    Tests that SVS contribution base:
    1. GSVG minimum base €551.10/month applies when income >= €6,613.20/year
    2. Maximum base €8,085/month is enforced for all types
    3. GSVG returns €0 when income < €6,613.20/year
    4. Neue Selbständige minimum contribution €160.81/month
    5. Contribution base is clamped between min and max limits
    """
    
    @given(
        annual_income=decimal_strategy(min_value=6613.20, max_value=200000)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_gsvg_minimum_base_applies_when_income_above_threshold(
        self,
        annual_income: Decimal,
        svs_calculator
    ):
        """
        Property: GSVG minimum contribution base applies when income >= €6,613.20
        
        For any annual income >= €6,613.20:
        contribution_base >= €551.10/month
        
        **Validates: Requirements 28.4**
        """
        result = svs_calculator.calculate_contributions(
            annual_income=annual_income,
            user_type=UserType.GSVG
        )
        
        # Verify minimum base is applied
        assert result.contribution_base >= Decimal('551.10'), \
            f"GSVG contribution base should be >= €551.10, got €{result.contribution_base}"
        
        # Verify result is deductible
        assert result.deductible, \
            "GSVG contributions should be deductible as Sonderausgaben"
        
        # Verify monthly total is positive
        assert result.monthly_total > Decimal('0.00'), \
            f"GSVG monthly total should be positive, got €{result.monthly_total}"
    
    @given(
        annual_income=decimal_strategy(min_value=0, max_value=6613.19)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_gsvg_returns_zero_when_income_below_threshold(
        self,
        annual_income: Decimal,
        svs_calculator
    ):
        """
        Property: GSVG returns €0 when annual income < €6,613.20
        
        For any annual income < €6,613.20:
        monthly_total = €0
        annual_total = €0
        contribution_base = €0
        
        **Validates: Requirements 28.4**
        """
        result = svs_calculator.calculate_contributions(
            annual_income=annual_income,
            user_type=UserType.GSVG
        )
        
        # Verify no contributions required
        assert result.monthly_total == Decimal('0.00'), \
            f"GSVG monthly total should be €0 for income < €6,613.20, got €{result.monthly_total}"
        
        assert result.annual_total == Decimal('0.00'), \
            f"GSVG annual total should be €0 for income < €6,613.20, got €{result.annual_total}"
        
        assert result.contribution_base == Decimal('0.00'), \
            f"GSVG contribution base should be €0 for income < €6,613.20, got €{result.contribution_base}"
        
        # Verify not deductible (no contributions)
        assert not result.deductible, \
            "GSVG contributions should not be deductible when no contributions are required"
        
        # Verify note explains why
        assert result.note is not None, \
            "Result should include a note explaining why no contributions are required"
    
    @given(
        annual_income=decimal_strategy(min_value=100000, max_value=500000)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_gsvg_maximum_base_cap_enforced(
        self,
        annual_income: Decimal,
        svs_calculator
    ):
        """
        Property: GSVG maximum contribution base is capped at €8,085/month
        
        For any annual income where monthly income > €8,085:
        contribution_base = €8,085
        
        **Validates: Requirements 28.5**
        """
        # Only test cases where monthly income exceeds maximum
        monthly_income = annual_income / Decimal('12')
        assume(monthly_income > Decimal('8085.00'))
        
        result = svs_calculator.calculate_contributions(
            annual_income=annual_income,
            user_type=UserType.GSVG
        )
        
        # Verify maximum base is enforced
        assert result.contribution_base == Decimal('8085.00'), \
            f"GSVG contribution base should be capped at €8,085, got €{result.contribution_base}"
        
        # Verify contributions are calculated based on maximum base
        expected_pension = Decimal('8085.00') * svs_calculator.PENSION_RATE
        assert result.breakdown['pension'] == expected_pension.quantize(Decimal('0.01')), \
            f"Pension should be calculated on max base, expected €{expected_pension.quantize(Decimal('0.01'))}, got €{result.breakdown['pension']}"
    
    @given(
        annual_income=decimal_strategy(min_value=6613.20, max_value=97020)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_gsvg_contribution_base_within_limits(
        self,
        annual_income: Decimal,
        svs_calculator
    ):
        """
        Property: GSVG contribution base is clamped between min and max
        
        For any valid annual income:
        €551.10 <= contribution_base <= €8,085
        
        **Validates: Requirements 28.4, 28.5**
        """
        # Only test range where monthly income is between min and max
        monthly_income = annual_income / Decimal('12')
        assume(Decimal('551.10') <= monthly_income <= Decimal('8085.00'))
        
        result = svs_calculator.calculate_contributions(
            annual_income=annual_income,
            user_type=UserType.GSVG
        )
        
        # Verify contribution base equals monthly income (within limits)
        assert result.contribution_base == monthly_income.quantize(Decimal('0.01')), \
            f"GSVG contribution base should equal monthly income €{monthly_income.quantize(Decimal('0.01'))}, got €{result.contribution_base}"
        
        # Verify base is within limits
        assert Decimal('551.10') <= result.contribution_base <= Decimal('8085.00'), \
            f"GSVG contribution base should be between €551.10 and €8,085, got €{result.contribution_base}"
    
    @given(
        annual_income=decimal_strategy(min_value=100000, max_value=500000)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_neue_selbstaendige_maximum_base_cap_enforced(
        self,
        annual_income: Decimal,
        svs_calculator
    ):
        """
        Property: Neue Selbständige maximum contribution base is capped at €8,085/month
        
        For any annual income where monthly income > €8,085:
        contribution_base = €8,085
        
        **Validates: Requirements 28.5**
        """
        # Only test cases where monthly income exceeds maximum
        monthly_income = annual_income / Decimal('12')
        assume(monthly_income > Decimal('8085.00'))
        
        result = svs_calculator.calculate_contributions(
            annual_income=annual_income,
            user_type=UserType.NEUE_SELBSTAENDIGE
        )
        
        # Verify maximum base is enforced
        assert result.contribution_base == Decimal('8085.00'), \
            f"Neue Selbständige contribution base should be capped at €8,085, got €{result.contribution_base}"
        
        # Verify contributions are calculated based on maximum base
        expected_pension = Decimal('8085.00') * svs_calculator.PENSION_RATE
        assert result.breakdown['pension'] == expected_pension.quantize(Decimal('0.01')), \
            f"Pension should be calculated on max base, expected €{expected_pension.quantize(Decimal('0.01'))}, got €{result.breakdown['pension']}"
    
    @given(
        annual_income=decimal_strategy(min_value=0, max_value=10000)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_neue_selbstaendige_minimum_contribution_enforced(
        self,
        annual_income: Decimal,
        svs_calculator
    ):
        """
        Property: Neue Selbständige minimum contribution €160.81/month
        
        For any annual income where calculated contribution < €160.81:
        monthly_total = €160.81
        
        **Validates: Requirements 28.6**
        """
        result = svs_calculator.calculate_contributions(
            annual_income=annual_income,
            user_type=UserType.NEUE_SELBSTAENDIGE
        )
        
        # Verify minimum contribution is enforced
        assert result.monthly_total >= Decimal('160.81'), \
            f"Neue Selbständige monthly contribution should be >= €160.81, got €{result.monthly_total}"
        
        # Verify result is deductible
        assert result.deductible, \
            "Neue Selbständige contributions should be deductible as Sonderausgaben"
        
        # If income is very low, minimum should be exactly applied
        monthly_income = annual_income / Decimal('12')
        calculated_total = (
            monthly_income * svs_calculator.PENSION_RATE +
            monthly_income * svs_calculator.HEALTH_RATE +
            svs_calculator.ACCIDENT_FIXED +
            monthly_income * svs_calculator.SUPPLEMENTARY_PENSION_RATE
        )
        
        if calculated_total < Decimal('160.81'):
            assert result.monthly_total == Decimal('160.81'), \
                f"When calculated < €160.81, monthly total should be exactly €160.81, got €{result.monthly_total}"
            assert "minimum" in result.note.lower(), \
                "Note should mention minimum contribution when applied"
    
    @given(
        annual_income=decimal_strategy(min_value=10000, max_value=97020)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_neue_selbstaendige_contribution_base_equals_monthly_income(
        self,
        annual_income: Decimal,
        svs_calculator
    ):
        """
        Property: Neue Selbständige contribution base equals monthly income (up to max)
        
        For any annual income where monthly income <= €8,085:
        contribution_base = monthly_income
        
        **Validates: Requirements 28.5, 28.6**
        """
        monthly_income = annual_income / Decimal('12')
        assume(monthly_income <= Decimal('8085.00'))
        
        result = svs_calculator.calculate_contributions(
            annual_income=annual_income,
            user_type=UserType.NEUE_SELBSTAENDIGE
        )
        
        # Verify contribution base equals monthly income
        assert result.contribution_base == monthly_income.quantize(Decimal('0.01')), \
            f"Neue Selbständige contribution base should equal monthly income €{monthly_income.quantize(Decimal('0.01'))}, got €{result.contribution_base}"
        
        # Verify base is within maximum limit
        assert result.contribution_base <= Decimal('8085.00'), \
            f"Neue Selbständige contribution base should be <= €8,085, got €{result.contribution_base}"
    
    @given(
        annual_income=decimal_strategy(min_value=6613.20, max_value=200000),
        user_type=st.sampled_from([UserType.GSVG, UserType.NEUE_SELBSTAENDIGE])
    )
    @settings(max_examples=150, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_contribution_amount_calculated_from_base_and_rates(
        self,
        annual_income: Decimal,
        user_type: UserType,
        svs_calculator
    ):
        """
        Property: Contribution components are calculated from base × rates
        
        For any valid income and user type:
        - Pension component is based on contribution base × pension rate
        - Health component is based on contribution base × health rate
        - Accident is fixed amount
        - Supplementary is based on contribution base × supplementary rate
        - Monthly total is sum of all components (within rounding tolerance)
        
        **Validates: Requirements 28.4, 28.5, 28.6**
        """
        result = svs_calculator.calculate_contributions(
            annual_income=annual_income,
            user_type=user_type
        )
        
        # Skip if no contributions (GSVG below threshold)
        if result.monthly_total == Decimal('0.00'):
            return
        
        # For Neue Selbständige, if minimum is applied, skip detailed breakdown check
        if user_type == UserType.NEUE_SELBSTAENDIGE and result.monthly_total == Decimal('160.81'):
            return
        
        # Verify breakdown components exist
        assert 'pension' in result.breakdown
        assert 'health' in result.breakdown
        assert 'accident' in result.breakdown
        assert 'supplementary' in result.breakdown
        
        # Verify accident is the fixed amount
        assert result.breakdown['accident'] == svs_calculator.ACCIDENT_FIXED, \
            f"Accident should be fixed at €{svs_calculator.ACCIDENT_FIXED}, got €{result.breakdown['accident']}"
        
        # Verify components are reasonable relative to contribution base
        # (allowing for rounding differences)
        base = result.contribution_base
        
        # Pension should be approximately base * 18.5%
        expected_pension_min = (base * Decimal('0.184')).quantize(Decimal('0.01'))
        expected_pension_max = (base * Decimal('0.186')).quantize(Decimal('0.01'))
        assert expected_pension_min <= result.breakdown['pension'] <= expected_pension_max, \
            f"Pension should be ~18.5% of base (€{base}), got €{result.breakdown['pension']}"
        
        # Health should be approximately base * 6.8%
        expected_health_min = (base * Decimal('0.067')).quantize(Decimal('0.01'))
        expected_health_max = (base * Decimal('0.069')).quantize(Decimal('0.01'))
        assert expected_health_min <= result.breakdown['health'] <= expected_health_max, \
            f"Health should be ~6.8% of base (€{base}), got €{result.breakdown['health']}"
        
        # Supplementary should be approximately base * 1.53%
        expected_supp_min = (base * Decimal('0.015')).quantize(Decimal('0.01'))
        expected_supp_max = (base * Decimal('0.016')).quantize(Decimal('0.01'))
        assert expected_supp_min <= result.breakdown['supplementary'] <= expected_supp_max, \
            f"Supplementary should be ~1.53% of base (€{base}), got €{result.breakdown['supplementary']}"
        
        # Verify monthly total is approximately the sum of breakdown
        # (allowing for rounding differences up to a few cents)
        breakdown_sum = sum(result.breakdown.values())
        diff = abs(result.monthly_total - breakdown_sum)
        assert diff <= Decimal('0.05'), \
            f"Monthly total (€{result.monthly_total}) should be close to sum of breakdown (€{breakdown_sum}), diff: €{diff}"
    
    @given(
        annual_income=decimal_strategy(min_value=0, max_value=500000),
        user_type=st.sampled_from([UserType.GSVG, UserType.NEUE_SELBSTAENDIGE])
    )
    @settings(max_examples=150, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_contribution_base_never_exceeds_maximum(
        self,
        annual_income: Decimal,
        user_type: UserType,
        svs_calculator
    ):
        """
        Property: Contribution base never exceeds €8,085/month for any user type
        
        For any income and any user type:
        contribution_base <= €8,085
        
        **Validates: Requirements 28.5**
        """
        result = svs_calculator.calculate_contributions(
            annual_income=annual_income,
            user_type=user_type
        )
        
        # Verify maximum base is never exceeded
        assert result.contribution_base <= Decimal('8085.00'), \
            f"{user_type.value} contribution base should never exceed €8,085, got €{result.contribution_base}"
    
    @given(
        annual_income=decimal_strategy(min_value=0, max_value=500000),
        user_type=st.sampled_from([UserType.GSVG, UserType.NEUE_SELBSTAENDIGE])
    )
    @settings(max_examples=150, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_all_monetary_values_have_two_decimal_places(
        self,
        annual_income: Decimal,
        user_type: UserType,
        svs_calculator
    ):
        """
        Property: All monetary values have exactly 2 decimal places
        
        For any calculation result:
        All Decimal values should have exactly 2 decimal places
        
        **Validates: Requirements 28.4, 28.5, 28.6**
        """
        result = svs_calculator.calculate_contributions(
            annual_income=annual_income,
            user_type=user_type
        )
        
        # Check main totals
        assert result.monthly_total.as_tuple().exponent == -2, \
            f"Monthly total should have 2 decimal places, got {result.monthly_total}"
        
        assert result.annual_total.as_tuple().exponent == -2, \
            f"Annual total should have 2 decimal places, got {result.annual_total}"
        
        assert result.contribution_base.as_tuple().exponent == -2, \
            f"Contribution base should have 2 decimal places, got {result.contribution_base}"
        
        # Check breakdown (if contributions exist)
        if result.monthly_total > Decimal('0.00'):
            for key, value in result.breakdown.items():
                assert value.as_tuple().exponent == -2, \
                    f"Breakdown {key} should have 2 decimal places, got {value}"
    
    @given(
        annual_income=decimal_strategy(min_value=0, max_value=500000),
        user_type=st.sampled_from([UserType.GSVG, UserType.NEUE_SELBSTAENDIGE])
    )
    @settings(max_examples=150, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_annual_total_is_reasonable_multiple_of_monthly(
        self,
        annual_income: Decimal,
        user_type: UserType,
        svs_calculator
    ):
        """
        Property: Annual total is approximately monthly total × 12
        
        For any calculation result:
        annual_total ≈ monthly_total × 12 (within small rounding tolerance)
        
        Note: Due to implementation details (quantization order), there may be
        small rounding differences, but they should be minimal (< €0.10)
        
        **Validates: Requirements 28.4, 28.5, 28.6**
        """
        result = svs_calculator.calculate_contributions(
            annual_income=annual_income,
            user_type=user_type
        )
        
        expected_annual = result.monthly_total * Decimal('12')
        
        # Allow for small rounding differences (up to 10 cents)
        # This accounts for the implementation's quantization order
        diff = abs(result.annual_total - expected_annual)
        assert diff <= Decimal('0.10'), \
            f"Annual total (€{result.annual_total}) should be close to monthly × 12 (€{expected_annual}), diff: €{diff}"
        
        # Verify annual is at least 11.9 * monthly and at most 12.1 * monthly
        # (this is a sanity check that the relationship is roughly correct)
        min_expected = result.monthly_total * Decimal('11.9')
        max_expected = result.monthly_total * Decimal('12.1')
        assert min_expected <= result.annual_total <= max_expected, \
            f"Annual total (€{result.annual_total}) should be roughly 12× monthly (€{result.monthly_total})"
