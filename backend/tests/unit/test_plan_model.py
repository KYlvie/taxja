"""Unit tests for Plan model"""
import pytest
from decimal import Decimal
from app.models.plan import Plan, PlanType, BillingCycle


class TestPlanModel:
    """Test Plan model methods"""
    
    def test_plan_creation(self):
        """Test creating a plan"""
        plan = Plan(
            plan_type=PlanType.FREE,
            name="Free Plan",
            monthly_price=Decimal("0.00"),
            yearly_price=Decimal("0.00"),
            features={"basic_tax_calc": True},
            quotas={"transactions": 50}
        )
        
        assert plan.plan_type == PlanType.FREE
        assert plan.name == "Free Plan"
        assert plan.monthly_price == Decimal("0.00")
        assert plan.features["basic_tax_calc"] is True
        assert plan.quotas["transactions"] == 50
    
    def test_has_feature_true(self):
        """Test has_feature returns True for existing feature"""
        plan = Plan(
            plan_type=PlanType.PLUS,
            name="Plus Plan",
            monthly_price=Decimal("4.90"),
            yearly_price=Decimal("49.00"),
            features={"ocr_scanning": True, "multi_language": True},
            quotas={"transactions": -1}
        )
        
        assert plan.has_feature("ocr_scanning") is True
        assert plan.has_feature("multi_language") is True
    
    def test_has_feature_false(self):
        """Test has_feature returns False for non-existing feature"""
        plan = Plan(
            plan_type=PlanType.FREE,
            name="Free Plan",
            monthly_price=Decimal("0.00"),
            yearly_price=Decimal("0.00"),
            features={"basic_tax_calc": True},
            quotas={"transactions": 50}
        )
        
        assert plan.has_feature("ai_assistant") is False
        assert plan.has_feature("ocr_scanning") is False
    
    def test_get_quota_existing(self):
        """Test get_quota returns correct value for existing quota"""
        plan = Plan(
            plan_type=PlanType.FREE,
            name="Free Plan",
            monthly_price=Decimal("0.00"),
            yearly_price=Decimal("0.00"),
            features={},
            quotas={"transactions": 50, "ocr_scans": 0}
        )
        
        assert plan.get_quota("transactions") == 50
        assert plan.get_quota("ocr_scans") == 0
    
    def test_get_quota_unlimited(self):
        """Test get_quota returns -1 for unlimited quota"""
        plan = Plan(
            plan_type=PlanType.PRO,
            name="Pro Plan",
            monthly_price=Decimal("9.90"),
            yearly_price=Decimal("99.00"),
            features={},
            quotas={"transactions": -1, "ocr_scans": -1}
        )
        
        assert plan.get_quota("transactions") == -1
        assert plan.get_quota("ocr_scans") == -1
    
    def test_get_quota_non_existing(self):
        """Test get_quota returns 0 for non-existing quota"""
        plan = Plan(
            plan_type=PlanType.FREE,
            name="Free Plan",
            monthly_price=Decimal("0.00"),
            yearly_price=Decimal("0.00"),
            features={},
            quotas={"transactions": 50}
        )
        
        assert plan.get_quota("non_existing") == 0
    
    def test_is_unlimited_true(self):
        """Test is_unlimited returns True for unlimited quota"""
        plan = Plan(
            plan_type=PlanType.PRO,
            name="Pro Plan",
            monthly_price=Decimal("9.90"),
            yearly_price=Decimal("99.00"),
            features={},
            quotas={"transactions": -1}
        )
        
        assert plan.is_unlimited("transactions") is True
    
    def test_is_unlimited_false(self):
        """Test is_unlimited returns False for limited quota"""
        plan = Plan(
            plan_type=PlanType.FREE,
            name="Free Plan",
            monthly_price=Decimal("0.00"),
            yearly_price=Decimal("0.00"),
            features={},
            quotas={"transactions": 50}
        )
        
        assert plan.is_unlimited("transactions") is False
    
    def test_yearly_discount(self):
        """Test yearly pricing has discount"""
        plan = Plan(
            plan_type=PlanType.PLUS,
            name="Plus Plan",
            monthly_price=Decimal("4.90"),
            yearly_price=Decimal("49.00"),
            features={},
            quotas={}
        )
        
        # Yearly should be less than 12 * monthly
        assert plan.yearly_price < (plan.monthly_price * 12)
        
        # Calculate discount percentage
        monthly_annual = plan.monthly_price * 12
        discount = ((monthly_annual - plan.yearly_price) / monthly_annual) * 100
        
        # Should be approximately 17% discount
        assert 16 <= discount <= 18
