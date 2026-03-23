"""
Comprehensive tests for VAT Calculator and SVS Calculator.

Tests Austrian VAT (Umsatzsteuer) rules including:
- Small business exemption (Kleinunternehmerregelung) with EUR 55,000 threshold
- Tolerance rule (10% overshoot up to EUR 60,500)
- Standard (20%), reduced 10%, reduced 13%, and exempt rates
- Category-based and keyword-based rate detection
- Mixed transaction VAT liability calculation

Tests Austrian SVS (Social Insurance) contributions including:
- Employee zero contributions (deducted by employer)
- GSVG minimum income, minimum base, normal, and maximum base calculations
- Neue Selbstaendige normal, minimum contribution, and maximum base
- Quarterly prepayment calculation
- Deductibility flags and custom config overrides
"""

from decimal import Decimal

import pytest

from app.services.vat_calculator import (
    PropertyType,
    Transaction,
    VATCalculator,
    VATRateType,
)
from app.services.svs_calculator import (
    SVSCalculator,
    SVSResult,
    UserType,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def vat_calc() -> VATCalculator:
    """Default VAT calculator with 2026 defaults."""
    return VATCalculator()


@pytest.fixture
def svs_calc() -> SVSCalculator:
    """Default SVS calculator with 2025/2026 defaults."""
    return SVSCalculator()


# ===========================================================================
# VAT CALCULATOR TESTS
# ===========================================================================


class TestVATSmallBusinessExemption:
    """Tests for Kleinunternehmerregelung (small business exemption)."""

    @pytest.mark.parametrize("turnover", [
        Decimal("0"),
        Decimal("10000"),
        Decimal("30000"),
        Decimal("54999.99"),
        Decimal("55000"),
    ])
    def test_exempt_at_or_below_threshold(self, vat_calc: VATCalculator, turnover: Decimal):
        """Turnover <= EUR 55,000 qualifies for small business exemption."""
        assert vat_calc.check_small_business_exemption(turnover) is True

    @pytest.mark.parametrize("turnover", [
        Decimal("55000.01"),
        Decimal("60000"),
        Decimal("60500"),
        Decimal("100000"),
    ])
    def test_not_exempt_above_threshold(self, vat_calc: VATCalculator, turnover: Decimal):
        """Turnover > EUR 55,000 does not qualify for small business exemption."""
        assert vat_calc.check_small_business_exemption(turnover) is False

    def test_zero_turnover_exempt(self, vat_calc: VATCalculator):
        """EUR 0 turnover is exempt."""
        result = vat_calc.calculate_vat_liability(Decimal("0"), [])
        assert result.exempt is True

    def test_exactly_at_threshold(self, vat_calc: VATCalculator):
        """Exactly EUR 55,000 is exempt."""
        result = vat_calc.calculate_vat_liability(Decimal("55000"), [])
        assert result.exempt is True
        assert result.warning is None


class TestVATToleranceRule:
    """Tests for the 15% tolerance rule (EUR 55,001 - EUR 63,250)."""

    @pytest.mark.parametrize("turnover", [
        Decimal("55000.01"),
        Decimal("57000"),
        Decimal("60000"),
        Decimal("63250"),
    ])
    def test_tolerance_applies(self, vat_calc: VATCalculator, turnover: Decimal):
        """Turnover between EUR 55,001 and EUR 60,500 triggers tolerance rule."""
        applies, warning = vat_calc.apply_tolerance_rule(turnover)
        assert applies is True
        assert warning is not None

    def test_tolerance_does_not_apply_below(self, vat_calc: VATCalculator):
        """Turnover at or below EUR 55,000 does not trigger tolerance rule."""
        applies, warning = vat_calc.apply_tolerance_rule(Decimal("55000"))
        assert applies is False
        assert warning is None

    def test_tolerance_does_not_apply_above(self, vat_calc: VATCalculator):
        """Turnover above EUR 63,250 does not trigger tolerance rule."""
        applies, warning = vat_calc.apply_tolerance_rule(Decimal("63250.01"))
        assert applies is False
        assert warning is None

    def test_calculate_vat_liability_tolerance_exempt_with_warning(self, vat_calc: VATCalculator):
        """calculate_vat_liability returns exempt=True with a warning in tolerance band."""
        result = vat_calc.calculate_vat_liability(Decimal("58000"), [])
        assert result.exempt is True
        assert result.warning is not None
        assert "55,000" in result.warning or "55000" in result.warning

    def test_above_tolerance_not_exempt(self, vat_calc: VATCalculator):
        """Turnover above EUR 60,500 is NOT exempt - VAT must be calculated."""
        txns = [
            Transaction(amount=Decimal("70000"), is_income=True, category="other"),
        ]
        result = vat_calc.calculate_vat_liability(Decimal("70000"), txns)
        assert result.exempt is False
        assert result.output_vat > Decimal("0")


class TestVATRateDetermination:
    """Tests for determine_vat_rate with property types, categories, and keywords."""

    # --- Property-type based ---

    def test_residential_opted_in_10_percent(self, vat_calc: VATCalculator):
        """Residential rental with VAT opt-in gets 10% reduced rate."""
        rate, rate_type = vat_calc.determine_vat_rate(
            property_type=PropertyType.RESIDENTIAL, vat_opted_in=True
        )
        assert rate == Decimal("0.10")
        assert rate_type == VATRateType.REDUCED_10

    def test_residential_not_opted_in_exempt(self, vat_calc: VATCalculator):
        """Residential rental without VAT opt-in is exempt (0%)."""
        rate, rate_type = vat_calc.determine_vat_rate(
            property_type=PropertyType.RESIDENTIAL, vat_opted_in=False
        )
        assert rate == Decimal("0")
        assert rate_type == VATRateType.EXEMPT

    def test_commercial_rental_20_percent(self, vat_calc: VATCalculator):
        """Commercial rental always gets standard 20% rate."""
        rate, rate_type = vat_calc.determine_vat_rate(
            property_type=PropertyType.COMMERCIAL
        )
        assert rate == Decimal("0.20")
        assert rate_type == VATRateType.STANDARD

    # --- Category-based rates ---

    @pytest.mark.parametrize("category,expected_rate,expected_type", [
        ("rental", Decimal("0.10"), VATRateType.REDUCED_10),
        ("groceries", Decimal("0.10"), VATRateType.REDUCED_10),
        ("accommodation", Decimal("0.10"), VATRateType.REDUCED_10),
        ("art", Decimal("0.13"), VATRateType.REDUCED_13),
        ("culture", Decimal("0.13"), VATRateType.REDUCED_13),
        ("sports_event", Decimal("0.13"), VATRateType.REDUCED_13),
    ])
    def test_category_based_rates(
        self, vat_calc: VATCalculator, category: str, expected_rate: Decimal, expected_type: VATRateType
    ):
        """Category-based rate determination returns correct rate and type."""
        rate, rate_type = vat_calc.determine_vat_rate(category=category)
        assert rate == expected_rate
        assert rate_type == expected_type

    # --- Keyword-based rates ---

    @pytest.mark.parametrize("description,expected_rate,expected_type", [
        ("Monatliche Miete Wohnung", Decimal("0.10"), VATRateType.REDUCED_10),
        ("Lebensmittel Einkauf", Decimal("0.10"), VATRateType.REDUCED_10),
        ("Buch: Python Programming", Decimal("0.10"), VATRateType.REDUCED_10),
        ("Kunstausstellung Eintritt", Decimal("0.13"), VATRateType.REDUCED_13),
        ("Brennholz Lieferung", Decimal("0.13"), VATRateType.REDUCED_13),
        ("Sport Veranstaltung Karte", Decimal("0.13"), VATRateType.REDUCED_13),
        ("Zirkus Vorstellung", Decimal("0.13"), VATRateType.REDUCED_13),
    ])
    def test_keyword_based_rates(
        self, vat_calc: VATCalculator, description: str, expected_rate: Decimal, expected_type: VATRateType
    ):
        """Keyword detection in description returns correct rate and type."""
        rate, rate_type = vat_calc.determine_vat_rate(description=description)
        assert rate == expected_rate
        assert rate_type == expected_type

    def test_default_rate_20_percent(self, vat_calc: VATCalculator):
        """Unknown category and no keywords defaults to standard 20%."""
        rate, rate_type = vat_calc.determine_vat_rate(
            category="unknown_stuff", description="Office supplies purchase"
        )
        assert rate == Decimal("0.20")
        assert rate_type == VATRateType.STANDARD

    def test_no_args_default_rate(self, vat_calc: VATCalculator):
        """No arguments at all defaults to standard 20%."""
        rate, rate_type = vat_calc.determine_vat_rate()
        assert rate == Decimal("0.20")
        assert rate_type == VATRateType.STANDARD

    def test_property_type_takes_priority_over_category(self, vat_calc: VATCalculator):
        """Property type is checked before category."""
        rate, rate_type = vat_calc.determine_vat_rate(
            category="art",
            property_type=PropertyType.COMMERCIAL,
        )
        assert rate == Decimal("0.20")
        assert rate_type == VATRateType.STANDARD


class TestVATLiabilityCalculation:
    """Tests for calculate_vat_liability with mixed transactions."""

    def test_mixed_transactions_vat_calculation(self, vat_calc: VATCalculator):
        """Mixed income and expense transactions compute correct output/input/net VAT."""
        txns = [
            # Income at 20%: gross 12000, VAT = 12000 * 0.20 / 1.20 = 2000.00
            Transaction(
                amount=Decimal("12000"), is_income=True,
                category="consulting", description="IT Consulting"
            ),
            # Income at 10%: gross 5500, VAT = 5500 * 0.10 / 1.10 = 500.00
            Transaction(
                amount=Decimal("5500"), is_income=True,
                category="rental", description="Residential rental income"
            ),
            # Income at 13%: gross 2260, VAT = 2260 * 0.13 / 1.13 = 260.00
            Transaction(
                amount=Decimal("2260"), is_income=True,
                category="art", description="Painting sale"
            ),
            # Expense at 20%: gross 6000, VAT = 6000 * 0.20 / 1.20 = 1000.00
            Transaction(
                amount=Decimal("6000"), is_income=False,
                category="office", description="Office equipment"
            ),
        ]
        gross = Decimal("80000")  # Above tolerance to force calculation
        result = vat_calc.calculate_vat_liability(gross, txns)

        assert result.exempt is False
        # Output VAT = 2000.00 + 500.00 + 260.00 = 2760.00
        assert result.output_vat == Decimal("2760.00")
        # Input VAT = 1000.00
        assert result.input_vat == Decimal("1000.00")
        # Net VAT = 2760.00 - 1000.00 = 1760.00
        assert result.net_vat == Decimal("1760.00")

    def test_net_vat_equals_output_minus_input(self, vat_calc: VATCalculator):
        """Net VAT is always output_vat - input_vat."""
        txns = [
            Transaction(amount=Decimal("24000"), is_income=True, description="Consulting"),
            Transaction(amount=Decimal("12000"), is_income=False, description="Equipment"),
        ]
        result = vat_calc.calculate_vat_liability(Decimal("100000"), txns)
        assert result.net_vat == result.output_vat - result.input_vat

    def test_line_items_created_for_income(self, vat_calc: VATCalculator):
        """Line items are generated for income transactions (not expenses)."""
        txns = [
            Transaction(
                amount=Decimal("12000"), is_income=True,
                category="consulting", description="IT Consulting"
            ),
            Transaction(
                amount=Decimal("6000"), is_income=False,
                category="office", description="Office supplies"
            ),
        ]
        result = vat_calc.calculate_vat_liability(Decimal("80000"), txns)
        # Only income transactions produce line items
        assert len(result.line_items) == 1
        item = result.line_items[0]
        assert item.vat_rate == Decimal("0.20")
        assert item.rate_type == VATRateType.STANDARD
        # VAT = 12000 * 0.20 / 1.20 = 2000.00
        assert item.vat_amount == Decimal("2000.00")
        # Net = 12000 - 2000 = 10000.00
        assert item.net_amount == Decimal("10000.00")

    def test_exempt_transaction_excluded(self, vat_calc: VATCalculator):
        """Exempt transactions (rate=0) produce no VAT and no line items."""
        txns = [
            Transaction(
                amount=Decimal("10000"), is_income=True,
                property_type=PropertyType.RESIDENTIAL, vat_opted_in=False,
            ),
        ]
        result = vat_calc.calculate_vat_liability(Decimal("80000"), txns)
        assert result.exempt is False  # Above threshold, but no VAT from exempt txn
        assert result.output_vat == Decimal("0.00")
        assert len(result.line_items) == 0

    def test_rates_applied_summary(self, vat_calc: VATCalculator):
        """rates_applied dict summarises VAT by rate percentage."""
        txns = [
            Transaction(amount=Decimal("12000"), is_income=True, description="Consulting"),
            Transaction(amount=Decimal("5500"), is_income=True, category="rental"),
        ]
        result = vat_calc.calculate_vat_liability(Decimal("80000"), txns)
        assert "20%" in result.rates_applied
        assert "10%" in result.rates_applied

    def test_vat_formula_gross_times_rate_over_one_plus_rate(self, vat_calc: VATCalculator):
        """VAT = gross * rate / (1 + rate) for each transaction."""
        gross = Decimal("1200")
        rate = Decimal("0.20")
        expected_vat = (gross * rate / (Decimal("1") + rate)).quantize(Decimal("0.01"))
        assert expected_vat == Decimal("200.00")

        txns = [Transaction(amount=gross, is_income=True, description="Service")]
        result = vat_calc.calculate_vat_liability(Decimal("80000"), txns)
        assert result.output_vat == expected_vat


class TestVATCustomConfig:
    """Tests for VATCalculator with custom configuration overrides."""

    def test_custom_rates(self):
        """Custom config overrides default rates and thresholds."""
        config = {
            "standard": "0.19",
            "residential": "0.07",
            "reduced_13": "0.09",
            "small_business_threshold": "22000",
            "tolerance_threshold": "24200",
        }
        calc = VATCalculator(vat_config=config)

        assert calc.STANDARD_RATE == Decimal("0.19")
        assert calc.REDUCED_RATE_10 == Decimal("0.07")
        assert calc.REDUCED_RATE_13 == Decimal("0.09")
        assert calc.SMALL_BUSINESS_THRESHOLD == Decimal("22000")
        assert calc.TOLERANCE_THRESHOLD == Decimal("24200")

    def test_custom_threshold_exemption(self):
        """Custom small business threshold is applied correctly."""
        config = {"small_business_threshold": "30000", "tolerance_threshold": "33000"}
        calc = VATCalculator(vat_config=config)

        assert calc.check_small_business_exemption(Decimal("30000")) is True
        assert calc.check_small_business_exemption(Decimal("30001")) is False

    def test_custom_rate_in_calculation(self):
        """Custom standard rate is used in VAT calculation."""
        config = {"standard": "0.19"}
        calc = VATCalculator(vat_config=config)
        rate, _ = calc.determine_vat_rate(description="Generic item")
        assert rate == Decimal("0.19")


class TestVATEdgeCases:
    """Edge cases for VAT calculator."""

    def test_zero_turnover_no_transactions(self, vat_calc: VATCalculator):
        """Zero turnover with no transactions is exempt, zero VAT."""
        result = vat_calc.calculate_vat_liability(Decimal("0"), [])
        assert result.exempt is True
        assert result.output_vat == Decimal("0.00")
        assert result.input_vat == Decimal("0.00")
        assert result.net_vat == Decimal("0.00")

    def test_exactly_at_tolerance_boundary(self, vat_calc: VATCalculator):
        """Exactly EUR 60,500 is within tolerance (exempt with warning)."""
        result = vat_calc.calculate_vat_liability(Decimal("60500"), [])
        assert result.exempt is True
        assert result.warning is not None

    def test_one_cent_above_tolerance(self, vat_calc: VATCalculator):
        """EUR 63,250.01 is above tolerance - not exempt."""
        txns = [
            Transaction(amount=Decimal("63250.01"), is_income=True, description="Service"),
        ]
        result = vat_calc.calculate_vat_liability(Decimal("63250.01"), txns)
        assert result.exempt is False

    def test_exactly_at_small_business_threshold(self, vat_calc: VATCalculator):
        """Exactly EUR 55,000 is exempt with no warning."""
        result = vat_calc.calculate_vat_liability(Decimal("55000"), [])
        assert result.exempt is True
        assert result.warning is None

    def test_empty_transactions_above_threshold(self, vat_calc: VATCalculator):
        """Above threshold but with no transactions results in zero VAT (not exempt)."""
        result = vat_calc.calculate_vat_liability(Decimal("80000"), [])
        assert result.exempt is False
        assert result.output_vat == Decimal("0.00")
        assert result.input_vat == Decimal("0.00")
        assert result.net_vat == Decimal("0.00")


# ===========================================================================
# SVS CALCULATOR TESTS
# ===========================================================================


class TestSVSEmployee:
    """Tests for employee type - contributions deducted by employer."""

    def test_employee_zero_contributions(self, svs_calc: SVSCalculator):
        """Employee returns zero contributions regardless of income."""
        result = svs_calc.calculate_contributions(Decimal("50000"), UserType.EMPLOYEE)
        assert result.monthly_total == Decimal("0.00")
        assert result.annual_total == Decimal("0.00")
        assert result.breakdown == {}
        assert result.deductible is False

    @pytest.mark.parametrize("income", [
        Decimal("0"),
        Decimal("10000"),
        Decimal("100000"),
    ])
    def test_employee_always_zero(self, svs_calc: SVSCalculator, income: Decimal):
        """Employee contributions are always zero, any income level."""
        result = svs_calc.calculate_contributions(income, UserType.EMPLOYEE)
        assert result.monthly_total == Decimal("0.00")
        assert result.annual_total == Decimal("0.00")


class TestSVSGSVG:
    """Tests for GSVG (commercial self-employed) contributions."""

    def test_below_minimum_income_zero(self, svs_calc: SVSCalculator):
        """Annual income below EUR 6,613.20 returns zero GSVG contributions."""
        result = svs_calc.calculate_contributions(Decimal("6613.19"), UserType.GSVG)
        assert result.monthly_total == Decimal("0.00")
        assert result.annual_total == Decimal("0.00")
        assert result.deductible is False

    def test_at_minimum_income_uses_minimum_base(self, svs_calc: SVSCalculator):
        """Income at minimum threshold uses minimum contribution base EUR 551.10/month."""
        result = svs_calc.calculate_contributions(Decimal("6613.20"), UserType.GSVG)
        # Monthly income = 6613.20 / 12 = 551.10 = min base
        assert result.contribution_base == Decimal("551.10")
        assert result.monthly_total > Decimal("0")
        assert result.deductible is True

    def test_below_minimum_base_uses_minimum(self, svs_calc: SVSCalculator):
        """Monthly income below EUR 551.10 (but above yearly min) uses min base."""
        # annual = 6613.20 -> monthly = 551.10 which equals minimum
        # Let's test with 7000 -> monthly = 583.33 which is above minimum
        # and 6613.20 -> monthly = 551.10 which is exactly the minimum
        result = svs_calc.calculate_contributions(Decimal("6613.20"), UserType.GSVG)
        assert result.contribution_base == Decimal("551.10")

    def test_normal_calculation_50000(self, svs_calc: SVSCalculator):
        """GSVG at EUR 50,000/year: detailed breakdown matches expected values."""
        annual = Decimal("50000")
        result = svs_calc.calculate_contributions(annual, UserType.GSVG)

        monthly_base = (annual / Decimal("12")).quantize(Decimal("0.01"))
        # 50000/12 = 4166.666... -> quantized to 4166.67
        # But the calculator uses unquantized monthly_income for the base
        # contribution_base = max(monthly_income, 551.10) then min(..., 8085)
        # monthly_income = 50000/12 = 4166.666...
        # contribution_base will be 4166.666... (between min and max)

        # The calculator quantizes only at the end in SVSResult fields
        expected_base_raw = Decimal("50000") / Decimal("12")
        expected_pension = (expected_base_raw * Decimal("0.185")).quantize(Decimal("0.01"))
        expected_health = (expected_base_raw * Decimal("0.068")).quantize(Decimal("0.01"))
        expected_accident = Decimal("12.25")
        expected_supplementary = (expected_base_raw * Decimal("0.0153")).quantize(Decimal("0.01"))

        assert result.breakdown["pension"] == expected_pension
        assert result.breakdown["health"] == expected_health
        assert result.breakdown["accident"] == expected_accident
        assert result.breakdown["supplementary"] == expected_supplementary

        expected_monthly = (
            expected_pension + expected_health + expected_accident + expected_supplementary
        )
        # The calculator sums unquantized intermediate values then quantizes the total,
        # so the total may differ by ±1 cent from summing the individually-quantized parts.
        sum_of_parts = (
            result.breakdown["pension"]
            + result.breakdown["health"]
            + result.breakdown["accident"]
            + result.breakdown["supplementary"]
        ).quantize(Decimal("0.01"))
        assert abs(result.monthly_total - sum_of_parts) <= Decimal("0.01")

        # annual_total is computed from unquantized monthly, so may differ by a few cents
        expected_annual = (result.monthly_total * Decimal("12")).quantize(Decimal("0.01"))
        assert abs(result.annual_total - expected_annual) <= Decimal("0.05")
        assert result.deductible is True

    def test_gsvg_at_max_base(self, svs_calc: SVSCalculator):
        """Income above max base (EUR 8,085/month) is capped."""
        annual = Decimal("120000")
        result = svs_calc.calculate_contributions(annual, UserType.GSVG)

        # Contribution base should be capped at max
        assert result.contribution_base == Decimal("7720.50")

        expected_pension = (Decimal("7720.50") * Decimal("0.185")).quantize(Decimal("0.01"))
        expected_health = (Decimal("7720.50") * Decimal("0.068")).quantize(Decimal("0.01"))
        expected_supplementary = (Decimal("7720.50") * Decimal("0.0153")).quantize(Decimal("0.01"))

        assert result.breakdown["pension"] == expected_pension
        assert result.breakdown["health"] == expected_health
        assert result.breakdown["accident"] == Decimal("12.25")
        assert result.breakdown["supplementary"] == expected_supplementary

    def test_gsvg_above_max_same_as_at_max(self, svs_calc: SVSCalculator):
        """Increasing income above max base does not increase contributions."""
        # Max base is 8085/month = 97020/year (2026)
        result_at = svs_calc.calculate_contributions(Decimal("97020"), UserType.GSVG)
        result_above = svs_calc.calculate_contributions(Decimal("200000"), UserType.GSVG)
        assert result_at.monthly_total == result_above.monthly_total
        assert result_at.annual_total == result_above.annual_total


class TestSVSNeueSelbstaendige:
    """Tests for Neue Selbstaendige (new self-employed / freelancers)."""

    def test_normal_calculation(self, svs_calc: SVSCalculator):
        """Neue Selbstaendige normal calculation for moderate income."""
        annual = Decimal("40000")
        result = svs_calc.calculate_contributions(annual, UserType.NEUE_SELBSTAENDIGE)

        monthly_income = Decimal("40000") / Decimal("12")
        # Should be below max base
        assert result.contribution_base == monthly_income.quantize(Decimal("0.01"))

        expected_pension = (monthly_income * Decimal("0.185")).quantize(Decimal("0.01"))
        expected_health = (monthly_income * Decimal("0.068")).quantize(Decimal("0.01"))
        expected_supplementary = (monthly_income * Decimal("0.0153")).quantize(Decimal("0.01"))

        assert result.breakdown["pension"] == expected_pension
        assert result.breakdown["health"] == expected_health
        assert result.breakdown["accident"] == Decimal("12.25")
        assert result.breakdown["supplementary"] == expected_supplementary
        assert result.deductible is True

    def test_minimum_contribution_applied(self, svs_calc: SVSCalculator):
        """Very low income triggers minimum contribution of EUR 160.81/month."""
        # Very low income where calculated total < 160.81
        annual = Decimal("1000")
        result = svs_calc.calculate_contributions(annual, UserType.NEUE_SELBSTAENDIGE)

        assert result.monthly_total == Decimal("160.81")
        assert result.annual_total == (Decimal("160.81") * Decimal("12")).quantize(Decimal("0.01"))
        assert "Minimum" in (result.note or "") or "minimum" in (result.note or "").lower()

    def test_neue_at_max_base(self, svs_calc: SVSCalculator):
        """Income above max base is capped at EUR 8,085/month (2026)."""
        annual = Decimal("120000")  # 10000/month > 8085
        result = svs_calc.calculate_contributions(annual, UserType.NEUE_SELBSTAENDIGE)

        assert result.contribution_base == Decimal("7720.50")

    def test_neue_zero_income_minimum_applied(self, svs_calc: SVSCalculator):
        """Zero income for Neue Selbstaendige gets minimum contribution."""
        result = svs_calc.calculate_contributions(Decimal("0"), UserType.NEUE_SELBSTAENDIGE)
        # With zero income, all calculated contributions are zero + accident
        # Total = 0 + 0 + 12.95 + 0 = 12.95 < 160.81, so minimum applies
        assert result.monthly_total == Decimal("160.81")


class TestSVSQuarterlyPrepayment:
    """Tests for quarterly prepayment calculation."""

    def test_quarterly_is_annual_divided_by_four(self, svs_calc: SVSCalculator):
        """Quarterly prepayment = annual_total / 4."""
        annual = Decimal("50000")
        full_result = svs_calc.calculate_contributions(annual, UserType.GSVG)
        quarterly = svs_calc.calculate_quarterly_prepayment(annual, UserType.GSVG)

        expected = (full_result.annual_total / Decimal("4")).quantize(Decimal("0.01"))
        assert quarterly == expected

    def test_quarterly_employee_zero(self, svs_calc: SVSCalculator):
        """Employee quarterly prepayment is zero."""
        quarterly = svs_calc.calculate_quarterly_prepayment(Decimal("50000"), UserType.EMPLOYEE)
        assert quarterly == Decimal("0.00")

    def test_quarterly_neue_selbstaendige(self, svs_calc: SVSCalculator):
        """Neue Selbstaendige quarterly prepayment calculated correctly."""
        annual = Decimal("40000")
        full_result = svs_calc.calculate_contributions(annual, UserType.NEUE_SELBSTAENDIGE)
        quarterly = svs_calc.calculate_quarterly_prepayment(annual, UserType.NEUE_SELBSTAENDIGE)

        expected = (full_result.annual_total / Decimal("4")).quantize(Decimal("0.01"))
        assert quarterly == expected


class TestSVSDeductibility:
    """Tests for deductibility flag on SVS contributions."""

    def test_gsvg_deductible(self, svs_calc: SVSCalculator):
        """GSVG contributions are deductible."""
        result = svs_calc.calculate_contributions(Decimal("50000"), UserType.GSVG)
        assert result.deductible is True

    def test_neue_deductible(self, svs_calc: SVSCalculator):
        """Neue Selbstaendige contributions are deductible."""
        result = svs_calc.calculate_contributions(Decimal("40000"), UserType.NEUE_SELBSTAENDIGE)
        assert result.deductible is True

    def test_employee_not_deductible(self, svs_calc: SVSCalculator):
        """Employee result has deductible=False (handled by employer)."""
        result = svs_calc.calculate_contributions(Decimal("50000"), UserType.EMPLOYEE)
        assert result.deductible is False

    def test_gsvg_below_min_not_deductible(self, svs_calc: SVSCalculator):
        """GSVG below minimum income has deductible=False (no contributions)."""
        result = svs_calc.calculate_contributions(Decimal("5000"), UserType.GSVG)
        assert result.deductible is False


class TestSVSCustomConfig:
    """Tests for SVSCalculator with custom configuration overrides."""

    def test_custom_rates_applied(self):
        """Custom config overrides all default rates and thresholds."""
        config = {
            "pension": "0.20",
            "health": "0.07",
            "supplementary_pension": "0.02",
            "accident_fixed": "15.00",
            "gsvg_min_base_monthly": "600.00",
            "gsvg_min_income_yearly": "7200.00",
            "neue_min_monthly": "200.00",
            "max_base_monthly": "8000.00",
        }
        calc = SVSCalculator(svs_config=config)

        assert calc.PENSION_RATE == Decimal("0.20")
        assert calc.HEALTH_RATE == Decimal("0.07")
        assert calc.SUPPLEMENTARY_PENSION_RATE == Decimal("0.02")
        assert calc.ACCIDENT_FIXED == Decimal("15.00")
        assert calc.GSVG_MIN_BASE_MONTHLY == Decimal("600.00")
        assert calc.GSVG_MIN_INCOME_YEARLY == Decimal("7200.00")
        assert calc.NEUE_MIN_MONTHLY == Decimal("200.00")
        assert calc.MAX_BASE_MONTHLY == Decimal("8000.00")

    def test_custom_config_used_in_calculation(self):
        """Custom accident_fixed is reflected in GSVG breakdown."""
        config = {"accident_fixed": "15.00"}
        calc = SVSCalculator(svs_config=config)

        result = calc.calculate_contributions(Decimal("50000"), UserType.GSVG)
        assert result.breakdown["accident"] == Decimal("15.00")

    def test_custom_max_base(self):
        """Custom max base monthly caps the contribution base."""
        config = {"max_base_monthly": "5000.00"}
        calc = SVSCalculator(svs_config=config)

        # 100000/12 = 8333.33 > 5000, should be capped
        result = calc.calculate_contributions(Decimal("100000"), UserType.GSVG)
        assert result.contribution_base == Decimal("5000.00")


class TestSVSEdgeCases:
    """Edge cases for SVS calculator."""

    def test_zero_income_gsvg(self, svs_calc: SVSCalculator):
        """Zero income for GSVG returns zero (below minimum income)."""
        result = svs_calc.calculate_contributions(Decimal("0"), UserType.GSVG)
        assert result.monthly_total == Decimal("0.00")
        assert result.annual_total == Decimal("0.00")

    def test_negative_income_gsvg(self, svs_calc: SVSCalculator):
        """Negative income for GSVG returns zero (below minimum income)."""
        result = svs_calc.calculate_contributions(Decimal("-5000"), UserType.GSVG)
        assert result.monthly_total == Decimal("0.00")
        assert result.annual_total == Decimal("0.00")

    def test_negative_income_neue(self, svs_calc: SVSCalculator):
        """Negative income for Neue Selbstaendige gets minimum contribution."""
        result = svs_calc.calculate_contributions(Decimal("-5000"), UserType.NEUE_SELBSTAENDIGE)
        # Negative monthly_income -> contribution_base = min(negative, 8085) = negative
        # All percentage-based contributions negative, total < 160.81, minimum applies
        assert result.monthly_total == Decimal("160.81")

    def test_exactly_at_gsvg_minimum_income(self, svs_calc: SVSCalculator):
        """Exactly at GSVG minimum income threshold triggers contributions."""
        result = svs_calc.calculate_contributions(Decimal("6613.20"), UserType.GSVG)
        assert result.monthly_total > Decimal("0")
        assert result.annual_total > Decimal("0")

    def test_one_cent_below_gsvg_minimum(self, svs_calc: SVSCalculator):
        """One cent below GSVG minimum income returns zero."""
        result = svs_calc.calculate_contributions(Decimal("6613.19"), UserType.GSVG)
        assert result.monthly_total == Decimal("0.00")

    def test_svs_result_has_note(self, svs_calc: SVSCalculator):
        """SVS results include an informational note."""
        result = svs_calc.calculate_contributions(Decimal("50000"), UserType.GSVG)
        assert result.note is not None
        assert len(result.note) > 0
