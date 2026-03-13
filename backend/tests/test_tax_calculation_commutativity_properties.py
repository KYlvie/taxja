"""
Property-based tests for Tax Calculation Commutativity

Property 6: Tax calculation commutativity
Validates: Requirements 16.1

This test ensures that the tax calculation is order-independent:
- Transaction order should not affect total tax calculation
- The same set of transactions should always produce the same tax result
"""

import pytest
from decimal import Decimal
from hypothesis import given, strategies as st, assume
from hypothesis import settings, HealthCheck
from typing import List
import random

from app.services.tax_calculation_engine import TaxCalculationEngine
from app.services.vat_calculator import Transaction, PropertyType
from app.services.svs_calculator import UserType
from app.services.deduction_calculator import FamilyInfo


@pytest.fixture
def tax_config_2026():
    """Tax configuration for 2026"""
    return {
        "tax_brackets": [
            {"lower": "0", "upper": "13539", "rate": "0.00"},
            {"lower": "13539", "upper": "21992", "rate": "0.20"},
            {"lower": "21992", "upper": "36458", "rate": "0.30"},
            {"lower": "36458", "upper": "70365", "rate": "0.40"},
            {"lower": "70365", "upper": "104859", "rate": "0.48"},
            {"lower": "104859", "upper": "1000000", "rate": "0.50"},
            {"lower": "1000000", "upper": None, "rate": "0.55"},
        ],
        "exemption_amount": "13539.00"
    }


# Strategy for generating transactions
@st.composite
def transaction_strategy(draw):
    """Generate a valid transaction"""
    is_income = draw(st.booleans())
    amount = draw(st.decimals(
        min_value=Decimal("0.01"),
        max_value=Decimal("10000.00"),
        places=2,
        allow_nan=False,
        allow_infinity=False
    ))
    
    return Transaction(
        amount=amount,
        is_income=is_income,
        property_type=None,
        vat_opted_in=False
    )


class TestTaxCalculationCommutativity:
    """
    Property 6: Tax calculation commutativity
    
    This test validates that tax calculations are order-independent:
    1. Transaction order does not affect total tax
    2. Same transactions in different orders produce identical results
    3. Shuffling transactions preserves tax calculation
    """
    
    @given(
        transactions=st.lists(
            transaction_strategy(),
            min_size=1,
            max_size=20
        ),
        gross_income=st.decimals(
            min_value=Decimal("10000.00"),
            max_value=Decimal("100000.00"),
            places=2,
            allow_nan=False,
            allow_infinity=False
        )
    )
    @settings(
        suppress_health_check=[HealthCheck.function_scoped_fixture],
        max_examples=50
    )
    def test_transaction_order_independence(self, tax_config_2026, transactions, gross_income):
        """
        Property: Tax calculation is independent of transaction order
        
        For any set of transactions T, tax(T) = tax(shuffle(T))
        
        This ensures that the order in which transactions are added
        does not affect the final tax calculation.
        """
        assume(len(transactions) > 0)
        
        engine = TaxCalculationEngine(tax_config_2026)
        
        # Calculate gross turnover from transactions
        gross_turnover = sum(
            txn.amount for txn in transactions if txn.is_income
        )
        
        # Calculate tax with original transaction order
        result1 = engine.calculate_total_tax(
            gross_income=gross_income,
            tax_year=2026,
            user_type=UserType.GSVG,
            transactions=transactions,
            gross_turnover=gross_turnover
        )
        
        # Shuffle transactions and calculate again
        shuffled_transactions = transactions.copy()
        random.shuffle(shuffled_transactions)
        
        result2 = engine.calculate_total_tax(
            gross_income=gross_income,
            tax_year=2026,
            user_type=UserType.GSVG,
            transactions=shuffled_transactions,
            gross_turnover=gross_turnover
        )
        
        # Assert commutativity: total tax should be identical
        assert result1.total_tax == result2.total_tax, (
            f"Commutativity violated: original order tax {result1.total_tax}, "
            f"shuffled order tax {result2.total_tax}"
        )
        
        # Also verify individual components are identical
        assert result1.income_tax.total_tax == result2.income_tax.total_tax, (
            f"Income tax differs: {result1.income_tax.total_tax} vs {result2.income_tax.total_tax}"
        )
        
        assert result1.vat.net_vat == result2.vat.net_vat, (
            f"VAT differs: {result1.vat.net_vat} vs {result2.vat.net_vat}"
        )
        
        assert result1.svs.annual_total == result2.svs.annual_total, (
            f"SVS differs: {result1.svs.annual_total} vs {result2.svs.annual_total}"
        )
    
    @given(
        transactions=st.lists(
            transaction_strategy(),
            min_size=2,
            max_size=10
        ),
        gross_income=st.decimals(
            min_value=Decimal("20000.00"),
            max_value=Decimal("80000.00"),
            places=2,
            allow_nan=False,
            allow_infinity=False
        )
    )
    @settings(
        suppress_health_check=[HealthCheck.function_scoped_fixture],
        max_examples=30
    )
    def test_multiple_shuffles_consistency(self, tax_config_2026, transactions, gross_income):
        """
        Property: Multiple shuffles of the same transactions produce identical tax
        
        This is a stronger test that verifies consistency across multiple
        random orderings of the same transaction set.
        """
        assume(len(transactions) >= 2)
        
        engine = TaxCalculationEngine(tax_config_2026)
        
        # Calculate gross turnover
        gross_turnover = sum(
            txn.amount for txn in transactions if txn.is_income
        )
        
        # Calculate tax with original order
        original_result = engine.calculate_total_tax(
            gross_income=gross_income,
            tax_year=2026,
            user_type=UserType.GSVG,
            transactions=transactions,
            gross_turnover=gross_turnover
        )
        
        # Test with 5 different random orderings
        for _ in range(5):
            shuffled = transactions.copy()
            random.shuffle(shuffled)
            
            shuffled_result = engine.calculate_total_tax(
                gross_income=gross_income,
                tax_year=2026,
                user_type=UserType.GSVG,
                transactions=shuffled,
                gross_turnover=gross_turnover
            )
            
            assert original_result.total_tax == shuffled_result.total_tax, (
                f"Consistency violated across shuffles: "
                f"original {original_result.total_tax}, shuffled {shuffled_result.total_tax}"
            )
    
    @given(
        transactions=st.lists(
            transaction_strategy(),
            min_size=1,
            max_size=15
        ),
        gross_income=st.decimals(
            min_value=Decimal("15000.00"),
            max_value=Decimal("90000.00"),
            places=2,
            allow_nan=False,
            allow_infinity=False
        )
    )
    @settings(
        suppress_health_check=[HealthCheck.function_scoped_fixture],
        max_examples=40
    )
    def test_reverse_order_equivalence(self, tax_config_2026, transactions, gross_income):
        """
        Property: Tax calculation with reversed transaction order is identical
        
        For any transaction list T, tax(T) = tax(reverse(T))
        
        This is a specific case of commutativity testing reverse order.
        """
        assume(len(transactions) > 0)
        
        engine = TaxCalculationEngine(tax_config_2026)
        
        # Calculate gross turnover
        gross_turnover = sum(
            txn.amount for txn in transactions if txn.is_income
        )
        
        # Calculate tax with original order
        forward_result = engine.calculate_total_tax(
            gross_income=gross_income,
            tax_year=2026,
            user_type=UserType.GSVG,
            transactions=transactions,
            gross_turnover=gross_turnover
        )
        
        # Calculate tax with reversed order
        reversed_transactions = list(reversed(transactions))
        
        reverse_result = engine.calculate_total_tax(
            gross_income=gross_income,
            tax_year=2026,
            user_type=UserType.GSVG,
            transactions=reversed_transactions,
            gross_turnover=gross_turnover
        )
        
        # Assert equivalence
        assert forward_result.total_tax == reverse_result.total_tax, (
            f"Reverse order equivalence violated: "
            f"forward {forward_result.total_tax}, reverse {reverse_result.total_tax}"
        )
        
        assert forward_result.net_income == reverse_result.net_income, (
            f"Net income differs: forward {forward_result.net_income}, "
            f"reverse {reverse_result.net_income}"
        )
    
    def test_known_transaction_sets(self, tax_config_2026):
        """
        Test commutativity with known transaction sets
        
        This test uses specific transaction sets to verify commutativity
        with concrete examples.
        """
        engine = TaxCalculationEngine(tax_config_2026)
        
        # Create a known set of transactions
        transactions = [
            Transaction(
                amount=Decimal("1000.00"),
                is_income=True,
                property_type=None,
                vat_opted_in=False
            ),
            Transaction(
                amount=Decimal("2000.00"),
                is_income=True,
                property_type=None,
                vat_opted_in=False
            ),
            Transaction(
                amount=Decimal("500.00"),
                is_income=False,
                property_type=None,
                vat_opted_in=False
            ),
            Transaction(
                amount=Decimal("1500.00"),
                is_income=True,
                property_type=None,
                vat_opted_in=False
            ),
        ]
        
        gross_income = Decimal("50000.00")
        gross_turnover = Decimal("4500.00")
        
        # Calculate with original order
        result1 = engine.calculate_total_tax(
            gross_income=gross_income,
            tax_year=2026,
            user_type=UserType.GSVG,
            transactions=transactions,
            gross_turnover=gross_turnover
        )
        
        # Test multiple orderings
        orderings = [
            [transactions[3], transactions[0], transactions[2], transactions[1]],
            [transactions[2], transactions[3], transactions[1], transactions[0]],
            [transactions[1], transactions[2], transactions[0], transactions[3]],
        ]
        
        for ordering in orderings:
            result = engine.calculate_total_tax(
                gross_income=gross_income,
                tax_year=2026,
                user_type=UserType.GSVG,
                transactions=ordering,
                gross_turnover=gross_turnover
            )
            
            assert result.total_tax == result1.total_tax, (
                f"Known transaction set commutativity failed: "
                f"expected {result1.total_tax}, got {result.total_tax}"
            )
    
    @given(
        gross_income=st.decimals(
            min_value=Decimal("20000.00"),
            max_value=Decimal("100000.00"),
            places=2,
            allow_nan=False,
            allow_infinity=False
        )
    )
    @settings(
        suppress_health_check=[HealthCheck.function_scoped_fixture],
        max_examples=30
    )
    def test_empty_and_single_transaction_commutativity(self, tax_config_2026, gross_income):
        """
        Property: Edge cases (empty and single transaction) are commutative
        
        This tests the trivial cases where commutativity should obviously hold.
        """
        engine = TaxCalculationEngine(tax_config_2026)
        
        # Test with no transactions (None)
        result_none = engine.calculate_total_tax(
            gross_income=gross_income,
            tax_year=2026,
            user_type=UserType.GSVG,
            transactions=None,
            gross_turnover=None
        )
        
        # Test with empty list
        result_empty = engine.calculate_total_tax(
            gross_income=gross_income,
            tax_year=2026,
            user_type=UserType.GSVG,
            transactions=[],
            gross_turnover=Decimal("0.00")
        )
        
        # Both should produce the same result (no VAT)
        assert result_none.total_tax == result_empty.total_tax, (
            f"Empty transaction commutativity failed: "
            f"None {result_none.total_tax}, empty {result_empty.total_tax}"
        )
        
        # Test with single transaction
        single_txn = [
            Transaction(
                amount=Decimal("1000.00"),
                is_income=True,
                property_type=None,
                vat_opted_in=False
            )
        ]
        
        result_single = engine.calculate_total_tax(
            gross_income=gross_income,
            tax_year=2026,
            user_type=UserType.GSVG,
            transactions=single_txn,
            gross_turnover=Decimal("1000.00")
        )
        
        # Single transaction should be commutative with itself (trivially)
        result_single_again = engine.calculate_total_tax(
            gross_income=gross_income,
            tax_year=2026,
            user_type=UserType.GSVG,
            transactions=single_txn,
            gross_turnover=Decimal("1000.00")
        )
        
        assert result_single.total_tax == result_single_again.total_tax, (
            f"Single transaction commutativity failed"
        )


class TestTaxCalculationDeterminism:
    """
    Additional tests for deterministic behavior of tax calculations
    
    These tests ensure that repeated calculations with the same inputs
    always produce the same outputs.
    """
    
    @given(
        gross_income=st.decimals(
            min_value=Decimal("10000.00"),
            max_value=Decimal("150000.00"),
            places=2,
            allow_nan=False,
            allow_infinity=False
        )
    )
    @settings(
        suppress_health_check=[HealthCheck.function_scoped_fixture],
        max_examples=50
    )
    def test_repeated_calculation_determinism(self, tax_config_2026, gross_income):
        """
        Property: Repeated calculations with same inputs produce identical results
        
        This ensures the tax calculation is deterministic and has no
        hidden state or randomness.
        """
        engine = TaxCalculationEngine(tax_config_2026)
        
        # Calculate tax multiple times with same inputs
        results = []
        for _ in range(10):
            result = engine.calculate_total_tax(
                gross_income=gross_income,
                tax_year=2026,
                user_type=UserType.GSVG
            )
            results.append(result.total_tax)
        
        # All results should be identical
        first_result = results[0]
        for i, result in enumerate(results[1:], start=1):
            assert result == first_result, (
                f"Determinism violated: calculation {i} produced {result}, "
                f"expected {first_result}"
            )
    
    @given(
        transactions=st.lists(
            transaction_strategy(),
            min_size=1,
            max_size=10
        ),
        gross_income=st.decimals(
            min_value=Decimal("20000.00"),
            max_value=Decimal("80000.00"),
            places=2,
            allow_nan=False,
            allow_infinity=False
        )
    )
    @settings(
        suppress_health_check=[HealthCheck.function_scoped_fixture],
        max_examples=30
    )
    def test_calculation_idempotence(self, tax_config_2026, transactions, gross_income):
        """
        Property: Calculating tax multiple times is idempotent
        
        For any inputs I, tax(I) = tax(I) = tax(I) ...
        
        This ensures that the calculation function has no side effects
        that would change results on repeated calls.
        """
        assume(len(transactions) > 0)
        
        engine = TaxCalculationEngine(tax_config_2026)
        
        gross_turnover = sum(
            txn.amount for txn in transactions if txn.is_income
        )
        
        # Calculate tax 5 times
        results = []
        for _ in range(5):
            result = engine.calculate_total_tax(
                gross_income=gross_income,
                tax_year=2026,
                user_type=UserType.GSVG,
                transactions=transactions,
                gross_turnover=gross_turnover
            )
            results.append(result)
        
        # All results should be identical
        first = results[0]
        for i, result in enumerate(results[1:], start=1):
            assert result.total_tax == first.total_tax, (
                f"Idempotence violated at call {i}: "
                f"got {result.total_tax}, expected {first.total_tax}"
            )
            assert result.net_income == first.net_income, (
                f"Net income idempotence violated at call {i}"
            )
