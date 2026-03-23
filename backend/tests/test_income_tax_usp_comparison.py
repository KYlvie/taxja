"""
Unit tests comparing IncomeTaxCalculator with official USP 2026 calculator.

**Validates: Requirements 3.7, 3.9**

This test suite validates that the tax calculation engine produces results
accurate to within €0.01 of the official Austrian USP 2026 tax calculator.

Test coverage:
- Each tax bracket boundary
- Values within each bracket
- Edge cases (exactly at bracket boundaries)
- Very low incomes (below exemption)
- Very high incomes (above €1M)
"""
import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

import pytest
from decimal import Decimal
from app.services.income_tax_calculator import IncomeTaxCalculator


# Official USP 2026 tax configuration
TAX_CONFIG_2026 = {
    "tax_brackets": [
        {"lower": "0", "upper": "13539", "rate": "0.00"},
        {"lower": "13539", "upper": "21992", "rate": "0.20"},
        {"lower": "21992", "upper": "36458", "rate": "0.30"},
        {"lower": "36458", "upper": "70365", "rate": "0.40"},
        {"lower": "70365", "upper": "104859", "rate": "0.48"},
        {"lower": "104859", "upper": "1000000", "rate": "0.50"},
        {"lower": "1000000", "upper": None, "rate": "0.55"},
    ],
    "exemption_amount": "13539.00"
}


@pytest.fixture
def calculator():
    """Create IncomeTaxCalculator with 2026 USP configuration"""
    return IncomeTaxCalculator(TAX_CONFIG_2026)


class TestUSPComparison:
    """
    Test suite comparing calculated tax with official USP 2026 calculator results.
    
    All expected values are derived from the official Austrian tax calculator
    using the 2026 USP tax brackets with 1.7333% inflation adjustment.
    """
    
    # Test cases: (taxable_income, expected_tax)
    # Expected values calculated using official USP 2026 formula
    USP_TEST_CASES = [
        # Below exemption threshold
        (Decimal("0.00"), Decimal("0.00")),
        (Decimal("5000.00"), Decimal("0.00")),
        (Decimal("10000.00"), Decimal("0.00")),
        (Decimal("13539.00"), Decimal("0.00")),  # Exactly at exemption
        
        # First bracket (20%): €13,539 - €21,992
        (Decimal("13539.01"), Decimal("0.00")),  # Just above exemption (still 0%)
        (Decimal("15000.00"), Decimal("292.20")),  # (15000 - 13539) * 0.20
        (Decimal("18000.00"), Decimal("892.20")),  # (18000 - 13539) * 0.20
        (Decimal("21992.00"), Decimal("1690.60")),  # (21992 - 13539) * 0.20
        
        # Second bracket (30%): €21,992 - €36,458
        (Decimal("21992.01"), Decimal("1690.60")),  # Just entered 30% bracket
        (Decimal("25000.00"), Decimal("2593.00")),  # 1690.60 + (25000 - 21992) * 0.30
        (Decimal("30000.00"), Decimal("4093.00")),  # 1690.60 + (30000 - 21992) * 0.30
        (Decimal("36458.00"), Decimal("6030.40")),  # 1690.60 + (36458 - 21992) * 0.30
        
        # Third bracket (40%): €36,458 - €70,365
        (Decimal("36458.01"), Decimal("6030.40")),  # Just entered 40% bracket
        (Decimal("40000.00"), Decimal("7447.20")),  # 6030.40 + (40000 - 36458) * 0.40
        (Decimal("50000.00"), Decimal("11447.20")),  # 6030.40 + (50000 - 36458) * 0.40
        (Decimal("60000.00"), Decimal("15447.20")),  # 6030.40 + (60000 - 36458) * 0.40
        (Decimal("70365.00"), Decimal("19593.20")),  # 6030.40 + (70365 - 36458) * 0.40
        
        # Fourth bracket (48%): €70,365 - €104,859
        (Decimal("70365.01"), Decimal("19593.20")),  # Just entered 48% bracket
        (Decimal("80000.00"), Decimal("24218.00")),  # 19593.20 + (80000 - 70365) * 0.48
        (Decimal("90000.00"), Decimal("29018.00")),  # 19593.20 + (90000 - 70365) * 0.48
        (Decimal("104859.00"), Decimal("36150.32")),  # 19593.20 + (104859 - 70365) * 0.48
        
        # Fifth bracket (50%): €104,859 - €1,000,000
        (Decimal("104859.01"), Decimal("36150.32")),  # Just entered 50% bracket
        (Decimal("150000.00"), Decimal("58720.82")),  # 36150.32 + (150000 - 104859) * 0.50
        (Decimal("250000.00"), Decimal("108720.82")),  # 36150.32 + (250000 - 104859) * 0.50
        (Decimal("500000.00"), Decimal("233720.82")),  # 36150.32 + (500000 - 104859) * 0.50
        (Decimal("1000000.00"), Decimal("483720.82")),  # 36150.32 + (1000000 - 104859) * 0.50
        
        # Sixth bracket (55%): €1,000,000+
        (Decimal("1000000.01"), Decimal("483720.83")),  # Just entered 55% bracket
        (Decimal("1500000.00"), Decimal("758720.82")),  # 483720.82 + (1500000 - 1000000) * 0.55
        (Decimal("2000000.00"), Decimal("1033720.82")),  # 483720.82 + (2000000 - 1000000) * 0.55
        (Decimal("5000000.00"), Decimal("2683720.82")),  # 483720.82 + (5000000 - 1000000) * 0.55
    ]
    
    @pytest.mark.parametrize("taxable_income,expected_tax", USP_TEST_CASES)
    def test_usp_comparison(self, calculator, taxable_income, expected_tax):
        """
        Test that calculated tax matches official USP 2026 calculator.
        
        Validates Requirements 3.7, 3.9:
        - Calculation error must be < €0.01
        - Uses official 2026 USP tax brackets
        """
        result = calculator.calculate_progressive_tax(taxable_income, 2026)
        
        # Calculate error
        error = abs(result.total_tax - expected_tax)
        
        # Assert error is less than €0.01
        assert error < Decimal("0.01"), (
            f"Tax calculation error exceeds €0.01 for income €{taxable_income:,.2f}\n"
            f"Expected: €{expected_tax:,.2f}\n"
            f"Calculated: €{result.total_tax:,.2f}\n"
            f"Error: €{error:,.2f}"
        )
    
    def test_bracket_boundaries_precision(self, calculator):
        """
        Test precision at exact bracket boundaries.
        
        Validates that transitions between brackets are handled correctly
        with no rounding errors at boundary points.
        """
        boundaries = [
            Decimal("13539.00"),
            Decimal("21992.00"),
            Decimal("36458.00"),
            Decimal("70365.00"),
            Decimal("104859.00"),
            Decimal("1000000.00"),
        ]
        
        for boundary in boundaries:
            # Test at boundary
            result_at = calculator.calculate_progressive_tax(boundary, 2026)
            
            # Test just below boundary
            result_below = calculator.calculate_progressive_tax(
                boundary - Decimal("0.01"), 2026
            )
            
            # Test just above boundary
            result_above = calculator.calculate_progressive_tax(
                boundary + Decimal("0.01"), 2026
            )
            
            # Tax should be monotonically increasing
            assert result_below.total_tax <= result_at.total_tax <= result_above.total_tax, (
                f"Tax not monotonic at boundary €{boundary:,.2f}"
            )
    
    def test_zero_and_negative_income(self, calculator):
        """
        Test edge cases with zero and negative income.
        
        Validates Requirement 3.7: When taxable income ≤ 0, tax should be €0.
        """
        test_cases = [
            Decimal("0.00"),
            Decimal("-100.00"),
            Decimal("-1000.00"),
            Decimal("-10000.00"),
        ]
        
        for income in test_cases:
            result = calculator.calculate_progressive_tax(income, 2026)
            assert result.total_tax == Decimal("0.00"), (
                f"Tax should be €0.00 for income €{income:,.2f}, "
                f"got €{result.total_tax:,.2f}"
            )
    
    def test_exemption_application(self, calculator):
        """
        Test that the 0% bracket acts as the tax-free allowance.

        With the 0% first bracket model, taxable_income equals gross_income
        (the exemption is embedded in the bracket, not subtracted separately).
        Tax should still be zero for income <= 13539.
        """
        gross_incomes = [
            (Decimal("13539.00"), Decimal("13539.00"), Decimal("0.00")),
            (Decimal("20000.00"), Decimal("20000.00"), Decimal("1292.20")),
            (Decimal("30000.00"), Decimal("30000.00"), Decimal("4093.00")),
            (Decimal("50000.00"), Decimal("50000.00"), Decimal("11447.20")),
        ]

        for gross_income, expected_taxable, expected_tax in gross_incomes:
            result = calculator.calculate_tax_with_exemption(gross_income, 2026)
            assert result.taxable_income == expected_taxable, (
                f"Taxable income incorrect for gross €{gross_income:,.2f}\n"
                f"Expected: €{expected_taxable:,.2f}\n"
                f"Got: €{result.taxable_income:,.2f}"
            )
            assert result.total_tax == expected_tax, (
                f"Tax incorrect for gross €{gross_income:,.2f}\n"
                f"Expected: €{expected_tax:,.2f}\n"
                f"Got: €{result.total_tax:,.2f}"
            )
    
    def test_effective_rate_calculation(self, calculator):
        """
        Test that effective tax rate is correctly calculated.
        
        Effective rate should be total_tax / taxable_income.
        """
        test_cases = [
            Decimal("20000.00"),
            Decimal("50000.00"),
            Decimal("100000.00"),
            Decimal("500000.00"),
        ]
        
        for income in test_cases:
            result = calculator.calculate_progressive_tax(income, 2026)
            
            if income > 0:
                expected_rate = result.total_tax / income
                assert abs(result.effective_rate - expected_rate) < Decimal("0.0001"), (
                    f"Effective rate incorrect for income €{income:,.2f}\n"
                    f"Expected: {expected_rate:.4f}\n"
                    f"Got: {result.effective_rate:.4f}"
                )
    
    def test_breakdown_sum_equals_total(self, calculator):
        """
        Test that sum of bracket taxes equals total tax.
        
        Validates internal consistency of tax calculation breakdown.
        """
        test_incomes = [
            Decimal("25000.00"),
            Decimal("50000.00"),
            Decimal("100000.00"),
            Decimal("500000.00"),
            Decimal("2000000.00"),
        ]
        
        for income in test_incomes:
            result = calculator.calculate_progressive_tax(income, 2026)
            
            # Sum all bracket taxes
            breakdown_sum = sum(
                bracket.tax_amount for bracket in result.breakdown
            )
            
            # Should equal total tax
            assert abs(breakdown_sum - result.total_tax) < Decimal("0.01"), (
                f"Breakdown sum doesn't match total for income €{income:,.2f}\n"
                f"Total tax: €{result.total_tax:,.2f}\n"
                f"Breakdown sum: €{breakdown_sum:,.2f}"
            )
    
    def test_high_income_scenarios(self, calculator):
        """
        Test very high income scenarios (multi-millionaire cases).
        
        Validates that the 55% top bracket is correctly applied.
        """
        high_income_cases = [
            (Decimal("10000000.00"), Decimal("5433720.82")),  # 10M: 483720.82 + (10M - 1M) * 0.55
            (Decimal("50000000.00"), Decimal("27433720.82")),  # 50M: 483720.82 + (50M - 1M) * 0.55
            (Decimal("100000000.00"), Decimal("54933720.82")),  # 100M: 483720.82 + (100M - 1M) * 0.55
        ]
        
        for income, expected_tax in high_income_cases:
            result = calculator.calculate_progressive_tax(income, 2026)
            error = abs(result.total_tax - expected_tax)
            
            assert error < Decimal("0.01"), (
                f"High income calculation error for €{income:,.2f}\n"
                f"Expected: €{expected_tax:,.2f}\n"
                f"Calculated: €{result.total_tax:,.2f}\n"
                f"Error: €{error:,.2f}"
            )
    
    def test_decimal_precision(self, calculator):
        """
        Test that all calculations maintain proper decimal precision.
        
        All monetary values should be rounded to 2 decimal places.
        """
        test_incomes = [
            Decimal("15432.67"),
            Decimal("28765.43"),
            Decimal("54321.98"),
            Decimal("123456.78"),
        ]
        
        for income in test_incomes:
            result = calculator.calculate_progressive_tax(income, 2026)
            
            # Check total tax has 2 decimal places
            assert result.total_tax == result.total_tax.quantize(Decimal("0.01")), (
                f"Total tax not properly rounded for income €{income:,.2f}"
            )
            
            # Check all breakdown amounts have 2 decimal places
            for bracket in result.breakdown:
                assert bracket.tax_amount == bracket.tax_amount.quantize(Decimal("0.01")), (
                    f"Bracket tax not properly rounded in {bracket.bracket_range}"
                )
                assert bracket.taxable_amount == bracket.taxable_amount.quantize(Decimal("0.01")), (
                    f"Taxable amount not properly rounded in {bracket.bracket_range}"
                )
    
    def test_typical_austrian_salaries(self, calculator):
        """
        Test typical Austrian salary scenarios.

        Tests common income levels in Austria via calculate_tax_with_exemption,
        which passes gross income through the 0% bracket (exemption embedded).
        """
        typical_salaries = [
            # (gross_annual, expected_tax)
            # 30000: 0-13539@0%, 13539-21992@20%=1690.60, 21992-30000@30%=2402.40 → 4093.00
            (Decimal("30000.00"), Decimal("4093.00")),
            # 45000: +36458-45000@40%=3416.80 → 9447.20
            (Decimal("45000.00"), Decimal("9447.20")),
            # 60000: +36458-60000@40%=9416.80 → 15447.20
            (Decimal("60000.00"), Decimal("15447.20")),
            # 80000: +70365-80000@48%=4624.80 → 24218.00
            (Decimal("80000.00"), Decimal("24218.00")),
            # 120000: +104859-120000@50%=7570.50 → 43720.82
            (Decimal("120000.00"), Decimal("43720.82")),
        ]

        for gross_income, expected_tax in typical_salaries:
            result = calculator.calculate_tax_with_exemption(gross_income, 2026)
            error = abs(result.total_tax - expected_tax)

            assert error < Decimal("0.01"), (
                f"Salary calculation error for €{gross_income:,.2f}\n"
                f"Expected: €{expected_tax:,.2f}\n"
                f"Calculated: €{result.total_tax:,.2f}\n"
                f"Error: €{error:,.2f}"
            )


class TestBracketTransitions:
    """Test smooth transitions between tax brackets"""
    
    def test_no_sudden_jumps(self, calculator):
        """
        Test that there are no sudden jumps in tax when crossing brackets.
        
        Tax should increase smoothly, never decrease when income increases.
        """
        # Test around each bracket boundary
        boundaries = [13539, 21992, 36458, 70365, 104859, 1000000]
        
        for boundary in boundaries:
            incomes = [
                Decimal(str(boundary - 100)),
                Decimal(str(boundary - 10)),
                Decimal(str(boundary - 1)),
                Decimal(str(boundary)),
                Decimal(str(boundary + 1)),
                Decimal(str(boundary + 10)),
                Decimal(str(boundary + 100)),
            ]
            
            previous_tax = None
            for income in incomes:
                result = calculator.calculate_progressive_tax(income, 2026)
                
                if previous_tax is not None:
                    # Tax should never decrease
                    assert result.total_tax >= previous_tax, (
                        f"Tax decreased at boundary €{boundary:,.2f}\n"
                        f"Income: €{income:,.2f}\n"
                        f"Previous tax: €{previous_tax:,.2f}\n"
                        f"Current tax: €{result.total_tax:,.2f}"
                    )
                
                previous_tax = result.total_tax
    
    def test_marginal_rate_application(self, calculator):
        """
        Test that marginal rates are correctly applied within each bracket.
        
        For a small income increase within a bracket, the tax increase
        should equal the income increase times the marginal rate.
        """
        test_cases = [
            # (income, marginal_rate)
            (Decimal("15000.00"), Decimal("0.20")),  # 20% bracket
            (Decimal("25000.00"), Decimal("0.30")),  # 30% bracket
            (Decimal("50000.00"), Decimal("0.40")),  # 40% bracket
            (Decimal("85000.00"), Decimal("0.48")),  # 48% bracket
            (Decimal("200000.00"), Decimal("0.50")),  # 50% bracket
            (Decimal("2000000.00"), Decimal("0.55")),  # 55% bracket
        ]
        
        for income, marginal_rate in test_cases:
            result1 = calculator.calculate_progressive_tax(income, 2026)
            result2 = calculator.calculate_progressive_tax(income + Decimal("100.00"), 2026)
            
            tax_increase = result2.total_tax - result1.total_tax
            expected_increase = Decimal("100.00") * marginal_rate
            
            # Allow small rounding error
            error = abs(tax_increase - expected_increase)
            assert error < Decimal("0.01"), (
                f"Marginal rate not correctly applied at €{income:,.2f}\n"
                f"Expected increase: €{expected_increase:,.2f}\n"
                f"Actual increase: €{tax_increase:,.2f}\n"
                f"Error: €{error:,.2f}"
            )
