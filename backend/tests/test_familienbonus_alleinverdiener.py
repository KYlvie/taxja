"""Tests for Familienbonus Plus and Alleinverdienerabsetzbetrag integration."""
import pytest
from decimal import Decimal
from hypothesis import given, strategies as st, settings, HealthCheck

from app.services.deduction_calculator import DeductionCalculator, FamilyInfo
from app.services.tax_calculation_engine import TaxCalculationEngine
from app.services.svs_calculator import UserType


@pytest.fixture
def calculator():
    return DeductionCalculator()


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


# ── Familienbonus Plus constants ──────────────────────────────────────────────

class TestFamilienbonusConstants:
    def test_under_18_value(self, calculator):
        assert calculator.FAMILIENBONUS_UNDER_18 == Decimal('2000.00')

    def test_18_to_24_value(self, calculator):
        assert calculator.FAMILIENBONUS_18_24 == Decimal('700.00')


# ── Alleinverdiener constants ─────────────────────────────────────────────────

class TestAlleinverdienerConstants:
    def test_base_value(self, calculator):
        assert calculator.ALLEINVERDIENER_BASE == Decimal('520.00')

    def test_per_child_value(self, calculator):
        assert calculator.ALLEINVERDIENER_PER_CHILD == Decimal('704.00')


# ── calculate_familienbonus ───────────────────────────────────────────────────

class TestCalculateFamilienbonus:
    def test_no_children(self, calculator):
        info = FamilyInfo(num_children=0)
        result = calculator.calculate_familienbonus(info)
        assert result.amount == Decimal('0.00')

    def test_one_child_under_18(self, calculator):
        info = FamilyInfo(num_children=1, children_under_18=1)
        result = calculator.calculate_familienbonus(info)
        assert result.amount == Decimal('2000.00')

    def test_two_children_under_18(self, calculator):
        info = FamilyInfo(num_children=2, children_under_18=2)
        result = calculator.calculate_familienbonus(info)
        assert result.amount == Decimal('4000.00')

    def test_one_child_18_to_24(self, calculator):
        info = FamilyInfo(num_children=1, children_18_to_24=1)
        result = calculator.calculate_familienbonus(info)
        assert result.amount == Decimal('700.00')

    def test_mixed_ages(self, calculator):
        info = FamilyInfo(num_children=3, children_under_18=2, children_18_to_24=1)
        result = calculator.calculate_familienbonus(info)
        assert result.amount == Decimal('4700.00')  # 2×2000 + 1×700

    def test_breakdown_structure(self, calculator):
        info = FamilyInfo(num_children=2, children_under_18=1, children_18_to_24=1)
        result = calculator.calculate_familienbonus(info)
        assert result.breakdown['children_under_18'] == 1
        assert result.breakdown['children_18_to_24'] == 1
        assert result.breakdown['bonus_under_18_total'] == Decimal('2000.00')
        assert result.breakdown['bonus_18_24_total'] == Decimal('700.00')


# ── calculate_alleinverdiener ─────────────────────────────────────────────────

class TestCalculateAlleinverdiener:
    def test_not_eligible_no_children(self, calculator):
        info = FamilyInfo(num_children=0, is_single_parent=True)
        result = calculator.calculate_alleinverdiener(info)
        assert result.amount == Decimal('0.00')

    def test_not_eligible_not_single_or_sole(self, calculator):
        info = FamilyInfo(num_children=2)
        result = calculator.calculate_alleinverdiener(info)
        assert result.amount == Decimal('0.00')

    def test_single_parent_one_child(self, calculator):
        info = FamilyInfo(num_children=1, is_single_parent=True, children_under_18=1)
        result = calculator.calculate_alleinverdiener(info)
        assert result.amount == Decimal('520.00')

    def test_single_parent_two_children(self, calculator):
        info = FamilyInfo(num_children=2, is_single_parent=True, children_under_18=2)
        result = calculator.calculate_alleinverdiener(info)
        assert result.amount == Decimal('1224.00')  # 520 + 704

    def test_single_parent_three_children(self, calculator):
        info = FamilyInfo(num_children=3, is_single_parent=True, children_under_18=3)
        result = calculator.calculate_alleinverdiener(info)
        assert result.amount == Decimal('1928.00')  # 520 + 2×704

    def test_sole_earner_one_child(self, calculator):
        info = FamilyInfo(num_children=1, is_sole_earner=True, children_under_18=1)
        result = calculator.calculate_alleinverdiener(info)
        assert result.amount == Decimal('520.00')

    def test_sole_earner_two_children(self, calculator):
        info = FamilyInfo(num_children=2, is_sole_earner=True, children_under_18=2)
        result = calculator.calculate_alleinverdiener(info)
        assert result.amount == Decimal('1224.00')

    def test_breakdown_type_single_parent(self, calculator):
        info = FamilyInfo(num_children=1, is_single_parent=True, children_under_18=1)
        result = calculator.calculate_alleinverdiener(info)
        assert result.breakdown['type'] == 'Alleinerzieherabsetzbetrag'

    def test_breakdown_type_sole_earner(self, calculator):
        info = FamilyInfo(num_children=1, is_sole_earner=True, children_under_18=1)
        result = calculator.calculate_alleinverdiener(info)
        assert result.breakdown['type'] == 'Alleinverdienerabsetzbetrag'


# ── calculate_total_deductions integration ────────────────────────────────────

class TestTotalDeductionsIntegration:
    def test_familienbonus_in_breakdown(self, calculator):
        info = FamilyInfo(num_children=1, children_under_18=1)
        result = calculator.calculate_total_deductions(family_info=info)
        assert 'familienbonus_amount' in result.breakdown
        assert result.breakdown['familienbonus_amount'] == Decimal('2000.00')

    def test_alleinverdiener_in_breakdown(self, calculator):
        info = FamilyInfo(num_children=1, is_single_parent=True, children_under_18=1)
        result = calculator.calculate_total_deductions(family_info=info)
        assert 'alleinverdiener_amount' in result.breakdown
        assert result.breakdown['alleinverdiener_amount'] == Decimal('520.00')

    def test_no_familienbonus_without_children(self, calculator):
        info = FamilyInfo(num_children=0)
        result = calculator.calculate_total_deductions(family_info=info)
        assert 'familienbonus_amount' not in result.breakdown

    def test_no_alleinverdiener_without_eligibility(self, calculator):
        info = FamilyInfo(num_children=2, children_under_18=2)
        result = calculator.calculate_total_deductions(family_info=info)
        assert 'alleinverdiener_amount' not in result.breakdown

    def test_both_credits_present(self, calculator):
        info = FamilyInfo(
            num_children=2, is_single_parent=True,
            children_under_18=2
        )
        result = calculator.calculate_total_deductions(family_info=info)
        assert result.breakdown['familienbonus_amount'] == Decimal('4000.00')
        assert result.breakdown['alleinverdiener_amount'] == Decimal('1224.00')


# ── Tax engine integration ────────────────────────────────────────────────────

class TestTaxEngineFamilienbonusIntegration:
    def test_familienbonus_reduces_tax(self, engine):
        """Familienbonus should reduce income tax liability."""
        family = FamilyInfo(num_children=1, children_under_18=1)
        with_bonus = engine.calculate_total_tax(
            gross_income=Decimal('50000'),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
            family_info=family,
        )
        without_bonus = engine.calculate_total_tax(
            gross_income=Decimal('50000'),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
            family_info=FamilyInfo(num_children=0),
        )
        # With Familienbonus, tax should be lower (Kinderabsetzbetrag also helps,
        # but the €2000 credit is the dominant factor)
        assert with_bonus.income_tax.total_tax < without_bonus.income_tax.total_tax

    def test_alleinverdiener_reduces_tax(self, engine):
        """Alleinverdiener credit should reduce income tax liability."""
        family_with = FamilyInfo(
            num_children=1, is_single_parent=True, children_under_18=1
        )
        family_without = FamilyInfo(
            num_children=1, children_under_18=1
        )
        with_credit = engine.calculate_total_tax(
            gross_income=Decimal('50000'),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
            family_info=family_with,
        )
        without_credit = engine.calculate_total_tax(
            gross_income=Decimal('50000'),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
            family_info=family_without,
        )
        assert with_credit.income_tax.total_tax < without_credit.income_tax.total_tax

    def test_tax_cannot_go_negative(self, engine):
        """Even with large credits, tax should not go below zero."""
        family = FamilyInfo(
            num_children=5, is_single_parent=True,
            children_under_18=5
        )
        result = engine.calculate_total_tax(
            gross_income=Decimal('15000'),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
            family_info=family,
        )
        assert result.income_tax.total_tax >= Decimal('0.00')

    def test_self_employed_gets_familienbonus(self, engine):
        """Familienbonus applies to all user types, not just employees."""
        family = FamilyInfo(num_children=1, children_under_18=1)
        with_bonus = engine.calculate_total_tax(
            gross_income=Decimal('50000'),
            tax_year=2026,
            user_type=UserType.GSVG,
            family_info=family,
        )
        without_bonus = engine.calculate_total_tax(
            gross_income=Decimal('50000'),
            tax_year=2026,
            user_type=UserType.GSVG,
            family_info=FamilyInfo(num_children=0),
        )
        assert with_bonus.income_tax.total_tax < without_bonus.income_tax.total_tax


# ── Property-based tests ─────────────────────────────────────────────────────

class TestFamilienbonusProperties:
    @given(
        under_18=st.integers(min_value=0, max_value=10),
        age_18_24=st.integers(min_value=0, max_value=5),
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_familienbonus_non_negative(self, calculator, under_18, age_18_24):
        total = under_18 + age_18_24
        info = FamilyInfo(
            num_children=total,
            children_under_18=under_18,
            children_18_to_24=age_18_24,
        )
        result = calculator.calculate_familienbonus(info)
        assert result.amount >= Decimal('0.00')

    @given(
        under_18=st.integers(min_value=0, max_value=10),
        age_18_24=st.integers(min_value=0, max_value=5),
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_familienbonus_exact_formula(self, calculator, under_18, age_18_24):
        total = under_18 + age_18_24
        info = FamilyInfo(
            num_children=total,
            children_under_18=under_18,
            children_18_to_24=age_18_24,
        )
        result = calculator.calculate_familienbonus(info)
        expected = (
            Decimal('2000') * under_18 + Decimal('700') * age_18_24
        ).quantize(Decimal('0.01'))
        assert result.amount == expected

    @given(
        num_children=st.integers(min_value=1, max_value=8),
        is_single_parent=st.booleans(),
        is_sole_earner=st.booleans(),
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_alleinverdiener_formula(
        self, calculator, num_children, is_single_parent, is_sole_earner
    ):
        info = FamilyInfo(
            num_children=num_children,
            is_single_parent=is_single_parent,
            is_sole_earner=is_sole_earner,
            children_under_18=num_children,
        )
        result = calculator.calculate_alleinverdiener(info)
        eligible = (is_single_parent or is_sole_earner) and num_children > 0
        if eligible:
            expected = (
                Decimal('520') + Decimal('704') * max(0, num_children - 1)
            ).quantize(Decimal('0.01'))
            assert result.amount == expected
        else:
            assert result.amount == Decimal('0.00')

    @given(income=st.integers(min_value=15000, max_value=200000))
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_tax_with_credits_non_negative(self, engine, income):
        family = FamilyInfo(
            num_children=3, is_single_parent=True,
            children_under_18=3
        )
        result = engine.calculate_total_tax(
            gross_income=Decimal(str(income)),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
            family_info=family,
            use_cache=False,
        )
        assert result.income_tax.total_tax >= Decimal('0.00')
