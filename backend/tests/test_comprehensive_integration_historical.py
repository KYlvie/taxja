"""
Comprehensive integration and historical tax year tests for TaxCalculationEngine.

Tests cover:
1. Complex real-world integration scenarios (employee, self-employed, freelancer, etc.)
2. Historical tax years (2023-2026) with cold-progression adjustments
3. Engine features (caching, quarterly prepayments, net income convenience)
4. Tax credits (Verkehrsabsetzbetrag, Familienbonus Plus, combined caps)
"""
import pytest
from decimal import Decimal
from datetime import date

from app.services.tax_calculation_engine import (
    TaxCalculationEngine,
    TaxBreakdown,
    SUPPORTED_TAX_YEARS,
)
from app.services.svs_calculator import UserType
from app.services.vat_calculator import Transaction, PropertyType
from app.services.deduction_calculator import FamilyInfo
from app.services.self_employed_tax_service import ExpenseMethod, ProfessionType


# ---------------------------------------------------------------------------
# Tax configurations for historical years
# ---------------------------------------------------------------------------

TAX_CONFIG_2024 = {
    "tax_year": 2024,
    "tax_brackets": [
        {"min": 0, "max": 11693, "rate": 0},
        {"min": 11693, "max": 19134, "rate": 20},
        {"min": 19134, "max": 32075, "rate": 30},
        {"min": 32075, "max": 62080, "rate": 40},
        {"min": 62080, "max": 93120, "rate": 48},
        {"min": 93120, "max": 1000000, "rate": 50},
        {"min": 1000000, "max": None, "rate": 55},
    ],
    "exemption_amount": 11693,
    "vat_rates": {
        "standard": 0.20,
        "residential": 0.10,
        "reduced_13": 0.13,
        "small_business_threshold": 35000,
        "tolerance_threshold": 40250,
    },
    "svs_rates": None,
    "deduction_config": None,
}

TAX_CONFIG_2025 = {
    "tax_year": 2025,
    "tax_brackets": [
        {"min": 0, "max": 13308, "rate": 0},
        {"min": 13308, "max": 21617, "rate": 20},
        {"min": 21617, "max": 35836, "rate": 30},
        {"min": 35836, "max": 69166, "rate": 40},
        {"min": 69166, "max": 103072, "rate": 48},
        {"min": 103072, "max": 1000000, "rate": 50},
        {"min": 1000000, "max": None, "rate": 55},
    ],
    "exemption_amount": 13308,
    "vat_rates": {
        "standard": 0.20,
        "residential": 0.10,
        "reduced_13": 0.13,
        "small_business_threshold": 55000,
        "tolerance_threshold": 63250,
    },
    "svs_rates": None,
    "deduction_config": None,
}

# The hardcoded fallback config from the engine (used when no config is passed)
TAX_CONFIG_2026_FALLBACK = {
    "tax_year": 2026,
    "tax_brackets": [
        {"min": 0, "max": 12816, "rate": 0},
        {"min": 12816, "max": 20818, "rate": 20},
        {"min": 20818, "max": 34513, "rate": 30},
        {"min": 34513, "max": 66612, "rate": 40},
        {"min": 66612, "max": 99266, "rate": 48},
        {"min": 99266, "max": 1000000, "rate": 50},
        {"min": 1000000, "max": None, "rate": 55},
    ],
    "exemption_amount": 12816,
    "vat_rates": None,
    "svs_rates": None,
    "deduction_config": None,
}


# ===================================================================
# Section 1: Integration Tests - Complex Real-World Scenarios
# ===================================================================


class TestIntegrationComplexScenarios:
    """Complex real-world scenarios exercising the full engine pipeline."""

    # ---- 1. Employee with family and commuting ----

    def test_employee_with_family_and_commuting(self):
        """
        Employee: EUR 65,000 gross, 30km commute with public transport,
        2 children under 18, home office eligible.
        Expects: deductions applied, income tax calculated, SVS = 0, VAT exempt.
        """
        engine = TaxCalculationEngine(TAX_CONFIG_2026_FALLBACK)
        family = FamilyInfo(
            num_children=2,
            is_single_parent=False,
            children_under_18=2,
            children_18_to_24=0,
        )
        result = engine.calculate_total_tax(
            gross_income=Decimal("65000"),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
            commuting_distance_km=30,
            public_transport_available=True,
            home_office_eligible=True,
            family_info=family,
            use_cache=False,
        )

        assert isinstance(result, TaxBreakdown)

        # Deductions should be > 0 (commuting + home office + family + employee)
        assert result.deductions.amount > Decimal("0")

        # SVS must be zero for employees
        assert result.svs.annual_total == Decimal("0.00")
        assert result.svs.deductible is False

        # VAT exempt (no transactions)
        assert result.vat.exempt is True

        # Total tax = income tax only (SVS is 0, VAT exempt)
        assert result.total_tax == result.income_tax.total_tax

        # Net income = gross - total_tax
        expected_net = result.gross_income - result.total_tax
        assert result.net_income == expected_net.quantize(Decimal("0.01"))

        # Income tax should be positive for 65k income
        assert result.income_tax.total_tax > Decimal("0")

    # ---- 2. Self-employed GSVG with VAT ----

    def test_self_employed_gsvg_with_vat(self):
        """
        Self-employed GSVG: EUR 120,000 gross, turnover EUR 120,000,
        transactions: income 120k at 20%, expenses 30k at 20%.
        Turnover > 55k so VAT liable.
        """
        engine = TaxCalculationEngine(TAX_CONFIG_2026_FALLBACK)
        transactions = [
            Transaction(amount=Decimal("120000"), is_income=True),
            Transaction(amount=Decimal("30000"), is_income=False),
        ]
        result = engine.calculate_total_tax(
            gross_income=Decimal("120000"),
            tax_year=2026,
            user_type=UserType.GSVG,
            transactions=transactions,
            gross_turnover=Decimal("120000"),
            use_cache=False,
        )

        # SVS should be calculated (GSVG, income above minimum)
        assert result.svs.annual_total > Decimal("0")
        assert result.svs.deductible is True

        # VAT should not be exempt (turnover 120k > 55k)
        assert result.vat.exempt is False
        assert result.vat.output_vat > Decimal("0")
        assert result.vat.input_vat > Decimal("0")
        # Net VAT = output - input
        assert result.vat.net_vat == (
            result.vat.output_vat - result.vat.input_vat
        )

        # Income tax calculated after SVS deduction
        assert result.income_tax.total_tax > Decimal("0")

        # Total tax includes income tax + SVS + net VAT
        expected_total = (
            result.income_tax.total_tax
            + result.svs.annual_total
            + result.vat.net_vat
        )
        assert result.total_tax == expected_total.quantize(Decimal("0.01"))

    # ---- 3. Freelancer (Neue Selbstaendige) below Kleinunternehmer ----

    def test_freelancer_below_kleinunternehmer(self):
        """
        Neue Selbstaendige: EUR 45,000 gross, turnover EUR 45,000.
        Below EUR 55,000 threshold => VAT exempt.
        """
        engine = TaxCalculationEngine(TAX_CONFIG_2026_FALLBACK)
        # Even with transactions, VAT calculator checks turnover first
        transactions = [
            Transaction(amount=Decimal("45000"), is_income=True),
        ]
        result = engine.calculate_total_tax(
            gross_income=Decimal("45000"),
            tax_year=2026,
            user_type=UserType.NEUE_SELBSTAENDIGE,
            transactions=transactions,
            gross_turnover=Decimal("45000"),
            use_cache=False,
        )

        # SVS calculated for Neue Selbstaendige
        assert result.svs.annual_total > Decimal("0")
        assert result.svs.deductible is True

        # VAT exempt (below 55k)
        assert result.vat.exempt is True

        # Income tax positive
        assert result.income_tax.total_tax > Decimal("0")

    # ---- 4. Self-employed with Gewinnfreibetrag ----

    def test_self_employed_with_gewinnfreibetrag(self):
        """
        GSVG: EUR 80,000 gross, qualifying investment EUR 10,000.
        Gewinnfreibetrag should reduce taxable income.
        """
        engine = TaxCalculationEngine(TAX_CONFIG_2026_FALLBACK)

        # Without investment
        result_no_inv = engine.calculate_total_tax(
            gross_income=Decimal("80000"),
            tax_year=2026,
            user_type=UserType.GSVG,
            qualifying_investment=Decimal("0"),
            use_cache=False,
        )

        # With investment
        result_inv = engine.calculate_total_tax(
            gross_income=Decimal("80000"),
            tax_year=2026,
            user_type=UserType.GSVG,
            qualifying_investment=Decimal("10000"),
            use_cache=False,
        )

        # Gewinnfreibetrag result should be present
        assert result_inv.gewinnfreibetrag is not None
        assert result_inv.gewinnfreibetrag.total_freibetrag > Decimal("0")

        # Grundfreibetrag applies in both cases
        assert result_no_inv.gewinnfreibetrag is not None
        assert result_no_inv.gewinnfreibetrag.grundfreibetrag > Decimal("0")

        # With investment, total freibetrag should be >= without investment
        assert (
            result_inv.gewinnfreibetrag.total_freibetrag
            >= result_no_inv.gewinnfreibetrag.total_freibetrag
        )

        # Tax with investment should be <= tax without
        assert result_inv.income_tax.total_tax <= result_no_inv.income_tax.total_tax

    # ---- 5. Self-employed with Basispauschalierung ----

    def test_self_employed_basispauschalierung(self):
        """
        GSVG: EUR 200,000 turnover, flat-rate expense method, general profession.
        Flat-rate expenses = 12% of turnover.
        """
        engine = TaxCalculationEngine(TAX_CONFIG_2026_FALLBACK)
        result = engine.calculate_total_tax(
            gross_income=Decimal("200000"),
            tax_year=2026,
            user_type=UserType.GSVG,
            gross_turnover=Decimal("200000"),
            expense_method=ExpenseMethod.FLAT_RATE,
            profession_type=ProfessionType.GENERAL,
            use_cache=False,
        )

        # Basispauschalierung result present and eligible
        assert result.basispauschalierung is not None
        assert result.basispauschalierung.eligible is True

        # Flat-rate percentage should be 12%
        assert result.basispauschalierung.flat_rate_pct == Decimal("0.12")

        # Flat-rate expenses = 12% * 200,000 = 24,000
        expected_flat_expenses = (Decimal("200000") * Decimal("0.12")).quantize(
            Decimal("0.01")
        )
        assert result.basispauschalierung.flat_rate_expenses == expected_flat_expenses

        # Taxable profit should be calculated
        assert result.basispauschalierung.taxable_profit > Decimal("0")
        assert result.basispauschalierung.taxable_profit < Decimal("200000")

        # Income tax based on flat-rate profit
        assert result.income_tax.total_tax > Decimal("0")

    # ---- 6. Employee with KESt (capital gains) ----

    def test_employee_with_kest(self):
        """
        Employee: EUR 50,000 salary + bank interest EUR 5,000 + dividends EUR 10,000.
        KESt: 25% on bank interest, 27.5% on dividends.
        """
        engine = TaxCalculationEngine(TAX_CONFIG_2026_FALLBACK)
        capital_items = [
            {
                "description": "Bank interest",
                "income_type": "bank_interest",
                "gross_amount": Decimal("5000"),
                "withheld": False,
            },
            {
                "description": "Dividends",
                "income_type": "dividends",
                "gross_amount": Decimal("10000"),
                "withheld": False,
            },
        ]
        result = engine.calculate_total_tax(
            gross_income=Decimal("50000"),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
            capital_income_items=capital_items,
            use_cache=False,
        )

        # KESt result present
        assert result.kest is not None

        # Bank interest: 25% of 5000 = 1250
        expected_bank_kest = Decimal("5000") * Decimal("0.25")
        # Dividends: 27.5% of 10000 = 2750
        expected_div_kest = Decimal("10000") * Decimal("0.275")

        assert result.kest.total_tax == (
            expected_bank_kest + expected_div_kest
        ).quantize(Decimal("0.01"))

        # Nothing withheld, so remaining = total
        assert result.kest.remaining_tax_due == result.kest.total_tax

        # Total tax includes income tax + KESt (SVS=0 for employee)
        expected_total = (
            result.income_tax.total_tax + result.kest.remaining_tax_due
        )
        assert result.total_tax == expected_total.quantize(Decimal("0.01"))

    # ---- 7. Property sale with ImmoESt ----

    def test_property_sale_with_immoest(self):
        """
        Employee: EUR 60,000 income + property sale (buy 200k, sell 350k).
        ImmoESt = 30% on gain.
        """
        engine = TaxCalculationEngine(TAX_CONFIG_2026_FALLBACK)
        property_sale = {
            "sale_price": Decimal("350000"),
            "acquisition_cost": Decimal("200000"),
            "acquisition_date": "2015-06-01",
            "improvement_costs": Decimal("0"),
            "selling_costs": Decimal("0"),
            "exemption": "none",
            "was_reclassified": False,
            "sale_date": "2026-01-15",
        }
        result = engine.calculate_total_tax(
            gross_income=Decimal("60000"),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
            property_sale=property_sale,
            use_cache=False,
        )

        # ImmoESt result present and not exempt
        assert result.immoest is not None
        assert result.immoest.exempt is False

        # Gain = 350,000 - 200,000 = 150,000
        expected_gain = Decimal("150000")
        assert result.immoest.taxable_gain == expected_gain.quantize(Decimal("0.01"))

        # Tax = 30% of 150,000 = 45,000
        expected_immoest = (expected_gain * Decimal("0.30")).quantize(Decimal("0.01"))
        assert result.immoest.total_tax == expected_immoest

        # Total tax includes income tax + ImmoESt
        expected_total = result.income_tax.total_tax + result.immoest.total_tax
        assert result.total_tax == expected_total.quantize(Decimal("0.01"))

    # ---- 8. Employee with loss carryforward ----

    def test_employee_with_loss_carryforward(self):
        """
        Employee: EUR 100,000 gross, loss carryforward EUR 20,000 applied.
        Taxable income should be reduced.
        """
        engine = TaxCalculationEngine(TAX_CONFIG_2026_FALLBACK)

        # Without loss carryforward
        result_no_loss = engine.calculate_total_tax(
            gross_income=Decimal("100000"),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
            use_cache=False,
        )

        # With loss carryforward
        result_loss = engine.calculate_total_tax(
            gross_income=Decimal("100000"),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
            loss_carryforward_applied=Decimal("20000"),
            remaining_loss_balance=Decimal("5000"),
            use_cache=False,
        )

        # Tax with loss carryforward should be lower
        assert result_loss.income_tax.total_tax < result_no_loss.income_tax.total_tax

        # Loss info in result
        assert result_loss.income_tax.loss_carryforward_applied == Decimal("20000.00")
        assert result_loss.income_tax.remaining_loss_balance == Decimal("5000.00")

    # ---- 9. Combined: Self-employed + family + commuting + capital gains ----

    def test_combined_self_employed_family_commuting_kest(self):
        """
        GSVG: EUR 90,000 income, 2 children (1 under 18, 1 aged 20),
        single parent, 25km commute no public transport, bank interest EUR 3,000.
        All components should be calculated correctly.
        """
        engine = TaxCalculationEngine(TAX_CONFIG_2026_FALLBACK)
        family = FamilyInfo(
            num_children=2,
            is_single_parent=True,
            children_under_18=1,
            children_18_to_24=1,
        )
        capital_items = [
            {
                "description": "Bank interest",
                "income_type": "bank_interest",
                "gross_amount": Decimal("3000"),
                "withheld": False,
            },
        ]
        result = engine.calculate_total_tax(
            gross_income=Decimal("90000"),
            tax_year=2026,
            user_type=UserType.GSVG,
            commuting_distance_km=25,
            public_transport_available=False,
            family_info=family,
            capital_income_items=capital_items,
            use_cache=False,
        )

        # SVS calculated (GSVG)
        assert result.svs.annual_total > Decimal("0")
        assert result.svs.deductible is True

        # Deductions applied (commuting + family)
        assert result.deductions.amount > Decimal("0")

        # Family-related items are exposed via informational child support plus
        # the current tax-credit fields used by the engine.
        assert "kinderabsetzbetrag_info" in result.deductions.breakdown
        assert "kinderabsetzbetrag_info_amount" in result.deductions.breakdown
        assert result.deductions.breakdown["kinderabsetzbetrag_info_amount"] > Decimal("0")
        assert "familienbonus_amount" in result.deductions.breakdown
        assert result.deductions.breakdown["familienbonus_amount"] > Decimal("0")
        assert "alleinverdiener_amount" in result.deductions.breakdown
        assert result.deductions.breakdown["alleinverdiener_amount"] > Decimal("0")

        # KESt calculated (bank interest at 25%)
        assert result.kest is not None
        expected_kest = (Decimal("3000") * Decimal("0.25")).quantize(Decimal("0.01"))
        assert result.kest.total_tax == expected_kest

        # Income tax positive
        assert result.income_tax.total_tax > Decimal("0")

        # VAT exempt (no transactions provided)
        assert result.vat.exempt is True

        # Total tax = income tax + SVS + KESt
        expected_total = (
            result.income_tax.total_tax
            + result.svs.annual_total
            + result.kest.remaining_tax_due
        )
        assert result.total_tax == expected_total.quantize(Decimal("0.01"))

    # ---- 10. Zero income ----

    def test_zero_income(self):
        """
        Zero income: all components should be zero or minimal.
        """
        engine = TaxCalculationEngine(TAX_CONFIG_2026_FALLBACK)
        result = engine.calculate_total_tax(
            gross_income=Decimal("0"),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
            use_cache=False,
        )

        assert result.income_tax.total_tax == Decimal("0.00")
        assert result.svs.annual_total == Decimal("0.00")
        assert result.vat.exempt is True
        assert result.total_tax == Decimal("0.00")
        assert result.net_income == Decimal("0.00")
        assert result.gross_income == Decimal("0")


# ===================================================================
# Section 2: Historical Tax Years (2023-2026)
# ===================================================================


class TestHistoricalTaxYears:
    """Tests verifying year-specific configurations and cold progression adjustment."""

    # ---- 1. Same income, different years ----

    def test_same_income_decreasing_tax_with_wider_brackets(self):
        """
        EUR 50,000 through 2024, 2025, 2026 configs.
        Tax should generally decrease as exemption amounts widen.
        """
        income = Decimal("50000")

        engine_2024 = TaxCalculationEngine(TAX_CONFIG_2024)
        result_2024 = engine_2024.calculate_total_tax(
            gross_income=income,
            tax_year=2024,
            user_type=UserType.EMPLOYEE,
            use_cache=False,
        )

        engine_2025 = TaxCalculationEngine(TAX_CONFIG_2025)
        result_2025 = engine_2025.calculate_total_tax(
            gross_income=income,
            tax_year=2025,
            user_type=UserType.EMPLOYEE,
            use_cache=False,
        )

        engine_2026 = TaxCalculationEngine(TAX_CONFIG_2026_FALLBACK)
        result_2026 = engine_2026.calculate_total_tax(
            gross_income=income,
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
            use_cache=False,
        )

        # 2024 has smaller exemption (11693) => higher tax
        # 2025 has larger exemption (13308)
        # 2026 fallback has exemption (12816)
        # Tax 2024 > Tax 2025 (wider brackets in 2025)
        assert result_2024.income_tax.total_tax > result_2025.income_tax.total_tax

        # All should be positive for 50k income
        assert result_2024.income_tax.total_tax > Decimal("0")
        assert result_2025.income_tax.total_tax > Decimal("0")
        assert result_2026.income_tax.total_tax > Decimal("0")

    # ---- 2. Historical Kleinunternehmer threshold ----

    def test_historical_kleinunternehmer_threshold(self):
        """
        2024 had EUR 35,000 threshold (tolerance 40,250); 2025+ has EUR 55,000.
        Turnover EUR 42,000: liable in 2024 (exceeds 40,250 tolerance), exempt in 2025.
        """
        turnover = Decimal("42000")
        transactions = [
            Transaction(amount=Decimal("42000"), is_income=True),
        ]

        # 2024: threshold 35,000, tolerance 40,250 => 42k exceeds tolerance
        engine_2024 = TaxCalculationEngine(TAX_CONFIG_2024)
        result_2024 = engine_2024.calculate_total_tax(
            gross_income=turnover,
            tax_year=2024,
            user_type=UserType.GSVG,
            transactions=transactions,
            gross_turnover=turnover,
            use_cache=False,
        )

        # 2025: threshold 55,000 => 42k below it
        engine_2025 = TaxCalculationEngine(TAX_CONFIG_2025)
        result_2025 = engine_2025.calculate_total_tax(
            gross_income=turnover,
            tax_year=2025,
            user_type=UserType.GSVG,
            transactions=transactions,
            gross_turnover=turnover,
            use_cache=False,
        )

        # In 2024, turnover 42k > 40,250 tolerance => VAT liable
        assert result_2024.vat.exempt is False

        # In 2025, turnover 42k <= 55,000 => VAT exempt
        assert result_2025.vat.exempt is True

    # ---- 3. Year-over-year comparison: cold progression ----

    def test_cold_progression_adjustment_reflected(self):
        """
        Verify that wider brackets in later years reduce effective tax rate.
        """
        income = Decimal("80000")

        engine_2024 = TaxCalculationEngine(TAX_CONFIG_2024)
        result_2024 = engine_2024.calculate_total_tax(
            gross_income=income,
            tax_year=2024,
            user_type=UserType.EMPLOYEE,
            use_cache=False,
        )

        engine_2025 = TaxCalculationEngine(TAX_CONFIG_2025)
        result_2025 = engine_2025.calculate_total_tax(
            gross_income=income,
            tax_year=2025,
            user_type=UserType.EMPLOYEE,
            use_cache=False,
        )

        # Effective rate in 2024 should be higher than 2025
        assert result_2024.effective_tax_rate > result_2025.effective_tax_rate

        # Tax in 2024 should be higher than 2025
        assert result_2024.income_tax.total_tax > result_2025.income_tax.total_tax

    # ---- 4. Unsupported year warning ----

    def test_unsupported_year_warning(self):
        """
        Using a year not in SUPPORTED_TAX_YEARS should produce a warning.
        """
        engine = TaxCalculationEngine(TAX_CONFIG_2026_FALLBACK)

        # 2020 is not in SUPPORTED_TAX_YEARS
        unsupported_year = 2020
        assert unsupported_year not in SUPPORTED_TAX_YEARS

        result = engine.calculate_total_tax(
            gross_income=Decimal("50000"),
            tax_year=unsupported_year,
            user_type=UserType.EMPLOYEE,
            use_cache=False,
        )

        # Should have a warning about unsupported year
        assert len(result.warnings) > 0
        warning_types = [w.get("type") for w in result.warnings]
        assert "unsupported_year" in warning_types

        # The warning message should mention the year
        unsupported_warnings = [
            w for w in result.warnings if w.get("type") == "unsupported_year"
        ]
        assert str(unsupported_year) in unsupported_warnings[0]["message"]

    def test_supported_year_no_unsupported_warning(self):
        """
        Using a supported year should not produce an unsupported_year warning.
        """
        engine = TaxCalculationEngine(TAX_CONFIG_2026_FALLBACK)
        result = engine.calculate_total_tax(
            gross_income=Decimal("50000"),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
            use_cache=False,
        )

        warning_types = [w.get("type") for w in result.warnings]
        assert "unsupported_year" not in warning_types

    def test_historical_bracket_boundaries(self):
        """
        Verify tax at bracket boundaries differs between years.
        """
        # Test at the exact exemption boundary for 2024 (11693)
        engine_2024 = TaxCalculationEngine(TAX_CONFIG_2024)
        result_at_exempt = engine_2024.calculate_total_tax(
            gross_income=Decimal("11693"),
            tax_year=2024,
            user_type=UserType.EMPLOYEE,
            use_cache=False,
        )
        # At exactly the exemption amount, taxable income = 0 => no tax
        assert result_at_exempt.income_tax.total_tax == Decimal("0.00")

        # Well above exemption to ensure taxable income lands in the 20% bracket.
        # 2024: exemption=11693, Werbungskosten=132, Verkehrsabsetzbetrag=496 (tax credit)
        # First bracket is 0% up to 11693. So we need taxable income ABOVE 11693.
        # gross=25000, deductions=132, taxable_before_exemption=24868
        # After exemption: taxable = 24868 - 11693 = 13175
        # First bracket 0% (width 11693) consumes 11693, next bracket 20% on 1482
        result_above_exempt = engine_2024.calculate_total_tax(
            gross_income=Decimal("25000"),
            tax_year=2024,
            user_type=UserType.EMPLOYEE,
            use_cache=False,
        )
        # The breakdown shows tax in the 20% bracket (€296.40) but the engine
        # applies Verkehrsabsetzbetrag (€496) as a tax credit, reducing total_tax to 0.
        # So we verify the bracket breakdown correctly shows tax before credits.
        assert len(result_above_exempt.income_tax.breakdown) >= 2
        bracket_20 = result_above_exempt.income_tax.breakdown[1]
        assert bracket_20.rate == "20%"
        assert bracket_20.tax_amount > Decimal("0")


# ===================================================================
# Section 3: Engine Features
# ===================================================================


class TestEngineFeatures:
    """Tests for caching, quarterly prepayment, and convenience methods."""

    # ---- 1. Cache ----

    def test_cache_returns_same_result(self):
        """
        Same parameters should return cached result on second call.
        """
        engine = TaxCalculationEngine(TAX_CONFIG_2026_FALLBACK)

        params = dict(
            gross_income=Decimal("75000"),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
            use_cache=True,
        )

        result1 = engine.calculate_total_tax(**params)
        result2 = engine.calculate_total_tax(**params)

        # Both results should be identical objects (from cache)
        assert result1 is result2

    def test_cache_invalidation(self):
        """
        After invalidate_cache(), the next call should compute a fresh result.
        """
        engine = TaxCalculationEngine(TAX_CONFIG_2026_FALLBACK)

        params = dict(
            gross_income=Decimal("75000"),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
            use_cache=True,
        )

        result1 = engine.calculate_total_tax(**params)
        engine.invalidate_cache()
        result2 = engine.calculate_total_tax(**params)

        # After invalidation, result2 is a new object (not the same reference)
        assert result1 is not result2

        # But the values should be equal
        assert result1.total_tax == result2.total_tax
        assert result1.net_income == result2.net_income

    def test_cache_disabled(self):
        """
        With use_cache=False, each call produces a new result object.
        """
        engine = TaxCalculationEngine(TAX_CONFIG_2026_FALLBACK)

        params = dict(
            gross_income=Decimal("75000"),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
            use_cache=False,
        )

        result1 = engine.calculate_total_tax(**params)
        result2 = engine.calculate_total_tax(**params)

        assert result1 is not result2
        assert result1.total_tax == result2.total_tax

    # ---- 2. Quarterly prepayment ----

    def test_quarterly_prepayment_calculation(self):
        """
        Quarterly prepayment should be 1/4 of annual income tax and SVS.
        """
        engine = TaxCalculationEngine(TAX_CONFIG_2026_FALLBACK)
        quarterly = engine.calculate_quarterly_prepayment(
            gross_income=Decimal("80000"),
            tax_year=2026,
            user_type=UserType.GSVG,
        )

        assert "income_tax" in quarterly
        assert "svs" in quarterly
        assert "total" in quarterly

        # Verify total ≈ income_tax + svs (allow ±1 cent for rounding)
        expected_total = (quarterly["income_tax"] + quarterly["svs"]).quantize(Decimal("0.01"))
        assert abs(quarterly["total"] - expected_total) <= Decimal("0.01")

        # Verify quarterly amounts are roughly 1/4 of annual
        breakdown = engine.calculate_total_tax(
            gross_income=Decimal("80000"),
            tax_year=2026,
            user_type=UserType.GSVG,
        )
        expected_quarterly_it = (breakdown.income_tax.total_tax / Decimal("4")).quantize(
            Decimal("0.01")
        )
        expected_quarterly_svs = (breakdown.svs.annual_total / Decimal("4")).quantize(
            Decimal("0.01")
        )

        assert quarterly["income_tax"] == expected_quarterly_it
        assert quarterly["svs"] == expected_quarterly_svs

    def test_quarterly_prepayment_employee(self):
        """
        Employee quarterly prepayment: SVS portion should be zero.
        """
        engine = TaxCalculationEngine(TAX_CONFIG_2026_FALLBACK)
        quarterly = engine.calculate_quarterly_prepayment(
            gross_income=Decimal("60000"),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
        )
        assert quarterly["svs"] == Decimal("0.00")
        assert quarterly["total"] == quarterly["income_tax"]

    # ---- 3. Net income convenience method ----

    def test_calculate_net_income_convenience(self):
        """
        calculate_net_income should return the same value as
        calculate_total_tax().net_income.
        """
        engine = TaxCalculationEngine(TAX_CONFIG_2026_FALLBACK)

        net = engine.calculate_net_income(
            gross_income=Decimal("55000"),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
        )

        breakdown = engine.calculate_total_tax(
            gross_income=Decimal("55000"),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
        )

        assert net == breakdown.net_income

    def test_calculate_net_income_self_employed(self):
        """
        Net income for self-employed should account for SVS deduction.
        """
        engine = TaxCalculationEngine(TAX_CONFIG_2026_FALLBACK)

        net = engine.calculate_net_income(
            gross_income=Decimal("100000"),
            tax_year=2026,
            user_type=UserType.GSVG,
        )

        # Net income should be less than gross
        assert net < Decimal("100000")
        assert net > Decimal("0")


# ===================================================================
# Section 4: Tax Credits
# ===================================================================


class TestTaxCredits:
    """Tests for Verkehrsabsetzbetrag, Familienbonus Plus, and combined caps."""

    # ---- 1. Verkehrsabsetzbetrag for employees ----

    def test_verkehrsabsetzbetrag_for_employee(self):
        """
        Employees should get EUR 496 Verkehrsabsetzbetrag deducted from tax liability.
        """
        engine = TaxCalculationEngine(TAX_CONFIG_2026_FALLBACK)

        # Employee without Verkehrsabsetzbetrag context (self-employed)
        result_gsvg = engine.calculate_total_tax(
            gross_income=Decimal("50000"),
            tax_year=2026,
            user_type=UserType.GSVG,
            use_cache=False,
        )

        # Employee gets Verkehrsabsetzbetrag
        result_emp = engine.calculate_total_tax(
            gross_income=Decimal("50000"),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
            use_cache=False,
        )

        # Employee deductions breakdown should contain verkehrsabsetzbetrag
        assert "verkehrsabsetzbetrag" in result_emp.deductions.breakdown
        assert result_emp.deductions.breakdown["verkehrsabsetzbetrag"] == Decimal("496.00")

    # ---- 2. Familienbonus Plus ----

    def test_familienbonus_plus_deducted_from_tax(self):
        """
        Familienbonus Plus should reduce tax liability (not taxable income).
        """
        engine = TaxCalculationEngine(TAX_CONFIG_2026_FALLBACK)

        # Without children
        result_no_kids = engine.calculate_total_tax(
            gross_income=Decimal("60000"),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
            use_cache=False,
        )

        # With 2 children under 18
        family = FamilyInfo(
            num_children=2,
            is_single_parent=False,
            children_under_18=2,
            children_18_to_24=0,
        )
        result_kids = engine.calculate_total_tax(
            gross_income=Decimal("60000"),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
            family_info=family,
            use_cache=False,
        )

        # Familienbonus should appear in deductions breakdown
        assert "familienbonus_amount" in result_kids.deductions.breakdown

        # Tax with children should be lower due to Familienbonus credit
        # (Familienbonus is a tax credit, deducted from liability)
        assert result_kids.income_tax.total_tax < result_no_kids.income_tax.total_tax

    def test_familienbonus_amounts(self):
        """
        Verify Familienbonus amounts: EUR 2000.16 per child under 18,
        EUR 700.08 per child 18-24.
        """
        engine = TaxCalculationEngine(TAX_CONFIG_2026_FALLBACK)
        family = FamilyInfo(
            num_children=3,
            is_single_parent=False,
            children_under_18=2,
            children_18_to_24=1,
        )
        result = engine.calculate_total_tax(
            gross_income=Decimal("80000"),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
            family_info=family,
            use_cache=False,
        )

        expected_bonus = (
            Decimal("2000.16") * 2  # 2 children under 18
            + Decimal("700.08") * 1  # 1 child 18-24
        ).quantize(Decimal("0.01"))

        assert result.deductions.breakdown["familienbonus_amount"] == expected_bonus

    # ---- 3. Combined tax credits cannot make tax negative ----

    def test_combined_credits_cannot_make_tax_negative(self):
        """
        Even with large tax credits, income tax cannot go below zero.
        Use low income + many children to push credits above raw tax.
        """
        engine = TaxCalculationEngine(TAX_CONFIG_2026_FALLBACK)
        family = FamilyInfo(
            num_children=5,
            is_single_parent=True,
            children_under_18=5,
            children_18_to_24=0,
        )
        # Low income: just above exemption so some small tax
        result = engine.calculate_total_tax(
            gross_income=Decimal("15000"),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
            family_info=family,
            use_cache=False,
        )

        # Income tax must be >= 0 even with large credits
        assert result.income_tax.total_tax >= Decimal("0.00")

    def test_alleinerzieher_credit_applied(self):
        """
        Single parent with children should get Alleinerzieherabsetzbetrag.
        """
        engine = TaxCalculationEngine(TAX_CONFIG_2026_FALLBACK)
        family = FamilyInfo(
            num_children=2,
            is_single_parent=True,
            children_under_18=2,
            children_18_to_24=0,
        )
        result = engine.calculate_total_tax(
            gross_income=Decimal("50000"),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
            family_info=family,
            use_cache=False,
        )

        # Alleinverdiener/Alleinerzieher amount should be in breakdown
        assert "alleinverdiener_amount" in result.deductions.breakdown
        alleinerzieher = result.deductions.breakdown["alleinverdiener_amount"]
        # Current 2026 config uses the explicit 2-children total for AEAB.
        expected = Decimal("828.00")
        assert alleinerzieher == expected.quantize(Decimal("0.01"))

    def test_employee_no_children_no_familienbonus(self):
        """
        Employee without children should not have Familienbonus in breakdown.
        """
        engine = TaxCalculationEngine(TAX_CONFIG_2026_FALLBACK)
        result = engine.calculate_total_tax(
            gross_income=Decimal("50000"),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
            use_cache=False,
        )

        assert "familienbonus_amount" not in result.deductions.breakdown

    def test_werbungskostenpauschale_applied_for_employee(self):
        """
        Employee should get Werbungskostenpauschale (EUR 132) as income deduction.
        """
        engine = TaxCalculationEngine(TAX_CONFIG_2026_FALLBACK)
        result = engine.calculate_total_tax(
            gross_income=Decimal("40000"),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
            use_cache=False,
        )

        assert "werbungskostenpauschale_amount" in result.deductions.breakdown
        assert result.deductions.breakdown["werbungskostenpauschale_amount"] == Decimal("132.00")
