"""
Regression tests for 8 critical tax logic fixes (March 2026 audit).

These tests pin the corrections to prevent regressions:
1. Employee refund: tax_before_credits != final_tax when credits exist
2. Familienbonus / AVAB / VAB / PAB reduce final_tax (not taxable_income)
3. Große Pendlerpauschale works at distance=5km with no public transport
4. AfA accelerated depreciation: Year 1 = 3×, Year 2 = 2×, Year 3+ = 1×
5. Kinderabsetzbetrag does NOT reduce taxable_income
6. calculate_total_deductions separates income deductions from tax credits
7. Pendlereuro is a tax credit (Absetzbetrag), not an income deduction
8. Sonderausgabenpauschale is an income deduction (Sonderausgabe), not a tax credit
"""

import pytest
from decimal import Decimal

from app.services.employee_refund_calculator import (
    EmployeeRefundCalculator,
    LohnzettelData,
    FamilyInfo,
)
from app.services.deduction_calculator import (
    DeductionCalculator,
    FamilyInfo as DeductionFamilyInfo,
)
from app.services.afa_calculator import AfACalculator


# ──────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────

class MockUser:
    """Minimal user for testing."""

    def __init__(
        self,
        commuting_distance=0,
        public_transport_available=False,
        num_children=0,
        is_single_parent=False,
        children_under_18=0,
        children_18_to_24=0,
        is_sole_earner=False,
        telearbeit_days=None,
        employer_telearbeit_pauschale=None,
    ):
        self.id = 1
        self.email = "test@example.com"
        self.commuting_distance = commuting_distance
        self.public_transport_available = public_transport_available
        self.telearbeit_days = telearbeit_days
        self.employer_telearbeit_pauschale = employer_telearbeit_pauschale
        self.family_info = FamilyInfo(
            num_children=num_children,
            is_single_parent=is_single_parent,
            children_under_18=children_under_18,
            children_18_to_24=children_18_to_24,
            is_sole_earner=is_sole_earner,
        )


def make_lohnzettel(gross=Decimal("40000"), withheld=Decimal("8000"), year=2026):
    return LohnzettelData(
        gross_income=gross,
        withheld_tax=withheld,
        withheld_svs=Decimal("0"),
        employer_name="Test GmbH",
        tax_year=year,
    )


# ══════════════════════════════════════════════════════
# 1. Employee refund: tax credits actually reduce tax
# ══════════════════════════════════════════════════════

class TestRefundAbsetzbetraegeApplied:
    """Verify that Absetzbeträge reduce final_tax below tariff_tax."""

    def test_tax_before_credits_differs_from_final_tax(self):
        """
        For a typical employee with €40k income, there is always
        at least VAB (€496) as a tax credit.
        So tax_before_credits must be strictly > actual_tax_liability.
        """
        calc = EmployeeRefundCalculator()
        user = MockUser()
        lz = make_lohnzettel(gross=Decimal("40000"), withheld=Decimal("8000"))

        result = calc.calculate_refund(lz, user)

        tax_before = Decimal(str(result.breakdown["tax_before_credits"]))
        final_tax = result.actual_tax_liability

        # Credits exist → final must be less than pre-credit tax
        assert final_tax < tax_before, (
            f"final_tax ({final_tax}) must be < tax_before_credits ({tax_before})"
        )
        # At minimum VAB = €496
        assert tax_before - final_tax >= Decimal("496"), (
            f"At least €496 credits expected, got {tax_before - final_tax}"
        )

    def test_tax_credits_dict_populated(self):
        """RefundResult.tax_credits_applied must contain VAB but NOT Sonderausgabenpauschale."""
        calc = EmployeeRefundCalculator()
        user = MockUser()
        lz = make_lohnzettel()

        result = calc.calculate_refund(lz, user)

        assert "verkehrsabsetzbetrag" in result.tax_credits_applied
        assert result.tax_credits_applied["verkehrsabsetzbetrag"] > Decimal("0")
        # Sonderausgabenpauschale is an income deduction, NOT a tax credit
        assert "sonderausgabenpauschale" not in result.tax_credits_applied


# ══════════════════════════════════════════════════════
# 2. Familienbonus / AVAB / VAB reduce tax liability
# ══════════════════════════════════════════════════════

class TestFamilienbonusReducesTax:
    """Familienbonus Plus must reduce actual_tax_liability, not taxable_income."""

    def test_familienbonus_reduces_final_tax(self):
        """
        User with 1 child under 18 should get ~€2000 Familienbonus.
        This must reduce final_tax, not appear in income deductions.
        """
        calc = EmployeeRefundCalculator()

        # Without children
        user_no_kids = MockUser()
        lz = make_lohnzettel(gross=Decimal("50000"), withheld=Decimal("10000"))
        result_no_kids = calc.calculate_refund(lz, user_no_kids)

        # With 1 child under 18
        user_1_child = MockUser(num_children=1, children_under_18=1)
        result_1_child = calc.calculate_refund(lz, user_1_child)

        # Familienbonus should reduce tax, not taxable income
        assert result_1_child.actual_tax_liability < result_no_kids.actual_tax_liability
        assert "familienbonus_plus" in result_1_child.tax_credits_applied

        # Taxable income should be the SAME (Familienbonus is NOT an income deduction)
        taxable_no_kids = Decimal(str(result_no_kids.breakdown["taxable_income"]))
        taxable_1_child = Decimal(str(result_1_child.breakdown["taxable_income"]))
        assert taxable_no_kids == taxable_1_child, (
            "Familienbonus must not change taxable_income"
        )

    def test_avab_reduces_final_tax(self):
        """Alleinverdienerabsetzbetrag must reduce final_tax."""
        calc = EmployeeRefundCalculator()

        user_avab = MockUser(
            num_children=1,
            children_under_18=1,
            is_sole_earner=True,
        )
        user_no_avab = MockUser(num_children=1, children_under_18=1)
        lz = make_lohnzettel(gross=Decimal("35000"), withheld=Decimal("7000"))

        result_avab = calc.calculate_refund(lz, user_avab)
        result_no = calc.calculate_refund(lz, user_no_avab)

        assert result_avab.actual_tax_liability <= result_no.actual_tax_liability


# ══════════════════════════════════════════════════════
# 3. Große Pendlerpauschale at 5km (no public transport)
# ══════════════════════════════════════════════════════

class TestGrossePendlerpauschale:
    """Große Pendlerpauschale must be available at distance >= 2km without public transport."""

    def test_5km_no_public_transport_gets_pendler(self):
        """
        distance=5km, public_transport_available=False → Große Pendlerpauschale
        This must produce a non-zero pendlerpauschale income deduction.
        """
        calc = EmployeeRefundCalculator()
        user = MockUser(commuting_distance=5, public_transport_available=False)
        lz = make_lohnzettel(gross=Decimal("40000"), withheld=Decimal("8000"))

        result = calc.calculate_refund(lz, user)

        assert "pendlerpauschale" in result.deductions_applied
        assert result.deductions_applied["pendlerpauschale"] > Decimal("0"), (
            "Große Pendlerpauschale must apply at 5km without public transport"
        )

    def test_2km_no_public_transport_gets_pendler(self):
        """Minimum distance for Große Pendlerpauschale is 2km."""
        calc = EmployeeRefundCalculator()
        user = MockUser(commuting_distance=2, public_transport_available=False)
        lz = make_lohnzettel()

        result = calc.calculate_refund(lz, user)

        assert "pendlerpauschale" in result.deductions_applied
        assert result.deductions_applied["pendlerpauschale"] > Decimal("0")

    def test_1km_gets_no_pendler(self):
        """1km should not qualify for any Pendlerpauschale."""
        calc = EmployeeRefundCalculator()
        user = MockUser(commuting_distance=1, public_transport_available=False)
        lz = make_lohnzettel()

        result = calc.calculate_refund(lz, user)

        assert "pendlerpauschale" not in result.deductions_applied

    def test_kleine_pendlerpauschale_20km_with_transport(self):
        """20km with public transport → Kleine Pendlerpauschale."""
        calc = EmployeeRefundCalculator()
        user = MockUser(commuting_distance=20, public_transport_available=True)
        lz = make_lohnzettel()

        result = calc.calculate_refund(lz, user)

        assert "pendlerpauschale" in result.deductions_applied
        assert result.deductions_applied["pendlerpauschale"] > Decimal("0")


# ══════════════════════════════════════════════════════
# 4. AfA accelerated depreciation: 3×, 2×, 1×
# ══════════════════════════════════════════════════════

class TestAfAAcceleratedDepreciation:
    """Verify AfA acceleration formula: Year 1 = 3×, Year 2 = 2×, Year 3+ = normal."""

    def setup_method(self):
        self.calc = AfACalculator()

    def test_residential_general_acceleration(self):
        """Post-2020 residential: 4.5% → 3.0% → 1.5%"""
        base = Decimal("0.015")

        y1 = self.calc.get_effective_rate(base, 2022, 2023, 2023)
        y2 = self.calc.get_effective_rate(base, 2022, 2024, 2023)
        y3 = self.calc.get_effective_rate(base, 2022, 2025, 2023)
        y4 = self.calc.get_effective_rate(base, 2022, 2026, 2023)

        assert y1 == Decimal("0.0450"), f"Year 1 should be 4.5%, got {y1}"
        assert y2 == Decimal("0.0300"), f"Year 2 should be 3.0%, got {y2}"
        assert y3 == Decimal("0.015"), f"Year 3 should be 1.5%, got {y3}"
        assert y4 == Decimal("0.015"), f"Year 4 should be 1.5%, got {y4}"

    def test_commercial_general_acceleration(self):
        """Post-2020 commercial: 7.5% → 5.0% → 2.5%"""
        base = Decimal("0.025")

        y1 = self.calc.get_effective_rate(base, 2022, 2023, 2023, is_residential=False)
        y2 = self.calc.get_effective_rate(base, 2022, 2024, 2023, is_residential=False)
        y3 = self.calc.get_effective_rate(base, 2022, 2025, 2023, is_residential=False)

        assert y1 == Decimal("0.0750"), f"Year 1 should be 7.5%, got {y1}"
        assert y2 == Decimal("0.0500"), f"Year 2 should be 5.0%, got {y2}"
        assert y3 == Decimal("0.025"), f"Year 3 should be 2.5%, got {y3}"

    def test_pre_2020_no_acceleration(self):
        """Buildings completed before 2020 get no acceleration."""
        base = Decimal("0.015")

        rate = self.calc.get_effective_rate(base, 2019, 2020, 2020)
        assert rate == Decimal("0.015"), "Pre-2020 must not be accelerated"

    def test_eco_residential_extended_acceleration(self):
        """Eco residential 2024-2026: 4.5% → 4.5% → 4.5% → 1.5%"""
        base = Decimal("0.015")

        y1 = self.calc.get_effective_rate(base, 2025, 2025, 2025, eco_standard=True)
        y2 = self.calc.get_effective_rate(base, 2025, 2026, 2025, eco_standard=True)
        y3 = self.calc.get_effective_rate(base, 2025, 2027, 2025, eco_standard=True)
        y4 = self.calc.get_effective_rate(base, 2025, 2028, 2025, eco_standard=True)

        assert y1 == Decimal("0.0450"), f"Eco Year 1: {y1}"
        assert y2 == Decimal("0.0450"), f"Eco Year 2: {y2}"
        assert y3 == Decimal("0.0450"), f"Eco Year 3: {y3}"
        assert y4 == Decimal("0.015"), f"Eco Year 4: {y4}"

    def test_eco_outside_2024_2026_no_extension(self):
        """Eco standard on a 2022 building doesn't get 3-year extension."""
        base = Decimal("0.015")

        y2 = self.calc.get_effective_rate(base, 2022, 2024, 2023, eco_standard=True)
        assert y2 == Decimal("0.0300"), "2022 build with eco: year 2 should be 2×, not 3×"

    def test_residential_vs_commercial_base_rate(self):
        """Residential = 1.5%, Commercial = 2.5%."""
        assert self.calc.determine_depreciation_rate(is_commercial=False) == Decimal("0.015")
        assert self.calc.determine_depreciation_rate(is_commercial=True) == Decimal("0.025")

    def test_no_1915_distinction(self):
        """Pre-1915 and post-1915 residential both get 1.5%."""
        rate_old = self.calc.determine_depreciation_rate(construction_year=1890)
        rate_new = self.calc.determine_depreciation_rate(construction_year=1990)
        assert rate_old == rate_new == Decimal("0.015")


# ══════════════════════════════════════════════════════
# 5. Kinderabsetzbetrag does NOT affect taxable_income
# ══════════════════════════════════════════════════════

class TestKinderabsetzbetragNotDeduction:
    """Kinderabsetzbetrag must NOT reduce taxable_income (paid via Familienbeihilfe)."""

    def test_kinderabsetzbetrag_excluded_from_total_deductions(self):
        """
        calculate_total_deductions with children must NOT include
        Kinderabsetzbetrag in the returned amount.
        """
        dc = DeductionCalculator()

        # Without children
        result_no = dc.calculate_total_deductions(
            family_info=DeductionFamilyInfo(num_children=0),
        )

        # With 2 children
        result_2 = dc.calculate_total_deductions(
            family_info=DeductionFamilyInfo(num_children=2),
        )

        # Total income deduction amount must be the SAME
        # (Kinderabsetzbetrag is informational only, not in total)
        assert result_no.amount == result_2.amount, (
            f"Children should not change total income deductions: "
            f"no_kids={result_no.amount}, 2_kids={result_2.amount}"
        )

    def test_kinderabsetzbetrag_in_breakdown_as_info(self):
        """Kinderabsetzbetrag should appear in breakdown as informational item."""
        dc = DeductionCalculator()

        result = dc.calculate_total_deductions(
            family_info=DeductionFamilyInfo(num_children=2),
        )

        assert "kinderabsetzbetrag_info" in result.breakdown, (
            "Kinderabsetzbetrag should be in breakdown as informational"
        )

    def test_employee_refund_taxable_income_unchanged_by_children(self):
        """In the full refund flow, taxable_income must not change due to children."""
        calc = EmployeeRefundCalculator()
        lz = make_lohnzettel(gross=Decimal("45000"), withheld=Decimal("9000"))

        result_no = calc.calculate_refund(lz, MockUser())
        result_kids = calc.calculate_refund(
            lz, MockUser(num_children=2, children_under_18=2)
        )

        ti_no = Decimal(str(result_no.breakdown["taxable_income"]))
        ti_kids = Decimal(str(result_kids.breakdown["taxable_income"]))

        assert ti_no == ti_kids, (
            f"Taxable income must not change: {ti_no} vs {ti_kids}"
        )


# ══════════════════════════════════════════════════════
# 6. Income deductions vs tax credits separation
# ══════════════════════════════════════════════════════

class TestDeductionCreditSeparation:
    """Verify clear separation between income deductions and tax credits."""

    def test_refund_breakdown_has_both_sections(self):
        """Breakdown must contain both income deductions and tax credits sections."""
        calc = EmployeeRefundCalculator()
        user = MockUser(num_children=1, children_under_18=1)
        lz = make_lohnzettel(gross=Decimal("50000"), withheld=Decimal("12000"))

        result = calc.calculate_refund(lz, user)

        # Income deductions section
        assert "total_income_deductions" in result.breakdown
        assert "taxable_income" in result.breakdown

        # Tax credits section
        assert "tax_before_credits" in result.breakdown
        assert "total_tax_credits" in result.breakdown
        assert "tax_credits_detail" in result.breakdown

        # Both are populated
        assert result.breakdown["total_tax_credits"] > 0
        assert result.breakdown["total_income_deductions"] > 0

    def test_five_step_flow_consistency(self):
        """
        Verify the 5-step calculation flow:
        1. taxable_income = gross - income_deductions
        2. tax_before_credits = tariff(taxable_income)
        3. tax_credits = sum of Absetzbeträge
        4. final_tax = max(0, tax_before_credits - tax_credits)
        5. refund = withheld - final_tax
        """
        calc = EmployeeRefundCalculator()
        user = MockUser(commuting_distance=25, public_transport_available=True)
        lz = make_lohnzettel(
            gross=Decimal("50000"),
            withheld=Decimal("12000"),
        )

        result = calc.calculate_refund(lz, user)
        bd = result.breakdown

        # Step 1
        expected_taxable = Decimal("50000") - Decimal(str(bd["total_income_deductions"]))
        assert Decimal(str(bd["taxable_income"])) == expected_taxable

        # Step 4
        tax_before = Decimal(str(bd["tax_before_credits"]))
        total_credits = Decimal(str(bd["total_tax_credits"]))
        expected_final = max(Decimal("0"), tax_before - total_credits)
        assert result.actual_tax_liability == expected_final

        # Step 5
        expected_refund = lz.withheld_tax - result.actual_tax_liability
        if expected_refund > Decimal("0"):
            assert result.is_refund is True
            assert result.refund_amount == expected_refund
        else:
            assert result.is_refund is False
            assert result.refund_amount == abs(expected_refund)


# ══════════════════════════════════════════════════════
# 7. Pendlereuro is a tax credit, not income deduction
# ══════════════════════════════════════════════════════

class TestPendlereuroClassification:
    """Pendlereuro (€6/km/year) must be an Absetzbetrag (tax credit), not an income deduction."""

    def test_pendlereuro_in_tax_credits(self):
        """Pendlereuro must appear in tax_credits_applied, not deductions_applied."""
        calc = EmployeeRefundCalculator()
        user = MockUser(commuting_distance=25, public_transport_available=True)
        lz = make_lohnzettel(gross=Decimal("40000"), withheld=Decimal("8000"))

        result = calc.calculate_refund(lz, user)

        # Pendlereuro = 25km × €6 = €150 → must be in tax_credits
        assert "pendlereuro" in result.tax_credits_applied
        assert result.tax_credits_applied["pendlereuro"] == Decimal("150.00")

        # Must NOT be in income deductions
        assert "pendlereuro" not in result.deductions_applied

    def test_pendlerpauschale_separate_from_pendlereuro(self):
        """Pendlerpauschale (income deduction) and Pendlereuro (tax credit) must be separate."""
        calc = EmployeeRefundCalculator()
        user = MockUser(commuting_distance=25, public_transport_available=False)
        lz = make_lohnzettel()

        result = calc.calculate_refund(lz, user)

        # Pendlerpauschale in income deductions (base_annual only, no Pendlereuro)
        assert "pendlerpauschale" in result.deductions_applied
        pendlerpauschale = result.deductions_applied["pendlerpauschale"]

        # Pendlereuro in tax credits
        assert "pendlereuro" in result.tax_credits_applied
        pendlereuro = result.tax_credits_applied["pendlereuro"]

        # Pendlerpauschale should be the bracket-based annual amount (not including Pendlereuro)
        # For 25km Große Pendlerpauschale: bracket 20-40km = €123/month × 12 = €1,476
        assert pendlerpauschale == Decimal("1476.00"), f"Expected €1,476, got {pendlerpauschale}"
        assert pendlereuro == Decimal("150.00"), f"Expected €150, got {pendlereuro}"

    def test_no_commute_no_pendlereuro(self):
        """Without commuting, there should be no Pendlereuro in tax credits."""
        calc = EmployeeRefundCalculator()
        user = MockUser(commuting_distance=0)
        lz = make_lohnzettel()

        result = calc.calculate_refund(lz, user)

        assert "pendlereuro" not in result.tax_credits_applied


# ══════════════════════════════════════════════════════
# 8. Sonderausgabenpauschale is an income deduction
# ══════════════════════════════════════════════════════

class TestSonderausgabenpauschaleClassification:
    """Sonderausgabenpauschale (€60) must be a Sonderausgabe (income deduction), not a tax credit."""

    def test_sonderausgabenpauschale_in_income_deductions(self):
        """Sonderausgabenpauschale must appear in deductions_applied, not tax_credits_applied."""
        calc = EmployeeRefundCalculator()
        user = MockUser()
        lz = make_lohnzettel(gross=Decimal("40000"), withheld=Decimal("8000"))

        result = calc.calculate_refund(lz, user)

        # Must be in income deductions
        assert "sonderausgabenpauschale" in result.deductions_applied
        assert result.deductions_applied["sonderausgabenpauschale"] == Decimal("60.00")

        # Must NOT be in tax credits
        assert "sonderausgabenpauschale" not in result.tax_credits_applied

    def test_sonderausgabenpauschale_reduces_taxable_income(self):
        """Sonderausgabenpauschale must reduce taxable_income, not final_tax."""
        calc = EmployeeRefundCalculator()
        lz = make_lohnzettel(gross=Decimal("40000"), withheld=Decimal("8000"))

        result = calc.calculate_refund(lz, MockUser())

        # SAP (€60) is part of total_income_deductions
        total_deductions = Decimal(str(result.breakdown["total_income_deductions"]))
        taxable_income = Decimal(str(result.breakdown["taxable_income"]))

        # taxable_income = gross - total_income_deductions
        assert taxable_income == Decimal("40000") - total_deductions

        # SAP must be included in total_income_deductions
        assert total_deductions >= Decimal("60.00"), (
            f"Total deductions {total_deductions} must include at least €60 SAP"
        )

    def test_checkpoint_a_income_deductions_purity(self):
        """
        Checkpoint A: income_deductions must NOT contain any Absetzbeträge.
        Specifically: no Familienbonus, AVAB, VAB, Zuschlag VAB, Pendlereuro, Kinderabsetzbetrag.
        """
        calc = EmployeeRefundCalculator()
        user = MockUser(
            commuting_distance=25,
            public_transport_available=True,
            num_children=1,
            children_under_18=1,
            is_sole_earner=True,
        )
        lz = make_lohnzettel(gross=Decimal("50000"), withheld=Decimal("12000"))

        result = calc.calculate_refund(lz, user)

        forbidden_in_deductions = {
            "familienbonus_plus", "familienbonus",
            "alleinverdiener_aeab", "alleinverdiener",
            "verkehrsabsetzbetrag",
            "zuschlag_verkehrsabsetzbetrag",
            "pendlereuro",
            "kinderabsetzbetrag",
        }

        for key in forbidden_in_deductions:
            assert key not in result.deductions_applied, (
                f"'{key}' is an Absetzbetrag and must NOT be in income deductions"
            )

    def test_checkpoint_b_tax_credits_purity(self):
        """
        Checkpoint B: tax_credits must NOT contain Sonderausgabenpauschale.
        """
        calc = EmployeeRefundCalculator()
        user = MockUser()
        lz = make_lohnzettel()

        result = calc.calculate_refund(lz, user)

        assert "sonderausgabenpauschale" not in result.tax_credits_applied, (
            "Sonderausgabenpauschale is a Sonderausgabe, NOT an Absetzbetrag"
        )


# ══════════════════════════════════════════════════════
# 9. Telearbeitspauschale precise per-day calculation
# ══════════════════════════════════════════════════════

class TestTelearbeitspauschale:
    """Telearbeitspauschale: €3/day, max 100 days, minus employer-paid amount."""

    def test_none_days_returns_legacy_fallback(self):
        """None telearbeit_days → legacy fallback €300 (user hasn't filled in the field)."""
        dc = DeductionCalculator()
        result = dc.calculate_home_office_deduction(telearbeit_days=None)
        assert result.amount == Decimal("300.00")
        assert result.breakdown['mode'] == 'flat_rate_fallback'

    def test_zero_days_returns_zero(self):
        """0 telearbeit_days → user explicitly has 0 home-office days → €0."""
        dc = DeductionCalculator()
        result = dc.calculate_home_office_deduction(telearbeit_days=0)
        assert result.amount == Decimal("0.00")
        assert result.breakdown['mode'] == 'precise'

    def test_40_days_no_employer(self):
        """40 days × €3 = €120, employer paid €0 → €120."""
        dc = DeductionCalculator()
        result = dc.calculate_home_office_deduction(telearbeit_days=40)
        assert result.amount == Decimal("120.00")

    def test_100_days_no_employer(self):
        """100 days × €3 = €300, employer paid €0 → €300."""
        dc = DeductionCalculator()
        result = dc.calculate_home_office_deduction(telearbeit_days=100)
        assert result.amount == Decimal("300.00")

    def test_120_days_capped_at_100(self):
        """120 days capped to 100 → €300."""
        dc = DeductionCalculator()
        result = dc.calculate_home_office_deduction(telearbeit_days=120)
        assert result.amount == Decimal("300.00")

    def test_80_days_employer_paid_200(self):
        """80 days × €3 = €240 − €200 employer = €40."""
        dc = DeductionCalculator()
        result = dc.calculate_home_office_deduction(
            telearbeit_days=80,
            employer_telearbeit_pauschale=Decimal("200.00"),
        )
        assert result.amount == Decimal("40.00")

    def test_80_days_employer_paid_300(self):
        """80 days × €3 = €240 − €300 employer = €0 (no negative)."""
        dc = DeductionCalculator()
        result = dc.calculate_home_office_deduction(
            telearbeit_days=80,
            employer_telearbeit_pauschale=Decimal("300.00"),
        )
        assert result.amount == Decimal("0.00")

    def test_telearbeit_in_refund_flow(self):
        """Full refund flow: 60 days, employer paid €100 → €80 in income deductions."""
        calc = EmployeeRefundCalculator()
        user = MockUser(telearbeit_days=60, employer_telearbeit_pauschale=Decimal("100.00"))
        lz = make_lohnzettel(gross=Decimal("40000"), withheld=Decimal("8000"))

        result = calc.calculate_refund(lz, user)

        assert "telearbeit_pauschale" in result.deductions_applied
        assert result.deductions_applied["telearbeit_pauschale"] == Decimal("80.00")

    def test_zero_days_refund_flow_no_deduction(self):
        """Full refund flow: explicit 0 days → no telearbeit deduction (not €300 fallback)."""
        calc = EmployeeRefundCalculator()
        user = MockUser(telearbeit_days=0)
        lz = make_lohnzettel(gross=Decimal("40000"), withheld=Decimal("8000"))

        result = calc.calculate_refund(lz, user)

        assert "telearbeit_pauschale" not in result.deductions_applied

    def test_none_days_refund_flow_legacy_fallback(self):
        """Full refund flow: None days (legacy) → €300 flat fallback."""
        calc = EmployeeRefundCalculator()
        user = MockUser(telearbeit_days=None)
        lz = make_lohnzettel(gross=Decimal("40000"), withheld=Decimal("8000"))

        result = calc.calculate_refund(lz, user)

        assert "telearbeit_pauschale" in result.deductions_applied
        assert result.deductions_applied["telearbeit_pauschale"] == Decimal("300.00")

    def test_telearbeit_is_income_deduction_not_credit(self):
        """Telearbeitspauschale is Werbungskosten (income deduction), not Absetzbetrag."""
        calc = EmployeeRefundCalculator()
        user = MockUser(telearbeit_days=50)
        lz = make_lohnzettel()

        result = calc.calculate_refund(lz, user)

        # In income deductions
        assert "telearbeit_pauschale" in result.deductions_applied
        # NOT in tax credits
        assert "telearbeit_pauschale" not in result.tax_credits_applied
