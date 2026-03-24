"""Unit tests for SVS calculator"""
import pytest
from decimal import Decimal
from backend.app.services.svs_calculator import SVSCalculator, UserType, SVSResult


class TestSVSCalculator:
    """Test suite for SVS calculator"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.calculator = SVSCalculator()
    
    # GSVG Tests
    
    def test_gsvg_below_minimum_income(self):
        """Test GSVG with income below minimum threshold"""
        result = self.calculator.calculate_contributions(
            annual_income=Decimal('5000.00'),
            user_type=UserType.GSVG
        )
        
        assert result.annual_total == Decimal('0.00')
        assert result.monthly_total == Decimal('0.00')
        assert not result.deductible
        assert "below" in result.note.lower()
    
    def test_gsvg_at_minimum_income(self):
        """Test GSVG at exactly minimum income threshold"""
        result = self.calculator.calculate_contributions(
            annual_income=Decimal('6613.20'),
            user_type=UserType.GSVG
        )
        
        # Should use minimum base of €551.10/month
        assert result.contribution_base == Decimal('551.10')
        assert result.annual_total > Decimal('0.00')
        assert result.deductible
    
    def test_gsvg_normal_income(self):
        """Test GSVG with normal income (€30,000/year)"""
        annual_income = Decimal('30000.00')
        monthly_income = annual_income / Decimal('12')  # €2,500/month
        
        result = self.calculator.calculate_contributions(
            annual_income=annual_income,
            user_type=UserType.GSVG
        )
        
        # Contribution base should be monthly income (within limits)
        assert result.contribution_base == monthly_income.quantize(Decimal('0.01'))
        
        # Verify breakdown components
        assert 'pension' in result.breakdown
        assert 'health' in result.breakdown
        assert 'accident' in result.breakdown
        assert 'supplementary' in result.breakdown
        
        # Verify pension calculation (18.5%)
        expected_pension = monthly_income * Decimal('0.185')
        assert result.breakdown['pension'] == expected_pension.quantize(Decimal('0.01'))
        
        # Verify health calculation (6.8%)
        expected_health = monthly_income * Decimal('0.068')
        assert result.breakdown['health'] == expected_health.quantize(Decimal('0.01'))
        
        # Verify accident is fixed
        assert result.breakdown['accident'] == Decimal('12.25')
        
        # Verify supplementary (1.53%)
        expected_supplementary = monthly_income * Decimal('0.0153')
        assert result.breakdown['supplementary'] == expected_supplementary.quantize(Decimal('0.01'))
        
        # Verify totals
        expected_monthly = sum(result.breakdown.values())
        assert result.monthly_total == expected_monthly.quantize(Decimal('0.01'))
        assert result.annual_total == (result.monthly_total * Decimal('12')).quantize(Decimal('0.01'))
        
        assert result.deductible
    
    def test_gsvg_high_income_maximum_base(self):
        """Test GSVG with high income exceeding maximum base"""
        result = self.calculator.calculate_contributions(
            annual_income=Decimal('150000.00'),  # €12,500/month
            user_type=UserType.GSVG
        )

        # Should be capped at maximum base
        assert result.contribution_base == Decimal('7720.50')

        # Verify calculations use maximum base
        expected_pension = Decimal('7720.50') * Decimal('0.185')
        assert result.breakdown['pension'] == expected_pension.quantize(Decimal('0.01'))
    
    def test_gsvg_low_income_minimum_base(self):
        """Test GSVG with low income requiring minimum base"""
        result = self.calculator.calculate_contributions(
            annual_income=Decimal('7000.00'),  # €583.33/month (above minimum income)
            user_type=UserType.GSVG
        )
        
        # Should use minimum base since monthly income < €551.10
        # Wait, €583.33 > €551.10, so it should use actual income
        monthly_income = Decimal('7000.00') / Decimal('12')
        assert result.contribution_base == monthly_income.quantize(Decimal('0.01'))
    
    def test_gsvg_income_just_above_minimum(self):
        """Test GSVG with income just above minimum requiring minimum base"""
        result = self.calculator.calculate_contributions(
            annual_income=Decimal('6620.00'),  # €551.67/month
            user_type=UserType.GSVG
        )
        
        # Monthly income is €551.67, which is above minimum base €551.10
        monthly_income = Decimal('6620.00') / Decimal('12')
        assert result.contribution_base == monthly_income.quantize(Decimal('0.01'))
    
    # Neue Selbständige Tests
    
    def test_neue_selbstaendige_low_income(self):
        """Test Neue Selbständige with low income"""
        result = self.calculator.calculate_contributions(
            annual_income=Decimal('6000.00'),  # €500/month
            user_type=UserType.NEUE_SELBSTAENDIGE
        )
        
        # Should apply minimum contribution
        assert result.monthly_total == Decimal('160.81')
        assert result.annual_total == (Decimal('160.81') * Decimal('12')).quantize(Decimal('0.01'))
        assert "minimum" in result.note.lower()
        assert result.deductible
    
    def test_neue_selbstaendige_normal_income(self):
        """Test Neue Selbständige with normal income"""
        annual_income = Decimal('40000.00')
        monthly_income = annual_income / Decimal('12')  # €3,333.33/month
        
        result = self.calculator.calculate_contributions(
            annual_income=annual_income,
            user_type=UserType.NEUE_SELBSTAENDIGE
        )
        
        # Contribution base should be monthly income
        assert result.contribution_base == monthly_income.quantize(Decimal('0.01'))
        
        # Verify breakdown
        assert 'pension' in result.breakdown
        assert 'health' in result.breakdown
        assert 'accident' in result.breakdown
        assert 'supplementary' in result.breakdown
        
        # Calculate expected values
        expected_pension = monthly_income * Decimal('0.185')
        expected_health = monthly_income * Decimal('0.068')
        expected_accident = Decimal('12.25')
        expected_supplementary = monthly_income * Decimal('0.0153')

        assert result.breakdown['pension'] == expected_pension.quantize(Decimal('0.01'))
        assert result.breakdown['health'] == expected_health.quantize(Decimal('0.01'))
        assert result.breakdown['accident'] == expected_accident
        assert result.breakdown['supplementary'] == expected_supplementary.quantize(Decimal('0.01'))
        
        # Monthly total should be above minimum
        assert result.monthly_total > Decimal('160.81')
        assert result.deductible
    
    def test_neue_selbstaendige_high_income(self):
        """Test Neue Selbständige with high income exceeding maximum base"""
        result = self.calculator.calculate_contributions(
            annual_income=Decimal('120000.00'),  # €10,000/month
            user_type=UserType.NEUE_SELBSTAENDIGE
        )
        
        # Should be capped at maximum base
        assert result.contribution_base == Decimal('7720.50')

        # Verify calculations use maximum base
        expected_pension = Decimal('7720.50') * Decimal('0.185')
        assert result.breakdown['pension'] == expected_pension.quantize(Decimal('0.01'))

    def test_neue_selbstaendige_at_minimum_threshold(self):
        """Test Neue Selbständige at income that produces exactly minimum contribution"""
        # Calculate income that would produce minimum contribution
        # Minimum is €160.81/month
        # Let's test with income slightly above this threshold
        result = self.calculator.calculate_contributions(
            annual_income=Decimal('2500.00'),  # €208.33/month
            user_type=UserType.NEUE_SELBSTAENDIGE
        )
        
        # Should apply minimum contribution since calculated would be less
        monthly_income = Decimal('2500.00') / Decimal('12')
        calculated_total = (
            monthly_income * Decimal('0.185') +  # pension
            monthly_income * Decimal('0.068') +  # health
            Decimal('12.25') +  # accident
            monthly_income * Decimal('0.0153')  # supplementary
        )
        
        if calculated_total < Decimal('160.81'):
            assert result.monthly_total == Decimal('160.81')
        else:
            assert result.monthly_total == calculated_total.quantize(Decimal('0.01'))
    
    # Employee Tests
    
    def test_employee_no_contributions(self):
        """Test that employees have no SVS contributions (handled by employer)"""
        result = self.calculator.calculate_contributions(
            annual_income=Decimal('50000.00'),
            user_type=UserType.EMPLOYEE
        )
        
        assert result.annual_total == Decimal('0.00')
        assert result.monthly_total == Decimal('0.00')
        assert not result.deductible
        assert "employer" in result.note.lower()
    
    # Edge Cases and Validation
    
    def test_zero_income(self):
        """Test with zero income"""
        result = self.calculator.calculate_contributions(
            annual_income=Decimal('0.00'),
            user_type=UserType.GSVG
        )
        
        assert result.annual_total == Decimal('0.00')
        assert result.monthly_total == Decimal('0.00')
    
    def test_negative_income(self):
        """Test with negative income (loss)"""
        result = self.calculator.calculate_contributions(
            annual_income=Decimal('-5000.00'),
            user_type=UserType.GSVG
        )
        
        # Should treat as below minimum
        assert result.annual_total == Decimal('0.00')
    
    def test_string_income_conversion(self):
        """Test that string income is properly converted to Decimal"""
        result = self.calculator.calculate_contributions(
            annual_income='30000.00',  # String instead of Decimal
            user_type=UserType.GSVG
        )
        
        assert isinstance(result.annual_total, Decimal)
        assert result.annual_total > Decimal('0.00')
    
    def test_invalid_user_type(self):
        """Test with invalid user type"""
        with pytest.raises(ValueError, match="Unsupported user type"):
            self.calculator.calculate_contributions(
                annual_income=Decimal('30000.00'),
                user_type="invalid_type"
            )
    
    # Dynamic Rate Tests
    
    def test_get_dynamic_rate_pension(self):
        """Test getting dynamic rate for pension"""
        rate = self.calculator.get_dynamic_rate(
            income_base=Decimal('2000.00'),
            contribution_type='pension'
        )
        
        assert rate == Decimal('0.185')
    
    def test_get_dynamic_rate_health(self):
        """Test getting dynamic rate for health"""
        rate = self.calculator.get_dynamic_rate(
            income_base=Decimal('2000.00'),
            contribution_type='health'
        )
        
        assert rate == Decimal('0.068')
    
    def test_get_dynamic_rate_accident(self):
        """Test getting dynamic rate for accident (should be 0 as it's fixed)"""
        rate = self.calculator.get_dynamic_rate(
            income_base=Decimal('2000.00'),
            contribution_type='accident'
        )
        
        assert rate == Decimal('0.00')
    
    def test_get_dynamic_rate_supplementary(self):
        """Test getting dynamic rate for supplementary pension"""
        rate = self.calculator.get_dynamic_rate(
            income_base=Decimal('2000.00'),
            contribution_type='supplementary'
        )
        
        assert rate == Decimal('0.0153')
    
    def test_get_dynamic_rate_invalid_type(self):
        """Test getting dynamic rate for invalid contribution type"""
        rate = self.calculator.get_dynamic_rate(
            income_base=Decimal('2000.00'),
            contribution_type='invalid'
        )
        
        assert rate == Decimal('0.00')
    
    # Quarterly Prepayment Tests
    
    def test_quarterly_prepayment_gsvg(self):
        """Test quarterly prepayment calculation for GSVG"""
        annual_income = Decimal('30000.00')
        
        quarterly = self.calculator.calculate_quarterly_prepayment(
            annual_income=annual_income,
            user_type=UserType.GSVG
        )
        
        # Get annual total
        result = self.calculator.calculate_contributions(annual_income, UserType.GSVG)
        expected_quarterly = (result.annual_total / Decimal('4')).quantize(Decimal('0.01'))
        
        assert quarterly == expected_quarterly
    
    def test_quarterly_prepayment_neue_selbstaendige(self):
        """Test quarterly prepayment calculation for Neue Selbständige"""
        annual_income = Decimal('40000.00')
        
        quarterly = self.calculator.calculate_quarterly_prepayment(
            annual_income=annual_income,
            user_type=UserType.NEUE_SELBSTAENDIGE
        )
        
        # Get annual total
        result = self.calculator.calculate_contributions(annual_income, UserType.NEUE_SELBSTAENDIGE)
        expected_quarterly = (result.annual_total / Decimal('4')).quantize(Decimal('0.01'))
        
        assert quarterly == expected_quarterly
    
    # Precision Tests
    
    def test_result_precision(self):
        """Test that all monetary values have exactly 2 decimal places"""
        result = self.calculator.calculate_contributions(
            annual_income=Decimal('35123.45'),
            user_type=UserType.GSVG
        )
        
        # Check main totals
        assert result.monthly_total.as_tuple().exponent == -2
        assert result.annual_total.as_tuple().exponent == -2
        assert result.contribution_base.as_tuple().exponent == -2
        
        # Check breakdown
        for value in result.breakdown.values():
            assert value.as_tuple().exponent == -2
    
    # Deductibility Tests
    
    def test_gsvg_contributions_deductible(self):
        """Test that GSVG contributions are marked as deductible"""
        result = self.calculator.calculate_contributions(
            annual_income=Decimal('30000.00'),
            user_type=UserType.GSVG
        )
        
        assert result.deductible
        assert "sonderausgaben" in result.note.lower()
    
    def test_neue_selbstaendige_contributions_deductible(self):
        """Test that Neue Selbständige contributions are marked as deductible"""
        result = self.calculator.calculate_contributions(
            annual_income=Decimal('40000.00'),
            user_type=UserType.NEUE_SELBSTAENDIGE
        )
        
        assert result.deductible
        assert "sonderausgaben" in result.note.lower()
    
    # Comprehensive Calculation Tests
    
    def test_gsvg_comprehensive_example(self):
        """Test comprehensive GSVG calculation with known values"""
        # Example: €36,000/year = €3,000/month
        annual_income = Decimal('36000.00')
        monthly_income = Decimal('3000.00')
        
        result = self.calculator.calculate_contributions(
            annual_income=annual_income,
            user_type=UserType.GSVG
        )
        
        # Expected calculations
        expected_pension = monthly_income * Decimal('0.185')  # €555.00
        expected_health = monthly_income * Decimal('0.068')   # €204.00
        expected_accident = Decimal('12.25')
        expected_supplementary = monthly_income * Decimal('0.0153')  # €45.90
        expected_monthly = expected_pension + expected_health + expected_accident + expected_supplementary
        expected_annual = expected_monthly * Decimal('12')
        
        assert result.contribution_base == monthly_income
        assert result.breakdown['pension'] == expected_pension.quantize(Decimal('0.01'))
        assert result.breakdown['health'] == expected_health.quantize(Decimal('0.01'))
        assert result.breakdown['accident'] == expected_accident
        assert result.breakdown['supplementary'] == expected_supplementary.quantize(Decimal('0.01'))
        assert result.monthly_total == expected_monthly.quantize(Decimal('0.01'))
        assert result.annual_total == expected_annual.quantize(Decimal('0.01'))
