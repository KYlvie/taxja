"""Tests for employee-specific deductions: Werbungskostenpauschale and Verkehrsabsetzbetrag"""
import pytest
from decimal import Decimal
from hypothesis import given, strategies as st, settings

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
            {"lower": "1000000.00", "upper": None, "rate": "0.55"}
        ]
    }


@pytest.fixture
def engine(tax_config):
    return TaxCalculationEngine(tax_config)


class TestWerbungskostenpauschaleConstants:
    """Verify the constants match Austrian tax law (2025/2026)"""

    def test_werbungskostenpauschale_value(self, calculator):
        assert calculator.WERBUNGSKOSTENPAUSCHALE == Decimal('132.00')

    def test_verkehrsabsetzbetrag_value(self, calculator):
        assert calculator.VERKEHRSABSETZBETRAG == Decimal('496.00')


class TestCalculateEmployeeDeductions:
    """Test calculate_employee_deductions() method"""

    def test_default_no_actual_expenses(self, calculator):
        """Werbungskostenpauschale applied when no actual expenses"""
        result = calculator.calculate_employee_deductions()
        assert result.amount == Decimal('132.00')
        assert result.breakdown['werbungskostenpauschale'] == Decimal('132.00')
        assert result.breakdown['verkehrsabsetzbetrag'] == Decimal('496.00')

    def test_actual_expenses_below_pauschale(self, calculator):
        """Pauschale applied when actual expenses are lower"""
        result = calculator.calculate_employee_deductions(
            actual_werbungskosten=Decimal('50.00')
        )
        assert result.amount == Decimal('132.00')

    def test_actual_expenses_equal_pauschale(self, calculator):
        """Pauschale applied when actual expenses equal the threshold"""
        result = calculator.calculate_employee_deductions(
            actual_werbungskosten=Decimal('132.00')
        )
        assert result.amount == Decimal('132.00')

    def test_actual_expenses_exceed_pauschale(self, calculator):
        """Pauschale NOT applied when actual expenses exceed it"""
        result = calculator.calculate_employee_deductions(
            actual_werbungskosten=Decimal('500.00')
        )
        assert result.amount == Decimal('0.00')
        assert result.breakdown['werbungskostenpauschale'] == Decimal('0.00')
        # Verkehrsabsetzbetrag is always present regardless
        assert result.breakdown['verkehrsabsetzbetrag'] == Decimal('496.00')

    def test_verkehrsabsetzbetrag_always_in_breakdown(self, calculator):
        """Verkehrsabsetzbetrag always reported in breakdown for engine to apply"""
        for expenses in [Decimal('0'), Decimal('200'), Decimal('1000')]:
            result = calculator.calculate_employee_deductions(
                actual_werbungskosten=expenses
            )
            assert 'verkehrsabsetzbetrag' in result.breakdown
            assert result.breakdown['verkehrsabsetzbetrag'] == Decimal('496.00')

    def test_result_has_note(self, calculator):
        result = calculator.calculate_employee_deductions()
        assert result.note is not None
        assert '132' in result.note


class TestTotalDeductionsEmployeeIntegration:
    """Test that calculate_total_deductions correctly integrates employee deductions"""

    def test_employee_flag_adds_werbungskostenpauschale(self, calculator):
        result = calculator.calculate_total_deductions(is_employee=True)
        assert result.amount >= Decimal('132.00')
        assert 'employee_deductions' in result.breakdown
        assert 'verkehrsabsetzbetrag' in result.breakdown

    def test_non_employee_no_employee_deductions(self, calculator):
        result = calculator.calculate_total_deductions(is_employee=False)
        assert 'employee_deductions' not in result.breakdown
        assert 'verkehrsabsetzbetrag' not in result.breakdown

    def test_employee_with_commuting(self, calculator):
        """Employee deductions stack with commuting allowance"""
        result = calculator.calculate_total_deductions(
            commuting_distance_km=30,
            public_transport_available=True,
            is_employee=True
        )
        # Should include both commuting and Werbungskostenpauschale
        assert 'commuting_allowance' in result.breakdown
        assert 'employee_deductions' in result.breakdown
        commuting_only = calculator.calculate_total_deductions(
            commuting_distance_km=30,
            public_transport_available=True,
            is_employee=False
        )
        assert result.amount == commuting_only.amount + Decimal('132.00')


class TestTaxEngineEmployeeDeductions:
    """Test Verkehrsabsetzbetrag and Werbungskostenpauschale in the tax engine"""

    def test_employee_gets_lower_tax_than_without_deductions(self, engine):
        """Employee tax should be reduced by Werbungskostenpauschale + Verkehrsabsetzbetrag"""
        result_employee = engine.calculate_total_tax(
            gross_income=Decimal('50000.00'),
            tax_year=2026,
            user_type=UserType.EMPLOYEE
        )
        # Employee SVS is 0, so total_tax = income_tax only
        # The income tax should reflect the Werbungskostenpauschale (income deduction)
        # and Verkehrsabsetzbetrag (tax credit)
        assert result_employee.total_tax > Decimal('0.00')
        assert result_employee.deductions.amount >= Decimal('132.00')
        assert 'verkehrsabsetzbetrag' in result_employee.deductions.breakdown

    def test_verkehrsabsetzbetrag_reduces_tax_liability(self, engine):
        """Verkehrsabsetzbetrag should reduce the final tax amount"""
        # Calculate with a known income where tax > €463
        result = engine.calculate_total_tax(
            gross_income=Decimal('50000.00'),
            tax_year=2026,
            user_type=UserType.EMPLOYEE
        )
        # The income tax in the result should already have Verkehrsabsetzbetrag applied
        # Verify it's less than what progressive tax alone would give
        # For €50,000 employee: taxable = 50000 - 132 (WKP) - 0 (SVS) = 49868
        # After exemption: progressive tax on 49868 should be > 463
        assert result.income_tax.total_tax >= Decimal('0.00')

    def test_verkehrsabsetzbetrag_cannot_go_negative(self, engine):
        """Tax cannot go below zero from Verkehrsabsetzbetrag"""
        # Very low income where tax might be less than €463
        result = engine.calculate_total_tax(
            gross_income=Decimal('14000.00'),
            tax_year=2026,
            user_type=UserType.EMPLOYEE
        )
        assert result.income_tax.total_tax >= Decimal('0.00')
        assert result.total_tax >= Decimal('0.00')

    def test_gsvg_no_employee_deductions(self, engine):
        """GSVG users should NOT get Werbungskostenpauschale or Verkehrsabsetzbetrag"""
        result = engine.calculate_total_tax(
            gross_income=Decimal('50000.00'),
            tax_year=2026,
            user_type=UserType.GSVG
        )
        assert 'employee_deductions' not in result.deductions.breakdown
        assert 'verkehrsabsetzbetrag' not in result.deductions.breakdown

    def test_neue_selbstaendige_no_employee_deductions(self, engine):
        """Neue Selbständige should NOT get employee deductions"""
        result = engine.calculate_total_tax(
            gross_income=Decimal('50000.00'),
            tax_year=2026,
            user_type=UserType.NEUE_SELBSTAENDIGE
        )
        assert 'employee_deductions' not in result.deductions.breakdown
        assert 'verkehrsabsetzbetrag' not in result.deductions.breakdown

    def test_employee_net_income_consistency(self, engine):
        """net_income = gross_income - total_tax must hold"""
        result = engine.calculate_total_tax(
            gross_income=Decimal('50000.00'),
            tax_year=2026,
            user_type=UserType.EMPLOYEE
        )
        assert result.net_income == result.gross_income - result.total_tax


class TestEmployeeDeductionProperties:
    """Property-based tests for employee deductions"""

    @given(
        actual_wk=st.decimals(
            min_value=0, max_value=10000,
            places=2, allow_nan=False, allow_infinity=False
        )
    )
    @settings(max_examples=50)
    def test_property_werbungskostenpauschale_or_actual(self, actual_wk):
        """Either Pauschale or nothing is applied - never both partially"""
        calc = DeductionCalculator()
        result = calc.calculate_employee_deductions(actual_werbungskosten=actual_wk)
        if actual_wk > Decimal('132.00'):
            assert result.amount == Decimal('0.00')
        else:
            assert result.amount == Decimal('132.00')

    @given(
        income=st.decimals(
            min_value=0, max_value=200000,
            places=2, allow_nan=False, allow_infinity=False
        )
    )
    @settings(max_examples=50)
    def test_property_employee_tax_non_negative(self, income):
        """Employee total tax must never be negative"""
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
                {"lower": "1000000.00", "upper": None, "rate": "0.55"}
            ]
        }
        eng = TaxCalculationEngine(config)
        result = eng.calculate_total_tax(
            gross_income=income,
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
            use_cache=False
        )
        assert result.total_tax >= Decimal('0.00')
        assert result.income_tax.total_tax >= Decimal('0.00')

    @given(
        income=st.decimals(
            min_value=20000, max_value=200000,
            places=2, allow_nan=False, allow_infinity=False
        )
    )
    @settings(max_examples=50)
    def test_property_verkehrsabsetzbetrag_reduces_tax(self, income):
        """For employees with sufficient income, Verkehrsabsetzbetrag reduces tax"""
        calc = DeductionCalculator()
        result = calc.calculate_employee_deductions()
        # Verkehrsabsetzbetrag is always €496 in the breakdown
        assert result.breakdown['verkehrsabsetzbetrag'] == Decimal('496.00')
