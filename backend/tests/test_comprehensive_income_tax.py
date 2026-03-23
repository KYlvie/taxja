"""
Comprehensive tests for the Austrian progressive income tax calculator.

Tests are based on the 2026 Austrian income tax brackets as published by
the Austrian Federal Ministry of Finance (BMF) via USP (Unternehmensserviceportal):

    - 0 to 13,541:       0%
    - 13,541 to 21,992: 20%
    - 21,992 to 36,458: 30%
    - 36,458 to 70,365: 40%
    - 70,365 to 104,859: 48%
    - 104,859 to 1,000,000: 50%
    - over 1,000,000:   55%

The calculator uses a 0% first bracket to represent the tax-free allowance
(Freibetrag). Gross income flows through all brackets starting from the 0%
zone, so no separate exemption subtraction is needed.

Source: https://www.bmf.gv.at / https://www.usp.gv.at
"""

import pytest
from decimal import Decimal

from app.services.income_tax_calculator import (
    IncomeTaxCalculator,
    IncomeTaxResult,
    TaxBracketResult,
)


# ---------------------------------------------------------------------------
# Tax configuration fixtures
# ---------------------------------------------------------------------------

TAX_CONFIG_2026 = {
    "tax_brackets": [
        {"lower": 0, "upper": 13539, "rate": 0},
        {"lower": 13539, "upper": 21992, "rate": 20},
        {"lower": 21992, "upper": 36458, "rate": 30},
        {"lower": 36458, "upper": 70365, "rate": 40},
        {"lower": 70365, "upper": 104859, "rate": 48},
        {"lower": 104859, "upper": 1000000, "rate": 50},
        {"lower": 1000000, "upper": None, "rate": 55},
    ],
    "exemption_amount": "13539.00",
}

TAX_CONFIG_2026_MIN_MAX = {
    "tax_brackets": [
        {"min": 0, "max": 13539, "rate": 0},
        {"min": 13539, "max": 21992, "rate": 20},
        {"min": 21992, "max": 36458, "rate": 30},
        {"min": 36458, "max": 70365, "rate": 40},
        {"min": 70365, "max": 104859, "rate": 48},
        {"min": 104859, "max": 1000000, "rate": 50},
        {"min": 1000000, "max": None, "rate": 55},
    ],
    "exemption_amount": "13539.00",
}

TAX_YEAR = 2026


@pytest.fixture
def calculator() -> IncomeTaxCalculator:
    """Return calculator initialised with the 2026 lower/upper config."""
    return IncomeTaxCalculator(TAX_CONFIG_2026)


@pytest.fixture
def calculator_min_max() -> IncomeTaxCalculator:
    """Return calculator initialised with the 2026 min/max config."""
    return IncomeTaxCalculator(TAX_CONFIG_2026_MIN_MAX)


# =========================================================================
# 1. Bracket boundary tests
# =========================================================================


class TestBracketBoundaries:
    """
    Verify tax at each official Austrian bracket boundary.

    The gross-income boundaries are:
        0, 13539, 21992, 36458, 70365, 104859, 1000000, 1500000

    Gross income flows directly through the 0% first bracket (which IS
    the exemption), then through the progressive brackets.
    """

    @pytest.mark.parametrize(
        "gross_income, expected_tax",
        [
            # Zero gross income -> 0 tax
            (Decimal("0"), Decimal("0.00")),
            # Exactly at exemption threshold -> taxable = 0
            (Decimal("13539"), Decimal("0.00")),
            # 21992 gross -> taxable = 8453 -> 8453 * 20% = 1690.60
            (Decimal("21992"), Decimal("1690.60")),
            # 36458 gross -> taxable = 22919
            #   8453 * 20% = 1690.60 + 14466 * 30% = 4339.80 = 6030.40
            (Decimal("36458"), Decimal("6030.40")),
            # 70365 gross -> taxable = 56826
            #   1690.60 + 4339.80 + 33907 * 40% = 13562.80 -> total 19593.20
            (Decimal("70365"), Decimal("19593.20")),
            # 104859 gross -> taxable = 91320
            #   19593.20 + 34494 * 48% = 16557.12 -> total 36150.32
            (Decimal("104859"), Decimal("36150.32")),
            # 1000000 gross -> taxable = 986461
            #   36150.32 + 895141 * 50% = 447570.50 -> total 483720.82
            (Decimal("1000000"), Decimal("483720.82")),
            # 1500000 gross -> taxable = 1486461
            #   483720.82 + 500000 * 55% = 275000 -> total 758720.82
            (Decimal("1500000"), Decimal("758720.82")),
        ],
        ids=[
            "gross_0",
            "gross_13539_exemption",
            "gross_21992",
            "gross_36458",
            "gross_70365",
            "gross_104859",
            "gross_1000000",
            "gross_1500000",
        ],
    )
    def test_tax_at_bracket_boundary(
        self, calculator: IncomeTaxCalculator, gross_income, expected_tax
    ):
        """Tax at each official Austrian bracket boundary should match hand-calculated values."""
        result = calculator.calculate_tax_with_exemption(gross_income, TAX_YEAR)
        assert result.total_tax == expected_tax


# =========================================================================
# 2. Zero and negative income
# =========================================================================


class TestZeroAndNegativeIncome:
    """Income at or below zero must produce zero tax."""

    def test_zero_gross_income(self, calculator: IncomeTaxCalculator):
        """Zero gross income yields zero tax."""
        result = calculator.calculate_tax_with_exemption(Decimal("0"), TAX_YEAR)
        assert result.total_tax == Decimal("0.00")
        assert result.effective_rate == Decimal("0.0000")
        assert result.breakdown == []

    def test_negative_gross_income(self, calculator: IncomeTaxCalculator):
        """Negative gross income yields zero tax (exemption floors at 0)."""
        result = calculator.calculate_tax_with_exemption(Decimal("-5000"), TAX_YEAR)
        assert result.total_tax == Decimal("0.00")

    def test_zero_taxable_income_directly(self, calculator: IncomeTaxCalculator):
        """Passing zero directly to progressive calculation yields zero tax."""
        result = calculator.calculate_progressive_tax(Decimal("0"), TAX_YEAR)
        assert result.total_tax == Decimal("0.00")
        assert result.breakdown == []

    def test_negative_taxable_income_directly(self, calculator: IncomeTaxCalculator):
        """Passing negative value directly to progressive calculation yields zero tax."""
        result = calculator.calculate_progressive_tax(Decimal("-10000"), TAX_YEAR)
        assert result.total_tax == Decimal("0.00")
        assert result.breakdown == []


# =========================================================================
# 3. Exemption application
# =========================================================================


class TestExemptionApplication:
    """Verify that apply_exemption correctly reduces gross income."""

    @pytest.mark.parametrize(
        "gross, expected_taxable",
        [
            (Decimal("50000"), Decimal("36461")),
            (Decimal("13539"), Decimal("0")),
            (Decimal("13540"), Decimal("1")),
            (Decimal("0"), Decimal("0")),
            (Decimal("5000"), Decimal("0")),  # below exemption
        ],
        ids=["50k", "exact_exemption", "one_above", "zero", "below_exemption"],
    )
    def test_apply_exemption(
        self, calculator: IncomeTaxCalculator, gross, expected_taxable
    ):
        """Exemption of 13539 is subtracted; result is floored at 0."""
        result = calculator.apply_exemption(gross)
        assert result == expected_taxable

    def test_apply_exemption_negative_gross(self, calculator: IncomeTaxCalculator):
        """Negative gross income floors to zero taxable income."""
        result = calculator.apply_exemption(Decimal("-1000"))
        assert result == Decimal("0")

    def test_exemption_amount_stored(self, calculator: IncomeTaxCalculator):
        """Calculator stores the exemption as Decimal('13539.00')."""
        assert calculator.exemption_amount == Decimal("13539.00")


# =========================================================================
# 4. Tax-free threshold
# =========================================================================


class TestTaxFreeThreshold:
    """Income at or below the 13,539 exemption should produce zero tax."""

    @pytest.mark.parametrize(
        "gross_income",
        [
            Decimal("0"),
            Decimal("1"),
            Decimal("100"),
            Decimal("5000"),
            Decimal("10000"),
            Decimal("13538"),
            Decimal("13539"),
        ],
        ids=["0", "1", "100", "5000", "10000", "13538", "13539"],
    )
    def test_no_tax_below_or_at_threshold(
        self, calculator: IncomeTaxCalculator, gross_income
    ):
        """Gross income at or below 13,539 must result in zero tax."""
        result = calculator.calculate_tax_with_exemption(gross_income, TAX_YEAR)
        assert result.total_tax == Decimal("0.00")

    def test_one_euro_above_threshold_has_tax(self, calculator: IncomeTaxCalculator):
        """13,540 gross => taxable = 1 => 1 * 20% = 0.20 tax."""
        result = calculator.calculate_tax_with_exemption(Decimal("13540"), TAX_YEAR)
        assert result.total_tax == Decimal("0.20")


# =========================================================================
# 5. Progressive calculation accuracy
# =========================================================================


class TestProgressiveCalculationAccuracy:
    """
    Hand-calculated expected taxes for specific gross incomes.

    All calculations follow: taxable = gross - 13539, then progressive brackets.
    Source: 2026 Austrian EStG progressive tax formula via BMF/USP.
    """

    @pytest.mark.parametrize(
        "gross_income, expected_tax",
        [
            # 25000: taxable=11461  -> 8453*0.20 + 3008*0.30
            #   = 1690.60 + 902.40 = 2593.00
            (Decimal("25000"), Decimal("2593.00")),
            # 50000: taxable=36461  -> 8453*0.20 + 14466*0.30 + 13542*0.40
            #   = 1690.60 + 4339.80 + 5416.80 = 11447.20
            (Decimal("50000"), Decimal("11447.20")),
            # 80000: taxable=66461  -> 8453*0.20 + 14466*0.30 + 33907*0.40 + 9635*0.48
            #   = 1690.60 + 4339.80 + 13562.80 + 4624.80 = 24218.00
            (Decimal("80000"), Decimal("24218.00")),
            # 120000: taxable=106461 -> 8453*0.20 + 14466*0.30 + 33907*0.40
            #   + 34494*0.48 + 15141*0.50
            #   = 1690.60 + 4339.80 + 13562.80 + 16557.12 + 7570.50 = 43720.82
            (Decimal("120000"), Decimal("43720.82")),
            # 1200000: taxable=1186461 -> 8453*0.20 + 14466*0.30 + 33907*0.40
            #   + 34494*0.48 + 895141*0.50 + 200000*0.55
            #   = 1690.60 + 4339.80 + 13562.80 + 16557.12 + 447570.50 + 110000
            #   = 593720.82
            (Decimal("1200000"), Decimal("593720.82")),
        ],
        ids=["25k", "50k", "80k", "120k", "1.2M"],
    )
    def test_progressive_tax_accuracy(
        self, calculator: IncomeTaxCalculator, gross_income, expected_tax
    ):
        """Tax for specific gross incomes must match hand-calculated values."""
        result = calculator.calculate_tax_with_exemption(gross_income, TAX_YEAR)
        assert result.total_tax == expected_tax


# =========================================================================
# 6. Effective rate calculations
# =========================================================================


class TestEffectiveRate:
    """Verify effective_rate = total_tax / taxable_income."""

    @pytest.mark.parametrize(
        "gross_income",
        [
            Decimal("25000"),
            Decimal("50000"),
            Decimal("80000"),
            Decimal("120000"),
            Decimal("1200000"),
        ],
        ids=["25k", "50k", "80k", "120k", "1.2M"],
    )
    def test_effective_rate_matches_formula(
        self, calculator: IncomeTaxCalculator, gross_income
    ):
        """effective_rate should equal total_tax / taxable_income rounded to 4 decimal places."""
        result = calculator.calculate_tax_with_exemption(gross_income, TAX_YEAR)
        if result.taxable_income > 0:
            expected_rate = (result.total_tax / result.taxable_income).quantize(
                Decimal("0.0001")
            )
            assert result.effective_rate == expected_rate

    def test_effective_rate_zero_for_zero_income(
        self, calculator: IncomeTaxCalculator
    ):
        """Effective rate is 0 when taxable income is zero."""
        result = calculator.calculate_tax_with_exemption(Decimal("0"), TAX_YEAR)
        assert result.effective_rate == Decimal("0.0000")

    def test_effective_rate_increases_with_income(
        self, calculator: IncomeTaxCalculator
    ):
        """A progressive system implies effective rate increases with income."""
        incomes = [
            Decimal("20000"),
            Decimal("40000"),
            Decimal("80000"),
            Decimal("200000"),
        ]
        rates = []
        for inc in incomes:
            r = calculator.calculate_tax_with_exemption(inc, TAX_YEAR)
            rates.append(r.effective_rate)
        for i in range(len(rates) - 1):
            assert rates[i] < rates[i + 1], (
                f"Effective rate should increase: {rates[i]} < {rates[i+1]}"
            )


# =========================================================================
# 7. Loss carryforward
# =========================================================================


class TestLossCarryforward:
    """
    Verify that loss carryforward reduces taxable income and tracks balances.

    The method: gross -> subtract loss_carryforward_applied -> progressive tax (0% bracket is exemption).
    """

    def test_loss_reduces_tax(self, calculator: IncomeTaxCalculator):
        """Applying a loss carryforward should reduce the tax owed."""
        result_no_loss = calculator.calculate_tax_with_exemption(
            Decimal("50000"), TAX_YEAR
        )
        result_with_loss = calculator.calculate_tax_with_loss_carryforward(
            gross_income=Decimal("50000"),
            tax_year=TAX_YEAR,
            loss_carryforward_applied=Decimal("10000"),
            remaining_loss_balance=Decimal("5000"),
        )
        assert result_with_loss.total_tax < result_no_loss.total_tax

    def test_loss_carryforward_fields_set(self, calculator: IncomeTaxCalculator):
        """Loss carryforward applied and remaining balance are stored on result."""
        result = calculator.calculate_tax_with_loss_carryforward(
            gross_income=Decimal("50000"),
            tax_year=TAX_YEAR,
            loss_carryforward_applied=Decimal("10000"),
            remaining_loss_balance=Decimal("5000"),
        )
        assert result.loss_carryforward_applied == Decimal("10000.00")
        assert result.remaining_loss_balance == Decimal("5000.00")

    def test_loss_exceeds_taxable_income(self, calculator: IncomeTaxCalculator):
        """Loss greater than income is capped at 75% (§18 Abs. 6 EStG)."""
        result = calculator.calculate_tax_with_loss_carryforward(
            gross_income=Decimal("20000"),
            tax_year=TAX_YEAR,
            loss_carryforward_applied=Decimal("999999"),
            remaining_loss_balance=Decimal("0"),
        )
        # 75% cap: max offset = 20000 * 0.75 = 15000, taxable = 5000
        # 5000 falls in 0% bracket so tax is still 0, but income is NOT zero
        assert result.loss_carryforward_applied == Decimal("15000.00")
        assert result.taxable_income == Decimal("5000.00")
        assert result.total_tax == Decimal("0.00")

    def test_loss_carryforward_exact_calculation(
        self, calculator: IncomeTaxCalculator
    ):
        """
        50000 gross - 10000 loss = 40000.
        40000: 13539*0.00=0, 8453*0.20=1690.60, 14466*0.30=4339.80, 3542*0.40=1416.80
        Total = 7447.20
        """
        result = calculator.calculate_tax_with_loss_carryforward(
            gross_income=Decimal("50000"),
            tax_year=TAX_YEAR,
            loss_carryforward_applied=Decimal("10000"),
            remaining_loss_balance=Decimal("0"),
        )
        assert result.total_tax == Decimal("7447.20")

    def test_zero_loss_carryforward(self, calculator: IncomeTaxCalculator):
        """Zero loss carryforward gives same result as calculate_tax_with_exemption."""
        result_exempt = calculator.calculate_tax_with_exemption(
            Decimal("50000"), TAX_YEAR
        )
        result_loss = calculator.calculate_tax_with_loss_carryforward(
            gross_income=Decimal("50000"),
            tax_year=TAX_YEAR,
            loss_carryforward_applied=Decimal("0"),
            remaining_loss_balance=Decimal("0"),
        )
        assert result_loss.total_tax == result_exempt.total_tax


# =========================================================================
# 8. Breakdown verification
# =========================================================================


class TestBreakdownVerification:
    """Verify each bracket in the breakdown has correct range, rate, and amounts."""

    def test_breakdown_count_for_25k(self, calculator: IncomeTaxCalculator):
        """25000 gross spans 3 brackets (0%, 20%, 30%)."""
        result = calculator.calculate_tax_with_exemption(Decimal("25000"), TAX_YEAR)
        assert len(result.breakdown) == 3

    def test_breakdown_count_for_120k(self, calculator: IncomeTaxCalculator):
        """120000 gross spans 6 brackets (0%, 20%, 30%, 40%, 48%, 50%)."""
        result = calculator.calculate_tax_with_exemption(Decimal("120000"), TAX_YEAR)
        assert len(result.breakdown) == 6

    def test_breakdown_amounts_sum_to_total(self, calculator: IncomeTaxCalculator):
        """Sum of bracket tax_amounts should equal total_tax."""
        result = calculator.calculate_tax_with_exemption(Decimal("80000"), TAX_YEAR)
        summed = sum(b.tax_amount for b in result.breakdown)
        assert summed == result.total_tax

    def test_breakdown_taxable_amounts_sum_to_taxable_income(
        self, calculator: IncomeTaxCalculator
    ):
        """Sum of bracket taxable_amounts should equal taxable_income."""
        result = calculator.calculate_tax_with_exemption(Decimal("80000"), TAX_YEAR)
        summed = sum(b.taxable_amount for b in result.breakdown)
        assert summed == result.taxable_income

    def test_breakdown_first_bracket_details(self, calculator: IncomeTaxCalculator):
        """First bracket for 50k gross: 0% zone, taxable=13539, tax=0."""
        result = calculator.calculate_tax_with_exemption(Decimal("50000"), TAX_YEAR)
        first = result.breakdown[0]
        assert first.taxable_amount == Decimal("13539.00")
        assert first.tax_amount == Decimal("0.00")
        assert first.rate == "0%"

    def test_breakdown_second_bracket_details(self, calculator: IncomeTaxCalculator):
        """Second bracket for 50k gross: taxable=8453, rate=20%, tax=1690.60."""
        result = calculator.calculate_tax_with_exemption(Decimal("50000"), TAX_YEAR)
        second = result.breakdown[1]
        assert second.taxable_amount == Decimal("8453.00")
        assert second.tax_amount == Decimal("1690.60")
        assert second.rate == "20%"

    def test_breakdown_partial_bracket(self, calculator: IncomeTaxCalculator):
        """Fourth bracket for 50k gross is partial: taxable=13542, rate=40%, tax=5416.80."""
        result = calculator.calculate_tax_with_exemption(Decimal("50000"), TAX_YEAR)
        fourth = result.breakdown[3]
        assert fourth.taxable_amount == Decimal("13542.00")
        assert fourth.tax_amount == Decimal("5416.80")
        assert fourth.rate == "40%"

    def test_breakdown_rates_are_formatted_strings(
        self, calculator: IncomeTaxCalculator
    ):
        """Rates in breakdown should be formatted as 'NN%' strings."""
        result = calculator.calculate_tax_with_exemption(Decimal("1200000"), TAX_YEAR)
        expected_rates = ["0%", "20%", "30%", "40%", "48%", "50%", "55%"]
        actual_rates = [b.rate for b in result.breakdown]
        assert actual_rates == expected_rates

    def test_breakdown_bracket_range_format(self, calculator: IncomeTaxCalculator):
        """Bracket ranges should be properly formatted strings."""
        result = calculator.calculate_tax_with_exemption(Decimal("1200000"), TAX_YEAR)
        # Last bracket should have '+' format
        last = result.breakdown[-1]
        assert "+" in last.bracket_range
        # Other brackets should have ' - ' format
        for b in result.breakdown[:-1]:
            assert " - " in b.bracket_range


# =========================================================================
# 9. Edge cases
# =========================================================================


class TestEdgeCases:
    """Edge cases: very small, very large incomes, and exact exemption."""

    def test_one_euro_income(self, calculator: IncomeTaxCalculator):
        """1 EUR gross is below exemption -> zero tax."""
        result = calculator.calculate_tax_with_exemption(Decimal("1"), TAX_YEAR)
        assert result.total_tax == Decimal("0.00")

    def test_one_euro_above_exemption(self, calculator: IncomeTaxCalculator):
        """13540 gross -> taxable = 1 -> 1 * 20% = 0.20."""
        result = calculator.calculate_tax_with_exemption(Decimal("13540"), TAX_YEAR)
        assert result.total_tax == Decimal("0.20")

    def test_very_large_income_10m(self, calculator: IncomeTaxCalculator):
        """
        10,000,000 gross -> taxable = 9,986,461
        8453*0.20 = 1690.60
        14466*0.30 = 4339.80
        33907*0.40 = 13562.80
        34494*0.48 = 16557.12
        895141*0.50 = 447570.50
        9000000*0.55 = 4950000.00
        Total = 5433720.82
        """
        result = calculator.calculate_tax_with_exemption(
            Decimal("10000000"), TAX_YEAR
        )
        assert result.total_tax == Decimal("5433720.82")

    def test_exact_exemption_amount(self, calculator: IncomeTaxCalculator):
        """Income exactly at exemption (13539) produces zero tax via 0% bracket."""
        result = calculator.calculate_tax_with_exemption(Decimal("13539"), TAX_YEAR)
        assert result.total_tax == Decimal("0.00")
        assert result.taxable_income == Decimal("13539")
        assert len(result.breakdown) == 1
        assert result.breakdown[0].rate == "0%"
        assert result.breakdown[0].tax_amount == Decimal("0.00")

    def test_fractional_cent_income(self, calculator: IncomeTaxCalculator):
        """Test with a non-round taxable income to verify Decimal precision."""
        result = calculator.calculate_progressive_tax(Decimal("0.01"), TAX_YEAR)
        # 0.01 * 20% = 0.002 -> quantized to 0.00
        assert result.total_tax == Decimal("0.00")

    def test_taxable_income_one_cent(self, calculator: IncomeTaxCalculator):
        """Taxable income of 0.05 -> 0.05 * 0.20 = 0.01."""
        result = calculator.calculate_progressive_tax(Decimal("0.05"), TAX_YEAR)
        assert result.total_tax == Decimal("0.01")


# =========================================================================
# 10. Rate normalisation
# =========================================================================


class TestRateNormalisation:
    """
    Verify rates > 1 are treated as percentages (divided by 100).

    The calculator normalises rates: if rate > 1 it divides by 100,
    so rate=20 becomes 0.20.
    """

    def test_percentage_rates_normalised(self):
        """Rates given as whole numbers (e.g. 20) are normalised to fractions."""
        config = {
            "tax_brackets": [
                {"lower": 0, "upper": 10000, "rate": 25},
            ],
            "exemption_amount": "0",
        }
        calc = IncomeTaxCalculator(config)
        result = calc.calculate_progressive_tax(Decimal("10000"), TAX_YEAR)
        # 10000 * 25% = 2500
        assert result.total_tax == Decimal("2500.00")

    def test_fractional_rates_not_normalised(self):
        """Rates given as fractions (e.g. 0.25) are kept as-is."""
        config = {
            "tax_brackets": [
                {"lower": 0, "upper": 10000, "rate": 0.25},
            ],
            "exemption_amount": "0",
        }
        calc = IncomeTaxCalculator(config)
        result = calc.calculate_progressive_tax(Decimal("10000"), TAX_YEAR)
        # 10000 * 0.25 = 2500
        assert result.total_tax == Decimal("2500.00")

    def test_rate_of_exactly_one(self):
        """Rate of exactly 1 is not normalised (1 is not > 1), so treated as 100%."""
        config = {
            "tax_brackets": [
                {"lower": 0, "upper": 10000, "rate": 1},
            ],
            "exemption_amount": "0",
        }
        calc = IncomeTaxCalculator(config)
        result = calc.calculate_progressive_tax(Decimal("5000"), TAX_YEAR)
        # 5000 * 1.0 = 5000 (rate=1 is not > 1, so no division)
        assert result.total_tax == Decimal("5000.00")

    def test_rate_100_normalised_to_1(self):
        """Rate of 100 is normalised to 1.00 (100/100)."""
        config = {
            "tax_brackets": [
                {"lower": 0, "upper": 10000, "rate": 100},
            ],
            "exemption_amount": "0",
        }
        calc = IncomeTaxCalculator(config)
        result = calc.calculate_progressive_tax(Decimal("5000"), TAX_YEAR)
        # 5000 * (100/100) = 5000
        assert result.total_tax == Decimal("5000.00")


# =========================================================================
# 11. Both bracket formats (min/max vs lower/upper)
# =========================================================================


class TestBothBracketFormats:
    """
    The calculator supports both {"lower","upper"} and {"min","max"} bracket key names.
    Both formats should produce identical results.
    """

    @pytest.mark.parametrize(
        "gross_income",
        [
            Decimal("25000"),
            Decimal("50000"),
            Decimal("80000"),
            Decimal("120000"),
            Decimal("1200000"),
        ],
        ids=["25k", "50k", "80k", "120k", "1.2M"],
    )
    def test_min_max_matches_lower_upper(
        self,
        calculator: IncomeTaxCalculator,
        calculator_min_max: IncomeTaxCalculator,
        gross_income,
    ):
        """min/max config produces same total_tax as lower/upper config."""
        result_lu = calculator.calculate_tax_with_exemption(gross_income, TAX_YEAR)
        result_mm = calculator_min_max.calculate_tax_with_exemption(
            gross_income, TAX_YEAR
        )
        assert result_lu.total_tax == result_mm.total_tax

    @pytest.mark.parametrize(
        "gross_income",
        [
            Decimal("25000"),
            Decimal("120000"),
        ],
        ids=["25k", "120k"],
    )
    def test_min_max_breakdown_matches(
        self,
        calculator: IncomeTaxCalculator,
        calculator_min_max: IncomeTaxCalculator,
        gross_income,
    ):
        """min/max config produces same breakdown details as lower/upper config."""
        result_lu = calculator.calculate_tax_with_exemption(gross_income, TAX_YEAR)
        result_mm = calculator_min_max.calculate_tax_with_exemption(
            gross_income, TAX_YEAR
        )
        assert len(result_lu.breakdown) == len(result_mm.breakdown)
        for b_lu, b_mm in zip(result_lu.breakdown, result_mm.breakdown):
            assert b_lu.rate == b_mm.rate
            assert b_lu.taxable_amount == b_mm.taxable_amount
            assert b_lu.tax_amount == b_mm.tax_amount


# =========================================================================
# Additional: configuration validation
# =========================================================================


class TestConfigurationValidation:
    """Test that the calculator validates its configuration properly."""

    def test_empty_brackets_raises(self):
        """Empty tax_brackets list should raise ValueError."""
        with pytest.raises(ValueError, match="Tax brackets configuration is required"):
            IncomeTaxCalculator({"tax_brackets": [], "exemption_amount": "13539.00"})

    def test_missing_brackets_raises(self):
        """Missing tax_brackets key should raise ValueError."""
        with pytest.raises(ValueError, match="Tax brackets configuration is required"):
            IncomeTaxCalculator({"exemption_amount": "13539.00"})

    def test_default_exemption_when_missing(self):
        """When exemption_amount is not provided, default to 13539.00."""
        config = {
            "tax_brackets": [{"lower": 0, "upper": 10000, "rate": 20}],
        }
        calc = IncomeTaxCalculator(config)
        assert calc.exemption_amount == Decimal("13539.00")


# =========================================================================
# Additional: numeric type coercion
# =========================================================================


class TestNumericTypeCoercion:
    """Verify that int and float inputs are coerced to Decimal correctly."""

    def test_int_gross_income(self, calculator: IncomeTaxCalculator):
        """Integer gross_income should be handled correctly."""
        result = calculator.calculate_tax_with_exemption(50000, TAX_YEAR)
        assert result.total_tax == Decimal("11447.20")

    def test_float_gross_income(self, calculator: IncomeTaxCalculator):
        """Float gross_income should be handled correctly."""
        result = calculator.calculate_tax_with_exemption(50000.0, TAX_YEAR)
        assert result.total_tax == Decimal("11447.20")

    def test_int_in_loss_carryforward(self, calculator: IncomeTaxCalculator):
        """Integer values for loss carryforward parameters should work."""
        result = calculator.calculate_tax_with_loss_carryforward(
            gross_income=50000,
            tax_year=TAX_YEAR,
            loss_carryforward_applied=10000,
            remaining_loss_balance=5000,
        )
        assert result.loss_carryforward_applied == Decimal("10000.00")
        assert result.remaining_loss_balance == Decimal("5000.00")
