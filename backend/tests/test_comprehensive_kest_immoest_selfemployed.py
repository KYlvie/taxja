"""
Comprehensive tests for KESt, ImmoESt, and Self-Employed Tax Service calculators.

Covers:
- KESt (Kapitalertragsteuer): capital gains tax rates (25% / 27.5%), mixed portfolios,
  withholding tracking, all income types.
- ImmoESt (Immobilienertragsteuer): standard sales, exemptions (Hauptwohnsitz, Hersteller),
  old-property rules (pre-2002), reclassification surcharge, boundary dates.
- Self-employed: Gewinnfreibetrag (Grundfreibetrag + investment tiers),
  Basispauschalierung (flat-rate expenses), Kleinunternehmerregelung, expense method comparison.
"""
from datetime import date
from decimal import Decimal

import pytest

from app.services.kest_calculator import (
    CapitalIncomeType,
    KEST_RATE_BANK,
    KEST_RATE_OTHER,
    KEStResult,
    calculate_kest,
    get_kest_rate,
)
from app.services.immoest_calculator import (
    ExemptionType,
    IMMOEST_RATE,
    OLD_PROPERTY_CUTOFF,
    OLD_PROPERTY_EFFECTIVE_RATE,
    OLD_PROPERTY_RECLASSIFIED_RATE,
    RECLASSIFICATION_SURCHARGE_RATE,
    RECLASSIFICATION_SURCHARGE_START,
    calculate_immoest,
)
from app.services.self_employed_tax_service import (
    BasispauschalierungResult,
    ExpenseMethod,
    GewinnfreibetragResult,
    KleinunternehmerStatus,
    ProfessionType,
    SelfEmployedConfig,
    calculate_basispauschalierung,
    calculate_gewinnfreibetrag,
    compare_expense_methods,
    determine_kleinunternehmer_status,
)


# =============================================================================
# KESt Calculator Tests
# =============================================================================


class TestGetKestRate:
    """Tests for get_kest_rate function."""

    def test_bank_interest_rate_is_25_percent(self):
        assert get_kest_rate(CapitalIncomeType.BANK_INTEREST) == Decimal("0.25")

    @pytest.mark.parametrize(
        "income_type",
        [
            CapitalIncomeType.DIVIDENDS,
            CapitalIncomeType.SECURITIES_GAINS,
            CapitalIncomeType.CRYPTO,
            CapitalIncomeType.BOND_INTEREST,
            CapitalIncomeType.FUND_DISTRIBUTIONS,
            CapitalIncomeType.GMBH_SHARES,
            CapitalIncomeType.OTHER,
        ],
    )
    def test_non_bank_rate_is_27_5_percent(self, income_type: CapitalIncomeType):
        assert get_kest_rate(income_type) == Decimal("0.275")

    def test_rate_constants(self):
        assert KEST_RATE_BANK == Decimal("0.25")
        assert KEST_RATE_OTHER == Decimal("0.275")


class TestCalculateKest:
    """Tests for calculate_kest function."""

    def test_bank_interest_10000(self):
        """Bank interest EUR 10,000 at 25% -> tax EUR 2,500."""
        result = calculate_kest([
            {
                "description": "Savings account interest",
                "income_type": "bank_interest",
                "gross_amount": Decimal("10000"),
                "withheld": False,
            }
        ])
        assert result.total_gross == Decimal("10000.00")
        assert result.total_tax == Decimal("2500.00")
        assert result.net_income == Decimal("7500.00")

    def test_dividends_5000(self):
        """Dividends EUR 5,000 at 27.5% -> tax EUR 1,375."""
        result = calculate_kest([
            {
                "description": "AT dividend",
                "income_type": "dividends",
                "gross_amount": Decimal("5000"),
                "withheld": False,
            }
        ])
        assert result.total_tax == Decimal("1375.00")

    def test_securities_gains_20000(self):
        """Securities gains EUR 20,000 at 27.5% -> tax EUR 5,500."""
        result = calculate_kest([
            {
                "description": "ETF sale gain",
                "income_type": "securities_gains",
                "gross_amount": Decimal("20000"),
                "withheld": False,
            }
        ])
        assert result.total_tax == Decimal("5500.00")

    def test_crypto_15000(self):
        """Crypto EUR 15,000 at 27.5% -> tax EUR 4,125."""
        result = calculate_kest([
            {
                "description": "Bitcoin gain",
                "income_type": "crypto",
                "gross_amount": Decimal("15000"),
                "withheld": False,
            }
        ])
        assert result.total_tax == Decimal("4125.00")

    def test_mixed_portfolio(self):
        """Mixed portfolio: bank EUR 10,000 + dividends EUR 5,000 + crypto EUR 8,000."""
        items = [
            {
                "description": "Savings interest",
                "income_type": "bank_interest",
                "gross_amount": Decimal("10000"),
                "withheld": True,
            },
            {
                "description": "Dividends",
                "income_type": "dividends",
                "gross_amount": Decimal("5000"),
                "withheld": False,
            },
            {
                "description": "Crypto gains",
                "income_type": "crypto",
                "gross_amount": Decimal("8000"),
                "withheld": False,
            },
        ]
        result = calculate_kest(items)

        expected_bank_tax = Decimal("10000") * Decimal("0.25")  # 2500
        expected_div_tax = Decimal("5000") * Decimal("0.275")   # 1375
        expected_crypto_tax = Decimal("8000") * Decimal("0.275")  # 2200
        expected_total_tax = (expected_bank_tax + expected_div_tax + expected_crypto_tax).quantize(Decimal("0.01"))

        assert result.total_gross == Decimal("23000.00")
        assert result.total_tax == expected_total_tax  # 6075.00
        assert result.total_already_withheld == expected_bank_tax.quantize(Decimal("0.01"))
        assert result.remaining_tax_due == (expected_total_tax - expected_bank_tax).quantize(Decimal("0.01"))
        assert result.net_income == (Decimal("23000") - expected_total_tax).quantize(Decimal("0.01"))
        assert len(result.line_items) == 3

    def test_withheld_tracking(self):
        """Bank interest withheld, crypto not withheld -> remaining = total - withheld."""
        items = [
            {
                "description": "Bank interest",
                "income_type": "bank_interest",
                "gross_amount": Decimal("10000"),
                "withheld": True,
            },
            {
                "description": "Crypto gain",
                "income_type": "crypto",
                "gross_amount": Decimal("15000"),
                "withheld": False,
            },
        ]
        result = calculate_kest(items)

        bank_tax = Decimal("2500.00")
        crypto_tax = Decimal("4125.00")
        total_tax = bank_tax + crypto_tax  # 6625.00

        assert result.total_tax == total_tax
        assert result.total_already_withheld == bank_tax
        assert result.remaining_tax_due == crypto_tax

    @pytest.mark.parametrize(
        "income_type_str,expected_rate",
        [
            ("bank_interest", Decimal("0.25")),
            ("dividends", Decimal("0.275")),
            ("securities_gains", Decimal("0.275")),
            ("crypto", Decimal("0.275")),
            ("bond_interest", Decimal("0.275")),
            ("fund_distributions", Decimal("0.275")),
            ("gmbh_shares", Decimal("0.275")),
            ("other", Decimal("0.275")),
        ],
    )
    def test_all_income_types_correct_rate(self, income_type_str: str, expected_rate: Decimal):
        """Verify each income type uses the correct rate in calculation."""
        result = calculate_kest([
            {
                "description": f"Test {income_type_str}",
                "income_type": income_type_str,
                "gross_amount": Decimal("1000"),
                "withheld": False,
            }
        ])
        expected_tax = (Decimal("1000") * expected_rate).quantize(Decimal("0.01"))
        assert result.total_tax == expected_tax
        assert result.line_items[0].rate == expected_rate

    def test_empty_items_list(self):
        """Empty items list returns zero result."""
        result = calculate_kest([])
        assert result.total_gross == Decimal("0.00")
        assert result.total_tax == Decimal("0.00")
        assert result.total_already_withheld == Decimal("0.00")
        assert result.remaining_tax_due == Decimal("0.00")
        assert result.net_income == Decimal("0.00")
        assert result.line_items == []

    def test_net_income_equals_gross_minus_tax(self):
        """net_income = gross - tax for any items."""
        items = [
            {
                "description": "Dividends",
                "income_type": "dividends",
                "gross_amount": Decimal("12345.67"),
                "withheld": False,
            },
            {
                "description": "Bank interest",
                "income_type": "bank_interest",
                "gross_amount": Decimal("9876.54"),
                "withheld": True,
            },
        ]
        result = calculate_kest(items)
        assert result.net_income == (result.total_gross - result.total_tax).quantize(Decimal("0.01"))

    def test_note_contains_withheld_info_when_withheld(self):
        """When KESt is withheld, note mentions it."""
        result = calculate_kest([
            {
                "description": "Bank interest",
                "income_type": "bank_interest",
                "gross_amount": Decimal("1000"),
                "withheld": True,
            }
        ])
        assert "einbehalten" in result.note.lower() or "bereits" in result.note.lower()

    def test_note_when_nothing_withheld(self):
        """When nothing withheld, note mentions E1kv declaration."""
        result = calculate_kest([
            {
                "description": "Crypto",
                "income_type": "crypto",
                "gross_amount": Decimal("5000"),
                "withheld": False,
            }
        ])
        assert "E1kv" in result.note

    def test_income_type_as_enum(self):
        """Income type can be passed as enum value directly."""
        result = calculate_kest([
            {
                "description": "Test",
                "income_type": CapitalIncomeType.DIVIDENDS,
                "gross_amount": Decimal("1000"),
                "withheld": False,
            }
        ])
        assert result.total_tax == Decimal("275.00")


# =============================================================================
# ImmoESt Calculator Tests
# =============================================================================


class TestCalculateImmoest:
    """Tests for calculate_immoest function."""

    def test_standard_sale(self):
        """Standard sale: buy 200k, sell 350k, improvements 20k, selling costs 10k.
        Gain = 350,000 - 200,000 - 20,000 - 10,000 = 120,000
        Tax = 120,000 * 30% = 36,000
        """
        result = calculate_immoest(
            sale_price=Decimal("350000"),
            acquisition_cost=Decimal("200000"),
            acquisition_date=date(2015, 6, 1),
            improvement_costs=Decimal("20000"),
            selling_costs=Decimal("10000"),
        )
        assert result.taxable_gain == Decimal("120000.00")
        assert result.tax_amount == Decimal("36000.00")
        assert result.total_tax == Decimal("36000.00")
        assert result.reclassification_surcharge == Decimal("0.00")
        assert result.exempt is False

    def test_hauptwohnsitz_exemption(self):
        """Hauptwohnsitz exemption: fully exempt, net = sale - selling costs."""
        result = calculate_immoest(
            sale_price=Decimal("500000"),
            acquisition_cost=Decimal("300000"),
            acquisition_date=date(2010, 1, 1),
            selling_costs=Decimal("15000"),
            exemption=ExemptionType.HAUPTWOHNSITZ,
        )
        assert result.exempt is True
        assert result.exemption_type == ExemptionType.HAUPTWOHNSITZ
        assert result.tax_amount == Decimal("0.00")
        assert result.total_tax == Decimal("0.00")
        assert result.net_proceeds == Decimal("485000")  # 500000 - 15000

    def test_hersteller_exemption(self):
        """Hersteller exemption: fully exempt."""
        result = calculate_immoest(
            sale_price=Decimal("400000"),
            acquisition_cost=Decimal("250000"),
            selling_costs=Decimal("10000"),
            exemption=ExemptionType.HERSTELLER,
        )
        assert result.exempt is True
        assert result.exemption_type == ExemptionType.HERSTELLER
        assert result.tax_amount == Decimal("0.00")
        assert result.net_proceeds == Decimal("390000")  # 400000 - 10000

    def test_old_property_no_reclassification(self):
        """Old property (pre-2002, no reclassification): sale 500k, rate 14% -> tax 70k."""
        result = calculate_immoest(
            sale_price=Decimal("500000"),
            acquisition_cost=Decimal("100000"),
            acquisition_date=date(1995, 3, 15),
        )
        assert result.is_old_property is True
        assert result.tax_rate == Decimal("0.14")
        assert result.tax_amount == Decimal("70000.00")
        assert result.total_tax == Decimal("70000.00")

    def test_old_property_reclassified(self):
        """Old property reclassified: sale 500k, rate 18% -> tax 90k."""
        result = calculate_immoest(
            sale_price=Decimal("500000"),
            acquisition_cost=Decimal("100000"),
            acquisition_date=date(1990, 6, 1),
            was_reclassified=True,
        )
        assert result.is_old_property is True
        assert result.tax_rate == Decimal("0.18")
        assert result.tax_amount == Decimal("90000.00")
        assert result.total_tax == Decimal("90000.00")

    def test_reclassification_surcharge_post_2025(self):
        """Reclassification surcharge (post-2025): gain 100k, surcharge 30%.
        Tax = 100,000 * 30% = 30,000
        Surcharge = 100,000 * 30% = 30,000
        Total = 60,000
        """
        result = calculate_immoest(
            sale_price=Decimal("300000"),
            acquisition_cost=Decimal("200000"),
            acquisition_date=date(2020, 1, 1),
            was_reclassified=True,
            reclassification_date=date(2025, 3, 1),  # after 2024-12-31
            sale_date=date(2025, 8, 1),  # on or after 2025-07-01
        )
        assert result.taxable_gain == Decimal("100000.00")
        assert result.tax_amount == Decimal("30000.00")
        assert result.reclassification_surcharge == Decimal("30000.00")
        assert result.total_tax == Decimal("60000.00")

    def test_no_gain_sale_below_cost(self):
        """No gain when sale < cost: tax = 0."""
        result = calculate_immoest(
            sale_price=Decimal("150000"),
            acquisition_cost=Decimal("200000"),
            acquisition_date=date(2015, 1, 1),
        )
        assert result.taxable_gain == Decimal("0.00")
        assert result.tax_amount == Decimal("0.00")
        assert result.total_tax == Decimal("0.00")

    @pytest.mark.parametrize(
        "acq_date,expected_old",
        [
            (date(2002, 3, 31), True),   # Exactly on cutoff -> old
            (date(2002, 4, 1), False),   # Day after cutoff -> new
            (date(2002, 3, 30), True),   # Day before cutoff -> old
        ],
        ids=["exactly_on_cutoff", "day_after_cutoff", "day_before_cutoff"],
    )
    def test_boundary_acquisition_dates(self, acq_date: date, expected_old: bool):
        """Boundary dates: acquisition on/before 2002-03-31 is old property."""
        result = calculate_immoest(
            sale_price=Decimal("300000"),
            acquisition_cost=Decimal("200000"),
            acquisition_date=acq_date,
        )
        assert result.is_old_property is expected_old

    def test_reclassification_date_boundary_before_2025(self):
        """Reclassification date on or before 2024-12-31 -> no surcharge."""
        result = calculate_immoest(
            sale_price=Decimal("300000"),
            acquisition_cost=Decimal("200000"),
            acquisition_date=date(2020, 1, 1),
            was_reclassified=True,
            reclassification_date=date(2024, 12, 31),  # exactly on boundary
            sale_date=date(2025, 8, 1),
        )
        assert result.reclassification_surcharge == Decimal("0.00")

    def test_reclassification_date_boundary_after_2025(self):
        """Reclassification date on 2025-01-01 -> surcharge applies if sale >= 2025-07-01."""
        result = calculate_immoest(
            sale_price=Decimal("300000"),
            acquisition_cost=Decimal("200000"),
            acquisition_date=date(2020, 1, 1),
            was_reclassified=True,
            reclassification_date=date(2025, 1, 1),  # after 2024-12-31
            sale_date=date(2025, 7, 1),  # exactly on surcharge start
        )
        assert result.reclassification_surcharge == Decimal("30000.00")

    def test_sale_date_before_surcharge_start(self):
        """Sale before 2025-07-01 -> no surcharge even if reclassified after 2024."""
        result = calculate_immoest(
            sale_price=Decimal("300000"),
            acquisition_cost=Decimal("200000"),
            acquisition_date=date(2020, 1, 1),
            was_reclassified=True,
            reclassification_date=date(2025, 3, 1),
            sale_date=date(2025, 6, 30),  # day before surcharge start
        )
        assert result.reclassification_surcharge == Decimal("0.00")

    def test_immoest_rate_constant(self):
        assert IMMOEST_RATE == Decimal("0.30")
        assert OLD_PROPERTY_EFFECTIVE_RATE == Decimal("0.14")
        assert OLD_PROPERTY_RECLASSIFIED_RATE == Decimal("0.18")
        assert OLD_PROPERTY_CUTOFF == date(2002, 3, 31)
        assert RECLASSIFICATION_SURCHARGE_START == date(2025, 7, 1)
        assert RECLASSIFICATION_SURCHARGE_RATE == Decimal("0.30")

    def test_net_proceeds_standard_sale(self):
        """Net proceeds = sale_price - selling_costs - total_tax."""
        result = calculate_immoest(
            sale_price=Decimal("400000"),
            acquisition_cost=Decimal("300000"),
            acquisition_date=date(2018, 5, 1),
            selling_costs=Decimal("5000"),
        )
        gain = Decimal("400000") - Decimal("300000") - Decimal("5000")  # 95000
        tax = (gain * Decimal("0.30")).quantize(Decimal("0.01"))
        expected_net = Decimal("400000") - Decimal("5000") - tax
        assert result.net_proceeds == expected_net.quantize(Decimal("0.01"))


# =============================================================================
# Self-Employed Tax Service Tests — Gewinnfreibetrag
# =============================================================================


class TestCalculateGewinnfreibetrag:
    """Tests for calculate_gewinnfreibetrag function."""

    def test_grundfreibetrag_only_small_profit(self):
        """Profit EUR 20,000 -> 15% * 20,000 = EUR 3,000."""
        result = calculate_gewinnfreibetrag(Decimal("20000"))
        assert result.grundfreibetrag == Decimal("3000.00")
        assert result.investment_freibetrag == Decimal("0.00")
        assert result.total_freibetrag == Decimal("3000.00")

    def test_grundfreibetrag_capped_at_33000(self):
        """Profit EUR 33,000 -> max EUR 4,950."""
        result = calculate_gewinnfreibetrag(Decimal("33000"))
        assert result.grundfreibetrag == Decimal("4950.00")
        assert result.investment_freibetrag == Decimal("0.00")
        assert result.total_freibetrag == Decimal("4950.00")

    def test_with_investment_tiers_profit_100k(self):
        """Profit EUR 100,000, investment EUR 50,000.
        Grundfreibetrag: EUR 4,950
        Excess: 100,000 - 33,000 = 67,000
        Tier 1: 67,000 * 13% = 8,710
        Investment cap: min(8,710, 50,000) = 8,710
        Total: 4,950 + 8,710 = 13,660
        """
        result = calculate_gewinnfreibetrag(
            Decimal("100000"),
            qualifying_investment=Decimal("50000"),
        )
        assert result.grundfreibetrag == Decimal("4950.00")
        assert result.investment_freibetrag == Decimal("8710.00")
        assert result.total_freibetrag == Decimal("13660.00")
        assert result.capped is False

    def test_large_profit_full_tiers_capped(self):
        """Profit EUR 600,000, investment EUR 100,000.
        Grundfreibetrag: 4,950
        Excess: 600,000 - 33,000 = 567,000
        Tier 1: min(567,000, 175,000) = 175,000 * 13% = 22,750
        Tier 2: min(392,000, 175,000) = 175,000 * 7% = 12,250
        Tier 3: min(217,000, 230,000) = 217,000 * 4.5% = 9,765
        Max investment FB: 22,750 + 12,250 + 9,765 = 44,765
        Investment cap: min(44,765, 100,000) = 44,765
        Total uncapped: 4,950 + 44,765 = 49,715
        But max is 46,400 -> capped.
        Investment FB becomes: 46,400 - 4,950 = 41,450
        """
        result = calculate_gewinnfreibetrag(
            Decimal("600000"),
            qualifying_investment=Decimal("100000"),
        )
        assert result.grundfreibetrag == Decimal("4950.00")
        assert result.total_freibetrag == Decimal("46400.00")
        assert result.investment_freibetrag == Decimal("41450.00")
        assert result.capped is True

    def test_zero_profit(self):
        """Zero profit -> no freibetrag."""
        result = calculate_gewinnfreibetrag(Decimal("0"))
        assert result.grundfreibetrag == Decimal("0.00")
        assert result.total_freibetrag == Decimal("0.00")

    def test_negative_profit(self):
        """Negative profit -> no freibetrag."""
        result = calculate_gewinnfreibetrag(Decimal("-5000"))
        assert result.grundfreibetrag == Decimal("0.00")
        assert result.total_freibetrag == Decimal("0.00")

    def test_investment_caps_freibetrag(self):
        """When investment is less than max allowance, it caps the investment FB."""
        result = calculate_gewinnfreibetrag(
            Decimal("100000"),
            qualifying_investment=Decimal("3000"),  # less than 8,710 max
        )
        assert result.grundfreibetrag == Decimal("4950.00")
        assert result.investment_freibetrag == Decimal("3000.00")
        assert result.total_freibetrag == Decimal("7950.00")
        assert result.investment_required == Decimal("8710.00")

    def test_no_investment_no_investment_fb(self):
        """Profit above 33k but no investment -> only Grundfreibetrag."""
        result = calculate_gewinnfreibetrag(
            Decimal("100000"),
            qualifying_investment=Decimal("0"),
        )
        assert result.grundfreibetrag == Decimal("4950.00")
        assert result.investment_freibetrag == Decimal("0.00")
        assert result.total_freibetrag == Decimal("4950.00")

    @pytest.mark.parametrize(
        "profit,expected_grundfb",
        [
            (Decimal("1000"), Decimal("150.00")),
            (Decimal("10000"), Decimal("1500.00")),
            (Decimal("33000"), Decimal("4950.00")),
            (Decimal("50000"), Decimal("4950.00")),  # capped at max
        ],
        ids=["1k", "10k", "exactly_33k", "above_limit"],
    )
    def test_grundfreibetrag_parametrized(self, profit: Decimal, expected_grundfb: Decimal):
        result = calculate_gewinnfreibetrag(profit)
        assert result.grundfreibetrag == expected_grundfb

    def test_tier2_reached(self):
        """Profit EUR 250,000, investment EUR 100,000.
        Excess: 217,000
        Tier 1: 175,000 * 13% = 22,750
        Tier 2: 42,000 * 7% = 2,940
        Max invest FB: 25,690
        Investment cap: min(25,690, 100,000) = 25,690
        Total: 4,950 + 25,690 = 30,640
        """
        result = calculate_gewinnfreibetrag(
            Decimal("250000"),
            qualifying_investment=Decimal("100000"),
        )
        assert result.grundfreibetrag == Decimal("4950.00")
        assert result.investment_freibetrag == Decimal("25690.00")
        assert result.total_freibetrag == Decimal("30640.00")
        assert result.capped is False


# =============================================================================
# Self-Employed Tax Service Tests — Basispauschalierung
# =============================================================================


class TestCalculateBasispauschalierung:
    """Tests for calculate_basispauschalierung function."""

    def test_general_profession_100k(self):
        """General profession, turnover EUR 100,000, SVS EUR 5,000.
        Flat-rate expenses: 100,000 * 13.5% = 13,500
        Profit: 100,000 - 13,500 - 5,000 = 81,500
        Grundfreibetrag: min(81,500 * 0.15, 4,950) = 4,950
        Taxable: 81,500 - 4,950 = 76,550
        """
        result = calculate_basispauschalierung(
            gross_turnover=Decimal("100000"),
            profession_type=ProfessionType.GENERAL,
            svs_contributions=Decimal("5000"),
        )
        assert result.eligible is True
        assert result.flat_rate_expenses == Decimal("13500.00")
        assert result.flat_rate_pct == Decimal("0.135")
        assert result.estimated_profit == Decimal("81500.00")
        assert result.grundfreibetrag == Decimal("4950.00")
        assert result.taxable_profit == Decimal("76550.00")

    def test_consulting_profession_6_percent(self):
        """Consulting profession uses 6% flat rate."""
        result = calculate_basispauschalierung(
            gross_turnover=Decimal("100000"),
            profession_type=ProfessionType.CONSULTING,
            svs_contributions=Decimal("5000"),
        )
        assert result.eligible is True
        assert result.flat_rate_pct == Decimal("0.06")
        assert result.flat_rate_expenses == Decimal("6000.00")
        # Profit: 100,000 - 6,000 - 5,000 = 89,000
        assert result.estimated_profit == Decimal("89000.00")

    def test_turnover_over_limit_not_eligible(self):
        """Turnover > EUR 320,000 -> not eligible."""
        result = calculate_basispauschalierung(
            gross_turnover=Decimal("320001"),
        )
        assert result.eligible is False
        assert "320" in result.reason

    def test_turnover_exactly_at_limit(self):
        """Turnover exactly EUR 320,000 -> eligible."""
        result = calculate_basispauschalierung(
            gross_turnover=Decimal("320000"),
        )
        assert result.eligible is True

    def test_grundfreibetrag_in_pauschalierung(self):
        """Grundfreibetrag is applied on top of flat-rate expenses."""
        result = calculate_basispauschalierung(
            gross_turnover=Decimal("50000"),
            svs_contributions=Decimal("0"),
        )
        # Expenses: 50,000 * 13.5% = 6,750
        # Profit: 50,000 - 6,750 = 43,250
        # Grundfreibetrag: min(43,250 * 0.15, 4,950) = 4,950
        assert result.grundfreibetrag == Decimal("4950.00")
        assert result.taxable_profit == Decimal("43250.00") - Decimal("4950.00")

    def test_small_turnover_grundfreibetrag_not_capped(self):
        """Small turnover where Grundfreibetrag is less than max."""
        result = calculate_basispauschalierung(
            gross_turnover=Decimal("20000"),
            svs_contributions=Decimal("0"),
        )
        # Expenses: 20,000 * 13.5% = 2,700
        # Profit: 17,300
        # Grundfreibetrag: 17,300 * 15% = 2,595
        assert result.estimated_profit == Decimal("17300.00")
        assert result.grundfreibetrag == Decimal("2595.00")

    def test_note_mentions_no_investment_freibetrag(self):
        """Note should mention that investment FB is not allowed with Pauschalierung."""
        result = calculate_basispauschalierung(
            gross_turnover=Decimal("50000"),
        )
        assert "investitionsbedingte" in result.note.lower() or "NICHT" in result.note


# =============================================================================
# Self-Employed Tax Service Tests — Kleinunternehmerregelung
# =============================================================================


class TestDetermineKleinunternehmerStatus:
    """Tests for determine_kleinunternehmer_status function."""

    def test_under_threshold_exempt(self):
        """Turnover under EUR 55,000 -> exempt."""
        status = determine_kleinunternehmer_status(Decimal("54000"))
        assert status.exempt is True
        assert status.tolerance_applies is False

    def test_exactly_at_threshold(self):
        """Turnover exactly EUR 55,000 -> exempt."""
        status = determine_kleinunternehmer_status(Decimal("55000"))
        assert status.exempt is True
        assert status.tolerance_applies is False

    def test_tolerance_zone(self):
        """Turnover EUR 55,001 to EUR 60,500 -> tolerance applies (still exempt this year)."""
        status = determine_kleinunternehmer_status(Decimal("58000"))
        assert status.exempt is True
        assert status.tolerance_applies is True

    def test_tolerance_zone_upper_boundary(self):
        """Turnover exactly EUR 60,500 -> tolerance still applies."""
        status = determine_kleinunternehmer_status(Decimal("60500"))
        assert status.exempt is True
        assert status.tolerance_applies is True

    def test_above_tolerance_not_exempt(self):
        """Turnover > EUR 60,500 -> not exempt."""
        status = determine_kleinunternehmer_status(Decimal("60501"))
        assert status.exempt is False
        assert status.ust_voranmeldung_required is True

    def test_tolerance_not_applicable_if_previous_year_exceeded(self):
        """Tolerance does not apply if previous year already exceeded threshold."""
        status = determine_kleinunternehmer_status(
            Decimal("58000"),
            previous_year_exceeded=True,
        )
        assert status.exempt is False

    def test_significant_input_vat_recommendation(self):
        """If significant input VAT, voluntary registration is recommended."""
        status = determine_kleinunternehmer_status(
            Decimal("40000"),
            has_significant_input_vat=True,
        )
        assert status.exempt is True
        assert status.voluntary_registration_recommended is True
        assert len(status.warnings) > 0

    @pytest.mark.parametrize(
        "turnover,frequency",
        [
            (Decimal("80000"), "quarterly"),
            (Decimal("100001"), "monthly"),
        ],
        ids=["quarterly", "monthly"],
    )
    def test_ust_voranmeldung_frequency(self, turnover: Decimal, frequency: str):
        """UVA frequency: quarterly if <= 100k, monthly if > 100k."""
        status = determine_kleinunternehmer_status(turnover)
        assert status.exempt is False
        assert status.ust_voranmeldung_frequency == frequency

    def test_exactly_at_monthly_threshold(self):
        """Turnover exactly EUR 100,000 -> quarterly (not monthly)."""
        status = determine_kleinunternehmer_status(Decimal("100000"))
        assert status.ust_voranmeldung_frequency == "quarterly"


# =============================================================================
# Self-Employed Tax Service Tests — Expense Method Comparison
# =============================================================================


class TestCompareExpenseMethods:
    """Tests for compare_expense_methods function."""

    def test_flat_rate_better(self):
        """When flat-rate gives lower taxable profit, recommend flat rate."""
        result = compare_expense_methods(
            gross_turnover=Decimal("100000"),
            actual_expenses=Decimal("5000"),  # low actual expenses
            svs_contributions=Decimal("5000"),
        )
        # Flat-rate: 13,500 expenses -> profit 81,500, GFB 4,950, taxable 76,550
        # Actual: 5,000 expenses -> profit 90,000, GFB 4,950 + invest FB 0 = 4,950, taxable 85,050
        assert result.recommended_method == ExpenseMethod.FLAT_RATE
        assert result.flat_rate_profit < result.actual_profit

    def test_actual_better(self):
        """When actual expenses are high, recommend actual."""
        result = compare_expense_methods(
            gross_turnover=Decimal("100000"),
            actual_expenses=Decimal("40000"),  # high actual expenses
            svs_contributions=Decimal("5000"),
        )
        # Flat-rate: expenses 13,500, profit 81,500, taxable ~76,550
        # Actual: expenses 40,000, profit 55,000, GFB 4,950 + invest, taxable ~50,050
        assert result.recommended_method == ExpenseMethod.ACTUAL

    def test_turnover_over_limit_forces_actual(self):
        """Turnover > 320k -> flat rate not eligible, must use actual."""
        result = compare_expense_methods(
            gross_turnover=Decimal("400000"),
            actual_expenses=Decimal("50000"),
            svs_contributions=Decimal("10000"),
        )
        assert result.recommended_method == ExpenseMethod.ACTUAL

    def test_comparison_with_investment(self):
        """Actual method benefits from investment-based Freibetrag."""
        result = compare_expense_methods(
            gross_turnover=Decimal("200000"),
            actual_expenses=Decimal("27000"),
            svs_contributions=Decimal("10000"),
            qualifying_investment=Decimal("50000"),
        )
        # Actual method gets full Gewinnfreibetrag including investment-based,
        # while flat-rate only gets Grundfreibetrag.
        # Actual profit: 200,000 - 27,000 - 10,000 = 163,000
        # GFB: 4,950 + invest FB on 130,000 excess at 13% = 16,900 -> total 21,850
        # Taxable: 163,000 - 21,850 = 141,150
        # Flat: 200,000 - 27,000 - 10,000 = 163,000... no, flat expenses = 200,000*13.5%=27,000
        # Flat profit: 200,000 - 27,000 - 10,000 = 163,000; GFB only 4,950; taxable 158,050
        # So actual (141,150) < flat (158,050) -> actual recommended
        assert result.recommended_method == ExpenseMethod.ACTUAL

    def test_same_result_prefers_flat_rate(self):
        """When both methods yield the same taxable profit, flat rate is recommended."""
        # This is hard to engineer exactly, so we test the logic path:
        # If actual expenses happen to equal flat-rate deduction and no investment FB
        config = SelfEmployedConfig()
        turnover = Decimal("100000")
        flat_expenses = (turnover * config.flat_rate_general).quantize(Decimal("0.01"))
        # If actual_expenses == flat_expenses, same profit, same GFB -> same taxable
        result = compare_expense_methods(
            gross_turnover=turnover,
            actual_expenses=flat_expenses,
            svs_contributions=Decimal("0"),
            qualifying_investment=Decimal("0"),
        )
        # With no investment, both have only Grundfreibetrag -> same taxable
        assert result.recommended_method == ExpenseMethod.FLAT_RATE
        assert result.difference == Decimal("0.00")


# =============================================================================
# Self-Employed Config Tests
# =============================================================================


class TestSelfEmployedConfig:
    """Tests for SelfEmployedConfig defaults and from_deduction_config."""

    def test_default_config_values(self):
        config = SelfEmployedConfig()
        assert config.grundfreibetrag_profit_limit == Decimal("33000.00")
        assert config.grundfreibetrag_rate == Decimal("0.15")
        assert config.grundfreibetrag_max == Decimal("4950.00")
        assert config.max_total_freibetrag == Decimal("46400.00")
        assert config.flat_rate_turnover_limit == Decimal("320000.00")
        assert config.flat_rate_general == Decimal("0.135")
        assert config.flat_rate_consulting == Decimal("0.06")
        assert config.kleinunternehmer_threshold == Decimal("55000.00")
        assert config.kleinunternehmer_tolerance == Decimal("60500.00")
        assert len(config.investment_tiers) == 3

    def test_from_deduction_config_empty(self):
        config = SelfEmployedConfig.from_deduction_config(None)
        assert config.grundfreibetrag_rate == Decimal("0.15")

    def test_from_deduction_config_legacy(self):
        config = SelfEmployedConfig.from_deduction_config({
            "basic_exemption_rate": "0.10",
            "basic_exemption_max": "3000",
        })
        assert config.grundfreibetrag_rate == Decimal("0.10")
        assert config.grundfreibetrag_max == Decimal("3000")

    def test_from_deduction_config_self_employed_section(self):
        config = SelfEmployedConfig.from_deduction_config({
            "self_employed": {
                "grundfreibetrag_rate": "0.12",
                "grundfreibetrag_max": "3600",
                "kleinunternehmer_threshold": "50000",
            }
        })
        assert config.grundfreibetrag_rate == Decimal("0.12")
        assert config.grundfreibetrag_max == Decimal("3600")
        assert config.kleinunternehmer_threshold == Decimal("50000")
