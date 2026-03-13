"""Tests for self-employed tax features: Gewinnfreibetrag, Basispauschalierung, Kleinunternehmer."""
from decimal import Decimal
import pytest

from app.services.self_employed_tax_service import (
    calculate_gewinnfreibetrag,
    calculate_basispauschalierung,
    determine_kleinunternehmer_status,
    compare_expense_methods,
    ExpenseMethod,
    ProfessionType,
    GRUNDFREIBETRAG_MAX,
    GRUNDFREIBETRAG_PROFIT_LIMIT,
    MAX_TOTAL_FREIBETRAG,
)


# ===================================================================
# Gewinnfreibetrag (§10 EStG)
# ===================================================================

class TestGewinnfreibetrag:
    """Test profit tax-free allowance calculation."""

    def test_zero_profit(self):
        result = calculate_gewinnfreibetrag(Decimal("0"))
        assert result.total_freibetrag == Decimal("0.00")
        assert result.grundfreibetrag == Decimal("0.00")

    def test_negative_profit(self):
        result = calculate_gewinnfreibetrag(Decimal("-5000"))
        assert result.total_freibetrag == Decimal("0.00")

    def test_small_profit_only_grundfreibetrag(self):
        """Profit €20,000 → 15% = €3,000 Grundfreibetrag, no investment needed."""
        result = calculate_gewinnfreibetrag(Decimal("20000"))
        assert result.grundfreibetrag == Decimal("3000.00")
        assert result.investment_freibetrag == Decimal("0.00")
        assert result.total_freibetrag == Decimal("3000.00")

    def test_profit_at_33000_max_grundfreibetrag(self):
        """Profit exactly €33,000 → 15% = €4,950 (max Grundfreibetrag)."""
        result = calculate_gewinnfreibetrag(Decimal("33000"))
        assert result.grundfreibetrag == GRUNDFREIBETRAG_MAX
        assert result.investment_freibetrag == Decimal("0.00")
        assert result.total_freibetrag == GRUNDFREIBETRAG_MAX

    def test_profit_above_33000_no_investment(self):
        """Profit €53,000 but no investment → only Grundfreibetrag."""
        result = calculate_gewinnfreibetrag(Decimal("53000"), Decimal("0"))
        assert result.grundfreibetrag == GRUNDFREIBETRAG_MAX
        assert result.investment_freibetrag == Decimal("0.00")
        assert result.total_freibetrag == GRUNDFREIBETRAG_MAX
        # investment_required should show what COULD be claimed
        assert result.investment_required > Decimal("0")

    def test_profit_53000_with_investment(self):
        """Profit €53,000, invested €2,000 in securities.
        Excess = €20,000, 13% = €2,600 max, but capped by investment €2,000.
        Total = €4,950 + €2,000 = €6,950.
        (This matches the WKO example.)
        """
        result = calculate_gewinnfreibetrag(Decimal("53000"), Decimal("2000"))
        assert result.grundfreibetrag == GRUNDFREIBETRAG_MAX
        assert result.investment_freibetrag == Decimal("2000.00")
        assert result.total_freibetrag == Decimal("6950.00")
        assert result.investment_required == Decimal("2600.00")

    def test_profit_53000_full_investment(self):
        """Profit €53,000, invested €5,000 (more than needed).
        Excess = €20,000, 13% = €2,600 max.
        Total = €4,950 + €2,600 = €7,550.
        """
        result = calculate_gewinnfreibetrag(Decimal("53000"), Decimal("5000"))
        assert result.grundfreibetrag == GRUNDFREIBETRAG_MAX
        assert result.investment_freibetrag == Decimal("2600.00")
        assert result.total_freibetrag == Decimal("7550.00")

    def test_high_profit_tiered_rates(self):
        """Profit €250,000 with full investment.
        Grundfreibetrag: €4,950
        Tier 1: €175,000 × 13% = €22,750
        Tier 2: (€250,000 - €33,000 - €175,000) = €42,000 × 7% = €2,940
        Total investment-based: €25,690
        Grand total: €4,950 + €25,690 = €30,640
        """
        result = calculate_gewinnfreibetrag(Decimal("250000"), Decimal("50000"))
        assert result.grundfreibetrag == GRUNDFREIBETRAG_MAX
        assert result.investment_freibetrag == Decimal("25690.00")
        assert result.total_freibetrag == Decimal("30640.00")

    def test_cap_at_max(self):
        """Very high profit should be capped at MAX_TOTAL_FREIBETRAG."""
        result = calculate_gewinnfreibetrag(Decimal("600000"), Decimal("100000"))
        assert result.total_freibetrag <= MAX_TOTAL_FREIBETRAG
        assert result.capped or result.total_freibetrag == MAX_TOTAL_FREIBETRAG

    def test_profit_above_580000_no_additional(self):
        """Profit above €580,000 → no further investment-based allowance beyond tiers."""
        result = calculate_gewinnfreibetrag(Decimal("700000"), Decimal("200000"))
        # Should be capped
        assert result.total_freibetrag <= MAX_TOTAL_FREIBETRAG


# ===================================================================
# Basispauschalierung (§17 EStG)
# ===================================================================

class TestBasispauschalierung:
    """Test flat-rate expense deduction."""

    def test_general_profession(self):
        """Turnover €100,000, general profession → 13.5% flat rate."""
        result = calculate_basispauschalierung(Decimal("100000"))
        assert result.eligible is True
        assert result.flat_rate_expenses == Decimal("13500.00")
        assert result.flat_rate_pct == Decimal("0.135")

    def test_consulting_profession(self):
        """Turnover €100,000, consulting → 6% flat rate."""
        result = calculate_basispauschalierung(
            Decimal("100000"), ProfessionType.CONSULTING
        )
        assert result.eligible is True
        assert result.flat_rate_expenses == Decimal("6000.00")

    def test_exceeds_turnover_limit(self):
        """Turnover €400,000 → not eligible."""
        result = calculate_basispauschalierung(Decimal("400000"))
        assert result.eligible is False

    def test_profit_calculation_with_svs(self):
        """Turnover €80,000, SVS €8,000.
        Flat expenses: €80,000 × 13.5% = €10,800
        Profit: €80,000 - €10,800 - €8,000 = €61,200
        Grundfreibetrag: 15% × €33,000 = €4,950 (capped)
        Taxable: €61,200 - €4,950 = €56,250
        """
        result = calculate_basispauschalierung(
            gross_turnover=Decimal("80000"),
            svs_contributions=Decimal("8000"),
        )
        assert result.eligible is True
        assert result.flat_rate_expenses == Decimal("10800.00")
        assert result.estimated_profit == Decimal("61200.00")
        assert result.grundfreibetrag == GRUNDFREIBETRAG_MAX
        assert result.taxable_profit == Decimal("56250.00")

    def test_small_turnover_grundfreibetrag_not_maxed(self):
        """Turnover €20,000, no SVS.
        Flat expenses: €2,700
        Profit: €17,300
        Grundfreibetrag: 15% × €17,300 = €2,595
        Taxable: €14,705
        """
        result = calculate_basispauschalierung(Decimal("20000"))
        assert result.eligible is True
        assert result.flat_rate_expenses == Decimal("2700.00")
        assert result.estimated_profit == Decimal("17300.00")
        assert result.grundfreibetrag == Decimal("2595.00")
        assert result.taxable_profit == Decimal("14705.00")

    def test_at_turnover_limit(self):
        """Turnover exactly €320,000 → still eligible."""
        result = calculate_basispauschalierung(Decimal("320000"))
        assert result.eligible is True


# ===================================================================
# Kleinunternehmerregelung
# ===================================================================

class TestKleinunternehmerStatus:
    """Test VAT exemption status determination."""

    def test_under_threshold_exempt(self):
        result = determine_kleinunternehmer_status(Decimal("40000"))
        assert result.exempt is True
        assert result.ust_voranmeldung_required is False

    def test_at_threshold_exempt(self):
        result = determine_kleinunternehmer_status(Decimal("55000"))
        assert result.exempt is True

    def test_tolerance_zone(self):
        """€57,000 → tolerance applies, still exempt this year."""
        result = determine_kleinunternehmer_status(Decimal("57000"))
        assert result.exempt is True
        assert result.tolerance_applies is True
        assert len(result.warnings) > 0

    def test_tolerance_zone_previous_exceeded(self):
        """€57,000 but previous year also exceeded → NOT exempt."""
        result = determine_kleinunternehmer_status(
            Decimal("57000"), previous_year_exceeded=True
        )
        assert result.exempt is False
        assert result.ust_voranmeldung_required is True

    def test_above_threshold_vat_liable(self):
        result = determine_kleinunternehmer_status(Decimal("80000"))
        assert result.exempt is False
        assert result.ust_voranmeldung_required is True
        assert result.ust_voranmeldung_frequency == "quarterly"

    def test_high_turnover_monthly_uva(self):
        result = determine_kleinunternehmer_status(Decimal("150000"))
        assert result.exempt is False
        assert result.ust_voranmeldung_frequency == "monthly"

    def test_voluntary_registration_hint(self):
        """Under threshold but high input VAT → suggest voluntary registration."""
        result = determine_kleinunternehmer_status(
            Decimal("30000"), has_significant_input_vat=True
        )
        assert result.exempt is True
        assert result.voluntary_registration_recommended is True
        assert len(result.warnings) > 0


# ===================================================================
# Expense method comparison
# ===================================================================

class TestExpenseMethodComparison:
    """Test flat-rate vs actual expense comparison."""

    def test_flat_rate_better(self):
        """Low actual expenses → flat rate is better."""
        result = compare_expense_methods(
            gross_turnover=Decimal("100000"),
            actual_expenses=Decimal("5000"),
        )
        assert result.recommended_method == ExpenseMethod.FLAT_RATE

    def test_actual_better(self):
        """High actual expenses → actual method is better."""
        result = compare_expense_methods(
            gross_turnover=Decimal("100000"),
            actual_expenses=Decimal("40000"),
        )
        assert result.recommended_method == ExpenseMethod.ACTUAL

    def test_not_eligible_for_flat_rate(self):
        """Turnover too high → must use actual."""
        result = compare_expense_methods(
            gross_turnover=Decimal("400000"),
            actual_expenses=Decimal("50000"),
        )
        assert result.recommended_method == ExpenseMethod.ACTUAL
        assert "nicht anwendbar" in result.reason

    def test_investment_freibetrag_advantage(self):
        """Actual method with qualifying investment should benefit from
        full Gewinnfreibetrag (investment-based), making it more attractive."""
        result = compare_expense_methods(
            gross_turnover=Decimal("100000"),
            actual_expenses=Decimal("12000"),
            qualifying_investment=Decimal("20000"),
        )
        # With investment, actual method gets more Freibetrag
        # This should tip the balance toward actual
        assert result.recommended_method == ExpenseMethod.ACTUAL
