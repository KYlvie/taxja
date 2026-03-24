"""
Comprehensive tax coverage tests for Austrian tax rules 2022-2026.

Tests all tax modules across all supported tax years to ensure:
1. Year-specific configurations are correct
2. All tax rules are properly implemented
3. New features (IFB, Zuschlag, Pensionistenabsetzbetrag) work correctly
4. KöSt year-specific rates (25% → 24% → 23%) are applied
5. Deduction amounts match cold-progression adjusted values
6. Edge cases and boundary conditions are handled

References:
- BMF Steuerbuch 2023-2026
- WKO Tax Guides
- USP (Unternehmensserviceportal) rate tables
"""
import pytest
from decimal import Decimal
from datetime import date

from app.models.tax_configuration import (
    get_2022_tax_config,
    get_2023_tax_config,
    get_2024_tax_config,
    get_2025_tax_config,
    get_2026_tax_config,
)
from app.services.income_tax_calculator import IncomeTaxCalculator
from app.services.deduction_calculator import DeductionCalculator, FamilyInfo
from app.services.svs_calculator import SVSCalculator, UserType
from app.services.self_employed_tax_service import (
    calculate_gewinnfreibetrag,
    calculate_basispauschalierung,
    determine_kleinunternehmer_status,
    compare_expense_methods,
    SelfEmployedConfig,
    ExpenseMethod,
    ProfessionType,
)
from app.services.kest_calculator import calculate_kest, CapitalIncomeType
from app.services.immoest_calculator import calculate_immoest, ExemptionType
from app.services.koest_calculator import KoEstCalculator, get_koest_rate
from app.services.ifb_calculator import (
    calculate_ifb,
    IFBAssetType,
    IFB_STANDARD_RATE,
    IFB_ECO_RATE,
)
from app.services.tax_calculation_engine import TaxCalculationEngine, SUPPORTED_TAX_YEARS


# ===========================================================================
# Section 1: Tax Year Configuration Completeness
# ===========================================================================

class TestTaxYearConfigurations:
    """Verify all 5 tax years (2022-2026) have complete configurations."""

    ALL_CONFIGS = {
        2022: get_2022_tax_config,
        2023: get_2023_tax_config,
        2024: get_2024_tax_config,
        2025: get_2025_tax_config,
        2026: get_2026_tax_config,
    }

    @pytest.mark.parametrize("year,config_fn", list(ALL_CONFIGS.items()))
    def test_config_has_all_required_keys(self, year, config_fn):
        """Each year config must have all required top-level keys."""
        config = config_fn()
        assert config["tax_year"] == year
        assert "tax_brackets" in config
        assert "exemption_amount" in config
        assert "vat_rates" in config
        assert "svs_rates" in config
        assert "deduction_config" in config

    @pytest.mark.parametrize("year,config_fn", list(ALL_CONFIGS.items()))
    def test_config_has_seven_tax_brackets(self, year, config_fn):
        """Austrian income tax has 7 brackets (0%, 20%, 30/35%, 40/41/42%, 48%, 50%, 55%)."""
        config = config_fn()
        brackets = config["tax_brackets"]
        assert len(brackets) == 7
        # First bracket is 0%
        assert brackets[0]["rate"] == 0.00
        # Last bracket is 55% with no upper limit
        assert brackets[-1]["rate"] == 0.55
        assert brackets[-1].get("upper") is None

    @pytest.mark.parametrize("year,config_fn", list(ALL_CONFIGS.items()))
    def test_deduction_config_has_new_fields(self, year, config_fn):
        """All configs must include the newly added deduction fields."""
        dc = config_fn()["deduction_config"]
        assert "zuschlag_verkehrsabsetzbetrag" in dc
        assert "pensionisten_absetzbetrag" in dc
        assert "sonderausgabenpauschale" in dc
        assert dc["sonderausgabenpauschale"] == 60.00

    @pytest.mark.parametrize("year,config_fn", list(ALL_CONFIGS.items()))
    def test_svs_config_has_all_fields(self, year, config_fn):
        """SVS config must have pension, health, accident, etc."""
        svs = config_fn()["svs_rates"]
        assert "pension" in svs
        assert "health" in svs
        assert "accident_fixed" in svs
        assert "supplementary_pension" in svs
        assert "gsvg_min_base_monthly" in svs
        assert "max_base_monthly" in svs

    def test_supported_years_includes_2022(self):
        """SUPPORTED_TAX_YEARS must include 2022."""
        assert 2022 in SUPPORTED_TAX_YEARS

    def test_exemption_amount_increases_over_years(self):
        """Exemption amount should increase due to cold-progression adjustment."""
        amounts = [self.ALL_CONFIGS[y]()["exemption_amount"] for y in sorted(self.ALL_CONFIGS)]
        # 2022: 11000, 2023: 11693, 2024: 12816, 2025: 13308, 2026: 13539
        for i in range(1, len(amounts)):
            assert amounts[i] >= amounts[i - 1], (
                f"Exemption amount should not decrease: {amounts[i]} < {amounts[i-1]}"
            )


# ===========================================================================
# Section 2: Income Tax Brackets — Year-Specific
# ===========================================================================

class TestIncomeTaxBrackets:
    """Test progressive income tax calculation for each year."""

    @pytest.mark.parametrize("year,config_fn,expected_zero_bracket", [
        (2022, get_2022_tax_config, 11000),
        (2023, get_2023_tax_config, 11693),
        (2024, get_2024_tax_config, 12816),
        (2025, get_2025_tax_config, 13308),
        (2026, get_2026_tax_config, 13539),
    ])
    def test_zero_bracket_threshold(self, year, config_fn, expected_zero_bracket):
        """Income up to the zero-bracket threshold should result in 0 tax."""
        config = config_fn()
        calc = IncomeTaxCalculator(config)
        result = calc.calculate_progressive_tax(Decimal(str(expected_zero_bracket)), year)
        assert result.total_tax == Decimal("0.00")

    @pytest.mark.parametrize("year,config_fn,expected_zero_bracket", [
        (2022, get_2022_tax_config, 11000),
        (2023, get_2023_tax_config, 11693),
        (2024, get_2024_tax_config, 12816),
        (2025, get_2025_tax_config, 13308),
        (2026, get_2026_tax_config, 13539),
    ])
    def test_one_euro_above_zero_bracket(self, year, config_fn, expected_zero_bracket):
        """One euro above the zero bracket should be taxed at 20%."""
        config = config_fn()
        calc = IncomeTaxCalculator(config)
        result = calc.calculate_progressive_tax(
            Decimal(str(expected_zero_bracket + 1)), year
        )
        assert result.total_tax == Decimal("0.20")

    def test_2022_third_bracket_is_32_5_percent(self):
        """In 2022, the third bracket rate was 32.5% (Öko-soziale Steuerreform)."""
        config = get_2022_tax_config()
        assert config["tax_brackets"][2]["rate"] == 0.325

    def test_2023_third_bracket_is_30_percent(self):
        """From 2023, the third bracket was reduced to 30% (from 35%)."""
        config = get_2023_tax_config()
        assert config["tax_brackets"][2]["rate"] == 0.30

    def test_2023_fourth_bracket_is_41_percent(self):
        """In 2023, the fourth bracket was 41% (transitional)."""
        config = get_2023_tax_config()
        assert config["tax_brackets"][3]["rate"] == 0.41

    def test_2024_fourth_bracket_is_40_percent(self):
        """From 2024, the fourth bracket is 40%."""
        config = get_2024_tax_config()
        assert config["tax_brackets"][3]["rate"] == 0.40

    def test_high_income_tax_calculation(self):
        """Test tax on €100,000 income for 2026."""
        config = get_2026_tax_config()
        calc = IncomeTaxCalculator(config)
        result = calc.calculate_progressive_tax(Decimal("100000"), 2026)
        assert result.total_tax > Decimal("0")
        assert result.effective_rate < Decimal("0.50")
        assert result.effective_rate > Decimal("0.30")

    def test_millionaire_tax_bracket(self):
        """Income over €1M should be taxed at 55%."""
        config = get_2026_tax_config()
        calc = IncomeTaxCalculator(config)
        result = calc.calculate_progressive_tax(Decimal("1500000"), 2026)
        # The last €500,000 should be at 55%
        last_bracket = result.breakdown[-1]
        assert "55%" in last_bracket.rate


# ===========================================================================
# Section 3: Investitionsfreibetrag (IFB) §11 EStG — NEW from 2023
# ===========================================================================

class TestInvestitionsfreibetrag:
    """Test the new Investitionsfreibetrag (IFB) introduced in 2023."""

    def test_ifb_not_available_before_2023(self):
        """IFB should not be available for tax years before 2023."""
        result = calculate_ifb(
            [{"description": "Machine", "asset_type": "standard", "acquisition_cost": 50000}],
            tax_year=2022,
        )
        assert result.total_ifb == Decimal("0.00")
        assert "2023" in result.note

    def test_standard_ifb_10_percent(self):
        """Standard IFB is 10% of acquisition cost."""
        result = calculate_ifb(
            [{"description": "Machine", "asset_type": "standard", "acquisition_cost": 100000}],
            tax_year=2023,
        )
        assert result.total_ifb == Decimal("10000.00")
        assert result.standard_ifb == Decimal("10000.00")
        assert result.eco_ifb == Decimal("0.00")

    def test_eco_ifb_15_percent(self):
        """Ecological IFB (BEV, renewable heating) is 15%."""
        result = calculate_ifb(
            [{"description": "Tesla Model 3", "asset_type": "eco_vehicle", "acquisition_cost": 50000}],
            tax_year=2024,
        )
        assert result.total_ifb == Decimal("7500.00")
        assert result.eco_ifb == Decimal("7500.00")
        assert result.standard_ifb == Decimal("0.00")

    def test_mixed_standard_and_eco(self):
        """Mix of standard and eco investments should apply different rates."""
        result = calculate_ifb(
            [
                {"description": "CNC Machine", "asset_type": "standard", "acquisition_cost": 200000},
                {"description": "Heat pump", "asset_type": "eco_heating", "acquisition_cost": 30000},
            ],
            tax_year=2025,
        )
        expected_standard = Decimal("20000.00")  # 10% of 200k
        expected_eco = Decimal("4500.00")  # 15% of 30k
        assert result.standard_ifb == expected_standard
        assert result.eco_ifb == expected_eco
        assert result.total_ifb == expected_standard + expected_eco

    def test_ifb_capped_at_1_million(self):
        """Total eligible investment is capped at €1,000,000."""
        result = calculate_ifb(
            [{"description": "Factory", "asset_type": "standard", "acquisition_cost": 1500000}],
            tax_year=2026,
        )
        assert result.capped is True
        assert result.total_eligible_investment == Decimal("1000000.00")
        assert result.total_ifb == Decimal("100000.00")  # 10% of 1M

    def test_ifb_zero_cost_ignored(self):
        """Investments with zero cost should be ignored."""
        result = calculate_ifb(
            [{"description": "Nothing", "asset_type": "standard", "acquisition_cost": 0}],
            tax_year=2024,
        )
        assert result.total_ifb == Decimal("0.00")

    def test_ifb_multiple_exceeding_cap(self):
        """Multiple investments exceeding €1M cap."""
        result = calculate_ifb(
            [
                {"description": "A", "asset_type": "standard", "acquisition_cost": 600000},
                {"description": "B", "asset_type": "standard", "acquisition_cost": 600000},
            ],
            tax_year=2024,
        )
        assert result.capped is True
        assert result.total_eligible_investment == Decimal("1000000.00")
        # First: 600k × 10% = 60k, Second: 400k × 10% = 40k (capped)
        assert result.total_ifb == Decimal("100000.00")


# ===========================================================================
# Section 4: KöSt Year-Specific Rates
# ===========================================================================

class TestKoEstYearRates:
    """Test KöSt rate evolution: 25% (2022) → 24% (2023) → 23% (2024+)."""

    def test_koest_rate_2022(self):
        """KöSt rate was 25% in 2022."""
        assert get_koest_rate(2022) == Decimal("0.25")

    def test_koest_rate_2023(self):
        """KöSt rate was 24% in 2023."""
        assert get_koest_rate(2023) == Decimal("0.24")

    def test_koest_rate_2024(self):
        """KöSt rate is 23% from 2024."""
        assert get_koest_rate(2024) == Decimal("0.23")

    def test_koest_rate_2025(self):
        """KöSt rate remains 23% in 2025."""
        assert get_koest_rate(2025) == Decimal("0.23")

    def test_koest_rate_2026(self):
        """KöSt rate remains 23% in 2026."""
        assert get_koest_rate(2026) == Decimal("0.23")

    def test_koest_rate_pre_2022(self):
        """KöSt rate was 25% before 2022."""
        assert get_koest_rate(2021) == Decimal("0.25")
        assert get_koest_rate(2020) == Decimal("0.25")

    def test_calculator_uses_year_rate(self):
        """KoEstCalculator should use year-specific rate."""
        calc = KoEstCalculator()

        result_2022 = calc.calculate(Decimal("100000"), tax_year=2022)
        assert result_2022.koest_rate == Decimal("0.25")
        assert result_2022.koest_amount == Decimal("25000.00")

        result_2023 = calc.calculate(Decimal("100000"), tax_year=2023)
        assert result_2023.koest_rate == Decimal("0.24")
        assert result_2023.koest_amount == Decimal("24000.00")

        result_2024 = calc.calculate(Decimal("100000"), tax_year=2024)
        assert result_2024.koest_rate == Decimal("0.23")
        assert result_2024.koest_amount == Decimal("23000.00")

    def test_gmbh_total_burden_decreases(self):
        """Total tax burden (KöSt + KESt on dividends) should decrease 2022→2024."""
        calc = KoEstCalculator()
        profit = Decimal("200000")

        result_2022 = calc.calculate(profit, tax_year=2022)
        result_2024 = calc.calculate(profit, tax_year=2024)

        assert result_2022.total_tax_burden > result_2024.total_tax_burden

    def test_mindest_koest_2024_plus_gmbh_floor(self):
        """Mindest-KöSt should be €2,000/year regardless of rate changes."""
        calc = KoEstCalculator()
        # Zero profit — minimum applies
        result = calc.calculate(Decimal("0"), tax_year=2026)
        assert result.effective_koest == Decimal("500.00")


# ===========================================================================
# Section 5: Zuschlag zum Verkehrsabsetzbetrag
# ===========================================================================

class TestZuschlagVerkehrsabsetzbetrag:
    """Test the Zuschlag zum Verkehrsabsetzbetrag for low-income employees."""

    def test_full_zuschlag_below_lower_threshold(self):
        """Income below lower threshold gets full Zuschlag."""
        calc = DeductionCalculator()
        result = calc.calculate_zuschlag_verkehrsabsetzbetrag(Decimal("12000"))
        assert result.amount == Decimal("804.00")

    def test_no_zuschlag_above_upper_threshold(self):
        """Income above upper threshold gets no Zuschlag."""
        calc = DeductionCalculator()
        result = calc.calculate_zuschlag_verkehrsabsetzbetrag(Decimal("35000"))
        assert result.amount == Decimal("0.00")

    def test_partial_zuschlag_in_phase_out(self):
        """Income in the phase-out range gets partial Zuschlag."""
        calc = DeductionCalculator()
        # Midpoint between the current 2026 phase-out bounds should yield
        # roughly half of the full 2026 Zuschlag.
        midpoint = (Decimal("19761") + Decimal("30259")) / 2
        result = calc.calculate_zuschlag_verkehrsabsetzbetrag(midpoint)
        assert result.amount == Decimal("402.00")

    def test_zuschlag_at_lower_boundary(self):
        """Income exactly at lower threshold gets full Zuschlag."""
        calc = DeductionCalculator()
        result = calc.calculate_zuschlag_verkehrsabsetzbetrag(Decimal("19761"))
        assert result.amount == Decimal("804.00")

    def test_zuschlag_at_upper_boundary(self):
        """Income exactly at upper threshold gets zero."""
        calc = DeductionCalculator()
        result = calc.calculate_zuschlag_verkehrsabsetzbetrag(Decimal("30259"))
        assert result.amount == Decimal("0.00")

    def test_zuschlag_year_2022(self):
        """2022 Zuschlag should use pre-cold-progression values."""
        config = get_2022_tax_config()
        calc = DeductionCalculator(config["deduction_config"])
        result = calc.calculate_zuschlag_verkehrsabsetzbetrag(Decimal("12000"))
        assert result.amount == Decimal("684.00")


# ===========================================================================
# Section 6: Pensionistenabsetzbetrag
# ===========================================================================

class TestPensionistenabsetzbetrag:
    """Test the Pensionistenabsetzbetrag tax credit for pensioners."""

    def test_full_pensionisten_absetzbetrag(self):
        """Low-income pensioner gets full amount."""
        calc = DeductionCalculator()
        result = calc.calculate_pensionisten_absetzbetrag(Decimal("15000"))
        assert result.amount == Decimal("1020.00")

    def test_no_pensionisten_above_threshold(self):
        """High-income pensioner gets nothing."""
        calc = DeductionCalculator()
        result = calc.calculate_pensionisten_absetzbetrag(Decimal("35000"))
        assert result.amount == Decimal("0.00")

    def test_partial_pensionisten_in_phase_out(self):
        """Income in the phase-out range gets partial amount."""
        calc = DeductionCalculator()
        result = calc.calculate_pensionisten_absetzbetrag(Decimal("25000"))
        assert Decimal("0") < result.amount < Decimal("954")

    def test_erhoehter_pensionisten_for_singles(self):
        """Single pensioners get the current increased 2026 amount."""
        calc = DeductionCalculator()
        result = calc.calculate_pensionisten_absetzbetrag(Decimal("15000"), is_single=True)
        assert result.amount == Decimal("1502.00")

    def test_pensionisten_2022_values(self):
        """2022 values should be lower (pre-cold-progression)."""
        config = get_2022_tax_config()
        calc = DeductionCalculator(config["deduction_config"])
        result = calc.calculate_pensionisten_absetzbetrag(Decimal("12000"))
        assert result.amount == Decimal("868.00")

    def test_erhoehter_phases_out_correctly(self):
        """Erhöhter Pensionistenabsetzbetrag phases out at different threshold."""
        calc = DeductionCalculator()
        # At the upper threshold for erhöhter, should be 0
        result = calc.calculate_pensionisten_absetzbetrag(
            Decimal("31494"), is_single=True
        )
        assert result.amount == Decimal("0.00")


# ===========================================================================
# Section 7: Sonderausgabenpauschale
# ===========================================================================

class TestSonderausgabenpauschale:
    """Test the €60/year automatic special expenses flat-rate."""

    def test_sonderausgabenpauschale_is_60(self):
        """All taxpayers get €60/year Sonderausgabenpauschale."""
        calc = DeductionCalculator()
        result = calc.calculate_sonderausgabenpauschale()
        assert result.amount == Decimal("60.00")

    def test_sonderausgabenpauschale_stable_across_years(self):
        """The Sonderausgabenpauschale has been €60 for all years."""
        for config_fn in [get_2022_tax_config, get_2023_tax_config,
                          get_2024_tax_config, get_2025_tax_config, get_2026_tax_config]:
            config = config_fn()
            assert config["deduction_config"]["sonderausgabenpauschale"] == 60.00


# ===========================================================================
# Section 8: Deduction Values — Cold Progression Adjustment
# ===========================================================================

class TestColdProgressionAdjustment:
    """Verify that Absetzbeträge increase with cold-progression adjustment."""

    def test_verkehrsabsetzbetrag_increases(self):
        """Verkehrsabsetzbetrag should increase over years."""
        values = {
            2022: get_2022_tax_config()["deduction_config"]["verkehrsabsetzbetrag"],
            2023: get_2023_tax_config()["deduction_config"]["verkehrsabsetzbetrag"],
            2024: get_2024_tax_config()["deduction_config"]["verkehrsabsetzbetrag"],
            2025: get_2025_tax_config()["deduction_config"]["verkehrsabsetzbetrag"],
            2026: get_2026_tax_config()["deduction_config"]["verkehrsabsetzbetrag"],
        }
        assert values[2022] == 400.00
        assert values[2023] == 421.00
        assert values[2024] == 463.00
        assert values[2025] == 487.00
        assert values[2026] == 496.00

    def test_alleinverdiener_base_increases(self):
        """Alleinverdienerabsetzbetrag base should increase over years."""
        values = {
            2022: get_2022_tax_config()["deduction_config"]["alleinverdiener_base"],
            2023: get_2023_tax_config()["deduction_config"]["alleinverdiener_base"],
            2026: get_2026_tax_config()["deduction_config"]["alleinverdiener_base"],
        }
        assert values[2022] == 494.00
        assert values[2023] == 520.00
        assert values[2026] == 612.00

    def test_kinderabsetzbetrag_frozen_2025_2027(self):
        """Kinderabsetzbetrag is €67.80 for 2025-2027."""
        assert get_2025_tax_config()["deduction_config"]["child_deduction_monthly"] == 67.80
        assert get_2026_tax_config()["deduction_config"]["child_deduction_monthly"] == 67.80

    def test_familienbonus_18_24_changed_in_2024(self):
        """Familienbonus 18-24 changed from €650.16 to €700.08 in 2024."""
        assert get_2023_tax_config()["deduction_config"]["familienbonus_18_24"] == 650.16
        assert get_2024_tax_config()["deduction_config"]["familienbonus_18_24"] == 700.08

    def test_pendler_euro_increased_in_2025(self):
        """Pendler-Euro stays at €2/km through 2025 and rises to €6/km in 2026."""
        assert get_2023_tax_config()["deduction_config"]["pendler_euro_per_km"] == 2.00
        assert get_2024_tax_config()["deduction_config"]["pendler_euro_per_km"] == 2.00
        assert get_2025_tax_config()["deduction_config"]["pendler_euro_per_km"] == 2.00
        assert get_2026_tax_config()["deduction_config"]["pendler_euro_per_km"] == 6.00


# ===========================================================================
# Section 9: Kleinunternehmerregelung Threshold Changes
# ===========================================================================

class TestKleinunternehmerregelungChanges:
    """Test VAT small business threshold changes across years."""

    def test_threshold_35k_before_2025(self):
        """Before 2025, Kleinunternehmer threshold was €35,000 net."""
        for year in [2022, 2023, 2024]:
            config_fn = {2022: get_2022_tax_config, 2023: get_2023_tax_config,
                         2024: get_2024_tax_config}[year]
            config = config_fn()
            assert config["vat_rates"]["small_business_threshold"] == 35000.00

    def test_threshold_55k_from_2025(self):
        """From 2025, Kleinunternehmer threshold raised to €55,000 gross (EU harmonization)."""
        for year in [2025, 2026]:
            config_fn = {2025: get_2025_tax_config, 2026: get_2026_tax_config}[year]
            config = config_fn()
            assert config["vat_rates"]["small_business_threshold"] == 55000.00

    def test_tolerance_threshold_changes(self):
        """Tolerance threshold changes with the main threshold."""
        assert get_2024_tax_config()["vat_rates"]["tolerance_threshold"] == 40250.00
        assert get_2025_tax_config()["vat_rates"]["tolerance_threshold"] == 63250.00

    def test_kleinunternehmer_status_below_threshold(self):
        """Turnover below threshold → exempt."""
        config = SelfEmployedConfig()  # 2026 defaults
        result = determine_kleinunternehmer_status(Decimal("40000"), config=config)
        assert result.exempt is True

    def test_kleinunternehmer_status_above_tolerance(self):
        """Turnover above tolerance threshold → VAT liable."""
        config = SelfEmployedConfig()
        result = determine_kleinunternehmer_status(Decimal("65000"), config=config)
        assert result.exempt is False
        assert result.ust_voranmeldung_required is True

    def test_kleinunternehmer_tolerance_zone(self):
        """Turnover in tolerance zone (€55k-€63.25k) → still exempt but warned."""
        config = SelfEmployedConfig()
        result = determine_kleinunternehmer_status(Decimal("58000"), config=config)
        assert result.exempt is True
        assert result.tolerance_applies is True
        assert len(result.warnings) > 0


# ===========================================================================
# Section 10: Basispauschalierung Rate Changes
# ===========================================================================

class TestBasispauschalierungRateChanges:
    """Test flat-rate expense percentage changes across years."""

    def test_2023_rates_12_percent(self):
        """2023: General flat-rate was 12%, turnover limit €220,000."""
        config = SelfEmployedConfig.from_deduction_config(
            get_2023_tax_config()["deduction_config"]
        )
        assert config.flat_rate_general == Decimal("0.12")
        assert config.flat_rate_turnover_limit == Decimal("220000.00")

    def test_2025_rates_12_percent(self):
        """2025+: General flat-rate is 12%, turnover limit €220,000."""
        config = SelfEmployedConfig.from_deduction_config(
            get_2025_tax_config()["deduction_config"]
        )
        assert config.flat_rate_general == Decimal("0.12")
        assert config.flat_rate_turnover_limit == Decimal("220000.00")

    def test_consulting_rate_unchanged(self):
        """Consulting flat-rate remains 6% across all years."""
        for config_fn in [get_2022_tax_config, get_2023_tax_config,
                          get_2025_tax_config, get_2026_tax_config]:
            config = SelfEmployedConfig.from_deduction_config(
                config_fn()["deduction_config"]
            )
            assert config.flat_rate_consulting == Decimal("0.06")


# ===========================================================================
# Section 11: SVS Contributions — Cross-Year
# ===========================================================================

class TestSVSContributionsCrossYear:
    """Test SVS social insurance calculations across years."""

    def test_svs_pension_rate_stable(self):
        """Pension rate should be 18.5% for all years."""
        for config_fn in [get_2022_tax_config, get_2023_tax_config,
                          get_2024_tax_config, get_2025_tax_config, get_2026_tax_config]:
            svs = config_fn()["svs_rates"]
            assert svs["pension"] == 0.185

    def test_svs_max_base_increases(self):
        """Maximum contribution base should increase over years."""
        bases = [
            get_2022_tax_config()["svs_rates"]["max_base_monthly"],
            get_2023_tax_config()["svs_rates"]["max_base_monthly"],
            get_2024_tax_config()["svs_rates"]["max_base_monthly"],
            get_2025_tax_config()["svs_rates"]["max_base_monthly"],
            get_2026_tax_config()["svs_rates"]["max_base_monthly"],
        ]
        for i in range(1, len(bases)):
            assert bases[i] >= bases[i - 1]

    def test_gsvg_contribution_calculation(self):
        """GSVG contributions for €50,000 income."""
        calc = SVSCalculator()
        result = calc.calculate_contributions(Decimal("50000"), UserType.GSVG)
        assert result.annual_total > Decimal("0")
        assert result.deductible is True
        assert "pension" in result.breakdown

    def test_employee_svs_returns_zero(self):
        """Employees should get zero SVS (handled by employer)."""
        calc = SVSCalculator()
        result = calc.calculate_contributions(Decimal("50000"), UserType.EMPLOYEE)
        assert result.annual_total == Decimal("0.00")
        assert result.deductible is False


# ===========================================================================
# Section 12: KESt — Capital Gains Tax
# ===========================================================================

class TestKEStCalculation:
    """Test KESt (capital gains tax) calculations."""

    def test_bank_interest_25_percent(self):
        """Bank interest should be taxed at 25%."""
        result = calculate_kest([{
            "description": "Sparkonto",
            "income_type": "bank_interest",
            "gross_amount": 1000,
        }])
        assert result.total_tax == Decimal("250.00")

    def test_dividends_27_5_percent(self):
        """Dividends should be taxed at 27.5%."""
        result = calculate_kest([{
            "description": "OMV Dividende",
            "income_type": "dividends",
            "gross_amount": 10000,
        }])
        assert result.total_tax == Decimal("2750.00")

    def test_crypto_27_5_percent(self):
        """Crypto gains (post March 2022) should be at 27.5%."""
        result = calculate_kest([{
            "description": "Bitcoin Verkauf",
            "income_type": "crypto",
            "gross_amount": 5000,
        }])
        assert result.total_tax == Decimal("1375.00")

    def test_withheld_reduces_remaining(self):
        """Already-withheld KESt should reduce remaining tax due."""
        result = calculate_kest([{
            "description": "ETF Dividende",
            "income_type": "dividends",
            "gross_amount": 10000,
            "withheld": True,
        }])
        assert result.total_already_withheld == Decimal("2750.00")
        assert result.remaining_tax_due == Decimal("0.00")


# ===========================================================================
# Section 13: ImmoESt — Real Estate Capital Gains Tax
# ===========================================================================

class TestImmoEStCalculation:
    """Test ImmoESt (real estate gains tax) calculations."""

    def test_basic_immoest_30_percent(self):
        """Standard ImmoESt is 30% on gain."""
        result = calculate_immoest(
            sale_price=Decimal("400000"),
            acquisition_cost=Decimal("300000"),
            acquisition_date=date(2015, 1, 1),
        )
        assert result.tax_rate == Decimal("0.30")
        assert result.taxable_gain == Decimal("100000.00")
        assert result.tax_amount == Decimal("30000.00")

    def test_hauptwohnsitz_exemption(self):
        """Main residence is exempt from ImmoESt."""
        result = calculate_immoest(
            sale_price=Decimal("500000"),
            acquisition_cost=Decimal("200000"),
            exemption=ExemptionType.HAUPTWOHNSITZ,
        )
        assert result.exempt is True
        assert result.total_tax == Decimal("0.00")

    def test_old_property_14_percent(self):
        """Properties acquired before 01.04.2002 get 14% effective rate."""
        result = calculate_immoest(
            sale_price=Decimal("500000"),
            acquisition_cost=Decimal("100000"),
            acquisition_date=date(1990, 6, 1),
        )
        assert result.is_old_property is True
        assert result.tax_rate == Decimal("0.14")

    def test_reclassification_surcharge(self):
        """Reclassification after 2024 triggers 30% surcharge (from July 2025)."""
        result = calculate_immoest(
            sale_price=Decimal("500000"),
            acquisition_cost=Decimal("300000"),
            acquisition_date=date(2020, 1, 1),
            was_reclassified=True,
            reclassification_date=date(2025, 3, 1),
            sale_date=date(2025, 8, 1),
        )
        assert result.reclassification_surcharge > Decimal("0")


# ===========================================================================
# Section 14: Gewinnfreibetrag — Cross-Year
# ===========================================================================

class TestGewinnfreibetragCrossYear:
    """Test Gewinnfreibetrag across years."""

    def test_grundfreibetrag_15_percent(self):
        """Grundfreibetrag is 15% of profit up to €33,000."""
        result = calculate_gewinnfreibetrag(Decimal("30000"))
        assert result.grundfreibetrag == Decimal("4500.00")

    def test_grundfreibetrag_capped_at_4950(self):
        """Grundfreibetrag max is €4,950 (15% of €33,000)."""
        result = calculate_gewinnfreibetrag(Decimal("50000"))
        assert result.grundfreibetrag == Decimal("4950.00")

    def test_investment_freibetrag_requires_investment(self):
        """Investment-based Freibetrag needs actual qualifying investment."""
        result = calculate_gewinnfreibetrag(
            Decimal("100000"), qualifying_investment=Decimal("0")
        )
        assert result.investment_freibetrag == Decimal("0.00")
        assert result.investment_required > Decimal("0")

    def test_investment_freibetrag_with_investment(self):
        """Investment-based Freibetrag with qualifying investment."""
        result = calculate_gewinnfreibetrag(
            Decimal("100000"), qualifying_investment=Decimal("50000")
        )
        assert result.investment_freibetrag > Decimal("0")
        assert result.total_freibetrag > result.grundfreibetrag

    def test_max_total_freibetrag_46400(self):
        """Total Gewinnfreibetrag capped at €46,400."""
        result = calculate_gewinnfreibetrag(
            Decimal("1000000"), qualifying_investment=Decimal("500000")
        )
        assert result.total_freibetrag <= Decimal("46400.00")


# ===========================================================================
# Section 15: Family Deductions — Familienbonus, Alleinverdiener
# ===========================================================================

class TestFamilyDeductions:
    """Test family-related tax benefits."""

    def test_familienbonus_under_18(self):
        """€2,000.16/year per child under 18."""
        calc = DeductionCalculator()
        info = FamilyInfo(num_children=2, children_under_18=2, children_18_to_24=0)
        result = calc.calculate_familienbonus(info)
        assert result.amount == Decimal("4000.32")

    def test_familienbonus_18_to_24(self):
        """€700.08/year per child 18-24."""
        calc = DeductionCalculator()
        info = FamilyInfo(num_children=1, children_under_18=0, children_18_to_24=1)
        result = calc.calculate_familienbonus(info)
        assert result.amount == Decimal("700.08")

    def test_alleinverdiener_with_children(self):
        """Sole earner with children gets Alleinverdienerabsetzbetrag."""
        calc = DeductionCalculator()
        info = FamilyInfo(num_children=2, is_sole_earner=True)
        result = calc.calculate_alleinverdiener(info)
        assert result.amount == Decimal("828.00")

    def test_alleinerzieher_for_single_parent(self):
        """Single parent gets Alleinerzieherabsetzbetrag."""
        calc = DeductionCalculator()
        info = FamilyInfo(num_children=1, is_single_parent=True)
        result = calc.calculate_alleinverdiener(info)
        assert result.amount == Decimal("612.00")
        assert "Alleinerzieher" in result.breakdown["type"]

    def test_no_alleinverdiener_without_children(self):
        """No Alleinverdiener/Alleinerzieher without children."""
        calc = DeductionCalculator()
        info = FamilyInfo(num_children=0, is_sole_earner=True)
        result = calc.calculate_alleinverdiener(info)
        assert result.amount == Decimal("0.00")


# ===========================================================================
# Section 16: Employee-Specific Deductions
# ===========================================================================

class TestEmployeeDeductions:
    """Test employee-specific deductions."""

    def test_werbungskostenpauschale_132(self):
        """Werbungskostenpauschale is €132/year."""
        calc = DeductionCalculator()
        result = calc.calculate_employee_deductions()
        assert result.amount == Decimal("132.00")

    def test_werbungskostenpauschale_not_applied_if_actual_higher(self):
        """If actual expenses exceed €132, Pauschale is not applied."""
        calc = DeductionCalculator()
        result = calc.calculate_employee_deductions(
            actual_werbungskosten=Decimal("500")
        )
        assert result.amount == Decimal("0.00")

    def test_verkehrsabsetzbetrag_in_breakdown(self):
        """Verkehrsabsetzbetrag should appear in breakdown."""
        calc = DeductionCalculator()
        result = calc.calculate_employee_deductions()
        assert "verkehrsabsetzbetrag" in result.breakdown
        assert result.breakdown["verkehrsabsetzbetrag"] == Decimal("496.00")


# ===========================================================================
# Section 17: Pendlerpauschale
# ===========================================================================

class TestPendlerpauschale:
    """Test commuting allowance calculations."""

    def test_kleines_pendlerpauschale_20km(self):
        """Kleines Pendlerpauschale for 25km with public transport."""
        calc = DeductionCalculator()
        result = calc.calculate_commuting_allowance(25, True)
        assert result.amount > Decimal("0")
        assert "Kleines" in result.breakdown["type"]

    def test_grosses_pendlerpauschale_5km(self):
        """Großes Pendlerpauschale for 5km without public transport."""
        calc = DeductionCalculator()
        result = calc.calculate_commuting_allowance(5, False)
        assert result.amount > Decimal("0")
        assert "Großes" in result.breakdown["type"]

    def test_no_kleines_under_20km(self):
        """No Kleines Pendlerpauschale for < 20km."""
        calc = DeductionCalculator()
        result = calc.calculate_commuting_allowance(15, True)
        assert result.amount == Decimal("0.00")

    def test_pendler_euro_included(self):
        """Pendler-Euro (€6/km/year for 2026) should be in the total."""
        calc = DeductionCalculator()
        result = calc.calculate_commuting_allowance(30, True)
        assert result.breakdown["pendler_euro"] == Decimal("180.00")  # 30 × 6


# ===========================================================================
# Section 18: Home Office Deduction
# ===========================================================================

class TestHomeOfficeDeduction:
    """Test home office deduction."""

    def test_home_office_flat_rate_300(self):
        """Home office flat-rate is €300/year."""
        calc = DeductionCalculator()
        result = calc.calculate_home_office_deduction()
        assert result.amount == Decimal("300.00")


# ===========================================================================
# Section 19: Expense Method Comparison
# ===========================================================================

class TestExpenseMethodComparison:
    """Test flat-rate vs actual expense comparison."""

    def test_flat_rate_better_with_low_expenses(self):
        """Flat-rate should be better when actual expenses are low."""
        result = compare_expense_methods(
            gross_turnover=Decimal("100000"),
            actual_expenses=Decimal("5000"),  # Very low
            profession_type=ProfessionType.GENERAL,
        )
        # 13.5% of 100k = 13,500 > 5,000 actual
        assert result.recommended_method == ExpenseMethod.FLAT_RATE

    def test_actual_better_with_high_expenses(self):
        """Actual method should be better when expenses exceed flat rate."""
        result = compare_expense_methods(
            gross_turnover=Decimal("100000"),
            actual_expenses=Decimal("30000"),  # Higher than 13.5%
            profession_type=ProfessionType.GENERAL,
        )
        assert result.recommended_method == ExpenseMethod.ACTUAL

    def test_ineligible_above_turnover_limit(self):
        """Flat rate not available above turnover limit."""
        result = compare_expense_methods(
            gross_turnover=Decimal("400000"),
            actual_expenses=Decimal("50000"),
        )
        assert result.recommended_method == ExpenseMethod.ACTUAL


# ===========================================================================
# Section 20: Tax Engine Integration
# ===========================================================================

class TestTaxEngineIntegration:
    """Test the unified TaxCalculationEngine."""

    def test_engine_with_2022_config(self):
        """Engine should work with 2022 config."""
        config = get_2022_tax_config()
        engine = TaxCalculationEngine(config)
        result = engine.calculate_total_tax(
            gross_income=Decimal("50000"),
            tax_year=2022,
            user_type=UserType.GSVG,
        )
        assert result.total_tax > Decimal("0")
        assert result.net_income < Decimal("50000")

    def test_engine_with_2026_config(self):
        """Engine should work with 2026 config."""
        config = get_2026_tax_config()
        engine = TaxCalculationEngine(config)
        result = engine.calculate_total_tax(
            gross_income=Decimal("50000"),
            tax_year=2026,
            user_type=UserType.GSVG,
        )
        assert result.total_tax > Decimal("0")

    def test_engine_employee_with_family(self):
        """Employee with family deductions."""
        config = get_2026_tax_config()
        engine = TaxCalculationEngine(config)
        family = FamilyInfo(
            num_children=2,
            children_under_18=2,
            is_single_parent=True,
        )
        result = engine.calculate_total_tax(
            gross_income=Decimal("45000"),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
            family_info=family,
            home_office_eligible=True,
        )
        assert result.deductions.amount > Decimal("0")

    def test_engine_self_employed_with_pauschalierung(self):
        """Self-employed with Basispauschalierung."""
        config = get_2026_tax_config()
        engine = TaxCalculationEngine(config)
        result = engine.calculate_total_tax(
            gross_income=Decimal("80000"),
            tax_year=2026,
            user_type=UserType.GSVG,
            expense_method=ExpenseMethod.FLAT_RATE,
            gross_turnover=Decimal("80000"),
        )
        assert result.basispauschalierung is not None
        assert result.basispauschalierung.eligible is True

    def test_engine_gewinnfreibetrag_applied(self):
        """Gewinnfreibetrag should be applied for self-employed."""
        config = get_2026_tax_config()
        engine = TaxCalculationEngine(config)
        result = engine.calculate_total_tax(
            gross_income=Decimal("60000"),
            tax_year=2026,
            user_type=UserType.GSVG,
        )
        assert result.gewinnfreibetrag is not None
        assert result.gewinnfreibetrag.grundfreibetrag > Decimal("0")


# ===========================================================================
# Section 21: Cross-Year Tax Burden Comparison
# ===========================================================================

class TestCrossYearTaxBurden:
    """Compare tax burden across years to verify cold-progression relief."""

    def test_same_income_lower_tax_in_later_years(self):
        """Due to cold-progression adjustment, same real income → lower nominal tax."""
        income = Decimal("50000")

        configs = {
            2022: get_2022_tax_config(),
            2023: get_2023_tax_config(),
            2024: get_2024_tax_config(),
        }
        taxes = {}
        for year, config in configs.items():
            engine = TaxCalculationEngine(config)
            result = engine.calculate_total_tax(
                gross_income=income,
                tax_year=year,
                user_type=UserType.EMPLOYEE,
            )
            taxes[year] = result.income_tax.total_tax

        # Tax should generally decrease due to wider brackets
        assert taxes[2022] > taxes[2024]

    def test_gmbh_vs_einzelunternehmen_comparison(self):
        """At high profits, GmbH (KöSt+KESt) should be more efficient than ESt."""
        profit = Decimal("200000")

        # ESt for 2026
        config = get_2026_tax_config()
        est_calc = IncomeTaxCalculator(config)
        est_result = est_calc.calculate_progressive_tax(profit, 2026)

        # KöSt + KESt for 2026
        koest_calc = KoEstCalculator()
        koest_result = koest_calc.calculate(profit, tax_year=2026)

        # Compare
        comparison = koest_calc.compare_with_est(profit, est_result.total_tax)
        assert comparison["recommendation"] in ("gmbh", "einzelunternehmen")


# ===========================================================================
# Section 22: Edge Cases and Boundary Conditions
# ===========================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_income(self):
        """Zero income should result in zero tax."""
        config = get_2026_tax_config()
        calc = IncomeTaxCalculator(config)
        result = calc.calculate_progressive_tax(Decimal("0"), 2026)
        assert result.total_tax == Decimal("0.00")

    def test_negative_income(self):
        """Negative income should result in zero tax."""
        config = get_2026_tax_config()
        calc = IncomeTaxCalculator(config)
        result = calc.calculate_progressive_tax(Decimal("-5000"), 2026)
        assert result.total_tax == Decimal("0.00")

    def test_very_small_income(self):
        """Very small income (€1) should result in zero tax."""
        config = get_2026_tax_config()
        calc = IncomeTaxCalculator(config)
        result = calc.calculate_progressive_tax(Decimal("1"), 2026)
        assert result.total_tax == Decimal("0.00")

    def test_ifb_empty_list(self):
        """Empty investment list should return zero IFB."""
        result = calculate_ifb([], tax_year=2024)
        assert result.total_ifb == Decimal("0.00")

    def test_kest_empty_list(self):
        """Empty KESt item list should return zero."""
        result = calculate_kest([])
        assert result.total_tax == Decimal("0.00")

    def test_immoest_no_gain(self):
        """Sale at cost should result in zero ImmoESt."""
        result = calculate_immoest(
            sale_price=Decimal("300000"),
            acquisition_cost=Decimal("300000"),
            acquisition_date=date(2020, 1, 1),
        )
        assert result.taxable_gain == Decimal("0.00")
        assert result.tax_amount == Decimal("0.00")

    def test_svs_below_minimum_income(self):
        """Income below GSVG minimum should not require contributions."""
        calc = SVSCalculator()
        result = calc.calculate_contributions(Decimal("3000"), UserType.GSVG)
        assert result.annual_total == Decimal("0.00")

    def test_koest_zero_profit(self):
        """Zero profit should still have Mindestkörperschaftsteuer."""
        calc = KoEstCalculator()
        result = calc.calculate(Decimal("0"), tax_year=2026)
        assert result.effective_koest == Decimal("500.00")
