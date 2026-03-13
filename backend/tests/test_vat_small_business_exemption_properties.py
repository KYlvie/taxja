"""
Property-based tests for VAT small business exemption rules

**Validates: Requirements 4.1, 4.6, 4.7, 4.13**

Property 8: VAT small business exemption rules
- Turnover <= €55,000 qualifies for small business exemption
- Turnover > €55,000 and <= €60,500 qualifies for tolerance rule
- Turnover > €60,500 requires VAT registration
- Exemption status is deterministic based on turnover
- Threshold boundaries are correctly enforced
- Tolerance rule provides warning about next year cancellation
"""

import pytest
from hypothesis import given, strategies as st, assume, settings, HealthCheck
from decimal import Decimal
from app.services.vat_calculator import (
    VATCalculator,
    VATResult,
    Transaction,
    PropertyType
)


# Custom strategies for generating test data
def decimal_strategy(min_value=0, max_value=1000000, places=2):
    """Generate Decimal values with specified precision"""
    return st.decimals(
        min_value=Decimal(str(min_value)),
        max_value=Decimal(str(max_value)),
        allow_nan=False,
        allow_infinity=False,
        places=places
    )


def turnover_strategy():
    """Generate turnover values across all threshold ranges"""
    return st.one_of(
        # Below small business threshold
        decimal_strategy(min_value=0, max_value=55000),
        # In tolerance range
        decimal_strategy(min_value=55000.01, max_value=60500),
        # Above tolerance threshold
        decimal_strategy(min_value=60500.01, max_value=500000)
    )


@pytest.fixture
def calculator():
    """Create a VATCalculator instance"""
    return VATCalculator()


class TestProperty8VATSmallBusinessExemption:
    """
    **Property 8: VAT small business exemption rules**
    **Validates: Requirements 4.1, 4.6, 4.7, 4.13**
    
    Tests that VAT small business exemption:
    1. Applies correctly for turnover <= €55,000
    2. Applies tolerance rule for €55,000 < turnover <= €60,500
    3. Requires VAT registration for turnover > €60,500
    4. Is deterministic based on turnover amount
    5. Enforces threshold boundaries correctly
    6. Provides appropriate warnings for tolerance rule
    """
    
    @given(
        turnover=decimal_strategy(min_value=0, max_value=55000)
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_small_business_exemption_below_threshold(
        self,
        turnover: Decimal,
        calculator
    ):
        """
        Property: All turnover <= €55,000 qualifies for small business exemption
        
        For any turnover where 0 <= turnover <= €55,000:
        - exempt = True
        - reason contains "Small business exemption"
        - output_vat = €0
        - input_vat = €0
        - net_vat = €0
        
        **Validates: Requirements 4.1, 4.6**
        """
        result = calculator.calculate_vat_liability(
            gross_turnover=turnover,
            transactions=[]
        )
        
        # Verify exemption applies
        assert result.exempt is True, \
            f"Turnover €{turnover} should qualify for small business exemption"
        
        # Verify reason mentions small business exemption
        assert result.reason is not None, \
            "Exemption reason should be provided"
        assert "Small business exemption" in result.reason or "small business" in result.reason.lower(), \
            f"Reason should mention small business exemption, got: {result.reason}"
        
        # Verify no VAT is calculated
        assert result.output_vat == Decimal('0.00'), \
            f"Output VAT should be €0 for exempt business, got €{result.output_vat}"
        assert result.input_vat == Decimal('0.00'), \
            f"Input VAT should be €0 for exempt business, got €{result.input_vat}"
        assert result.net_vat == Decimal('0.00'), \
            f"Net VAT should be €0 for exempt business, got €{result.net_vat}"
        
        # Verify no warning for standard exemption
        # (Warning only applies to tolerance rule)
        if turnover < calculator.SMALL_BUSINESS_THRESHOLD:
            assert result.warning is None or "Tolerance" not in result.warning, \
                "Standard exemption should not have tolerance rule warning"
    
    @given(
        turnover=decimal_strategy(min_value=55000.01, max_value=60500)
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_tolerance_rule_applies_in_range(
        self,
        turnover: Decimal,
        calculator
    ):
        """
        Property: Tolerance rule applies for €55,000 < turnover <= €60,500
        
        For any turnover where €55,000 < turnover <= €60,500:
        - exempt = True
        - reason contains "Tolerance rule"
        - warning is provided about next year cancellation
        - warning mentions consulting Steuerberater
        
        **Validates: Requirements 4.7, 4.13**
        """
        result = calculator.calculate_vat_liability(
            gross_turnover=turnover,
            transactions=[]
        )
        
        # Verify exemption still applies
        assert result.exempt is True, \
            f"Turnover €{turnover} should qualify for tolerance rule exemption"
        
        # Verify reason mentions tolerance rule
        assert result.reason is not None, \
            "Tolerance rule reason should be provided"
        assert "Tolerance rule" in result.reason or "tolerance" in result.reason.lower(), \
            f"Reason should mention tolerance rule, got: {result.reason}"
        
        # Verify warning is provided
        assert result.warning is not None, \
            f"Tolerance rule should provide warning for turnover €{turnover}"
        
        # Verify warning mentions key information
        warning_lower = result.warning.lower()
        assert "steuerberater" in warning_lower or "tax advisor" in warning_lower, \
            f"Warning should mention consulting Steuerberater, got: {result.warning}"
        
        # Verify no VAT is calculated (still exempt)
        assert result.output_vat == Decimal('0.00'), \
            f"Output VAT should be €0 under tolerance rule, got €{result.output_vat}"
        assert result.input_vat == Decimal('0.00'), \
            f"Input VAT should be €0 under tolerance rule, got €{result.input_vat}"
        assert result.net_vat == Decimal('0.00'), \
            f"Net VAT should be €0 under tolerance rule, got €{result.net_vat}"
    
    @given(
        turnover=decimal_strategy(min_value=60500.01, max_value=500000)
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_vat_required_above_tolerance_threshold(
        self,
        turnover: Decimal,
        calculator
    ):
        """
        Property: VAT registration required for turnover > €60,500
        
        For any turnover where turnover > €60,500:
        - exempt = False
        - VAT must be calculated and paid
        - No exemption reason provided
        
        **Validates: Requirements 4.1, 4.6**
        """
        # Create some sample transactions to test VAT calculation
        transactions = [
            Transaction(amount=Decimal('12000.00'), is_income=True),
            Transaction(amount=Decimal('6000.00'), is_income=False),
        ]
        
        result = calculator.calculate_vat_liability(
            gross_turnover=turnover,
            transactions=transactions
        )
        
        # Verify no exemption applies
        assert result.exempt is False, \
            f"Turnover €{turnover} should require VAT registration (no exemption)"
        
        # Verify VAT is calculated
        # With transactions provided, output VAT should be > 0
        assert result.output_vat > Decimal('0.00'), \
            f"Output VAT should be calculated for turnover €{turnover}, got €{result.output_vat}"
        
        # Verify no exemption reason
        assert result.reason is None or "exempt" not in result.reason.lower(), \
            f"Should not have exemption reason for turnover €{turnover}"
    
    @given(
        turnover=turnover_strategy()
    )
    @settings(max_examples=300, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_exemption_status_is_deterministic(
        self,
        turnover: Decimal,
        calculator
    ):
        """
        Property: Exemption status is deterministic based on turnover
        
        For any turnover, calling calculate_vat_liability multiple times
        with the same turnover should always return the same exemption status.
        
        **Validates: Requirements 4.1, 4.6, 4.7**
        """
        # Calculate VAT liability twice
        result1 = calculator.calculate_vat_liability(
            gross_turnover=turnover,
            transactions=[]
        )
        
        result2 = calculator.calculate_vat_liability(
            gross_turnover=turnover,
            transactions=[]
        )
        
        # Verify results are identical
        assert result1.exempt == result2.exempt, \
            f"Exemption status should be deterministic for turnover €{turnover}"
        
        # Verify reason consistency
        assert result1.reason == result2.reason, \
            f"Exemption reason should be consistent for turnover €{turnover}"
        
        # Verify warning consistency
        assert result1.warning == result2.warning, \
            f"Warning should be consistent for turnover €{turnover}"
    
    @given(
        turnover=turnover_strategy()
    )
    @settings(max_examples=300, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_threshold_boundaries_correctly_enforced(
        self,
        turnover: Decimal,
        calculator
    ):
        """
        Property: Threshold boundaries are correctly enforced
        
        For any turnover:
        - If turnover <= €55,000: small business exemption
        - If €55,000 < turnover <= €60,500: tolerance rule
        - If turnover > €60,500: VAT required
        
        **Validates: Requirements 4.1, 4.6, 4.7**
        """
        result = calculator.calculate_vat_liability(
            gross_turnover=turnover,
            transactions=[]
        )
        
        # Determine expected exemption status based on thresholds
        if turnover <= calculator.SMALL_BUSINESS_THRESHOLD:
            # Should be exempt with small business exemption
            assert result.exempt is True, \
                f"Turnover €{turnover} <= €55,000 should be exempt"
            assert result.reason is not None and "small business" in result.reason.lower(), \
                f"Should have small business exemption reason for €{turnover}"
        
        elif turnover <= calculator.TOLERANCE_THRESHOLD:
            # Should be exempt with tolerance rule
            assert result.exempt is True, \
                f"Turnover €{turnover} in tolerance range should be exempt"
            assert result.reason is not None and "tolerance" in result.reason.lower(), \
                f"Should have tolerance rule reason for €{turnover}"
            assert result.warning is not None, \
                f"Should have warning for tolerance rule at €{turnover}"
        
        else:
            # Should not be exempt
            assert result.exempt is False, \
                f"Turnover €{turnover} > €60,500 should not be exempt"
    
    @given(
        turnover1=decimal_strategy(min_value=0, max_value=55000),
        turnover2=decimal_strategy(min_value=0, max_value=55000)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_all_turnovers_below_threshold_are_exempt(
        self,
        turnover1: Decimal,
        turnover2: Decimal,
        calculator
    ):
        """
        Property: All turnovers <= €55,000 are exempt (no exceptions)
        
        For any two turnovers both <= €55,000:
        - Both should be exempt
        - Both should have small business exemption reason
        
        **Validates: Requirements 4.1, 4.6**
        """
        result1 = calculator.calculate_vat_liability(
            gross_turnover=turnover1,
            transactions=[]
        )
        
        result2 = calculator.calculate_vat_liability(
            gross_turnover=turnover2,
            transactions=[]
        )
        
        # Both should be exempt
        assert result1.exempt is True, \
            f"Turnover €{turnover1} should be exempt"
        assert result2.exempt is True, \
            f"Turnover €{turnover2} should be exempt"
        
        # Both should have small business exemption
        assert "small business" in result1.reason.lower(), \
            f"€{turnover1} should have small business exemption"
        assert "small business" in result2.reason.lower(), \
            f"€{turnover2} should have small business exemption"
    
    @given(
        turnover1=decimal_strategy(min_value=55000.01, max_value=60500),
        turnover2=decimal_strategy(min_value=55000.01, max_value=60500)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_all_turnovers_in_tolerance_range_have_warning(
        self,
        turnover1: Decimal,
        turnover2: Decimal,
        calculator
    ):
        """
        Property: All turnovers in tolerance range have warning
        
        For any two turnovers both in (€55,000, €60,500]:
        - Both should be exempt
        - Both should have tolerance rule reason
        - Both should have warning
        
        **Validates: Requirements 4.7, 4.13**
        """
        result1 = calculator.calculate_vat_liability(
            gross_turnover=turnover1,
            transactions=[]
        )
        
        result2 = calculator.calculate_vat_liability(
            gross_turnover=turnover2,
            transactions=[]
        )
        
        # Both should be exempt
        assert result1.exempt is True, \
            f"Turnover €{turnover1} should be exempt under tolerance rule"
        assert result2.exempt is True, \
            f"Turnover €{turnover2} should be exempt under tolerance rule"
        
        # Both should have tolerance rule
        assert "tolerance" in result1.reason.lower(), \
            f"€{turnover1} should have tolerance rule"
        assert "tolerance" in result2.reason.lower(), \
            f"€{turnover2} should have tolerance rule"
        
        # Both should have warning
        assert result1.warning is not None, \
            f"€{turnover1} should have warning"
        assert result2.warning is not None, \
            f"€{turnover2} should have warning"
    
    @given(
        turnover1=decimal_strategy(min_value=60500.01, max_value=500000),
        turnover2=decimal_strategy(min_value=60500.01, max_value=500000)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_all_turnovers_above_tolerance_require_vat(
        self,
        turnover1: Decimal,
        turnover2: Decimal,
        calculator
    ):
        """
        Property: All turnovers > €60,500 require VAT registration
        
        For any two turnovers both > €60,500:
        - Both should not be exempt
        - Both should calculate VAT
        
        **Validates: Requirements 4.1, 4.6**
        """
        transactions = [
            Transaction(amount=Decimal('10000.00'), is_income=True),
        ]
        
        result1 = calculator.calculate_vat_liability(
            gross_turnover=turnover1,
            transactions=transactions
        )
        
        result2 = calculator.calculate_vat_liability(
            gross_turnover=turnover2,
            transactions=transactions
        )
        
        # Both should not be exempt
        assert result1.exempt is False, \
            f"Turnover €{turnover1} should not be exempt"
        assert result2.exempt is False, \
            f"Turnover €{turnover2} should not be exempt"
        
        # Both should calculate VAT
        assert result1.output_vat > Decimal('0.00'), \
            f"€{turnover1} should calculate output VAT"
        assert result2.output_vat > Decimal('0.00'), \
            f"€{turnover2} should calculate output VAT"
    
    def test_exact_threshold_boundaries(self, calculator):
        """
        Property: Exact threshold boundaries are correctly handled
        
        Test the exact boundary values:
        - €55,000.00: small business exemption (inclusive)
        - €55,000.01: tolerance rule
        - €60,500.00: tolerance rule (inclusive)
        - €60,500.01: VAT required
        
        **Validates: Requirements 4.1, 4.6, 4.7**
        """
        # Test €55,000.00 (exactly at small business threshold)
        result_55k = calculator.calculate_vat_liability(
            gross_turnover=Decimal('55000.00'),
            transactions=[]
        )
        assert result_55k.exempt is True, \
            "€55,000.00 should be exempt (small business)"
        assert "small business" in result_55k.reason.lower(), \
            "€55,000.00 should have small business exemption"
        
        # Test €55,000.01 (just above small business threshold)
        result_55k_01 = calculator.calculate_vat_liability(
            gross_turnover=Decimal('55000.01'),
            transactions=[]
        )
        assert result_55k_01.exempt is True, \
            "€55,000.01 should be exempt (tolerance rule)"
        assert "tolerance" in result_55k_01.reason.lower(), \
            "€55,000.01 should have tolerance rule"
        assert result_55k_01.warning is not None, \
            "€55,000.01 should have warning"
        
        # Test €60,500.00 (exactly at tolerance threshold)
        result_60_5k = calculator.calculate_vat_liability(
            gross_turnover=Decimal('60500.00'),
            transactions=[]
        )
        assert result_60_5k.exempt is True, \
            "€60,500.00 should be exempt (tolerance rule)"
        assert "tolerance" in result_60_5k.reason.lower(), \
            "€60,500.00 should have tolerance rule"
        
        # Test €60,500.01 (just above tolerance threshold)
        result_60_5k_01 = calculator.calculate_vat_liability(
            gross_turnover=Decimal('60500.01'),
            transactions=[
                Transaction(amount=Decimal('10000.00'), is_income=True)
            ]
        )
        assert result_60_5k_01.exempt is False, \
            "€60,500.01 should not be exempt (VAT required)"
    
    @given(
        turnover=decimal_strategy(min_value=0, max_value=60500)
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_check_small_business_exemption_method(
        self,
        turnover: Decimal,
        calculator
    ):
        """
        Property: check_small_business_exemption method is consistent
        
        For any turnover <= €55,000:
        - check_small_business_exemption returns True
        
        For any turnover > €55,000:
        - check_small_business_exemption returns False
        
        **Validates: Requirements 4.1, 4.6**
        """
        result = calculator.check_small_business_exemption(turnover)
        
        if turnover <= calculator.SMALL_BUSINESS_THRESHOLD:
            assert result is True, \
                f"check_small_business_exemption should return True for €{turnover}"
        else:
            assert result is False, \
                f"check_small_business_exemption should return False for €{turnover}"
    
    @given(
        turnover=decimal_strategy(min_value=0, max_value=100000)
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_apply_tolerance_rule_method(
        self,
        turnover: Decimal,
        calculator
    ):
        """
        Property: apply_tolerance_rule method is consistent
        
        For any turnover in (€55,000, €60,500]:
        - apply_tolerance_rule returns (True, warning_message)
        
        For any turnover outside this range:
        - apply_tolerance_rule returns (False, None)
        
        **Validates: Requirements 4.7, 4.13**
        """
        applies, warning = calculator.apply_tolerance_rule(turnover)
        
        if calculator.SMALL_BUSINESS_THRESHOLD < turnover <= calculator.TOLERANCE_THRESHOLD:
            assert applies is True, \
                f"Tolerance rule should apply for €{turnover}"
            assert warning is not None, \
                f"Warning should be provided for €{turnover}"
            assert "next year" in warning.lower() or "automatically cancelled" in warning.lower(), \
                f"Warning should mention next year cancellation for €{turnover}"
        else:
            assert applies is False, \
                f"Tolerance rule should not apply for €{turnover}"
            assert warning is None, \
                f"No warning should be provided for €{turnover}"
    
    @given(
        turnover=turnover_strategy(),
        num_transactions=st.integers(min_value=0, max_value=10)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_exemption_independent_of_transaction_count(
        self,
        turnover: Decimal,
        num_transactions: int,
        calculator
    ):
        """
        Property: Exemption status depends only on turnover, not transaction count
        
        For any turnover and any number of transactions:
        - Exemption status should be the same regardless of transaction count
        - Only turnover amount determines exemption
        
        **Validates: Requirements 4.1, 4.6, 4.7**
        """
        # Create transactions
        transactions = [
            Transaction(amount=Decimal('1000.00'), is_income=True)
            for _ in range(num_transactions)
        ]
        
        # Calculate with transactions
        result_with_txns = calculator.calculate_vat_liability(
            gross_turnover=turnover,
            transactions=transactions
        )
        
        # Calculate without transactions
        result_without_txns = calculator.calculate_vat_liability(
            gross_turnover=turnover,
            transactions=[]
        )
        
        # Exemption status should be the same
        assert result_with_txns.exempt == result_without_txns.exempt, \
            f"Exemption status should depend only on turnover €{turnover}, not transaction count"
        
        # Reason should be the same
        assert result_with_txns.reason == result_without_txns.reason, \
            f"Exemption reason should depend only on turnover €{turnover}, not transaction count"
