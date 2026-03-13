"""Tests for multi-year tax configuration correctness.

Verifies that each year's tax brackets produce the exact income tax amounts
shown in the official USP examples at:
https://www.usp.gv.at/en/.../tarifstufen.html

Each example uses a trader with taxable income of €40,000.
"""
import pytest
from decimal import Decimal

from app.services.tax_calculation_engine import TaxCalculationEngine
from app.services.income_tax_calculator import IncomeTaxCalculator
from app.models.tax_configuration import (
    get_2023_tax_config,
    get_2024_tax_config,
    get_2025_tax_config,
    get_2026_tax_config,
)
from app.services.svs_calculator import UserType


# USP official examples: taxable income €40,000 → expected income tax
USP_EXAMPLES = [
    (get_2023_tax_config, Decimal("8619.75")),  # USP shows 8619.25 (likely typo), math: 8619.75
    (get_2024_tax_config, Decimal("7903.70")),
    (get_2025_tax_config, Decimal("7593.10")),
    (get_2026_tax_config, Decimal("7447.20")),
]


class TestUSPExamples:
    """Verify income tax matches official USP examples for each year."""

    @pytest.mark.parametrize("config_fn,expected_tax", USP_EXAMPLES)
    def test_usp_example_40k_income(self, config_fn, expected_tax):
        """Income tax on €40,000 taxable income must match USP example."""
        config = config_fn()
        calc = IncomeTaxCalculator(config)
        # USP examples use €40,000 as taxable income (already after exemption)
        result = calc.calculate_progressive_tax(
            taxable_income=Decimal("40000.00"),
            tax_year=config["tax_year"],
        )
        assert result.total_tax == expected_tax, (
            f"Year {config['tax_year']}: expected €{expected_tax}, "
            f"got €{result.total_tax}"
        )


class TestYearSpecificEngine:
    """Verify the engine loads correct configs for each year without DB."""

    @pytest.fixture
    def engine(self):
        return TaxCalculationEngine(get_2026_tax_config())

    def test_2023_uses_41_percent_bracket(self, engine):
        """2023 has a 41% rate for the 4th bracket (not 40%)."""
        config = get_2023_tax_config()
        brackets = config["tax_brackets"]
        fourth_bracket = brackets[3]
        assert fourth_bracket["rate"] == 0.41

    def test_2024_uses_40_percent_bracket(self, engine):
        """2024 reduced the 4th bracket from 41% to 40%."""
        config = get_2024_tax_config()
        brackets = config["tax_brackets"]
        fourth_bracket = brackets[3]
        assert fourth_bracket["rate"] == 0.40

    def test_2023_exemption_amount(self):
        config = get_2023_tax_config()
        assert config["exemption_amount"] == 11693.00

    def test_2024_exemption_amount(self):
        config = get_2024_tax_config()
        assert config["exemption_amount"] == 12816.00

    def test_2025_exemption_amount(self):
        config = get_2025_tax_config()
        assert config["exemption_amount"] == 13308.00

    def test_2026_exemption_amount(self):
        config = get_2026_tax_config()
        assert config["exemption_amount"] == 13539.00

    def test_kleinunternehmer_threshold_pre_2025(self):
        """Before 2025, Kleinunternehmer threshold was €35,000 net."""
        for getter in (get_2023_tax_config, get_2024_tax_config):
            config = getter()
            assert config["vat_rates"]["small_business_threshold"] == 35000.00, (
                f"Year {config['tax_year']}"
            )

    def test_kleinunternehmer_threshold_from_2025(self):
        """From 2025, Kleinunternehmer threshold raised to €55,000 gross."""
        for getter in (get_2025_tax_config, get_2026_tax_config):
            config = getter()
            assert config["vat_rates"]["small_business_threshold"] == 55000.00, (
                f"Year {config['tax_year']}"
            )

    def test_engine_no_db_fallback_2023(self):
        """Without DB, engine falls back to default year config for unknown years."""
        engine = TaxCalculationEngine(get_2026_tax_config())
        result = engine.calculate_total_tax(
            gross_income=Decimal("40000.00"),
            tax_year=2023,
            user_type=UserType.EMPLOYEE,
        )
        result_2026 = engine.calculate_total_tax(
            gross_income=Decimal("40000.00"),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
        )
        # Without DB, 2023 uses 2026 default config → same tax
        assert result.income_tax.total_tax == result_2026.income_tax.total_tax

    def test_engine_no_db_fallback_2024(self):
        """Without DB, engine falls back to default year config for unknown years."""
        engine = TaxCalculationEngine(get_2026_tax_config())
        result = engine.calculate_total_tax(
            gross_income=Decimal("40000.00"),
            tax_year=2024,
            user_type=UserType.EMPLOYEE,
        )
        result_2026 = engine.calculate_total_tax(
            gross_income=Decimal("40000.00"),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
        )
        # Without DB, 2024 uses 2026 default config → same tax
        assert result.income_tax.total_tax == result_2026.income_tax.total_tax


class TestSeedConfigCompleteness:
    """Verify all year configs have required keys."""

    @pytest.mark.parametrize("config_fn", [
        get_2023_tax_config,
        get_2024_tax_config,
        get_2025_tax_config,
        get_2026_tax_config,
    ])
    def test_config_has_all_required_keys(self, config_fn):
        config = config_fn()
        required = [
            "tax_year", "tax_brackets", "exemption_amount",
            "vat_rates", "svs_rates", "deduction_config",
        ]
        for key in required:
            assert key in config, f"Missing key '{key}' in {config['tax_year']} config"

    @pytest.mark.parametrize("config_fn", [
        get_2023_tax_config,
        get_2024_tax_config,
        get_2025_tax_config,
        get_2026_tax_config,
    ])
    def test_config_has_self_employed_section(self, config_fn):
        config = config_fn()
        se = config["deduction_config"].get("self_employed")
        assert se is not None, (
            f"Year {config['tax_year']} missing self_employed in deduction_config"
        )
        assert "grundfreibetrag_rate" in se
        assert "kleinunternehmer_threshold" in se

    @pytest.mark.parametrize("config_fn", [
        get_2023_tax_config,
        get_2024_tax_config,
        get_2025_tax_config,
        get_2026_tax_config,
    ])
    def test_svs_rates_complete(self, config_fn):
        config = config_fn()
        svs = config["svs_rates"]
        required_svs = [
            "pension", "health", "accident_fixed",
            "supplementary_pension", "gsvg_min_base_monthly",
            "gsvg_min_income_yearly", "neue_min_monthly", "max_base_monthly",
        ]
        for key in required_svs:
            assert key in svs, (
                f"Missing SVS key '{key}' in {config['tax_year']} config"
            )
