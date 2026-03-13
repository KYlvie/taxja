"""Tests for KESt and ImmoESt integration into TaxCalculationEngine."""
import pytest
from decimal import Decimal
from datetime import date

from app.services.tax_calculation_engine import TaxCalculationEngine, TaxBreakdown
from app.services.svs_calculator import UserType
from app.services.kest_calculator import KEStResult
from app.services.immoest_calculator import ImmoEStResult


@pytest.fixture
def tax_config():
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
    }


@pytest.fixture
def engine(tax_config):
    return TaxCalculationEngine(tax_config)


class TestKEStIntegration:
    """Test KESt integration into calculate_total_tax."""

    def test_no_capital_income_no_kest(self, engine):
        """Without capital_income_items, kest should be None."""
        result = engine.calculate_total_tax(
            gross_income=Decimal("50000"),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
            use_cache=False,
        )
        assert result.kest is None

    def test_bank_interest_25_percent(self, engine):
        """Bank interest should be taxed at 25%."""
        items = [
            {
                "description": "Sparbuch Zinsen",
                "income_type": "bank_interest",
                "gross_amount": Decimal("1000"),
                "withheld": False,
            }
        ]
        result = engine.calculate_total_tax(
            gross_income=Decimal("50000"),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
            capital_income_items=items,
            use_cache=False,
        )
        assert result.kest is not None
        assert result.kest.total_tax == Decimal("250.00")
        assert result.kest.remaining_tax_due == Decimal("250.00")

    def test_dividends_27_5_percent(self, engine):
        """Dividends should be taxed at 27.5%."""
        items = [
            {
                "description": "ATX Dividenden",
                "income_type": "dividends",
                "gross_amount": Decimal("2000"),
                "withheld": True,
            }
        ]
        result = engine.calculate_total_tax(
            gross_income=Decimal("50000"),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
            capital_income_items=items,
            use_cache=False,
        )
        assert result.kest.total_tax == Decimal("550.00")
        # Already withheld, so remaining = 0
        assert result.kest.remaining_tax_due == Decimal("0.00")

    def test_kest_adds_to_total_tax(self, engine):
        """KESt remaining_tax_due should be added to total_tax."""
        base = engine.calculate_total_tax(
            gross_income=Decimal("50000"),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
            use_cache=False,
        )
        items = [
            {
                "description": "Crypto gains",
                "income_type": "crypto",
                "gross_amount": Decimal("10000"),
                "withheld": False,
            }
        ]
        with_kest = engine.calculate_total_tax(
            gross_income=Decimal("50000"),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
            capital_income_items=items,
            use_cache=False,
        )
        kest_due = Decimal("10000") * Decimal("0.275")  # €2,750
        assert with_kest.total_tax == (base.total_tax + kest_due).quantize(Decimal("0.01"))

    def test_withheld_kest_not_added_to_total(self, engine):
        """Already-withheld KESt should NOT increase total_tax."""
        base = engine.calculate_total_tax(
            gross_income=Decimal("50000"),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
            use_cache=False,
        )
        items = [
            {
                "description": "Bank dividends",
                "income_type": "dividends",
                "gross_amount": Decimal("5000"),
                "withheld": True,
            }
        ]
        with_kest = engine.calculate_total_tax(
            gross_income=Decimal("50000"),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
            capital_income_items=items,
            use_cache=False,
        )
        # remaining_tax_due = 0, so total_tax unchanged
        assert with_kest.total_tax == base.total_tax


class TestImmoEStIntegration:
    """Test ImmoESt integration into calculate_total_tax."""

    def test_no_property_sale_no_immoest(self, engine):
        """Without property_sale, immoest should be None."""
        result = engine.calculate_total_tax(
            gross_income=Decimal("50000"),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
            use_cache=False,
        )
        assert result.immoest is None

    def test_property_sale_30_percent(self, engine):
        """Standard property sale: 30% on gain."""
        sale = {
            "sale_price": "500000",
            "acquisition_cost": "300000",
            "improvement_costs": "50000",
            "selling_costs": "10000",
        }
        result = engine.calculate_total_tax(
            gross_income=Decimal("50000"),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
            property_sale=sale,
            use_cache=False,
        )
        assert result.immoest is not None
        # Gain = 500k - 300k - 50k - 10k = 140k
        # Tax = 140k * 30% = 42k
        assert result.immoest.taxable_gain == Decimal("140000.00")
        assert result.immoest.total_tax == Decimal("42000.00")

    def test_hauptwohnsitz_exempt(self, engine):
        """Hauptwohnsitzbefreiung: no ImmoESt."""
        sale = {
            "sale_price": "500000",
            "acquisition_cost": "300000",
            "exemption": "hauptwohnsitz",
        }
        result = engine.calculate_total_tax(
            gross_income=Decimal("50000"),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
            property_sale=sale,
            use_cache=False,
        )
        assert result.immoest.exempt is True
        assert result.immoest.total_tax == Decimal("0.00")

    def test_immoest_adds_to_total_tax(self, engine):
        """ImmoESt should be added to total_tax."""
        base = engine.calculate_total_tax(
            gross_income=Decimal("50000"),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
            use_cache=False,
        )
        sale = {
            "sale_price": "400000",
            "acquisition_cost": "300000",
        }
        with_immo = engine.calculate_total_tax(
            gross_income=Decimal("50000"),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
            property_sale=sale,
            use_cache=False,
        )
        # Gain = 100k, tax = 30k
        expected_immo_tax = Decimal("30000.00")
        assert with_immo.total_tax == (base.total_tax + expected_immo_tax).quantize(
            Decimal("0.01")
        )

    def test_exempt_immoest_not_added_to_total(self, engine):
        """Exempt ImmoESt should NOT increase total_tax."""
        base = engine.calculate_total_tax(
            gross_income=Decimal("50000"),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
            use_cache=False,
        )
        sale = {
            "sale_price": "500000",
            "acquisition_cost": "300000",
            "exemption": "hauptwohnsitz",
        }
        with_immo = engine.calculate_total_tax(
            gross_income=Decimal("50000"),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
            property_sale=sale,
            use_cache=False,
        )
        assert with_immo.total_tax == base.total_tax

    def test_old_property_14_percent(self, engine):
        """Pre-2002 property: 14% flat rate on sale price."""
        sale = {
            "sale_price": "400000",
            "acquisition_cost": "100000",
            "acquisition_date": "2000-06-15",
        }
        result = engine.calculate_total_tax(
            gross_income=Decimal("50000"),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
            property_sale=sale,
            use_cache=False,
        )
        assert result.immoest.is_old_property is True
        # 14% of sale price = 400k * 0.14 = 56k
        assert result.immoest.total_tax == Decimal("56000.00")


class TestCombinedKEStAndImmoESt:
    """Test both KESt and ImmoESt together."""

    def test_both_add_to_total(self, engine):
        """Both KESt and ImmoESt should be reflected in total_tax."""
        base = engine.calculate_total_tax(
            gross_income=Decimal("50000"),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
            use_cache=False,
        )
        items = [
            {
                "description": "ETF gains",
                "income_type": "securities_gains",
                "gross_amount": Decimal("20000"),
                "withheld": False,
            }
        ]
        sale = {
            "sale_price": "300000",
            "acquisition_cost": "200000",
        }
        combined = engine.calculate_total_tax(
            gross_income=Decimal("50000"),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
            capital_income_items=items,
            property_sale=sale,
            use_cache=False,
        )
        kest_due = Decimal("20000") * Decimal("0.275")  # €5,500
        immo_tax = Decimal("100000") * Decimal("0.30")  # €30,000
        expected = (base.total_tax + kest_due + immo_tax).quantize(Decimal("0.01"))
        assert combined.total_tax == expected


class TestGenerateBreakdownIntegration:
    """Test that generate_tax_breakdown includes KESt and ImmoESt."""

    def test_breakdown_includes_kest(self, engine):
        items = [
            {
                "description": "Zinsen",
                "income_type": "bank_interest",
                "gross_amount": Decimal("500"),
                "withheld": False,
            }
        ]
        bd = engine.generate_tax_breakdown(
            gross_income=Decimal("50000"),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
            capital_income_items=items,
            use_cache=False,
        )
        assert "kest" in bd
        assert bd["kest"]["total_tax"] == 125.0
        assert len(bd["kest"]["line_items"]) == 1

    def test_breakdown_includes_immoest(self, engine):
        sale = {
            "sale_price": "200000",
            "acquisition_cost": "150000",
        }
        bd = engine.generate_tax_breakdown(
            gross_income=Decimal("50000"),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
            property_sale=sale,
            use_cache=False,
        )
        assert "immoest" in bd
        assert bd["immoest"]["taxable_gain"] == 50000.0
        assert bd["immoest"]["total_tax"] == 15000.0

    def test_breakdown_no_kest_immoest_when_absent(self, engine):
        bd = engine.generate_tax_breakdown(
            gross_income=Decimal("50000"),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
            use_cache=False,
        )
        assert "kest" not in bd
        assert "immoest" not in bd
