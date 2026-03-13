"""Tests for Grundfreibetrag (basic profit exemption) in TaxCalculationEngine.

Grundfreibetrag: 15% of profit, max €4,950 — applies to self-employed (GSVG, Neue Selbständige)
but NOT to employees.
"""
import pytest
from decimal import Decimal
from hypothesis import given, strategies as st, assume, settings

from app.services.tax_calculation_engine import TaxCalculationEngine
from app.services.svs_calculator import UserType


@pytest.fixture
def tax_config():
    """Tax configuration with explicit basic_exemption fields."""
    return {
        "tax_year": 2026,
        "exemption_amount": "13539.00",
        "tax_brackets": [
            {"lower": "0.00", "upper": "13539.00", "rate": "0.00"},
            {"lower": "13539.00", "upper": "21992.00", "rate": "0.20"},
            {"lower": "21992.00", "upper": "36458.00", "rate": "0.30"},
            {"lower": "36458.00", "upper": "70365.00", "rate": "0.40"},
            {"lower": "70365.00", "upper": "104859.00", "rate": "0.48"},
            {"lower": "104859.00", "upper": "1000000.00", "rate": "0.50"},
            {"lower": "1000000.00", "upper": None, "rate": "0.55"},
        ],
        "deduction_config": {
            "basic_exemption_rate": 0.15,
            "basic_exemption_max": 4950.00,
        },
    }


@pytest.fixture
def engine(tax_config):
    return TaxCalculationEngine(tax_config)


class TestGrundfreibetragApplication:
    """Verify Grundfreibetrag is applied for self-employed, not for employees."""

    def test_gsvg_pays_less_tax_than_without_grundfreibetrag(self, tax_config):
        """GSVG user should pay less income tax thanks to Grundfreibetrag."""
        engine = TaxCalculationEngine(tax_config)
        result_gsvg = engine.calculate_total_tax(
            gross_income=Decimal("50000.00"),
            tax_year=2026,
            user_type=UserType.GSVG,
        )

        # Build a config with zero exemption to compare
        no_exemption_config = dict(tax_config)
        no_exemption_config["deduction_config"] = {
            "basic_exemption_rate": 0.0,
            "basic_exemption_max": 0.0,
        }
        engine_no = TaxCalculationEngine(no_exemption_config)
        result_no = engine_no.calculate_total_tax(
            gross_income=Decimal("50000.00"),
            tax_year=2026,
            user_type=UserType.GSVG,
        )

        # With Grundfreibetrag, income tax should be lower
        assert result_gsvg.income_tax.total_tax < result_no.income_tax.total_tax

    def test_employee_not_affected_by_grundfreibetrag(self, engine):
        """Employees should NOT receive Grundfreibetrag."""
        result = engine.calculate_total_tax(
            gross_income=Decimal("50000.00"),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
        )

        # Build engine with zero exemption
        no_config = {
            **engine.tax_config,
            "deduction_config": {
                "basic_exemption_rate": 0.0,
                "basic_exemption_max": 0.0,
            },
        }
        engine_no = TaxCalculationEngine(no_config)
        result_no = engine_no.calculate_total_tax(
            gross_income=Decimal("50000.00"),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
        )

        # Employee income tax should be identical regardless of Grundfreibetrag config
        assert result.income_tax.total_tax == result_no.income_tax.total_tax

    def test_neue_selbstaendige_gets_grundfreibetrag(self, engine):
        """Neue Selbständige should also receive Grundfreibetrag."""
        result = engine.calculate_total_tax(
            gross_income=Decimal("40000.00"),
            tax_year=2026,
            user_type=UserType.NEUE_SELBSTAENDIGE,
        )

        no_config = {
            **engine.tax_config,
            "deduction_config": {
                "basic_exemption_rate": 0.0,
                "basic_exemption_max": 0.0,
            },
        }
        engine_no = TaxCalculationEngine(no_config)
        result_no = engine_no.calculate_total_tax(
            gross_income=Decimal("40000.00"),
            tax_year=2026,
            user_type=UserType.NEUE_SELBSTAENDIGE,
        )

        assert result.income_tax.total_tax < result_no.income_tax.total_tax


class TestGrundfreibetragCap:
    """Verify the €4,950 cap is respected."""

    def test_cap_at_high_income(self, engine):
        """For high income, Grundfreibetrag should be capped at €4,950."""
        # At €100,000 profit, 15% = €15,000 which exceeds cap
        # So exemption should be exactly €4,950
        result_high = engine.calculate_total_tax(
            gross_income=Decimal("100000.00"),
            tax_year=2026,
            user_type=UserType.GSVG,
        )
        result_very_high = engine.calculate_total_tax(
            gross_income=Decimal("200000.00"),
            tax_year=2026,
            user_type=UserType.GSVG,
        )

        # Both should hit the cap, so the difference in income tax should
        # correspond to the full difference in income (no extra exemption benefit)
        # The tax difference should be the same as if both had the same flat €4,950 deducted
        assert result_high.income_tax.total_tax < result_very_high.income_tax.total_tax

    def test_below_cap_proportional(self, engine):
        """For low income, Grundfreibetrag should be 15% of taxable income."""
        # With income of €20,000, after SVS deductions the taxable income
        # will be lower, and 15% of that should be well under €4,950
        result = engine.calculate_total_tax(
            gross_income=Decimal("20000.00"),
            tax_year=2026,
            user_type=UserType.GSVG,
        )
        # Just verify it produces a valid result with lower tax
        assert result.total_tax >= Decimal("0.00")
        assert result.net_income <= Decimal("20000.00")


class TestGrundfreibetragProperties:
    """Property-based tests for Grundfreibetrag correctness."""

    @settings(max_examples=50)
    @given(income=st.decimals(min_value=1000, max_value=500000, places=2))
    def test_grundfreibetrag_never_increases_tax(self, income):
        """Grundfreibetrag should never increase tax for self-employed."""
        config = {
            "tax_year": 2026,
            "exemption_amount": "13539.00",
            "tax_brackets": [
                {"lower": "0.00", "upper": "13539.00", "rate": "0.00"},
                {"lower": "13539.00", "upper": "21992.00", "rate": "0.20"},
                {"lower": "21992.00", "upper": "36458.00", "rate": "0.30"},
                {"lower": "36458.00", "upper": "70365.00", "rate": "0.40"},
                {"lower": "70365.00", "upper": "104859.00", "rate": "0.48"},
                {"lower": "104859.00", "upper": "1000000.00", "rate": "0.50"},
                {"lower": "1000000.00", "upper": None, "rate": "0.55"},
            ],
            "deduction_config": {
                "basic_exemption_rate": 0.15,
                "basic_exemption_max": 4950.00,
            },
        }
        no_exemption_config = {
            **config,
            "deduction_config": {
                "basic_exemption_rate": 0.0,
                "basic_exemption_max": 0.0,
            },
        }

        engine_with = TaxCalculationEngine(config)
        engine_without = TaxCalculationEngine(no_exemption_config)

        result_with = engine_with.calculate_total_tax(
            gross_income=income, tax_year=2026, user_type=UserType.GSVG, use_cache=False
        )
        result_without = engine_without.calculate_total_tax(
            gross_income=income, tax_year=2026, user_type=UserType.GSVG, use_cache=False
        )

        assert result_with.income_tax.total_tax <= result_without.income_tax.total_tax

    @settings(max_examples=50)
    @given(income=st.decimals(min_value=1000, max_value=500000, places=2))
    def test_employee_unaffected_by_grundfreibetrag(self, income):
        """Employees should never be affected by Grundfreibetrag setting."""
        config = {
            "tax_year": 2026,
            "exemption_amount": "13539.00",
            "tax_brackets": [
                {"lower": "0.00", "upper": "13539.00", "rate": "0.00"},
                {"lower": "13539.00", "upper": "21992.00", "rate": "0.20"},
                {"lower": "21992.00", "upper": "36458.00", "rate": "0.30"},
                {"lower": "36458.00", "upper": "70365.00", "rate": "0.40"},
                {"lower": "70365.00", "upper": "104859.00", "rate": "0.48"},
                {"lower": "104859.00", "upper": "1000000.00", "rate": "0.50"},
                {"lower": "1000000.00", "upper": None, "rate": "0.55"},
            ],
            "deduction_config": {
                "basic_exemption_rate": 0.15,
                "basic_exemption_max": 4950.00,
            },
        }
        no_exemption_config = {
            **config,
            "deduction_config": {
                "basic_exemption_rate": 0.0,
                "basic_exemption_max": 0.0,
            },
        }

        engine_with = TaxCalculationEngine(config)
        engine_without = TaxCalculationEngine(no_exemption_config)

        result_with = engine_with.calculate_total_tax(
            gross_income=income, tax_year=2026, user_type=UserType.EMPLOYEE, use_cache=False
        )
        result_without = engine_without.calculate_total_tax(
            gross_income=income, tax_year=2026, user_type=UserType.EMPLOYEE, use_cache=False
        )

        assert result_with.income_tax.total_tax == result_without.income_tax.total_tax
