"""
Property-based tests for employee tax refund calculation

Property 23: Employee tax refund calculation correctness
Validates: Requirements 37.3, 37.4

These tests verify universal properties that must hold for all valid
employee refund calculations.
"""

import pytest
from decimal import Decimal
from hypothesis import given, strategies as st, assume, settings
from datetime import datetime

from app.services.employee_refund_calculator import (
    EmployeeRefundCalculator,
    LohnzettelData,
    RefundResult,
    FamilyInfo,
)


# Simple User class for testing
class User:
    def __init__(self):
        self.id = 1
        self.email = "test@example.com"
        self.commuting_distance = 0
        self.public_transport_available = False
        self.family_info = FamilyInfo()


# Strategies for generating test data
@st.composite
def lohnzettel_data_strategy(draw):
    """Generate valid Lohnzettel data"""
    gross_income = draw(
        st.decimals(
            min_value=Decimal("10000.00"),
            max_value=Decimal("150000.00"),
            places=2,
        )
    )

    # Withheld tax should be reasonable (0-50% of gross income)
    withheld_tax = draw(
        st.decimals(
            min_value=Decimal("0.00"),
            max_value=gross_income * Decimal("0.50"),
            places=2,
        )
    )

    # Withheld SVS should be reasonable (0-20% of gross income)
    withheld_svs = draw(
        st.decimals(
            min_value=Decimal("0.00"),
            max_value=gross_income * Decimal("0.20"),
            places=2,
        )
    )

    employer_name = draw(st.text(min_size=1, max_size=100))
    tax_year = draw(st.integers(min_value=2020, max_value=2030))

    return LohnzettelData(
        gross_income=gross_income,
        withheld_tax=withheld_tax,
        withheld_svs=withheld_svs,
        employer_name=employer_name,
        tax_year=tax_year,
    )


@st.composite
def user_strategy(draw):
    """Generate valid User with family and commuting info"""
    user = User()
    user.id = draw(st.integers(min_value=1, max_value=10000))
    user.email = f"user{user.id}@example.com"

    # Commuting info
    user.commuting_distance = draw(st.integers(min_value=0, max_value=100))
    user.public_transport_available = draw(st.booleans())

    # Family info
    num_children = draw(st.integers(min_value=0, max_value=5))
    is_single_parent = draw(st.booleans())

    user.family_info = FamilyInfo(
        num_children=num_children, is_single_parent=is_single_parent
    )

    return user


class TestEmployeeRefundProperties:
    """Property-based tests for employee refund calculation"""

    @given(lohnzettel_data=lohnzettel_data_strategy(), user=user_strategy())
    @settings(max_examples=100, deadline=None)
    def test_refund_amount_equals_difference(self, lohnzettel_data, user):
        """
        Property: Refund amount should equal withheld tax minus actual tax liability

        For all valid Lohnzettel data and user info:
        refund_amount = |withheld_tax - actual_tax_liability|
        """
        calculator = EmployeeRefundCalculator()

        result = calculator.calculate_refund(lohnzettel_data, user)

        expected_refund = abs(
            lohnzettel_data.withheld_tax - result.actual_tax_liability
        )

        assert result.refund_amount == expected_refund, (
            f"Refund amount {result.refund_amount} does not equal "
            f"difference {expected_refund}"
        )

    @given(lohnzettel_data=lohnzettel_data_strategy(), user=user_strategy())
    @settings(max_examples=100, deadline=None)
    def test_refund_flag_consistency(self, lohnzettel_data, user):
        """
        Property: is_refund flag should be consistent with refund amount

        For all valid calculations:
        - is_refund = True when withheld_tax > actual_tax_liability
        - is_refund = False when withheld_tax < actual_tax_liability
        """
        calculator = EmployeeRefundCalculator()

        result = calculator.calculate_refund(lohnzettel_data, user)

        if lohnzettel_data.withheld_tax > result.actual_tax_liability:
            assert result.is_refund is True, "Should be refund when withheld > actual"
        elif lohnzettel_data.withheld_tax < result.actual_tax_liability:
            assert (
                result.is_refund is False
            ), "Should not be refund when withheld < actual"
        else:
            # Equal case - either flag is acceptable
            pass

    @given(lohnzettel_data=lohnzettel_data_strategy(), user=user_strategy())
    @settings(max_examples=100, deadline=None)
    def test_actual_tax_never_exceeds_gross_income(self, lohnzettel_data, user):
        """
        Property: Actual tax liability should never exceed gross income

        For all valid calculations:
        actual_tax_liability <= gross_income
        """
        calculator = EmployeeRefundCalculator()

        result = calculator.calculate_refund(lohnzettel_data, user)

        assert result.actual_tax_liability <= lohnzettel_data.gross_income, (
            f"Actual tax {result.actual_tax_liability} exceeds "
            f"gross income {lohnzettel_data.gross_income}"
        )

    @given(lohnzettel_data=lohnzettel_data_strategy(), user=user_strategy())
    @settings(max_examples=100, deadline=None)
    def test_deductions_reduce_tax_liability(self, lohnzettel_data, user):
        """
        Property: Applying deductions should reduce or maintain tax liability

        For all valid calculations:
        tax_with_deductions <= tax_without_deductions
        """
        calculator = EmployeeRefundCalculator()

        # Calculate with deductions
        result_with_deductions = calculator.calculate_refund(lohnzettel_data, user)

        # Calculate without deductions (create user with no deduction eligibility)
        user_no_deductions = User()
        user_no_deductions.id = user.id
        user_no_deductions.email = user.email
        user_no_deductions.commuting_distance = 0  # No commuting allowance
        user_no_deductions.family_info = FamilyInfo(
            num_children=0, is_single_parent=False
        )

        result_without_deductions = calculator.calculate_refund(
            lohnzettel_data, user_no_deductions
        )

        assert result_with_deductions.actual_tax_liability <= result_without_deductions.actual_tax_liability, (
            f"Tax with deductions {result_with_deductions.actual_tax_liability} "
            f"exceeds tax without deductions {result_without_deductions.actual_tax_liability}"
        )

    @given(lohnzettel_data=lohnzettel_data_strategy(), user=user_strategy())
    @settings(max_examples=100, deadline=None)
    def test_refund_calculation_deterministic(self, lohnzettel_data, user):
        """
        Property: Refund calculation should be deterministic

        For all valid inputs:
        Calculating twice with same inputs produces same result
        """
        calculator = EmployeeRefundCalculator()

        result1 = calculator.calculate_refund(lohnzettel_data, user)
        result2 = calculator.calculate_refund(lohnzettel_data, user)

        assert result1.refund_amount == result2.refund_amount
        assert result1.is_refund == result2.is_refund
        assert result1.actual_tax_liability == result2.actual_tax_liability

    @given(
        gross_income=st.decimals(
            min_value=Decimal("10000.00"),
            max_value=Decimal("150000.00"),
            places=2,
        ),
        user=user_strategy(),
    )
    @settings(max_examples=50, deadline=None)
    def test_higher_income_never_decreases_absolute_tax(self, gross_income, user):
        """
        Property: Higher gross income should never decrease absolute tax liability

        For all valid incomes:
        If income2 > income1, then tax(income2) >= tax(income1)
        (Progressive tax system property)
        """
        calculator = EmployeeRefundCalculator()

        # Calculate tax for base income
        lohnzettel1 = LohnzettelData(
            gross_income=gross_income,
            withheld_tax=Decimal("0.00"),
            withheld_svs=Decimal("0.00"),
            employer_name="Test",
            tax_year=2026,
        )

        result1 = calculator.calculate_refund(lohnzettel1, user)

        # Calculate tax for higher income
        higher_income = gross_income + Decimal("1000.00")
        lohnzettel2 = LohnzettelData(
            gross_income=higher_income,
            withheld_tax=Decimal("0.00"),
            withheld_svs=Decimal("0.00"),
            employer_name="Test",
            tax_year=2026,
        )

        result2 = calculator.calculate_refund(lohnzettel2, user)

        assert result2.actual_tax_liability >= result1.actual_tax_liability, (
            f"Higher income {higher_income} resulted in lower tax "
            f"{result2.actual_tax_liability} vs {result1.actual_tax_liability}"
        )

    @given(lohnzettel_data=lohnzettel_data_strategy(), user=user_strategy())
    @settings(max_examples=100, deadline=None)
    def test_breakdown_consistency(self, lohnzettel_data, user):
        """
        Property: Breakdown should be consistent with result

        For all valid calculations:
        - breakdown.gross_income == lohnzettel_data.gross_income
        - breakdown.withheld_tax == lohnzettel_data.withheld_tax
        - breakdown.difference == refund_amount (with correct sign)
        """
        calculator = EmployeeRefundCalculator()

        result = calculator.calculate_refund(lohnzettel_data, user)

        assert Decimal(str(result.breakdown["gross_income"])) == lohnzettel_data.gross_income
        assert Decimal(str(result.breakdown["withheld_tax"])) == lohnzettel_data.withheld_tax

        expected_difference = (
            lohnzettel_data.withheld_tax - result.actual_tax_liability
        )
        assert Decimal(str(result.breakdown["difference"])) == expected_difference

    @given(lohnzettel_data=lohnzettel_data_strategy(), user=user_strategy())
    @settings(max_examples=100, deadline=None)
    def test_explanation_not_empty(self, lohnzettel_data, user):
        """
        Property: Explanation should always be provided

        For all valid calculations:
        explanation is not empty and contains key information
        """
        calculator = EmployeeRefundCalculator()

        result = calculator.calculate_refund(lohnzettel_data, user)

        assert result.explanation, "Explanation should not be empty"
        assert len(result.explanation) > 50, "Explanation should be meaningful"

        # Check for key terms
        if result.is_refund:
            assert "refund" in result.explanation.lower()
        else:
            assert "additional" in result.explanation.lower() or "pay" in result.explanation.lower()

    @given(
        lohnzettel_data=lohnzettel_data_strategy(),
        user=user_strategy(),
        additional_deduction=st.decimals(
            min_value=Decimal("0.00"),
            max_value=Decimal("5000.00"),
            places=2,
        ),
    )
    @settings(max_examples=50, deadline=None)
    def test_additional_deductions_increase_refund(
        self, lohnzettel_data, user, additional_deduction
    ):
        """
        Property: Additional deductions should increase refund (or decrease payment)

        For all valid calculations:
        refund_with_additional >= refund_without_additional
        """
        calculator = EmployeeRefundCalculator()

        # Calculate without additional deductions
        result_without = calculator.calculate_refund(lohnzettel_data, user)

        # Calculate with additional deductions
        result_with = calculator.calculate_refund(
            lohnzettel_data, user, additional_deductions={"donation": additional_deduction}
        )

        # Additional deductions should reduce tax liability
        assert result_with.actual_tax_liability <= result_without.actual_tax_liability

        # If it was a refund, it should be larger; if payment, it should be smaller
        if result_without.is_refund and result_with.is_refund:
            assert result_with.refund_amount >= result_without.refund_amount
        elif not result_without.is_refund and not result_with.is_refund:
            assert result_with.refund_amount <= result_without.refund_amount


class TestRefundCalculationEdgeCases:
    """Test edge cases for refund calculation"""

    def test_zero_withheld_tax(self):
        """Test when no tax was withheld"""
        calculator = EmployeeRefundCalculator()

        lohnzettel = LohnzettelData(
            gross_income=Decimal("30000.00"),
            withheld_tax=Decimal("0.00"),
            withheld_svs=Decimal("0.00"),
            employer_name="Test",
            tax_year=2026,
        )

        user = User()
        user.id = 1
        user.email = "test@example.com"
        user.commuting_distance = 0
        user.family_info = FamilyInfo(num_children=0, is_single_parent=False)

        result = calculator.calculate_refund(lohnzettel, user)

        # Should owe tax
        assert result.is_refund is False
        assert result.refund_amount > 0
        assert result.actual_tax_liability > 0

    def test_very_high_withheld_tax(self):
        """Test when withheld tax is very high"""
        calculator = EmployeeRefundCalculator()

        lohnzettel = LohnzettelData(
            gross_income=Decimal("30000.00"),
            withheld_tax=Decimal("15000.00"),  # 50% withheld
            withheld_svs=Decimal("0.00"),
            employer_name="Test",
            tax_year=2026,
        )

        user = User()
        user.id = 1
        user.email = "test@example.com"
        user.commuting_distance = 0
        user.family_info = FamilyInfo(num_children=0, is_single_parent=False)

        result = calculator.calculate_refund(lohnzettel, user)

        # Should get large refund
        assert result.is_refund is True
        assert result.refund_amount > 0

    def test_income_below_exemption(self):
        """Test when income is below tax exemption threshold"""
        calculator = EmployeeRefundCalculator()

        lohnzettel = LohnzettelData(
            gross_income=Decimal("12000.00"),  # Below €13,539 exemption
            withheld_tax=Decimal("500.00"),
            withheld_svs=Decimal("0.00"),
            employer_name="Test",
            tax_year=2026,
        )

        user = User()
        user.id = 1
        user.email = "test@example.com"
        user.commuting_distance = 0
        user.family_info = FamilyInfo(num_children=0, is_single_parent=False)

        result = calculator.calculate_refund(lohnzettel, user)

        # Should get full refund (no tax owed)
        assert result.is_refund is True
        assert result.actual_tax_liability == Decimal("0.00")
        assert result.refund_amount == Decimal("500.00")
