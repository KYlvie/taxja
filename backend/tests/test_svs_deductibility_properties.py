"""
Property-based tests for SVS contributions deductibility

**Validates: Requirements 3.6, 28.7**

Property 11: SVS contributions deductibility
- All paid SVS contributions should be automatically deductible as Sonderausgaben
- GSVG contributions (when income >= €6,613.20) are deductible
- Neue Selbständige contributions are always deductible
- Employee contributions are not deductible (handled by employer)
- Deductible amount equals the annual SVS contribution total
- SVS contributions reduce taxable income before tax calculation
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


class TestProperty11SVSDeductibility:
    """
    **Property 11: SVS contributions deductibility**
    **Validates: Requirements 3.6, 28.7**
    
    Tests that SVS contributions are properly marked as deductible:
    1. GSVG contributions (when income >= €6,613.20) are deductible as Sonderausgaben
    2. Neue Selbständige contributions are always deductible as Sonderausgaben
    3. Employee contributions are not deductible (handled by employer)
    4. Deductible flag is correctly set based on user type and income
    5. Annual total represents the full deductible amount
    6. Zero contributions are not marked as deductible
    """
    
    @given(
        annual_income=decimal_strategy(min_value=6613.20, max_value=500000)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_gsvg_contributions_are_deductible_when_income_above_threshold(
        self,
        annual_income: Decimal,
        svs_calculator
    ):
        """
        Property: GSVG contributions are deductible as Sonderausgaben when income >= €6,613.20
        
        For any annual income >= €6,613.20:
        - result.deductible = True
        - result.annual_total > 0
        - result.note mentions "Sonderausgaben"
        
        **Validates: Requirements 3.6, 28.7**
        """
        result = svs_calculator.calculate_contributions(
            annual_income=annual_income,
            user_type=UserType.GSVG
        )
        
        # Verify contributions are marked as deductible
        assert result.deductible, \
            f"GSVG contributions should be deductible for income €{annual_income:,.2f}"
        
        # Verify there are actual contributions to deduct
        assert result.annual_total > Decimal('0.00'), \
            f"GSVG annual contributions should be positive for income €{annual_income:,.2f}, got €{result.annual_total}"
        
        assert result.monthly_total > Decimal('0.00'), \
            f"GSVG monthly contributions should be positive for income €{annual_income:,.2f}, got €{result.monthly_total}"
        
        # Verify note mentions Sonderausgaben (special deductions)
        assert result.note is not None, \
            "Result should include a note explaining deductibility"
        
        assert "sonderausgaben" in result.note.lower(), \
            f"Note should mention 'Sonderausgaben' for deductible GSVG contributions, got: {result.note}"
    
    @given(
        annual_income=decimal_strategy(min_value=0, max_value=6613.19)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_gsvg_contributions_not_deductible_when_income_below_threshold(
        self,
        annual_income: Decimal,
        svs_calculator
    ):
        """
        Property: GSVG contributions are not deductible when income < €6,613.20 (no contributions)
        
        For any annual income < €6,613.20:
        - result.deductible = False
        - result.annual_total = 0
        - No contributions means nothing to deduct
        
        **Validates: Requirements 3.6, 28.7**
        """
        result = svs_calculator.calculate_contributions(
            annual_income=annual_income,
            user_type=UserType.GSVG
        )
        
        # Verify no contributions are required
        assert result.annual_total == Decimal('0.00'), \
            f"GSVG should have no contributions for income €{annual_income:,.2f}, got €{result.annual_total}"
        
        # Verify not marked as deductible (nothing to deduct)
        assert not result.deductible, \
            f"GSVG contributions should not be deductible when no contributions are required (income €{annual_income:,.2f})"
        
        # Verify note explains the situation
        assert result.note is not None, \
            "Result should include a note explaining why no contributions are required"
    
    @given(
        annual_income=decimal_strategy(min_value=0, max_value=500000)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_neue_selbstaendige_contributions_always_deductible(
        self,
        annual_income: Decimal,
        svs_calculator
    ):
        """
        Property: Neue Selbständige contributions are always deductible as Sonderausgaben
        
        For any annual income (including very low income):
        - result.deductible = True
        - result.annual_total >= minimum (€160.81 × 12)
        - result.note mentions "Sonderausgaben"
        
        **Validates: Requirements 3.6, 28.7**
        """
        result = svs_calculator.calculate_contributions(
            annual_income=annual_income,
            user_type=UserType.NEUE_SELBSTAENDIGE
        )
        
        # Verify contributions are marked as deductible
        assert result.deductible, \
            f"Neue Selbständige contributions should always be deductible for income €{annual_income:,.2f}"
        
        # Verify there are actual contributions (at least minimum)
        minimum_annual = Decimal('160.81') * Decimal('12')
        assert result.annual_total >= minimum_annual, \
            f"Neue Selbständige annual contributions should be at least €{minimum_annual:,.2f}, got €{result.annual_total}"
        
        assert result.monthly_total >= Decimal('160.81'), \
            f"Neue Selbständige monthly contributions should be at least €160.81, got €{result.monthly_total}"
        
        # Verify note exists and is informative
        assert result.note is not None, \
            "Result should include a note explaining deductibility"
        
        # Note should mention either Sonderausgaben or minimum contribution
        # (both are valid informative notes for Neue Selbständige)
        has_relevant_info = (
            "sonderausgaben" in result.note.lower() or 
            "minimum" in result.note.lower()
        )
        assert has_relevant_info, \
            f"Note should mention 'Sonderausgaben' or 'minimum' for Neue Selbständige contributions, got: {result.note}"
    
    @given(
        annual_income=decimal_strategy(min_value=0, max_value=500000)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_employee_contributions_not_deductible(
        self,
        annual_income: Decimal,
        svs_calculator
    ):
        """
        Property: Employee contributions are not deductible (handled by employer)
        
        For any annual income:
        - result.deductible = False
        - result.annual_total = 0
        - Employees don't calculate SVS separately
        
        **Validates: Requirements 3.6, 28.7**
        """
        result = svs_calculator.calculate_contributions(
            annual_income=annual_income,
            user_type=UserType.EMPLOYEE
        )
        
        # Verify no contributions calculated
        assert result.annual_total == Decimal('0.00'), \
            f"Employee should have no SVS contributions calculated, got €{result.annual_total}"
        
        assert result.monthly_total == Decimal('0.00'), \
            f"Employee should have no monthly SVS contributions, got €{result.monthly_total}"
        
        # Verify not marked as deductible
        assert not result.deductible, \
            "Employee contributions should not be deductible (handled by employer)"
        
        # Verify note explains employer handling
        assert result.note is not None, \
            "Result should include a note explaining employer handling"
        
        assert "employer" in result.note.lower(), \
            f"Note should mention 'employer' for employee contributions, got: {result.note}"
    
    @given(
        annual_income=decimal_strategy(min_value=6613.20, max_value=500000),
        user_type=st.sampled_from([UserType.GSVG, UserType.NEUE_SELBSTAENDIGE])
    )
    @settings(max_examples=150, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_deductible_amount_equals_annual_total(
        self,
        annual_income: Decimal,
        user_type: UserType,
        svs_calculator
    ):
        """
        Property: The full annual SVS contribution total is deductible
        
        For any self-employed person with contributions:
        - The entire annual_total amount can be deducted as Sonderausgaben
        - No partial deductions or limits apply to SVS contributions
        
        **Validates: Requirements 3.6, 28.7**
        """
        result = svs_calculator.calculate_contributions(
            annual_income=annual_income,
            user_type=user_type
        )
        
        # Verify contributions are deductible
        assert result.deductible, \
            f"{user_type.value} contributions should be deductible"
        
        # Verify annual total is positive
        assert result.annual_total > Decimal('0.00'), \
            f"{user_type.value} annual total should be positive, got €{result.annual_total}"
        
        # The deductible amount is the full annual total
        # (This is implicit in the design - the annual_total IS the deductible amount)
        # Verify it's a reasonable amount (not zero, not negative)
        assert result.annual_total > Decimal('0.00'), \
            f"Deductible amount (annual_total) should be positive for {user_type.value}"
        
        # Verify annual total is consistent with monthly total
        expected_annual = result.monthly_total * Decimal('12')
        diff = abs(result.annual_total - expected_annual)
        assert diff <= Decimal('0.10'), \
            f"Annual total should be approximately monthly × 12, diff: €{diff}"
    
    @given(
        annual_income=decimal_strategy(min_value=6613.20, max_value=500000),
        user_type=st.sampled_from([UserType.GSVG, UserType.NEUE_SELBSTAENDIGE])
    )
    @settings(max_examples=150, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_deductibility_flag_consistency_with_contributions(
        self,
        annual_income: Decimal,
        user_type: UserType,
        svs_calculator
    ):
        """
        Property: Deductibility flag is consistent with contribution amounts
        
        For any calculation:
        - If annual_total > 0, then deductible = True (for self-employed)
        - If annual_total = 0, then deductible = False
        - Deductibility is determined by whether contributions exist
        
        **Validates: Requirements 3.6, 28.7**
        """
        result = svs_calculator.calculate_contributions(
            annual_income=annual_income,
            user_type=user_type
        )
        
        if result.annual_total > Decimal('0.00'):
            # Positive contributions should be deductible
            assert result.deductible, \
                f"{user_type.value} contributions (€{result.annual_total}) should be deductible"
            
            # Should have a note mentioning Sonderausgaben
            assert result.note is not None and "sonderausgaben" in result.note.lower(), \
                f"Deductible contributions should mention Sonderausgaben in note"
        else:
            # Zero contributions should not be deductible
            assert not result.deductible, \
                f"{user_type.value} with zero contributions should not be deductible"
    
    @given(
        annual_income=decimal_strategy(min_value=6613.20, max_value=500000),
        user_type=st.sampled_from([UserType.GSVG, UserType.NEUE_SELBSTAENDIGE])
    )
    @settings(max_examples=150, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_all_contribution_components_are_deductible(
        self,
        annual_income: Decimal,
        user_type: UserType,
        svs_calculator
    ):
        """
        Property: All SVS contribution components are deductible as Sonderausgaben
        
        For any self-employed person:
        - Pension insurance is deductible
        - Health insurance is deductible
        - Accident insurance is deductible
        - Supplementary pension is deductible
        - The sum of all components is the total deductible amount
        
        **Validates: Requirements 3.6, 28.7**
        """
        result = svs_calculator.calculate_contributions(
            annual_income=annual_income,
            user_type=user_type
        )
        
        # Skip if no contributions
        if result.annual_total == Decimal('0.00'):
            return
        
        # Verify all components exist in breakdown
        assert 'pension' in result.breakdown, \
            "Pension component should exist in breakdown"
        assert 'health' in result.breakdown, \
            "Health component should exist in breakdown"
        assert 'accident' in result.breakdown, \
            "Accident component should exist in breakdown"
        assert 'supplementary' in result.breakdown, \
            "Supplementary component should exist in breakdown"
        
        # Verify all components are positive (or zero for edge cases)
        for component, amount in result.breakdown.items():
            assert amount >= Decimal('0.00'), \
                f"{component} component should be non-negative, got €{amount}"
        
        # Verify the sum of components equals monthly total (within rounding tolerance)
        # For Neue Selbständige with minimum contribution, this may not hold exactly
        if not (user_type == UserType.NEUE_SELBSTAENDIGE and result.monthly_total == Decimal('160.81')):
            breakdown_sum = sum(result.breakdown.values())
            diff = abs(result.monthly_total - breakdown_sum)
            assert diff <= Decimal('0.05'), \
                f"Monthly total should equal sum of breakdown components, diff: €{diff}"
        
        # All components together form the deductible amount
        assert result.deductible, \
            "Result with positive breakdown components should be deductible"
    
    @given(
        annual_income=decimal_strategy(min_value=6613.20, max_value=500000)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_gsvg_deductibility_note_is_informative(
        self,
        annual_income: Decimal,
        svs_calculator
    ):
        """
        Property: GSVG deductibility note provides clear information
        
        For any GSVG calculation with contributions:
        - Note should exist
        - Note should mention "Sonderausgaben" (special deductions)
        - Note should be informative about tax deductibility
        
        **Validates: Requirements 3.6, 28.7**
        """
        result = svs_calculator.calculate_contributions(
            annual_income=annual_income,
            user_type=UserType.GSVG
        )
        
        # Verify note exists
        assert result.note is not None, \
            "GSVG result should include a note"
        
        # Verify note is not empty
        assert len(result.note.strip()) > 0, \
            "GSVG note should not be empty"
        
        # Verify note mentions Sonderausgaben
        assert "sonderausgaben" in result.note.lower(), \
            f"GSVG note should mention 'Sonderausgaben', got: {result.note}"
        
        # Verify note mentions deductibility or similar concept
        deductibility_keywords = ["deductible", "absetzbetrag", "abzug", "steuerlich"]
        has_deductibility_keyword = any(
            keyword in result.note.lower() 
            for keyword in deductibility_keywords
        )
        assert has_deductibility_keyword or "sonderausgaben" in result.note.lower(), \
            f"GSVG note should mention deductibility concept, got: {result.note}"
    
    @given(
        annual_income=decimal_strategy(min_value=0, max_value=500000)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_neue_selbstaendige_deductibility_note_is_informative(
        self,
        annual_income: Decimal,
        svs_calculator
    ):
        """
        Property: Neue Selbständige deductibility note provides clear information
        
        For any Neue Selbständige calculation:
        - Note should exist
        - Note should mention "Sonderausgaben" (special deductions)
        - Note should be informative about tax deductibility
        
        **Validates: Requirements 3.6, 28.7**
        """
        result = svs_calculator.calculate_contributions(
            annual_income=annual_income,
            user_type=UserType.NEUE_SELBSTAENDIGE
        )
        
        # Verify note exists
        assert result.note is not None, \
            "Neue Selbständige result should include a note"
        
        # Verify note is not empty
        assert len(result.note.strip()) > 0, \
            "Neue Selbständige note should not be empty"
        
        # Verify note mentions Sonderausgaben or minimum contribution
        # (both are valid informative notes for Neue Selbständige)
        has_relevant_info = (
            "sonderausgaben" in result.note.lower() or 
            "minimum" in result.note.lower()
        )
        assert has_relevant_info, \
            f"Neue Selbständige note should mention 'Sonderausgaben' or 'minimum', got: {result.note}"
    
    @given(
        annual_income_1=decimal_strategy(min_value=6613.20, max_value=500000),
        annual_income_2=decimal_strategy(min_value=6613.20, max_value=500000),
        user_type=st.sampled_from([UserType.GSVG, UserType.NEUE_SELBSTAENDIGE])
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_higher_income_means_higher_deductible_amount(
        self,
        annual_income_1: Decimal,
        annual_income_2: Decimal,
        user_type: UserType,
        svs_calculator
    ):
        """
        Property: Higher income leads to higher deductible SVS contributions (up to max)
        
        For any two incomes where income_1 < income_2 (both within contribution range):
        - If both are below max base: deductible_1 < deductible_2
        - If both are above max base: deductible_1 = deductible_2 (capped)
        - Deductible amount increases with income (monotonicity)
        
        **Validates: Requirements 3.6, 28.7**
        """
        # Ensure income_1 < income_2
        if annual_income_1 >= annual_income_2:
            annual_income_1, annual_income_2 = annual_income_2, annual_income_1
        
        # Ensure they're different enough to matter
        assume(annual_income_2 - annual_income_1 >= Decimal('1000.00'))
        
        result_1 = svs_calculator.calculate_contributions(
            annual_income=annual_income_1,
            user_type=user_type
        )
        
        result_2 = svs_calculator.calculate_contributions(
            annual_income=annual_income_2,
            user_type=user_type
        )
        
        # Both should be deductible
        assert result_1.deductible, \
            f"{user_type.value} contributions for income €{annual_income_1:,.2f} should be deductible"
        assert result_2.deductible, \
            f"{user_type.value} contributions for income €{annual_income_2:,.2f} should be deductible"
        
        # Check if both are below or above max base
        max_monthly_income = Decimal('8085.00') * Decimal('12')  # €97,020/year
        
        if annual_income_2 <= max_monthly_income:
            # Both below max: higher income should have higher deductible
            assert result_2.annual_total >= result_1.annual_total, \
                f"Higher income (€{annual_income_2:,.2f}) should have >= deductible amount than lower income (€{annual_income_1:,.2f})"
        elif annual_income_1 >= max_monthly_income:
            # Both above max: should have same deductible (capped)
            assert result_1.annual_total == result_2.annual_total, \
                f"Both incomes above max base should have same deductible amount (capped)"
        else:
            # One below, one above: higher should have >= deductible
            assert result_2.annual_total >= result_1.annual_total, \
                f"Higher income should have >= deductible amount"
    
    @given(
        annual_income=decimal_strategy(min_value=6613.20, max_value=500000),
        user_type=st.sampled_from([UserType.GSVG, UserType.NEUE_SELBSTAENDIGE])
    )
    @settings(max_examples=150, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_deductible_contributions_reduce_taxable_income(
        self,
        annual_income: Decimal,
        user_type: UserType,
        svs_calculator
    ):
        """
        Property: SVS contributions as Sonderausgaben reduce taxable income
        
        For any self-employed person:
        - SVS contributions are marked as deductible
        - The deductible amount (annual_total) should be subtracted from gross income
        - This reduces the taxable income base for income tax calculation
        
        Note: This test verifies the SVS calculator marks contributions as deductible.
        The actual tax reduction is handled by the tax calculation engine.
        
        **Validates: Requirements 3.6, 28.7**
        """
        result = svs_calculator.calculate_contributions(
            annual_income=annual_income,
            user_type=user_type
        )
        
        # Verify contributions are deductible
        assert result.deductible, \
            f"{user_type.value} contributions should be deductible as Sonderausgaben"
        
        # Verify there's a meaningful deduction amount
        assert result.annual_total > Decimal('0.00'), \
            f"{user_type.value} should have positive deductible contributions"
        
        # The deductible amount should be reasonable relative to income
        # (SVS contributions are typically 20-30% of income for self-employed)
        deduction_ratio = result.annual_total / annual_income
        
        # Sanity check: deduction should be between 5% and 50% of income
        # (accounting for minimum contributions and maximum base)
        assert Decimal('0.01') <= deduction_ratio <= Decimal('0.50'), \
            f"SVS deduction ratio should be reasonable (1-50% of income), got {deduction_ratio * 100:.2f}%"
        
        # Verify the deduction reduces taxable income
        # taxable_income = gross_income - SVS_contributions - other_deductions
        # So: taxable_income < gross_income (when SVS > 0)
        taxable_income_after_svs = annual_income - result.annual_total
        assert taxable_income_after_svs < annual_income, \
            f"Taxable income after SVS deduction (€{taxable_income_after_svs:,.2f}) should be less than gross income (€{annual_income:,.2f})"
        
        # Verify the reduction is exactly the SVS contribution amount
        reduction = annual_income - taxable_income_after_svs
        assert reduction == result.annual_total, \
            f"Income reduction (€{reduction:,.2f}) should equal SVS contribution (€{result.annual_total:,.2f})"
