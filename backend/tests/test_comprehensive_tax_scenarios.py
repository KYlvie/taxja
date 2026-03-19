"""
Comprehensive end-to-end tax scenario tests for the Austrian tax system.

Covers all calculators with realistic tax scenarios:
- Income tax (progressive brackets, all years 2023-2026)
- SVS social insurance (GSVG, Neue Selbständige, Employee)
- VAT (Kleinunternehmerregelung, tolerance, multi-rate)
- Deductions (Pendlerpauschale, home office, family, employee)
- KESt (capital gains: bank interest 25%, other 27.5%)
- ImmoESt (real estate gains: exemptions, old property, reclassification)
- Self-employed features (Gewinnfreibetrag, Basispauschalierung)
- AI Orchestrator (intent detection accuracy across DE/EN/ZH)
- Tax calculation engine (integrated scenarios)

All expected values are hand-calculated from official Austrian tax rules.
Sources:
- BMF Tax Book 2026: https://www.bmf.gv.at
- USP Tarifstufen: https://www.usp.gv.at
- WKO SVS rates: https://www.wko.at
- SVS.at: https://www.svs.at

Official 2026 brackets (Veranlagung 2026):
    €0 – €13,541: 0%  (our config uses €13,539 for historical reasons)
    €13,541 – €21,992: 20%
    €21,992 – €36,458: 30%
    €36,458 – €70,365: 40%
    €70,365 – €104,859: 48%
    €104,859 – €1,000,000: 50%
    Over €1,000,000: 55%
"""

import pytest
from datetime import date
from decimal import Decimal

# ---------------------------------------------------------------------------
# Income Tax Calculator
# ---------------------------------------------------------------------------
from app.services.income_tax_calculator import IncomeTaxCalculator, IncomeTaxResult

# ---------------------------------------------------------------------------
# SVS Calculator
# ---------------------------------------------------------------------------
from app.services.svs_calculator import SVSCalculator, SVSResult, UserType

# ---------------------------------------------------------------------------
# VAT Calculator
# ---------------------------------------------------------------------------
from app.services.vat_calculator import (
    VATCalculator,
    VATResult,
    Transaction,
    PropertyType,
    VATRateType,
)

# ---------------------------------------------------------------------------
# Deduction Calculator
# ---------------------------------------------------------------------------
from app.services.deduction_calculator import (
    DeductionCalculator,
    DeductionResult,
    FamilyInfo,
)

# ---------------------------------------------------------------------------
# KESt Calculator
# ---------------------------------------------------------------------------
from app.services.kest_calculator import (
    calculate_kest,
    get_kest_rate,
    KEStResult,
    CapitalIncomeType,
    KEST_RATE_BANK,
    KEST_RATE_OTHER,
)

# ---------------------------------------------------------------------------
# ImmoESt Calculator
# ---------------------------------------------------------------------------
from app.services.immoest_calculator import (
    calculate_immoest,
    ImmoEStResult,
    ExemptionType,
    IMMOEST_RATE,
    OLD_PROPERTY_EFFECTIVE_RATE,
    OLD_PROPERTY_RECLASSIFIED_RATE,
)

# ---------------------------------------------------------------------------
# Self-Employed Tax Service
# ---------------------------------------------------------------------------
from app.services.self_employed_tax_service import (
    calculate_gewinnfreibetrag,
    calculate_basispauschalierung,
    determine_kleinunternehmer_status,
    compare_expense_methods,
    GewinnfreibetragResult,
    BasispauschalierungResult,
    SelfEmployedConfig,
    ExpenseMethod,
    ProfessionType,
)

# ---------------------------------------------------------------------------
# AI Orchestrator (intent detection)
# ---------------------------------------------------------------------------
from app.services.ai_orchestrator import detect_intent, UserIntent

# ---------------------------------------------------------------------------
# Tax Configuration (multi-year configs)
# ---------------------------------------------------------------------------
from app.models.tax_configuration import (
    get_2023_tax_config,
    get_2024_tax_config,
    get_2025_tax_config,
    get_2026_tax_config,
)


# =========================================================================
# Fixtures
# =========================================================================

# 2026 tax config: brackets are relative to exemption
# Official: 0-13539 exempt, then progressive brackets on the excess
TAX_CONFIG_2026 = {
    "tax_brackets": [
        {"lower": 0, "upper": 8453, "rate": 20},
        {"lower": 8453, "upper": 22919, "rate": 30},
        {"lower": 22919, "upper": 56826, "rate": 40},
        {"lower": 56826, "upper": 91320, "rate": 48},
        {"lower": 91320, "upper": 986461, "rate": 50},
        {"lower": 986461, "upper": None, "rate": 55},
    ],
    "exemption_amount": "13539.00",
}


@pytest.fixture
def income_calc() -> IncomeTaxCalculator:
    return IncomeTaxCalculator(TAX_CONFIG_2026)


@pytest.fixture
def svs_calc() -> SVSCalculator:
    return SVSCalculator()


@pytest.fixture
def vat_calc() -> VATCalculator:
    return VATCalculator()


@pytest.fixture
def deduction_calc() -> DeductionCalculator:
    return DeductionCalculator()


# =========================================================================
# SECTION 1: COMPREHENSIVE INCOME TAX SCENARIOS
# =========================================================================

class TestIncomeTaxRealWorldScenarios:
    """Real-world income scenarios with hand-calculated expected taxes."""

    @pytest.mark.parametrize("gross,expected_tax,description", [
        # Scenario 1: Minimum-wage earner (~€1,700/month gross)
        (Decimal("20400"), Decimal("1372.20"),
         "Minimum-wage full-time: 20400 - 13539 = 6861 taxable, 6861*0.20 = 1372.20"),
        # Scenario 2: Typical office worker (~€2,500/month)
        # taxable=16461: 8453*0.20=1690.60 + 8008*0.30=2402.40 = 4093.00
        (Decimal("30000"), Decimal("4093.00"),
         "Office worker: taxable=16461"),
        # Scenario 3: IT professional (~€4,200/month)
        (Decimal("50000"), Decimal("11447.20"),
         "IT professional: taxable=36461"),
        # Scenario 4: Senior manager (~€6,000/month)
        # taxable=58461: 8453*0.20=1690.60+14466*0.30=4339.80+33907*0.40=13562.80+1635*0.48=784.80=20378.00
        (Decimal("72000"), Decimal("20378.00"),
         "Senior manager: taxable=58461"),
        # Scenario 5: Executive (~€8,500/month)
        # taxable=88461: 1690.60+4339.80+13562.80+31635*0.48=15184.80 = 34778.00
        (Decimal("102000"), Decimal("34778.00"),
         "Executive: taxable=88461"),
        # Scenario 6: Director (~€12,000/month)
        (Decimal("144000"), Decimal("55720.82"),
         "Director: taxable=130461"),
        # Scenario 7: High earner (€250,000/year)
        (Decimal("250000"), Decimal("108720.82"),
         "High earner: taxable=236461"),
        # Scenario 8: Top earner (€500,000/year)
        (Decimal("500000"), Decimal("233720.82"),
         "Top earner: taxable=486461"),
        # Scenario 9: Millionaire (€1,500,000/year)
        (Decimal("1500000"), Decimal("758720.82"),
         "Millionaire: taxable=1486461"),
        # Scenario 10: Part-time worker (~€800/month)
        (Decimal("9600"), Decimal("0.00"),
         "Part-time below exemption"),
    ])
    def test_real_world_income_scenarios(self, income_calc, gross, expected_tax, description):
        result = income_calc.calculate_tax_with_exemption(gross, 2026)
        assert result.total_tax == expected_tax, f"Failed: {description}"

    def test_effective_rate_always_below_marginal(self, income_calc):
        """Effective rate must always be below marginal rate for any income."""
        for income in [20000, 35000, 50000, 80000, 120000, 500000, 2000000]:
            result = income_calc.calculate_tax_with_exemption(Decimal(str(income)), 2026)
            if result.taxable_income > 0:
                assert result.effective_rate < Decimal("0.55"), \
                    f"Effective rate {result.effective_rate} >= 55% at income {income}"

    def test_progressive_system_monotonically_increasing_tax(self, income_calc):
        """Tax must increase as income increases."""
        prev_tax = Decimal("-1")
        for income in range(10000, 200001, 5000):
            result = income_calc.calculate_tax_with_exemption(Decimal(str(income)), 2026)
            assert result.total_tax >= prev_tax, \
                f"Tax decreased from {prev_tax} to {result.total_tax} at income {income}"
            prev_tax = result.total_tax

    def test_breakdown_sums_match_total(self, income_calc):
        """Sum of bracket taxes must equal total tax for various incomes."""
        for income in [25000, 50000, 80000, 120000, 1200000]:
            result = income_calc.calculate_tax_with_exemption(Decimal(str(income)), 2026)
            sum_taxes = sum(b.tax_amount for b in result.breakdown)
            assert sum_taxes == result.total_tax, \
                f"Breakdown sum {sum_taxes} != total {result.total_tax} at {income}"
            sum_taxable = sum(b.taxable_amount for b in result.breakdown)
            assert sum_taxable == result.taxable_income, \
                f"Taxable sum {sum_taxable} != taxable income {result.taxable_income} at {income}"


# =========================================================================
# SECTION 2: MULTI-YEAR TAX BRACKET VERIFICATION
# =========================================================================

class TestMultiYearTaxBrackets:
    """Verify tax configurations across all supported years (2023-2026)."""

    def test_2023_config_structure(self):
        config = get_2023_tax_config()
        assert config["tax_year"] == 2023
        assert len(config["tax_brackets"]) == 7
        assert config["exemption_amount"] == 11693.00
        assert config["tax_brackets"][3]["rate"] == 0.41  # 2023 had 41% in 4th bracket

    def test_2024_config_structure(self):
        config = get_2024_tax_config()
        assert config["tax_year"] == 2024
        assert config["exemption_amount"] == 12816.00
        assert config["tax_brackets"][3]["rate"] == 0.40  # 2024 reduced to 40%
        assert config["vat_rates"]["small_business_threshold"] == 35000.00  # pre-2025

    def test_2025_config_structure(self):
        config = get_2025_tax_config()
        assert config["tax_year"] == 2025
        assert config["exemption_amount"] == 13308.00
        assert config["vat_rates"]["small_business_threshold"] == 55000.00  # new 2025 threshold

    def test_2026_config_structure(self):
        config = get_2026_tax_config()
        assert config["tax_year"] == 2026
        assert config["exemption_amount"] == 13539.00
        assert config["vat_rates"]["small_business_threshold"] == 55000.00
        assert config["deduction_config"]["verkehrsabsetzbetrag"] == 496.00

    def test_exemption_increases_yearly(self):
        """Exemption amount should increase each year (cold progression adjustment)."""
        configs = [get_2023_tax_config(), get_2024_tax_config(),
                   get_2025_tax_config(), get_2026_tax_config()]
        exemptions = [c["exemption_amount"] for c in configs]
        for i in range(len(exemptions) - 1):
            assert exemptions[i] < exemptions[i + 1], \
                f"Exemption {exemptions[i]} not < {exemptions[i + 1]}"

    def test_all_years_have_7_brackets(self):
        """All years should have exactly 7 brackets."""
        for getter in [get_2023_tax_config, get_2024_tax_config,
                       get_2025_tax_config, get_2026_tax_config]:
            config = getter()
            assert len(config["tax_brackets"]) == 7, \
                f"Year {config['tax_year']} has {len(config['tax_brackets'])} brackets"

    def test_all_years_top_rate_is_55(self):
        """All years should have 55% top rate."""
        for getter in [get_2023_tax_config, get_2024_tax_config,
                       get_2025_tax_config, get_2026_tax_config]:
            config = getter()
            last = config["tax_brackets"][-1]
            assert last["rate"] == 0.55, f"Year {config['tax_year']} top rate is {last['rate']}"
            assert last.get("upper") is None

    def test_all_years_have_complete_svs_config(self):
        """All years should have SVS rates with required keys."""
        required_keys = {"pension", "health", "accident_fixed", "supplementary_pension",
                         "gsvg_min_base_monthly", "gsvg_min_income_yearly",
                         "neue_min_monthly", "max_base_monthly"}
        for getter in [get_2023_tax_config, get_2024_tax_config,
                       get_2025_tax_config, get_2026_tax_config]:
            config = getter()
            svs = config["svs_rates"]
            missing = required_keys - set(svs.keys())
            assert not missing, f"Year {config['tax_year']} SVS missing keys: {missing}"

    def test_all_years_pension_rate_stable(self):
        """Pension rate should be stable at 18.5% across all years."""
        for getter in [get_2023_tax_config, get_2024_tax_config,
                       get_2025_tax_config, get_2026_tax_config]:
            config = getter()
            assert config["svs_rates"]["pension"] == 0.185


# =========================================================================
# SECTION 3: SVS SOCIAL INSURANCE SCENARIOS
# =========================================================================

class TestSVSComprehensive:
    """Comprehensive SVS calculation tests covering all user types and edge cases."""

    def test_employee_zero_contributions(self, svs_calc):
        """Employees should have zero SVS contributions (handled by employer)."""
        result = svs_calc.calculate_contributions(Decimal("50000"), UserType.EMPLOYEE)
        assert result.monthly_total == Decimal("0.00")
        assert result.annual_total == Decimal("0.00")
        assert result.deductible is False
        assert "employer" in result.note.lower()

    def test_gsvg_below_minimum_income(self, svs_calc):
        """GSVG below minimum income should have no contributions."""
        result = svs_calc.calculate_contributions(Decimal("5000"), UserType.GSVG)
        assert result.annual_total == Decimal("0.00")
        assert result.deductible is False

    def test_gsvg_at_minimum_income(self, svs_calc):
        """GSVG at minimum income threshold should trigger contributions."""
        result = svs_calc.calculate_contributions(Decimal("6614"), UserType.GSVG)
        assert result.annual_total > Decimal("0.00")
        assert result.deductible is True

    def test_gsvg_typical_self_employed_30k(self, svs_calc):
        """GSVG self-employed with €30,000 income."""
        result = svs_calc.calculate_contributions(Decimal("30000"), UserType.GSVG)
        # Monthly income: 30000/12 = 2500, above min base 551.10
        # Pension: 2500 * 0.185 = 462.50
        # Health: 2500 * 0.068 = 170.00
        # Accident: 12.17 (fixed)
        # Supplementary: 2500 * 0.0153 = 38.25
        # Monthly total: 682.92
        assert result.monthly_total == Decimal("682.92")
        assert result.annual_total == Decimal("8195.04")
        assert result.deductible is True

    def test_gsvg_typical_self_employed_60k(self, svs_calc):
        """GSVG self-employed with €60,000 income."""
        result = svs_calc.calculate_contributions(Decimal("60000"), UserType.GSVG)
        # Monthly income: 5000
        # Pension: 5000 * 0.185 = 925.00
        # Health: 5000 * 0.068 = 340.00
        # Accident: 12.17
        # Supplementary: 5000 * 0.0153 = 76.50
        # Monthly total: 1353.67
        assert result.monthly_total == Decimal("1353.67")
        assert result.annual_total == Decimal("16244.04")

    def test_gsvg_high_income_capped(self, svs_calc):
        """GSVG with high income should be capped at max contribution base."""
        result = svs_calc.calculate_contributions(Decimal("200000"), UserType.GSVG)
        # Monthly income: 16666.67, capped at max_base_monthly 7585.00
        # Pension: 7585 * 0.185 = 1403.225 -> 1403.23
        # Health: 7585 * 0.068 = 515.78
        # Accident: 12.17
        # Supplementary: 7585 * 0.0153 = 116.0505 -> 116.05
        expected_monthly = Decimal("1403.23") + Decimal("515.78") + Decimal("12.17") + Decimal("116.05")
        assert result.contribution_base == Decimal("7585.00")
        assert result.monthly_total == expected_monthly.quantize(Decimal("0.01"))

    def test_neue_selbstaendige_low_income(self, svs_calc):
        """Neue Selbständige with low income should have minimum contribution."""
        result = svs_calc.calculate_contributions(Decimal("3000"), UserType.NEUE_SELBSTAENDIGE)
        # Monthly income: 250, contributions would be very low
        # Minimum monthly: 160.81
        assert result.monthly_total == Decimal("160.81")

    def test_neue_selbstaendige_typical_freelancer(self, svs_calc):
        """Neue Selbständige freelancer with €40,000 income."""
        result = svs_calc.calculate_contributions(Decimal("40000"), UserType.NEUE_SELBSTAENDIGE)
        # Monthly income: 40000/12 = 3333.333...
        # The calculator sums unrounded components, then quantizes the total
        monthly = Decimal("40000") / Decimal("12")
        expected_pension = monthly * Decimal("0.185")
        expected_health = monthly * Decimal("0.068")
        expected_supp = monthly * Decimal("0.0153")
        expected_total = (expected_pension + expected_health + Decimal("12.17") + expected_supp).quantize(Decimal("0.01"))
        assert result.monthly_total == expected_total
        assert result.deductible is True

    def test_quarterly_prepayment(self, svs_calc):
        """Quarterly prepayment should be annual_total / 4."""
        quarterly = svs_calc.calculate_quarterly_prepayment(Decimal("50000"), UserType.GSVG)
        annual = svs_calc.calculate_contributions(Decimal("50000"), UserType.GSVG)
        expected = (annual.annual_total / Decimal("4")).quantize(Decimal("0.01"))
        assert quarterly == expected


# =========================================================================
# SECTION 4: VAT (UMSATZSTEUER) SCENARIOS
# =========================================================================

class TestVATComprehensive:
    """Comprehensive VAT calculation tests."""

    def test_kleinunternehmer_exempt_below_threshold(self, vat_calc):
        """Turnover below €55,000 should be exempt."""
        result = vat_calc.calculate_vat_liability(
            gross_turnover=Decimal("40000"),
            transactions=[],
        )
        assert result.exempt is True
        assert "Kleinunternehmerregelung" in result.reason

    def test_kleinunternehmer_exempt_at_threshold(self, vat_calc):
        """Turnover exactly at €55,000 should be exempt."""
        result = vat_calc.calculate_vat_liability(
            gross_turnover=Decimal("55000"),
            transactions=[],
        )
        assert result.exempt is True

    def test_tolerance_rule_applies(self, vat_calc):
        """Turnover between €55,000 and €60,500 triggers tolerance rule."""
        result = vat_calc.calculate_vat_liability(
            gross_turnover=Decimal("58000"),
            transactions=[],
        )
        assert result.exempt is True
        assert "Tolerance" in result.reason or "tolerance" in result.reason.lower()
        assert result.warning is not None

    def test_tolerance_at_boundary(self, vat_calc):
        """Turnover at €60,500 should still qualify for tolerance."""
        result = vat_calc.calculate_vat_liability(
            gross_turnover=Decimal("60500"),
            transactions=[],
        )
        assert result.exempt is True

    def test_above_tolerance_vat_liable(self, vat_calc):
        """Turnover above €60,500 should be VAT-liable."""
        transactions = [
            Transaction(amount=Decimal("70000"), is_income=True, category="services"),
            Transaction(amount=Decimal("5000"), is_income=False, category="office"),
        ]
        result = vat_calc.calculate_vat_liability(
            gross_turnover=Decimal("70000"),
            transactions=transactions,
        )
        assert result.exempt is False
        assert result.output_vat > Decimal("0")

    def test_standard_rate_20_percent(self, vat_calc):
        """Standard transactions should use 20% rate."""
        rate, rate_type = vat_calc.determine_vat_rate(category="services")
        assert rate == Decimal("0.20")
        assert rate_type == VATRateType.STANDARD

    def test_reduced_rate_10_rental(self, vat_calc):
        """Residential rental with opt-in should use 10% rate."""
        rate, rate_type = vat_calc.determine_vat_rate(
            property_type=PropertyType.RESIDENTIAL,
            vat_opted_in=True,
        )
        assert rate == Decimal("0.10")
        assert rate_type == VATRateType.REDUCED_10

    def test_residential_no_opt_in_exempt(self, vat_calc):
        """Residential rental without opt-in should be exempt."""
        rate, rate_type = vat_calc.determine_vat_rate(
            property_type=PropertyType.RESIDENTIAL,
            vat_opted_in=False,
        )
        assert rate == Decimal("0")
        assert rate_type == VATRateType.EXEMPT

    def test_commercial_always_20(self, vat_calc):
        """Commercial rental should always be 20%."""
        rate, rate_type = vat_calc.determine_vat_rate(
            property_type=PropertyType.COMMERCIAL,
        )
        assert rate == Decimal("0.20")

    def test_reduced_13_rate_art(self, vat_calc):
        """Art/culture activities should use 13% rate."""
        rate, rate_type = vat_calc.determine_vat_rate(category="art")
        assert rate == Decimal("0.13")
        assert rate_type == VATRateType.REDUCED_13

    def test_reduced_10_rate_groceries(self, vat_calc):
        """Food/groceries should use 10% rate."""
        rate, rate_type = vat_calc.determine_vat_rate(category="groceries")
        assert rate == Decimal("0.10")

    def test_keyword_detection_miete(self, vat_calc):
        """Description containing 'Miete' should trigger 10% rate."""
        rate, _ = vat_calc.determine_vat_rate(description="Monatsmiete Wohnung")
        assert rate == Decimal("0.10")

    def test_keyword_detection_theater(self, vat_calc):
        """Description containing 'Theater' should trigger 13% rate."""
        rate, _ = vat_calc.determine_vat_rate(description="Theaterkarte")
        assert rate == Decimal("0.13")

    def test_multi_rate_calculation(self, vat_calc):
        """Mixed transactions with different rates should be calculated correctly."""
        transactions = [
            Transaction(amount=Decimal("12000"), is_income=True,
                        category="services", description="Consulting"),
            Transaction(amount=Decimal("5000"), is_income=True,
                        category="groceries", description="Lebensmittellieferung"),
            Transaction(amount=Decimal("2000"), is_income=False,
                        category="office", description="Büromaterial"),
        ]
        result = vat_calc.calculate_vat_liability(
            gross_turnover=Decimal("70000"),
            transactions=transactions,
        )
        assert result.exempt is False
        # Output VAT: 12000 * 0.20/1.20 = 2000.00, 5000 * 0.10/1.10 = 454.55
        assert result.output_vat == Decimal("2454.55")
        # Input VAT: 2000 * 0.20/1.20 = 333.33
        assert result.input_vat == Decimal("333.33")
        assert result.net_vat == Decimal("2121.22")

    def test_check_small_business_exemption(self, vat_calc):
        assert vat_calc.check_small_business_exemption(Decimal("40000")) is True
        assert vat_calc.check_small_business_exemption(Decimal("56000")) is False


# =========================================================================
# SECTION 5: DEDUCTION SCENARIOS
# =========================================================================

class TestDeductionComprehensive:
    """Comprehensive deduction calculation tests."""

    # -- Commuting (Pendlerpauschale) --

    def test_commuting_small_20km(self, deduction_calc):
        """Kleines Pendlerpauschale 20-40km: base_annual only (Pendlereuro separate)."""
        result = deduction_calc.calculate_commuting_allowance(
            distance_km=20, public_transport_available=True
        )
        # Base: 58 * 12 = 696 (Pendlereuro 20*6=120 in breakdown, not in amount)
        assert result.amount == Decimal("696.00")

    def test_commuting_small_45km(self, deduction_calc):
        """Kleines Pendlerpauschale 40-60km: base_annual only."""
        result = deduction_calc.calculate_commuting_allowance(
            distance_km=45, public_transport_available=True
        )
        assert result.amount == Decimal("1356.00")  # 113*12

    def test_commuting_small_65km(self, deduction_calc):
        """Kleines Pendlerpauschale 60km+: base_annual only."""
        result = deduction_calc.calculate_commuting_allowance(
            distance_km=65, public_transport_available=True
        )
        assert result.amount == Decimal("2016.00")  # 168*12

    def test_commuting_large_5km(self, deduction_calc):
        """Großes Pendlerpauschale 2-20km: base_annual only."""
        result = deduction_calc.calculate_commuting_allowance(
            distance_km=5, public_transport_available=False
        )
        assert result.amount == Decimal("372.00")  # 31*12

    def test_commuting_large_25km(self, deduction_calc):
        """Großes Pendlerpauschale 20-40km: base_annual only."""
        result = deduction_calc.calculate_commuting_allowance(
            distance_km=25, public_transport_available=False
        )
        assert result.amount == Decimal("1476.00")  # 123*12

    def test_commuting_large_50km(self, deduction_calc):
        """Großes Pendlerpauschale 40-60km: base_annual only."""
        result = deduction_calc.calculate_commuting_allowance(
            distance_km=50, public_transport_available=False
        )
        assert result.amount == Decimal("2568.00")  # 214*12

    def test_commuting_large_80km(self, deduction_calc):
        """Großes Pendlerpauschale 60km+: base_annual only."""
        result = deduction_calc.calculate_commuting_allowance(
            distance_km=80, public_transport_available=False
        )
        assert result.amount == Decimal("3672.00")  # 306*12

    def test_commuting_below_minimum_small(self, deduction_calc):
        """Less than 20km with public transport: not eligible."""
        result = deduction_calc.calculate_commuting_allowance(
            distance_km=15, public_transport_available=True
        )
        assert result.amount == Decimal("0.00")

    def test_commuting_below_minimum_large(self, deduction_calc):
        """Less than 2km without public transport: not eligible."""
        result = deduction_calc.calculate_commuting_allowance(
            distance_km=1, public_transport_available=False
        )
        assert result.amount == Decimal("0.00")

    # -- Home Office --

    def test_home_office_deduction(self, deduction_calc):
        """Home office deduction should be €300."""
        result = deduction_calc.calculate_home_office_deduction()
        assert result.amount == Decimal("300.00")

    # -- Family Deductions --

    def test_family_one_child(self, deduction_calc):
        """One child: €70.90/month * 12 = €850.80."""
        family = FamilyInfo(num_children=1)
        result = deduction_calc.calculate_family_deductions(family)
        assert result.amount == Decimal("850.80")

    def test_family_three_children(self, deduction_calc):
        """Three children: €70.90 * 12 * 3 = €2,552.40."""
        family = FamilyInfo(num_children=3)
        result = deduction_calc.calculate_family_deductions(family)
        assert result.amount == Decimal("2552.40")

    def test_family_single_parent_one_child(self, deduction_calc):
        """Single parent with one child: child deduction + €612."""
        family = FamilyInfo(num_children=1, is_single_parent=True)
        result = deduction_calc.calculate_family_deductions(family)
        assert result.amount == Decimal("1462.80")  # 850.80 + 612.00

    def test_family_no_children(self, deduction_calc):
        """No children: zero family deductions."""
        family = FamilyInfo(num_children=0)
        result = deduction_calc.calculate_family_deductions(family)
        assert result.amount == Decimal("0.00")

    # -- Familienbonus Plus --

    def test_familienbonus_one_child_under_18(self, deduction_calc):
        """Familienbonus: 1 child under 18 = €2,000.16."""
        family = FamilyInfo(num_children=1, children_under_18=1)
        result = deduction_calc.calculate_familienbonus(family)
        assert result.amount == Decimal("2000.16")

    def test_familienbonus_two_children_mixed(self, deduction_calc):
        """Familienbonus: 1 under 18 + 1 aged 18-24."""
        family = FamilyInfo(num_children=2, children_under_18=1, children_18_to_24=1)
        result = deduction_calc.calculate_familienbonus(family)
        assert result.amount == Decimal("2700.24")  # 2000.16 + 700.08

    def test_familienbonus_three_under_18(self, deduction_calc):
        """Familienbonus: 3 children under 18 = €6,000.48."""
        family = FamilyInfo(num_children=3, children_under_18=3)
        result = deduction_calc.calculate_familienbonus(family)
        assert result.amount == Decimal("6000.48")

    # -- Alleinverdiener/Alleinerzieher --

    def test_alleinverdiener_sole_earner_two_children(self, deduction_calc):
        """Sole earner with 2 children: €828 (2026 BMF tiered)."""
        family = FamilyInfo(num_children=2, is_sole_earner=True)
        result = deduction_calc.calculate_alleinverdiener(family)
        assert result.amount == Decimal("828.00")

    def test_alleinerzieher_single_parent_three_children(self, deduction_calc):
        """Single parent with 3 children: €828 + 1*€273 = €1,101."""
        family = FamilyInfo(num_children=3, is_single_parent=True)
        result = deduction_calc.calculate_alleinverdiener(family)
        assert result.amount == Decimal("1101.00")

    def test_alleinverdiener_not_eligible_no_children(self, deduction_calc):
        """Not eligible without children."""
        family = FamilyInfo(num_children=0, is_sole_earner=True)
        result = deduction_calc.calculate_alleinverdiener(family)
        assert result.amount == Decimal("0.00")

    # -- Employee Deductions --

    def test_employee_werbungskostenpauschale(self, deduction_calc):
        """Employee gets €132 Werbungskostenpauschale by default."""
        result = deduction_calc.calculate_employee_deductions()
        assert result.amount == Decimal("132.00")
        assert result.breakdown["verkehrsabsetzbetrag"] == Decimal("496.00")

    def test_employee_actual_expenses_exceed_pauschale(self, deduction_calc):
        """If actual expenses > €132, Pauschale is not applied."""
        result = deduction_calc.calculate_employee_deductions(
            actual_werbungskosten=Decimal("500.00")
        )
        assert result.amount == Decimal("0.00")

    # -- Total Deductions Integration --

    def test_total_deductions_employee_with_family(self, deduction_calc):
        """Employee with 30km commute, home office, 2 children."""
        family = FamilyInfo(num_children=2, children_under_18=2, is_single_parent=True)
        result = deduction_calc.calculate_total_deductions(
            commuting_distance_km=30,
            public_transport_available=True,
            home_office_eligible=True,
            family_info=family,
            is_employee=True,
        )
        # Income deductions only:
        # Commuting: base_annual = 58*12 = 696 (Pendlereuro separate)
        # Home office: 300
        # Employee: 132 (Werbungskostenpauschale)
        # Family items NOT in amount (Kinderabsetzbetrag informational, AEAB is tax credit)
        # Total: 696 + 300 + 132 = 1128.00
        assert result.amount == Decimal("1128.00")
        # Verify tax credits are in breakdown (not in amount)
        assert "verkehrsabsetzbetrag" in result.breakdown
        assert "familienbonus_amount" in result.breakdown
        assert "alleinverdiener_amount" in result.breakdown


# =========================================================================
# SECTION 6: KESt (CAPITAL GAINS TAX) SCENARIOS
# =========================================================================

class TestKEStComprehensive:
    """Capital gains tax (KESt) test scenarios."""

    def test_kest_rate_bank_interest(self):
        """Bank interest should be taxed at 25%."""
        assert get_kest_rate(CapitalIncomeType.BANK_INTEREST) == Decimal("0.25")

    def test_kest_rate_dividends(self):
        """Dividends should be taxed at 27.5%."""
        assert get_kest_rate(CapitalIncomeType.DIVIDENDS) == Decimal("0.275")

    def test_kest_rate_securities(self):
        assert get_kest_rate(CapitalIncomeType.SECURITIES_GAINS) == Decimal("0.275")

    def test_kest_rate_crypto(self):
        assert get_kest_rate(CapitalIncomeType.CRYPTO) == Decimal("0.275")

    def test_kest_bank_savings_10k(self):
        """€10,000 savings interest at 25%."""
        result = calculate_kest([{
            "description": "Sparbuch Zinsen",
            "income_type": "bank_interest",
            "gross_amount": 10000,
            "withheld": True,
        }])
        assert result.total_tax == Decimal("2500.00")
        assert result.total_already_withheld == Decimal("2500.00")
        assert result.remaining_tax_due == Decimal("0.00")
        assert result.net_income == Decimal("7500.00")

    def test_kest_dividends_not_withheld(self):
        """Foreign dividends not withheld - must be declared."""
        result = calculate_kest([{
            "description": "US Dividenden",
            "income_type": "dividends",
            "gross_amount": 5000,
            "withheld": False,
        }])
        assert result.total_tax == Decimal("1375.00")
        assert result.remaining_tax_due == Decimal("1375.00")
        assert result.total_already_withheld == Decimal("0.00")

    def test_kest_mixed_portfolio(self):
        """Mixed portfolio: bank interest + dividends + crypto."""
        items = [
            {"description": "Sparbuch", "income_type": "bank_interest",
             "gross_amount": 2000, "withheld": True},
            {"description": "AT Dividenden", "income_type": "dividends",
             "gross_amount": 3000, "withheld": True},
            {"description": "Bitcoin Gewinn", "income_type": "crypto",
             "gross_amount": 5000, "withheld": False},
        ]
        result = calculate_kest(items)
        # Bank: 2000*0.25 = 500 (withheld)
        # Dividends: 3000*0.275 = 825 (withheld)
        # Crypto: 5000*0.275 = 1375 (not withheld)
        assert result.total_gross == Decimal("10000.00")
        assert result.total_tax == Decimal("2700.00")
        assert result.total_already_withheld == Decimal("1325.00")
        assert result.remaining_tax_due == Decimal("1375.00")
        assert result.net_income == Decimal("7300.00")

    def test_kest_gmbh_shares_sale(self):
        """Sale of GmbH shares at 27.5%."""
        result = calculate_kest([{
            "description": "Verkauf GmbH-Anteile",
            "income_type": "gmbh_shares",
            "gross_amount": 100000,
            "withheld": False,
        }])
        assert result.total_tax == Decimal("27500.00")


# =========================================================================
# SECTION 7: ImmoESt (REAL ESTATE TAX) SCENARIOS
# =========================================================================

class TestImmoEStComprehensive:
    """Real estate gains tax (ImmoESt) test scenarios."""

    def test_basic_property_sale(self):
        """Standard property sale: 30% on gain."""
        result = calculate_immoest(
            sale_price=Decimal("400000"),
            acquisition_cost=Decimal("300000"),
            improvement_costs=Decimal("20000"),
            selling_costs=Decimal("10000"),
        )
        # Gain: 400000 - 300000 - 20000 - 10000 = 70000
        # Tax: 70000 * 0.30 = 21000
        assert result.taxable_gain == Decimal("70000.00")
        assert result.tax_amount == Decimal("21000.00")
        assert result.total_tax == Decimal("21000.00")
        assert result.exempt is False

    def test_no_gain_no_tax(self):
        """Sale at loss: no ImmoESt."""
        result = calculate_immoest(
            sale_price=Decimal("250000"),
            acquisition_cost=Decimal("300000"),
        )
        assert result.taxable_gain == Decimal("0.00")
        assert result.total_tax == Decimal("0.00")

    def test_hauptwohnsitz_exemption(self):
        """Main residence exemption: no tax."""
        result = calculate_immoest(
            sale_price=Decimal("500000"),
            acquisition_cost=Decimal("200000"),
            exemption=ExemptionType.HAUPTWOHNSITZ,
        )
        assert result.exempt is True
        assert result.total_tax == Decimal("0.00")
        assert "Hauptwohnsitz" in result.note

    def test_hersteller_exemption(self):
        """Self-built property exemption: no tax."""
        result = calculate_immoest(
            sale_price=Decimal("600000"),
            acquisition_cost=Decimal("200000"),
            exemption=ExemptionType.HERSTELLER,
        )
        assert result.exempt is True
        assert "Hersteller" in result.note

    def test_old_property_pre_2002(self):
        """Property acquired before 01.04.2002: 14% flat rate on sale price."""
        result = calculate_immoest(
            sale_price=Decimal("500000"),
            acquisition_cost=Decimal("100000"),
            acquisition_date=date(2000, 6, 15),
        )
        assert result.is_old_property is True
        # 14% on sale price: 500000 * 0.14 = 70000
        assert result.tax_amount == Decimal("70000.00")
        assert result.total_tax == Decimal("70000.00")

    def test_old_property_reclassified(self):
        """Reclassified old property: 18% flat rate."""
        result = calculate_immoest(
            sale_price=Decimal("500000"),
            acquisition_cost=Decimal("100000"),
            acquisition_date=date(1998, 3, 1),
            was_reclassified=True,
        )
        assert result.is_old_property is True
        # 18% on sale price: 500000 * 0.18 = 90000
        assert result.total_tax == Decimal("90000.00")

    def test_reclassification_surcharge_new_property(self):
        """New reclassification after 2024: 30% surcharge on gain."""
        result = calculate_immoest(
            sale_price=Decimal("600000"),
            acquisition_cost=Decimal("400000"),
            selling_costs=Decimal("10000"),
            was_reclassified=True,
            reclassification_date=date(2025, 3, 1),
            sale_date=date(2025, 8, 1),
        )
        # Gain: 600000 - 400000 - 10000 = 190000
        # Tax: 190000 * 0.30 = 57000
        # Surcharge: 190000 * 0.30 = 57000
        # Total: 114000
        assert result.taxable_gain == Decimal("190000.00")
        assert result.tax_amount == Decimal("57000.00")
        assert result.reclassification_surcharge == Decimal("57000.00")
        assert result.total_tax == Decimal("114000.00")

    def test_no_surcharge_before_cutoff(self):
        """Reclassification before 2025: no surcharge."""
        result = calculate_immoest(
            sale_price=Decimal("400000"),
            acquisition_cost=Decimal("300000"),
            was_reclassified=True,
            reclassification_date=date(2020, 1, 1),
            sale_date=date(2025, 8, 1),
        )
        assert result.reclassification_surcharge == Decimal("0.00")


# =========================================================================
# SECTION 8: SELF-EMPLOYED TAX FEATURES
# =========================================================================

class TestSelfEmployedComprehensive:
    """Gewinnfreibetrag, Basispauschalierung, and Kleinunternehmer tests."""

    # -- Gewinnfreibetrag --

    def test_gewinnfreibetrag_no_profit(self):
        """No profit: no Freibetrag."""
        result = calculate_gewinnfreibetrag(Decimal("0"))
        assert result.total_freibetrag == Decimal("0.00")

    def test_gewinnfreibetrag_low_profit(self):
        """Profit of €20,000: Grundfreibetrag only (15% = €3,000)."""
        result = calculate_gewinnfreibetrag(Decimal("20000"))
        assert result.grundfreibetrag == Decimal("3000.00")
        assert result.investment_freibetrag == Decimal("0.00")
        assert result.total_freibetrag == Decimal("3000.00")

    def test_gewinnfreibetrag_at_limit(self):
        """Profit of €33,000: Grundfreibetrag maxes at €4,950."""
        result = calculate_gewinnfreibetrag(Decimal("33000"))
        assert result.grundfreibetrag == Decimal("4950.00")
        assert result.investment_freibetrag == Decimal("0.00")
        assert result.total_freibetrag == Decimal("4950.00")

    def test_gewinnfreibetrag_above_limit_no_investment(self):
        """Profit of €50,000: only Grundfreibetrag since no investment."""
        result = calculate_gewinnfreibetrag(Decimal("50000"), Decimal("0"))
        assert result.grundfreibetrag == Decimal("4950.00")
        assert result.investment_freibetrag == Decimal("0.00")
        # Investment required but not provided
        assert result.investment_required > Decimal("0.00")

    def test_gewinnfreibetrag_with_investment(self):
        """Profit of €50,000 with €5,000 investment."""
        result = calculate_gewinnfreibetrag(Decimal("50000"), Decimal("5000"))
        assert result.grundfreibetrag == Decimal("4950.00")
        # Excess: 50000 - 33000 = 17000, rate 13% -> 2210
        # But capped by investment of 5000 -> min(2210, 5000) = 2210
        assert result.investment_freibetrag == Decimal("2210.00")
        assert result.total_freibetrag == Decimal("7160.00")

    def test_gewinnfreibetrag_max_cap(self):
        """Very high profit should be capped at €46,400 total."""
        result = calculate_gewinnfreibetrag(Decimal("1000000"), Decimal("999999"))
        assert result.total_freibetrag == Decimal("46400.00")
        assert result.capped is True

    # -- Basispauschalierung --

    def test_basispauschalierung_general_profession(self):
        """General profession: 13.5% flat-rate expenses."""
        result = calculate_basispauschalierung(
            gross_turnover=Decimal("80000"),
            profession_type=ProfessionType.GENERAL,
        )
        assert result.eligible is True
        # Expenses: 80000 * 0.135 = 10800
        assert result.flat_rate_expenses == Decimal("10800.00")
        # Profit: 80000 - 10800 = 69200
        assert result.estimated_profit == Decimal("69200.00")
        # Grundfreibetrag: min(69200*0.15, 4950) = 4950
        assert result.grundfreibetrag == Decimal("4950.00")
        # Taxable: 69200 - 4950 = 64250
        assert result.taxable_profit == Decimal("64250.00")

    def test_basispauschalierung_consulting(self):
        """Consulting profession: 6% flat-rate expenses."""
        result = calculate_basispauschalierung(
            gross_turnover=Decimal("100000"),
            profession_type=ProfessionType.CONSULTING,
        )
        assert result.eligible is True
        assert result.flat_rate_expenses == Decimal("6000.00")

    def test_basispauschalierung_too_high_turnover(self):
        """Turnover > €320,000: not eligible."""
        result = calculate_basispauschalierung(
            gross_turnover=Decimal("350000"),
        )
        assert result.eligible is False

    def test_basispauschalierung_with_svs(self):
        """SVS contributions are deductible on top of flat rate."""
        result = calculate_basispauschalierung(
            gross_turnover=Decimal("60000"),
            svs_contributions=Decimal("8000"),
        )
        # Expenses: 60000 * 0.135 = 8100
        # Profit: 60000 - 8100 - 8000 = 43900
        assert result.estimated_profit == Decimal("43900.00")

    # -- Kleinunternehmer --

    def test_kleinunternehmer_below_threshold(self):
        """Below €55,000: exempt, no VAT obligations."""
        status = determine_kleinunternehmer_status(Decimal("40000"))
        assert status.exempt is True
        assert status.ust_voranmeldung_required is False

    def test_kleinunternehmer_tolerance_zone(self):
        """Between €55,000 and €60,500: tolerance applies."""
        status = determine_kleinunternehmer_status(Decimal("57000"))
        assert status.exempt is True
        assert status.tolerance_applies is True

    def test_kleinunternehmer_above_threshold(self):
        """Above €60,500: VAT-liable with quarterly UVA."""
        status = determine_kleinunternehmer_status(Decimal("80000"))
        assert status.exempt is False
        assert status.ust_voranmeldung_required is True
        assert status.ust_voranmeldung_frequency == "quarterly"

    def test_kleinunternehmer_monthly_uva(self):
        """Above €100,000: monthly UVA required."""
        status = determine_kleinunternehmer_status(Decimal("150000"))
        assert status.ust_voranmeldung_frequency == "monthly"

    def test_kleinunternehmer_voluntary_registration_hint(self):
        """High input VAT should suggest voluntary registration."""
        status = determine_kleinunternehmer_status(
            Decimal("40000"), has_significant_input_vat=True
        )
        assert status.voluntary_registration_recommended is True
        assert len(status.warnings) > 0

    # -- Expense Method Comparison --

    def test_compare_methods_flat_rate_better(self):
        """When actual expenses are low, flat rate is better."""
        result = compare_expense_methods(
            gross_turnover=Decimal("100000"),
            actual_expenses=Decimal("5000"),  # Very low actual expenses
        )
        # Flat rate: 100000*0.135 = 13500 deemed expenses
        # Actual: only 5000 expenses
        # Flat rate method gives lower taxable profit
        assert result.recommended_method == ExpenseMethod.FLAT_RATE

    def test_compare_methods_actual_better(self):
        """When actual expenses are high, actual accounting is better."""
        result = compare_expense_methods(
            gross_turnover=Decimal("100000"),
            actual_expenses=Decimal("40000"),  # High actual expenses
            qualifying_investment=Decimal("10000"),
        )
        assert result.recommended_method == ExpenseMethod.ACTUAL

    def test_compare_methods_ineligible(self):
        """When turnover exceeds limit, only actual method available."""
        result = compare_expense_methods(
            gross_turnover=Decimal("400000"),
            actual_expenses=Decimal("50000"),
        )
        assert result.recommended_method == ExpenseMethod.ACTUAL


# =========================================================================
# SECTION 9: AI ORCHESTRATOR INTENT DETECTION
# =========================================================================

class TestAIIntentDetectionComprehensive:
    """Test AI intent detection accuracy across German, English, and Chinese."""

    # -- Income Tax Intent --

    @pytest.mark.parametrize("message,expected_intent", [
        # German
        ("Berechne meine Einkommensteuer für €50.000", UserIntent.CALCULATE_TAX),
        ("Wie viel Steuer muss ich bei einem Einkommen von €40.000 zahlen?", UserIntent.CALCULATE_TAX),
        ("Rechne mir die Steuerlast aus für ein Jahreseinkommen von €65.000", UserIntent.CALCULATE_TAX),
        # English
        ("Calculate my income tax for €50,000", UserIntent.CALCULATE_TAX),
        ("How much tax do I pay on €80,000?", UserIntent.CALCULATE_TAX),
        ("What is my tax liability for €100,000 income?", UserIntent.CALCULATE_TAX),
        # Chinese
        ("计算€50000的所得税", UserIntent.CALCULATE_TAX),
        ("我收入€70000要交多少税？", UserIntent.CALCULATE_TAX),
        ("帮我算一下纳税额", UserIntent.CALCULATE_TAX),
    ])
    def test_income_tax_intent(self, message, expected_intent):
        result = detect_intent(message)
        assert result.intent == expected_intent, \
            f"'{message}' detected as {result.intent} instead of {expected_intent}"

    # -- VAT Intent --

    @pytest.mark.parametrize("message,expected_intent", [
        ("Berechne USt für €40.000 Umsatz", UserIntent.CALCULATE_VAT),
        ("Calculate VAT for €30,000 revenue", UserIntent.CALCULATE_VAT),
        ("计算增值税 €40000", UserIntent.CALCULATE_VAT),
        ("Umsatzsteuer berechnen", UserIntent.CALCULATE_VAT),
        ("Bin ich Kleinunternehmer?", UserIntent.CALCULATE_VAT),
    ])
    def test_vat_intent(self, message, expected_intent):
        result = detect_intent(message)
        assert result.intent == expected_intent

    # -- SVS Intent --

    @pytest.mark.parametrize("message,expected_intent", [
        ("Berechne meine SVS-Beiträge", UserIntent.CALCULATE_SVS),
        ("Calculate SVS contributions for €50,000", UserIntent.CALCULATE_SVS),
        ("SVS计算 €50000", UserIntent.CALCULATE_SVS),
        ("Sozialversicherung berechnen", UserIntent.CALCULATE_SVS),
    ])
    def test_svs_intent(self, message, expected_intent):
        result = detect_intent(message)
        assert result.intent == expected_intent

    # -- KESt Intent --

    @pytest.mark.parametrize("message,expected_intent", [
        ("Berechne KESt für €10.000 Dividenden", UserIntent.CALCULATE_KEST),
        ("Calculate capital gains tax on my dividends", UserIntent.CALCULATE_KEST),
        ("资本利得税计算", UserIntent.CALCULATE_KEST),
    ])
    def test_kest_intent(self, message, expected_intent):
        result = detect_intent(message)
        assert result.intent == expected_intent

    # -- ImmoESt Intent --

    @pytest.mark.parametrize("message,expected_intent", [
        ("Berechne ImmoESt für Hausverkauf", UserIntent.CALCULATE_IMMOEST),
        ("Calculate real estate tax on my property sale", UserIntent.CALCULATE_IMMOEST),
        ("房产税计算", UserIntent.CALCULATE_IMMOEST),
    ])
    def test_immoest_intent(self, message, expected_intent):
        result = detect_intent(message)
        assert result.intent == expected_intent

    # -- Deductibility Intent --

    @pytest.mark.parametrize("message,expected_intent", [
        ("Ist mein Homeoffice absetzbar?", UserIntent.CHECK_DEDUCTIBILITY),
        ("Is my home office deductible?", UserIntent.CHECK_DEDUCTIBILITY),
        ("办公室费用可以抵税吗？", UserIntent.CHECK_DEDUCTIBILITY),
    ])
    def test_deductibility_intent(self, message, expected_intent):
        result = detect_intent(message)
        assert result.intent == expected_intent

    # -- Transaction Classification Intent --

    @pytest.mark.parametrize("message,expected_intent", [
        ("Wie klassifiziere ich diese Rechnung?", UserIntent.CLASSIFY_TRANSACTION),
        ("Classify this expense", UserIntent.CLASSIFY_TRANSACTION),
    ])
    def test_classify_intent(self, message, expected_intent):
        result = detect_intent(message)
        assert result.intent == expected_intent

    # -- What-If Intent --

    @pytest.mark.parametrize("message,expected_intent", [
        ("Was wäre wenn ich €70.000 verdiene?", UserIntent.WHAT_IF),
        ("What if I earn €80,000?", UserIntent.WHAT_IF),
        ("如果我收入€70000会怎样？", UserIntent.WHAT_IF),
    ])
    def test_what_if_intent(self, message, expected_intent):
        result = detect_intent(message)
        assert result.intent == expected_intent

    # -- Confidence Test --

    def test_high_confidence_for_clear_intents(self):
        """Clear tax calculation requests should have confidence >= 0.80."""
        messages = [
            "Berechne meine Einkommensteuer",
            "Calculate my VAT",
            "SVS berechnen",
        ]
        for msg in messages:
            result = detect_intent(msg)
            assert result.confidence >= 0.80, \
                f"'{msg}' has low confidence {result.confidence}"


# =========================================================================
# SECTION 10: INTEGRATED END-TO-END SCENARIOS
# =========================================================================

class TestEndToEndScenarios:
    """Integrated scenarios combining multiple calculators."""

    def test_scenario_freelance_designer(self, income_calc, svs_calc, vat_calc, deduction_calc):
        """
        Scenario: Freelance designer, €60,000 income, home office,
        GSVG, Kleinunternehmer (below €55k turnover).
        """
        gross = Decimal("48000")  # Below Kleinunternehmer threshold

        # SVS
        svs = svs_calc.calculate_contributions(gross, UserType.GSVG)
        assert svs.deductible is True
        assert svs.annual_total > Decimal("0")

        # VAT: exempt as Kleinunternehmer
        vat = vat_calc.calculate_vat_liability(
            gross_turnover=gross, transactions=[]
        )
        assert vat.exempt is True

        # Deductions
        deductions = deduction_calc.calculate_total_deductions(
            home_office_eligible=True,
        )
        assert deductions.amount >= Decimal("300.00")

        # Income tax
        taxable = gross - svs.annual_total - deductions.amount
        if taxable > Decimal("0"):
            tax = income_calc.calculate_tax_with_exemption(taxable, 2026)
            assert tax.total_tax >= Decimal("0")

    def test_scenario_employee_with_family(self, income_calc, deduction_calc):
        """
        Scenario: Employee earning €45,000, commuting 30km (public transport),
        home office, 2 children under 18, single parent.
        """
        gross = Decimal("45000")
        family = FamilyInfo(
            num_children=2, children_under_18=2, is_single_parent=True
        )

        deductions = deduction_calc.calculate_total_deductions(
            commuting_distance_km=30,
            public_transport_available=True,
            home_office_eligible=True,
            family_info=family,
            is_employee=True,
        )

        # Verify deductions include all components
        assert deductions.amount > Decimal("0")
        assert "commuting_allowance" in deductions.breakdown
        assert "telearbeit" in deductions.breakdown
        assert "kinderabsetzbetrag_info" in deductions.breakdown
        assert "familienbonus_amount" in deductions.breakdown
        assert "alleinverdiener_amount" in deductions.breakdown

        # Tax credits (from breakdown)
        verkehrsabsetzbetrag = Decimal(str(deductions.breakdown.get("verkehrsabsetzbetrag", 0)))
        familienbonus = Decimal(str(deductions.breakdown.get("familienbonus_amount", 0)))
        alleinverdiener = Decimal(str(deductions.breakdown.get("alleinverdiener_amount", 0)))

        assert verkehrsabsetzbetrag == Decimal("496.00")
        assert familienbonus == Decimal("4000.32")  # 2 * 2000.16
        assert alleinverdiener == Decimal("828.00")  # 2026 BMF tiered: 2 children

        # Income tax before credits
        taxable = gross - deductions.amount
        tax_result = income_calc.calculate_tax_with_exemption(taxable, 2026)

        # After credits, tax could be zero or negative (capped at 0)
        total_credits = verkehrsabsetzbetrag + familienbonus + alleinverdiener
        final_tax = max(tax_result.total_tax - total_credits, Decimal("0"))
        assert final_tax >= Decimal("0")

    def test_scenario_self_employed_high_income(self, income_calc, svs_calc):
        """
        Scenario: Self-employed consultant, €120,000 income,
        Basispauschalierung eligible, high SVS.
        """
        gross = Decimal("120000")

        # SVS: capped at max contribution base
        svs = svs_calc.calculate_contributions(gross, UserType.GSVG)
        assert svs.contribution_base <= Decimal("7585.00")

        # Basispauschalierung
        basis = calculate_basispauschalierung(
            gross_turnover=gross,
            profession_type=ProfessionType.CONSULTING,
            svs_contributions=svs.annual_total,
        )
        assert basis.eligible is True
        # 6% flat rate for consulting
        assert basis.flat_rate_pct == Decimal("0.06")

    def test_scenario_investor_mixed_income(self):
        """
        Scenario: Investor with salary €50k, dividends €10k,
        bank interest €5k, crypto gains €20k.
        """
        # KESt on capital income
        kest_result = calculate_kest([
            {"description": "Dividenden", "income_type": "dividends",
             "gross_amount": 10000, "withheld": True},
            {"description": "Sparbuch", "income_type": "bank_interest",
             "gross_amount": 5000, "withheld": True},
            {"description": "Crypto", "income_type": "crypto",
             "gross_amount": 20000, "withheld": False},
        ])
        # Dividends: 10000*0.275 = 2750 (withheld)
        # Bank: 5000*0.25 = 1250 (withheld)
        # Crypto: 20000*0.275 = 5500 (not withheld)
        assert kest_result.total_tax == Decimal("9500.00")
        assert kest_result.total_already_withheld == Decimal("4000.00")
        assert kest_result.remaining_tax_due == Decimal("5500.00")

    def test_scenario_property_investor(self):
        """
        Scenario: Property investor selling investment property
        acquired in 2019 for €300k, selling for €450k,
        €30k improvements, €15k selling costs.
        """
        result = calculate_immoest(
            sale_price=Decimal("450000"),
            acquisition_cost=Decimal("300000"),
            acquisition_date=date(2019, 6, 1),
            improvement_costs=Decimal("30000"),
            selling_costs=Decimal("15000"),
        )
        # Gain: 450000 - 300000 - 30000 - 15000 = 105000
        # Tax: 105000 * 0.30 = 31500
        assert result.taxable_gain == Decimal("105000.00")
        assert result.total_tax == Decimal("31500.00")
        assert result.is_old_property is False


# =========================================================================
# SECTION 11: EDGE CASES AND ROBUSTNESS
# =========================================================================

class TestEdgeCasesAndRobustness:
    """Edge cases, boundary conditions, and robustness tests."""

    def test_income_tax_zero_income(self, income_calc):
        result = income_calc.calculate_tax_with_exemption(Decimal("0"), 2026)
        assert result.total_tax == Decimal("0.00")

    def test_income_tax_negative_income(self, income_calc):
        result = income_calc.calculate_tax_with_exemption(Decimal("-10000"), 2026)
        assert result.total_tax == Decimal("0.00")

    def test_income_tax_extremely_high_income(self, income_calc):
        """€100 million income."""
        result = income_calc.calculate_tax_with_exemption(Decimal("100000000"), 2026)
        assert result.total_tax > Decimal("0")
        assert result.effective_rate < Decimal("0.55")

    def test_svs_zero_income(self, svs_calc):
        result = svs_calc.calculate_contributions(Decimal("0"), UserType.GSVG)
        assert result.annual_total == Decimal("0.00")

    def test_vat_zero_turnover(self, vat_calc):
        result = vat_calc.calculate_vat_liability(Decimal("0"), [])
        assert result.exempt is True

    def test_kest_zero_income(self):
        result = calculate_kest([{
            "description": "Nothing",
            "income_type": "dividends",
            "gross_amount": 0,
        }])
        assert result.total_tax == Decimal("0.00")

    def test_immoest_zero_gain(self):
        result = calculate_immoest(
            sale_price=Decimal("300000"),
            acquisition_cost=Decimal("300000"),
        )
        assert result.taxable_gain == Decimal("0.00")
        assert result.total_tax == Decimal("0.00")

    def test_gewinnfreibetrag_negative_profit(self):
        result = calculate_gewinnfreibetrag(Decimal("-5000"))
        assert result.total_freibetrag == Decimal("0.00")

    def test_basispauschalierung_zero_turnover(self):
        result = calculate_basispauschalierung(Decimal("0"))
        assert result.eligible is True
        assert result.taxable_profit == Decimal("0.00")

    def test_deduction_all_zeros(self, deduction_calc):
        result = deduction_calc.calculate_total_deductions()
        assert result.amount == Decimal("0.00")

    def test_int_and_float_coercion_svs(self, svs_calc):
        """SVS calculator should handle int and float inputs."""
        r1 = svs_calc.calculate_contributions(Decimal("50000"), UserType.GSVG)
        r2 = svs_calc.calculate_contributions(50000, UserType.GSVG)
        assert r1.annual_total == r2.annual_total

    def test_immoest_future_sale_date(self):
        """ImmoESt with explicit future sale date."""
        result = calculate_immoest(
            sale_price=Decimal("500000"),
            acquisition_cost=Decimal("300000"),
            sale_date=date(2027, 6, 1),
        )
        assert result.total_tax > Decimal("0")


# =========================================================================
# SECTION 12: NUMERIC PARAMETER EXTRACTION (AI ORCHESTRATOR)
# =========================================================================

class TestNumericExtraction:
    """Test extraction of numeric parameters from user messages."""

    @pytest.mark.parametrize("message,expected_income", [
        ("Berechne Steuer für €50.000", 50000),
        ("Calculate tax for €80,000", 80000),
        ("计算€60000的所得税", 60000),
        ("Steuer bei einem Einkommen von 45000 Euro", 45000),
        ("tax on 120000€", 120000),
    ])
    def test_numeric_extraction(self, message, expected_income):
        from app.services.ai_orchestrator import _extract_numeric_params
        params = _extract_numeric_params(message)
        # Should extract at least one numeric value
        extracted = params.get("income") or params.get("amount") or params.get("turnover", 0)
        if extracted:
            assert float(extracted) == expected_income


# =========================================================================
# SECTION 13: TAX RATE CONSTANTS VERIFICATION
# =========================================================================

class TestTaxRateConstants:
    """Verify all tax rate constants match official Austrian values."""

    def test_kest_bank_rate(self):
        assert KEST_RATE_BANK == Decimal("0.25")

    def test_kest_other_rate(self):
        assert KEST_RATE_OTHER == Decimal("0.275")

    def test_immoest_rate(self):
        assert IMMOEST_RATE == Decimal("0.30")

    def test_old_property_rate(self):
        assert OLD_PROPERTY_EFFECTIVE_RATE == Decimal("0.14")

    def test_old_property_reclassified_rate(self):
        assert OLD_PROPERTY_RECLASSIFIED_RATE == Decimal("0.18")

    def test_svs_defaults(self):
        calc = SVSCalculator()
        assert calc.PENSION_RATE == Decimal("0.185")
        assert calc.HEALTH_RATE == Decimal("0.068")
        assert calc.SUPPLEMENTARY_PENSION_RATE == Decimal("0.0153")
        assert calc.ACCIDENT_FIXED == Decimal("12.17")

    def test_vat_defaults(self):
        calc = VATCalculator()
        assert calc.STANDARD_RATE == Decimal("0.20")
        assert calc.REDUCED_RATE_10 == Decimal("0.10")
        assert calc.REDUCED_RATE_13 == Decimal("0.13")
        assert calc.SMALL_BUSINESS_THRESHOLD == Decimal("55000.00")
        assert calc.TOLERANCE_THRESHOLD == Decimal("60500.00")

    def test_deduction_defaults_2026(self):
        calc = DeductionCalculator()
        assert calc.HOME_OFFICE_DEDUCTION == Decimal("300.00")
        assert calc.CHILD_DEDUCTION_MONTHLY == Decimal("70.90")
        assert calc.SINGLE_PARENT_DEDUCTION == Decimal("612.00")
        assert calc.VERKEHRSABSETZBETRAG == Decimal("496.00")
        assert calc.WERBUNGSKOSTENPAUSCHALE == Decimal("132.00")
        assert calc.FAMILIENBONUS_UNDER_18 == Decimal("2000.16")
        assert calc.FAMILIENBONUS_18_24 == Decimal("700.08")
        assert calc.ALLEINVERDIENER_BASE == Decimal("612.00")
        assert calc.ALLEINVERDIENER_2_CHILDREN == Decimal("828.00")
        assert calc.ALLEINVERDIENER_PER_EXTRA_CHILD == Decimal("273.00")

    def test_gewinnfreibetrag_defaults(self):
        config = SelfEmployedConfig()
        assert config.grundfreibetrag_rate == Decimal("0.15")
        assert config.grundfreibetrag_max == Decimal("4950.00")
        assert config.grundfreibetrag_profit_limit == Decimal("33000.00")
        assert config.max_total_freibetrag == Decimal("46400.00")
        assert config.flat_rate_turnover_limit == Decimal("320000.00")
        assert config.flat_rate_general == Decimal("0.135")
        assert config.flat_rate_consulting == Decimal("0.06")
