"""Unit tests for PlanService"""
import pytest
from unittest.mock import Mock, MagicMock
from decimal import Decimal

from app.services.plan_service import PlanService
from app.models.plan import Plan, PlanType
from app.schemas.subscription import PlanCreate, PlanUpdate


class TestPlanService:
    """Test PlanService methods"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.mock_db = Mock()
        self.service = PlanService(self.mock_db)
    
    def test_get_plan_found(self):
        """Test get_plan returns plan when found"""
        mock_plan = Plan(id=1, plan_type=PlanType.FREE, name="Free")
        self.mock_db.query().filter().first.return_value = mock_plan
        
        result = self.service.get_plan(1)
        
        assert result == mock_plan
        assert result.id == 1
    
    def test_get_plan_not_found(self):
        """Test get_plan returns None when not found"""
        self.mock_db.query().filter().first.return_value = None
        
        result = self.service.get_plan(999)
        
        assert result is None
    
    def test_get_plan_by_type_found(self):
        """Test get_plan_by_type returns plan"""
        mock_plan = Plan(id=1, plan_type=PlanType.PRO, name="Pro")
        self.mock_db.query().filter().first.return_value = mock_plan
        
        result = self.service.get_plan_by_type(PlanType.PRO)
        
        assert result == mock_plan
        assert result.plan_type == PlanType.PRO
    
    def test_list_plans(self):
        """Test list_plans returns all plans ordered by price"""
        mock_plans = [
            Plan(id=1, plan_type=PlanType.FREE, name="Free", monthly_price=Decimal("0")),
            Plan(id=2, plan_type=PlanType.PLUS, name="Plus", monthly_price=Decimal("4.90")),
            Plan(id=3, plan_type=PlanType.PRO, name="Pro", monthly_price=Decimal("9.90")),
        ]
        self.mock_db.query().order_by().all.return_value = mock_plans
        
        result = self.service.list_plans()
        
        assert len(result) == 3
        assert result[0].plan_type == PlanType.FREE
        assert result[2].plan_type == PlanType.PRO
    
    def test_create_plan_success(self):
        """Test create_plan successfully creates new plan"""
        plan_data = PlanCreate(
            plan_type=PlanType.FREE,
            name="Free Plan",
            monthly_price=Decimal("0.00"),
            yearly_price=Decimal("0.00"),
            features={"basic_tax_calc": True},
            quotas={"transactions": 50}
        )
        
        # Mock no existing plan
        self.mock_db.query().filter().first.return_value = None
        
        result = self.service.create_plan(plan_data)
        
        self.mock_db.add.assert_called_once()
        self.mock_db.commit.assert_called_once()
        self.mock_db.refresh.assert_called_once()
    
    def test_create_plan_duplicate_type(self):
        """Test create_plan raises error for duplicate plan type"""
        plan_data = PlanCreate(
            plan_type=PlanType.FREE,
            name="Free Plan",
            monthly_price=Decimal("0.00"),
            yearly_price=Decimal("0.00"),
            features={},
            quotas={}
        )
        
        # Mock existing plan
        existing_plan = Plan(id=1, plan_type=PlanType.FREE, name="Existing")
        self.mock_db.query().filter().first.return_value = existing_plan
        
        with pytest.raises(ValueError, match="already exists"):
            self.service.create_plan(plan_data)
    
    def test_update_plan_success(self):
        """Test update_plan successfully updates plan"""
        mock_plan = Plan(
            id=1,
            plan_type=PlanType.PLUS,
            name="Plus",
            monthly_price=Decimal("4.90"),
            yearly_price=Decimal("49.00"),
            features={"ocr_scanning": True},
            quotas={"transactions": -1}
        )
        self.mock_db.query().filter().first.return_value = mock_plan
        
        plan_data = PlanUpdate(name="Plus Updated")
        
        result = self.service.update_plan(1, plan_data)
        
        self.mock_db.commit.assert_called_once()
        self.mock_db.refresh.assert_called_once()
    
    def test_update_plan_not_found(self):
        """Test update_plan raises error when plan not found"""
        self.mock_db.query().filter().first.return_value = None
        
        plan_data = PlanUpdate(name="Updated")
        
        with pytest.raises(ValueError, match="not found"):
            self.service.update_plan(999, plan_data)
    
    def test_get_plan_features(self):
        """Test get_plan_features returns features dict"""
        mock_plan = Plan(
            id=1,
            plan_type=PlanType.PRO,
            name="Pro",
            monthly_price=Decimal("9.90"),
            yearly_price=Decimal("99.00"),
            features={"ai_assistant": True, "e1_generation": True},
            quotas={}
        )
        self.mock_db.query().filter().first.return_value = mock_plan
        
        result = self.service.get_plan_features(1)
        
        assert result == {"ai_assistant": True, "e1_generation": True}
    
    def test_get_plan_quotas(self):
        """Test get_plan_quotas returns quotas dict"""
        mock_plan = Plan(
            id=1,
            plan_type=PlanType.FREE,
            name="Free",
            monthly_price=Decimal("0"),
            yearly_price=Decimal("0"),
            features={},
            quotas={"transactions": 50, "ocr_scans": 0}
        )
        self.mock_db.query().filter().first.return_value = mock_plan
        
        result = self.service.get_plan_quotas(1)
        
        assert result == {"transactions": 50, "ocr_scans": 0}
    
    def test_check_feature_access_true(self):
        """Test check_feature_access returns True when feature exists"""
        mock_plan = Plan(
            id=1,
            plan_type=PlanType.PLUS,
            name="Plus",
            monthly_price=Decimal("4.90"),
            yearly_price=Decimal("49.00"),
            features={"ocr_scanning": True},
            quotas={}
        )
        self.mock_db.query().filter().first.return_value = mock_plan
        
        result = self.service.check_feature_access(1, "ocr_scanning")
        
        assert result is True
    
    def test_check_feature_access_false(self):
        """Test check_feature_access returns False when feature doesn't exist"""
        mock_plan = Plan(
            id=1,
            plan_type=PlanType.FREE,
            name="Free",
            monthly_price=Decimal("0"),
            yearly_price=Decimal("0"),
            features={"basic_tax_calc": True},
            quotas={}
        )
        self.mock_db.query().filter().first.return_value = mock_plan
        
        result = self.service.check_feature_access(1, "ai_assistant")
        
        assert result is False
    
    def test_get_quota_limit(self):
        """Test get_quota_limit returns correct limit"""
        mock_plan = Plan(
            id=1,
            plan_type=PlanType.PLUS,
            name="Plus",
            monthly_price=Decimal("4.90"),
            yearly_price=Decimal("49.00"),
            features={},
            quotas={"transactions": -1, "ocr_scans": 20}
        )
        self.mock_db.query().filter().first.return_value = mock_plan
        
        result_unlimited = self.service.get_quota_limit(1, "transactions")
        result_limited = self.service.get_quota_limit(1, "ocr_scans")
        
        assert result_unlimited == -1  # Unlimited
        assert result_limited == 20
