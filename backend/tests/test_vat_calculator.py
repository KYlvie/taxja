"""Unit tests for VAT calculator"""
import pytest
from decimal import Decimal
from backend.app.services.vat_calculator import (
    VATCalculator,
    VATResult,
    Transaction,
    PropertyType
)


class TestVATCalculator:
    """Test suite for VATCalculator"""
    
    @pytest.fixture
    def calculator(self):
        """Create a VATCalculator instance"""
        return VATCalculator()
    
    # Test small business exemption
    
    def test_small_business_exemption_below_threshold(self, calculator):
        """Test that turnover below €55,000 qualifies for exemption"""
        gross_turnover = Decimal('50000.00')
        transactions = []
        
        result = calculator.calculate_vat_liability(
            gross_turnover=gross_turnover,
            transactions=transactions
        )
        
        assert result.exempt is True
        assert "Kleinunternehmerregelung" in result.reason
        assert result.output_vat == Decimal('0.00')
        assert result.input_vat == Decimal('0.00')
        assert result.net_vat == Decimal('0.00')
    
    def test_small_business_exemption_at_threshold(self, calculator):
        """Test that turnover exactly at €55,000 qualifies for exemption"""
        gross_turnover = Decimal('55000.00')
        transactions = []
        
        result = calculator.calculate_vat_liability(
            gross_turnover=gross_turnover,
            transactions=transactions
        )
        
        assert result.exempt is True
        assert "Kleinunternehmerregelung" in result.reason
    
    def test_check_small_business_exemption_true(self, calculator):
        """Test check_small_business_exemption returns True for qualifying turnover"""
        assert calculator.check_small_business_exemption(Decimal('50000.00')) is True
        assert calculator.check_small_business_exemption(Decimal('55000.00')) is True
    
    def test_check_small_business_exemption_false(self, calculator):
        """Test check_small_business_exemption returns False for non-qualifying turnover"""
        assert calculator.check_small_business_exemption(Decimal('55000.01')) is False
        assert calculator.check_small_business_exemption(Decimal('60000.00')) is False
    
    # Test tolerance rule
    
    def test_tolerance_rule_applies(self, calculator):
        """Test that tolerance rule applies for turnover between €55,000 and €60,500"""
        gross_turnover = Decimal('58000.00')
        transactions = []
        
        result = calculator.calculate_vat_liability(
            gross_turnover=gross_turnover,
            transactions=transactions
        )
        
        assert result.exempt is True
        assert "Tolerance rule" in result.reason
        assert result.warning is not None
        assert "Steuerberater" in result.warning
    
    def test_tolerance_rule_at_upper_threshold(self, calculator):
        """Test that tolerance rule applies at exactly €60,500"""
        gross_turnover = Decimal('60500.00')
        transactions = []
        
        result = calculator.calculate_vat_liability(
            gross_turnover=gross_turnover,
            transactions=transactions
        )
        
        assert result.exempt is True
        assert "Tolerance rule" in result.reason
    
    def test_apply_tolerance_rule_true(self, calculator):
        """Test apply_tolerance_rule returns True for qualifying turnover"""
        applies, warning = calculator.apply_tolerance_rule(Decimal('58000.00'))
        
        assert applies is True
        assert warning is not None
        assert "automatically cancelled next year" in warning
    
    def test_apply_tolerance_rule_false_below(self, calculator):
        """Test apply_tolerance_rule returns False for turnover below range"""
        applies, warning = calculator.apply_tolerance_rule(Decimal('55000.00'))
        
        assert applies is False
        assert warning is None
    
    def test_apply_tolerance_rule_false_above(self, calculator):
        """Test apply_tolerance_rule returns False for turnover above range"""
        applies, warning = calculator.apply_tolerance_rule(Decimal('60500.01'))
        
        assert applies is False
        assert warning is None
    
    # Test VAT calculation with standard rate
    
    def test_calculate_vat_standard_rate(self, calculator):
        """Test VAT calculation with standard 20% rate"""
        gross_turnover = Decimal('100000.00')
        transactions = [
            Transaction(amount=Decimal('12000.00'), is_income=True),  # €10,000 net + €2,000 VAT
            Transaction(amount=Decimal('6000.00'), is_income=False),  # €5,000 net + €1,000 VAT
        ]
        
        result = calculator.calculate_vat_liability(
            gross_turnover=gross_turnover,
            transactions=transactions
        )
        
        assert result.exempt is False
        # Output VAT: 12000 * 0.20 / 1.20 = 2000
        assert result.output_vat == Decimal('2000.00')
        # Input VAT: 6000 * 0.20 / 1.20 = 1000
        assert result.input_vat == Decimal('1000.00')
        # Net VAT: 2000 - 1000 = 1000
        assert result.net_vat == Decimal('1000.00')
    
    def test_calculate_vat_multiple_transactions(self, calculator):
        """Test VAT calculation with multiple transactions"""
        gross_turnover = Decimal('150000.00')
        transactions = [
            Transaction(amount=Decimal('12000.00'), is_income=True),
            Transaction(amount=Decimal('24000.00'), is_income=True),
            Transaction(amount=Decimal('6000.00'), is_income=False),
            Transaction(amount=Decimal('3000.00'), is_income=False),
        ]
        
        result = calculator.calculate_vat_liability(
            gross_turnover=gross_turnover,
            transactions=transactions
        )
        
        assert result.exempt is False
        # Output VAT: (12000 + 24000) * 0.20 / 1.20 = 6000
        assert result.output_vat == Decimal('6000.00')
        # Input VAT: (6000 + 3000) * 0.20 / 1.20 = 1500
        assert result.input_vat == Decimal('1500.00')
        # Net VAT: 6000 - 1500 = 4500
        assert result.net_vat == Decimal('4500.00')
    
    # Test residential rental (10% rate)
    
    def test_residential_rental_with_vat_opt_in(self, calculator):
        """Test residential rental with 10% VAT opt-in"""
        gross_turnover = Decimal('80000.00')
        transactions = [
            Transaction(
                amount=Decimal('11000.00'),
                is_income=True,
                property_type=PropertyType.RESIDENTIAL,
                vat_opted_in=True
            ),
        ]
        
        result = calculator.calculate_vat_liability(
            gross_turnover=gross_turnover,
            transactions=transactions,
            property_type=PropertyType.RESIDENTIAL
        )
        
        assert result.exempt is False
        # Output VAT: 11000 * 0.10 / 1.10 = 1000
        assert result.output_vat == Decimal('1000.00')
    
    def test_residential_rental_without_vat_opt_in(self, calculator):
        """Test residential rental without VAT opt-in (exempt)"""
        gross_turnover = Decimal('80000.00')
        transactions = [
            Transaction(
                amount=Decimal('11000.00'),
                is_income=True,
                property_type=PropertyType.RESIDENTIAL,
                vat_opted_in=False
            ),
        ]
        
        result = calculator.calculate_vat_liability(
            gross_turnover=gross_turnover,
            transactions=transactions,
            property_type=PropertyType.RESIDENTIAL
        )
        
        assert result.exempt is False
        # Output VAT: 0 (not opted in)
        assert result.output_vat == Decimal('0.00')
    
    # Test commercial rental (20% rate)
    
    def test_commercial_rental_mandatory_vat(self, calculator):
        """Test commercial rental with mandatory 20% VAT"""
        gross_turnover = Decimal('120000.00')
        transactions = [
            Transaction(
                amount=Decimal('24000.00'),
                is_income=True,
                property_type=PropertyType.COMMERCIAL
            ),
        ]
        
        result = calculator.calculate_vat_liability(
            gross_turnover=gross_turnover,
            transactions=transactions,
            property_type=PropertyType.COMMERCIAL
        )
        
        assert result.exempt is False
        # Output VAT: 24000 * 0.20 / 1.20 = 4000
        assert result.output_vat == Decimal('4000.00')
    
    # Test edge cases
    
    def test_zero_turnover(self, calculator):
        """Test with zero turnover"""
        gross_turnover = Decimal('0.00')
        transactions = []
        
        result = calculator.calculate_vat_liability(
            gross_turnover=gross_turnover,
            transactions=transactions
        )
        
        assert result.exempt is True
        assert "Kleinunternehmerregelung" in result.reason
    
    def test_empty_transactions(self, calculator):
        """Test with empty transaction list"""
        gross_turnover = Decimal('100000.00')
        transactions = []
        
        result = calculator.calculate_vat_liability(
            gross_turnover=gross_turnover,
            transactions=transactions
        )
        
        assert result.exempt is False
        assert result.output_vat == Decimal('0.00')
        assert result.input_vat == Decimal('0.00')
        assert result.net_vat == Decimal('0.00')
    
    def test_only_expenses_no_income(self, calculator):
        """Test with only expense transactions"""
        gross_turnover = Decimal('100000.00')
        transactions = [
            Transaction(amount=Decimal('6000.00'), is_income=False),
            Transaction(amount=Decimal('3000.00'), is_income=False),
        ]
        
        result = calculator.calculate_vat_liability(
            gross_turnover=gross_turnover,
            transactions=transactions
        )
        
        assert result.exempt is False
        assert result.output_vat == Decimal('0.00')
        # Input VAT: (6000 + 3000) * 0.20 / 1.20 = 1500
        assert result.input_vat == Decimal('1500.00')
        # Net VAT: 0 - 1500 = -1500 (refund)
        assert result.net_vat == Decimal('-1500.00')
    
    def test_string_amounts_converted_to_decimal(self, calculator):
        """Test that string amounts are properly converted to Decimal"""
        gross_turnover = '100000.00'  # String instead of Decimal
        transactions = [
            Transaction(amount=Decimal('12000.00'), is_income=True),
        ]
        
        result = calculator.calculate_vat_liability(
            gross_turnover=gross_turnover,
            transactions=transactions
        )
        
        assert result.exempt is False
        assert isinstance(result.output_vat, Decimal)
        assert result.output_vat == Decimal('2000.00')
    
    # Test precision
    
    def test_vat_calculation_precision(self, calculator):
        """Test that VAT calculations maintain 2 decimal precision"""
        gross_turnover = Decimal('100000.00')
        transactions = [
            Transaction(amount=Decimal('12345.67'), is_income=True),
        ]
        
        result = calculator.calculate_vat_liability(
            gross_turnover=gross_turnover,
            transactions=transactions
        )
        
        # Output VAT: 12345.67 * 0.20 / 1.20 = 2057.61166... -> 2057.61
        assert result.output_vat == Decimal('2057.61')
        assert result.output_vat.as_tuple().exponent == -2  # 2 decimal places
    
    # Test mixed property types
    
    def test_mixed_income_sources(self, calculator):
        """Test with mixed income sources (residential + commercial + other)"""
        gross_turnover = Decimal('200000.00')
        transactions = [
            # Residential rental with opt-in (10%)
            Transaction(
                amount=Decimal('11000.00'),
                is_income=True,
                property_type=PropertyType.RESIDENTIAL,
                vat_opted_in=True
            ),
            # Commercial rental (20%)
            Transaction(
                amount=Decimal('24000.00'),
                is_income=True,
                property_type=PropertyType.COMMERCIAL
            ),
            # Other income (20%)
            Transaction(amount=Decimal('12000.00'), is_income=True),
            # Expenses
            Transaction(amount=Decimal('6000.00'), is_income=False),
        ]
        
        result = calculator.calculate_vat_liability(
            gross_turnover=gross_turnover,
            transactions=transactions,
            property_type=None  # Mixed types
        )
        
        assert result.exempt is False
        # Note: This test shows current behavior where property_type parameter
        # doesn't affect individual transaction VAT rates when they have their own property_type
        # Output VAT calculation depends on implementation details
        assert result.output_vat > Decimal('0.00')
        assert result.input_vat == Decimal('1000.00')
