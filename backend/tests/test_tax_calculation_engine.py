"""Unit tests for TaxCalculationEngine"""
import pytest
from decimal import Decimal

from app.services.tax_calculation_engine import TaxCalculationEngine
from app.services.vat_calculator import Transaction, PropertyType
from app.services.svs_calculator import UserType
from app.services.deduction_calculator import FamilyInfo


@pytest.fixture
def tax_config():
    """Tax configuration for 2026"""
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
    """Create TaxCalculationEngine instance"""
    return TaxCalculationEngine(tax_config)


class TestTaxCalculationEngineBasic:
    """Test basic tax calculation functionality"""
    
    def test_calculate_total_tax_employee_simple(self, engine):
        """Test total tax calculation for simple employee case"""
        result = engine.calculate_total_tax(
            gross_income=Decimal('50000.00'),
            tax_year=2026,
            user_type=UserType.EMPLOYEE
        )
        
        # Verify structure
        assert result.gross_income == Decimal('50000.00')
        assert result.total_tax > Decimal('0.00')
        assert result.net_income > Decimal('0.00')
        assert result.net_income == result.gross_income - result.total_tax
        
        # Employee should have no SVS contributions
        assert result.svs.annual_total == Decimal('0.00')
        
        # Should have income tax
        assert result.income_tax.total_tax > Decimal('0.00')
    
    def test_calculate_total_tax_gsvg(self, engine):
        """Test total tax calculation for GSVG self-employed"""
        result = engine.calculate_total_tax(
            gross_income=Decimal('50000.00'),
            tax_year=2026,
            user_type=UserType.GSVG
        )
        
        # GSVG should have SVS contributions
        assert result.svs.annual_total > Decimal('0.00')
        assert result.svs.deductible is True
        
        # Total tax should include income tax and SVS
        assert result.total_tax == result.income_tax.total_tax + result.svs.annual_total
        
        # Net income should be gross minus total tax
        assert result.net_income == result.gross_income - result.total_tax
    
    def test_calculate_total_tax_neue_selbstaendige(self, engine):
        """Test total tax calculation for Neue Selbständige"""
        result = engine.calculate_total_tax(
            gross_income=Decimal('30000.00'),
            tax_year=2026,
            user_type=UserType.NEUE_SELBSTAENDIGE
        )
        
        # Should have SVS contributions
        assert result.svs.annual_total > Decimal('0.00')
        
        # Total tax should include income tax and SVS
        assert result.total_tax == result.income_tax.total_tax + result.svs.annual_total
    
    def test_calculate_net_income(self, engine):
        """Test net income calculation convenience method"""
        net_income = engine.calculate_net_income(
            gross_income=Decimal('50000.00'),
            tax_year=2026,
            user_type=UserType.EMPLOYEE
        )
        
        assert isinstance(net_income, Decimal)
        assert net_income > Decimal('0.00')
        assert net_income < Decimal('50000.00')


class TestTaxCalculationEngineWithDeductions:
    """Test tax calculation with various deductions"""
    
    def test_with_commuting_allowance(self, engine):
        """Test tax calculation with commuting allowance"""
        result = engine.calculate_total_tax(
            gross_income=Decimal('50000.00'),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
            commuting_distance_km=45,
            public_transport_available=True
        )
        
        # Should have commuting deduction
        assert result.deductions.amount > Decimal('0.00')
        assert 'commuting_allowance' in result.deductions.breakdown
        
        # Tax should be lower due to deduction
        result_no_deduction = engine.calculate_total_tax(
            gross_income=Decimal('50000.00'),
            tax_year=2026,
            user_type=UserType.EMPLOYEE
        )
        
        assert result.income_tax.total_tax < result_no_deduction.income_tax.total_tax
    
    def test_with_home_office_deduction(self, engine):
        """Test tax calculation with home office deduction"""
        result = engine.calculate_total_tax(
            gross_income=Decimal('50000.00'),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
            home_office_eligible=True
        )
        
        # Should have home office deduction of €300 + Werbungskostenpauschale €132
        assert result.deductions.amount == Decimal('432.00')
        assert 'home_office' in result.deductions.breakdown
        assert result.deductions.breakdown['home_office_amount'] == Decimal('300.00')
    
    def test_with_family_deductions(self, engine):
        """Test tax calculation with family deductions"""
        family_info = FamilyInfo(num_children=2, is_single_parent=True)
        
        result = engine.calculate_total_tax(
            gross_income=Decimal('50000.00'),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
            family_info=family_info
        )
        
        # Should have family deductions
        assert result.deductions.amount > Decimal('0.00')
        assert 'family_deductions' in result.deductions.breakdown
        
        # Should include child deduction and single parent deduction
        family_breakdown = result.deductions.breakdown['family_deductions']
        assert family_breakdown['num_children'] == 2
        assert family_breakdown['is_single_parent'] is True
    
    def test_with_all_deductions(self, engine):
        """Test tax calculation with all deductions combined"""
        family_info = FamilyInfo(num_children=1, is_single_parent=False)
        
        result = engine.calculate_total_tax(
            gross_income=Decimal('50000.00'),
            tax_year=2026,
            user_type=UserType.EMPLOYEE,
            commuting_distance_km=50,
            public_transport_available=False,
            home_office_eligible=True,
            family_info=family_info
        )
        
        # Should have all three types of deductions
        assert 'commuting_allowance' in result.deductions.breakdown
        assert 'home_office' in result.deductions.breakdown
        assert 'family_deductions' in result.deductions.breakdown
        
        # Total deduction should be sum of all
        assert result.deductions.amount > Decimal('1000.00')


class TestTaxCalculationEngineWithVAT:
    """Test tax calculation with VAT"""
    
    def test_with_vat_exempt(self, engine):
        """Test tax calculation with VAT exemption"""
        transactions = [
            Transaction(amount=Decimal('30000.00'), is_income=True),
            Transaction(amount=Decimal('10000.00'), is_income=False)
        ]
        
        result = engine.calculate_total_tax(
            gross_income=Decimal('50000.00'),
            tax_year=2026,
            user_type=UserType.GSVG,
            transactions=transactions,
            gross_turnover=Decimal('30000.00')
        )
        
        # Should be VAT exempt (below €55,000 threshold)
        assert result.vat.exempt is True
        assert result.vat.net_vat == Decimal('0.00')
        
        # Total tax should not include VAT
        assert result.total_tax == result.income_tax.total_tax + result.svs.annual_total
    
    def test_with_vat_liable(self, engine):
        """Test tax calculation with VAT liability"""
        transactions = [
            Transaction(amount=Decimal('70000.00'), is_income=True),
            Transaction(amount=Decimal('20000.00'), is_income=False)
        ]
        
        result = engine.calculate_total_tax(
            gross_income=Decimal('70000.00'),
            tax_year=2026,
            user_type=UserType.GSVG,
            transactions=transactions,
            gross_turnover=Decimal('70000.00')
        )
        
        # Should be VAT liable (above €60,500 threshold)
        assert result.vat.exempt is False
        assert result.vat.net_vat > Decimal('0.00')
        
        # Total tax should include VAT
        expected_total = result.income_tax.total_tax + result.svs.annual_total + result.vat.net_vat
        assert result.total_tax == expected_total
    
    def test_with_vat_tolerance_rule(self, engine):
        """Test tax calculation with VAT tolerance rule"""
        transactions = [
            Transaction(amount=Decimal('58000.00'), is_income=True),
            Transaction(amount=Decimal('10000.00'), is_income=False)
        ]
        
        result = engine.calculate_total_tax(
            gross_income=Decimal('58000.00'),
            tax_year=2026,
            user_type=UserType.GSVG,
            transactions=transactions,
            gross_turnover=Decimal('58000.00')
        )
        
        # Should be exempt under tolerance rule
        assert result.vat.exempt is True
        assert result.vat.warning is not None
        assert 'tolerance' in result.vat.reason.lower()


class TestTaxCalculationEngineWithLossCarryforward:
    """Test tax calculation with loss carryforward"""
    
    def test_with_loss_carryforward(self, engine):
        """Test tax calculation with loss carryforward applied"""
        result = engine.calculate_total_tax(
            gross_income=Decimal('50000.00'),
            tax_year=2026,
            user_type=UserType.GSVG,
            loss_carryforward_applied=Decimal('10000.00'),
            remaining_loss_balance=Decimal('5000.00')
        )
        
        # Should have loss carryforward info
        assert result.income_tax.loss_carryforward_applied == Decimal('10000.00')
        assert result.income_tax.remaining_loss_balance == Decimal('5000.00')
        
        # Tax should be lower due to loss carryforward
        result_no_loss = engine.calculate_total_tax(
            gross_income=Decimal('50000.00'),
            tax_year=2026,
            user_type=UserType.GSVG
        )
        
        assert result.income_tax.total_tax < result_no_loss.income_tax.total_tax


class TestTaxCalculationEngineBreakdown:
    """Test tax breakdown generation"""
    
    def test_generate_tax_breakdown(self, engine):
        """Test generating structured tax breakdown"""
        family_info = FamilyInfo(num_children=1, is_single_parent=False)
        
        breakdown = engine.generate_tax_breakdown(
            gross_income=Decimal('50000.00'),
            tax_year=2026,
            user_type=UserType.GSVG,
            commuting_distance_km=30,
            public_transport_available=True,
            home_office_eligible=True,
            family_info=family_info
        )
        
        # Verify structure
        assert 'gross_income' in breakdown
        assert 'tax_year' in breakdown
        assert 'user_type' in breakdown
        assert 'deductions' in breakdown
        assert 'income_tax' in breakdown
        assert 'svs' in breakdown
        assert 'vat' in breakdown
        assert 'total_tax' in breakdown
        assert 'net_income' in breakdown
        assert 'effective_tax_rate' in breakdown
        
        # Verify types (should be float for JSON serialization)
        assert isinstance(breakdown['gross_income'], float)
        assert isinstance(breakdown['total_tax'], float)
        assert isinstance(breakdown['net_income'], float)
        
        # Verify income tax breakdown
        assert 'brackets' in breakdown['income_tax']
        assert len(breakdown['income_tax']['brackets']) > 0
        
        # Verify SVS breakdown
        assert 'breakdown' in breakdown['svs']
        assert 'pension' in breakdown['svs']['breakdown']
        
        # Verify deductions breakdown
        assert 'breakdown' in breakdown['deductions']
    
    def test_breakdown_with_loss_carryforward(self, engine):
        """Test breakdown includes loss carryforward info"""
        breakdown = engine.generate_tax_breakdown(
            gross_income=Decimal('50000.00'),
            tax_year=2026,
            user_type=UserType.GSVG,
            loss_carryforward_applied=Decimal('5000.00'),
            remaining_loss_balance=Decimal('2000.00')
        )
        
        # Should include loss carryforward fields
        assert 'loss_carryforward_applied' in breakdown['income_tax']
        assert 'remaining_loss_balance' in breakdown['income_tax']
        assert breakdown['income_tax']['loss_carryforward_applied'] == 5000.00
        assert breakdown['income_tax']['remaining_loss_balance'] == 2000.00


class TestTaxCalculationEngineQuarterlyPrepayment:
    """Test quarterly prepayment calculation"""
    
    def test_calculate_quarterly_prepayment_employee(self, engine):
        """Test quarterly prepayment for employee"""
        prepayment = engine.calculate_quarterly_prepayment(
            gross_income=Decimal('50000.00'),
            tax_year=2026,
            user_type=UserType.EMPLOYEE
        )
        
        # Should have income tax prepayment
        assert prepayment['income_tax'] > Decimal('0.00')
        
        # Employee should have no SVS prepayment
        assert prepayment['svs'] == Decimal('0.00')
        
        # Total should equal income tax only
        assert prepayment['total'] == prepayment['income_tax']
    
    def test_calculate_quarterly_prepayment_gsvg(self, engine):
        """Test quarterly prepayment for GSVG"""
        prepayment = engine.calculate_quarterly_prepayment(
            gross_income=Decimal('50000.00'),
            tax_year=2026,
            user_type=UserType.GSVG
        )
        
        # Should have both income tax and SVS prepayment
        assert prepayment['income_tax'] > Decimal('0.00')
        assert prepayment['svs'] > Decimal('0.00')
        
        # Total should be sum of both
        assert prepayment['total'] == prepayment['income_tax'] + prepayment['svs']
    
    def test_quarterly_prepayment_is_one_fourth(self, engine):
        """Test that quarterly prepayment is 1/4 of annual"""
        # Calculate annual tax
        annual_breakdown = engine.calculate_total_tax(
            gross_income=Decimal('50000.00'),
            tax_year=2026,
            user_type=UserType.GSVG
        )
        
        # Calculate quarterly prepayment
        quarterly = engine.calculate_quarterly_prepayment(
            gross_income=Decimal('50000.00'),
            tax_year=2026,
            user_type=UserType.GSVG
        )
        
        # Verify quarterly is 1/4 of annual
        expected_income_tax = annual_breakdown.income_tax.total_tax / Decimal('4')
        expected_svs = annual_breakdown.svs.annual_total / Decimal('4')
        
        assert quarterly['income_tax'] == expected_income_tax.quantize(Decimal('0.01'))
        assert quarterly['svs'] == expected_svs.quantize(Decimal('0.01'))


class TestTaxCalculationEngineEdgeCases:
    """Test edge cases and boundary conditions"""
    
    def test_zero_income(self, engine):
        """Test calculation with zero income"""
        result = engine.calculate_total_tax(
            gross_income=Decimal('0.00'),
            tax_year=2026,
            user_type=UserType.EMPLOYEE
        )
        
        assert result.total_tax == Decimal('0.00')
        assert result.net_income == Decimal('0.00')
        assert result.income_tax.total_tax == Decimal('0.00')
    
    def test_negative_income(self, engine):
        """Test calculation with negative income (loss)"""
        result = engine.calculate_total_tax(
            gross_income=Decimal('-10000.00'),
            tax_year=2026,
            user_type=UserType.GSVG
        )
        
        # Should have zero income tax
        assert result.income_tax.total_tax == Decimal('0.00')
        
        # May still have minimum SVS contributions
        # (depends on GSVG minimum income threshold)
    
    def test_very_high_income(self, engine):
        """Test calculation with very high income (top bracket)"""
        result = engine.calculate_total_tax(
            gross_income=Decimal('2000000.00'),
            tax_year=2026,
            user_type=UserType.GSVG
        )
        
        # Should have tax in all brackets including 55% top bracket
        assert result.income_tax.total_tax > Decimal('500000.00')
        assert len(result.income_tax.breakdown) == 7  # All 7 brackets
        
        # Last bracket should be 55%
        last_bracket = result.income_tax.breakdown[-1]
        assert last_bracket.rate == '55%'
    
    def test_svs_deductibility_reduces_income_tax(self, engine):
        """Test that SVS contributions reduce income tax"""
        # Calculate with GSVG (has SVS)
        result_gsvg = engine.calculate_total_tax(
            gross_income=Decimal('50000.00'),
            tax_year=2026,
            user_type=UserType.GSVG
        )
        
        # Calculate with employee (no SVS)
        result_employee = engine.calculate_total_tax(
            gross_income=Decimal('50000.00'),
            tax_year=2026,
            user_type=UserType.EMPLOYEE
        )
        
        # GSVG should have lower income tax due to SVS deductibility
        # (even though total tax is higher due to SVS contributions)
        assert result_gsvg.income_tax.total_tax < result_employee.income_tax.total_tax
