"""Unit tests for PlanService"""
import pytest
from decimal import Decimal
from sqlalchemy.orm import Session

from app.models.plan import Plan, PlanType
from app.schemas.subscription import PlanCreate, PlanUpdate
from app.services.plan_service import PlanService


@pytest.fixture
def plan_service(db_session: Session):
    """Create PlanService instance with test database session"""
    return PlanService(db_session)


@pytest.fixture
def sample_free_plan(db_session: Session):
    """Create a sample FREE plan for testing"""
    plan = Plan(
        plan_type=PlanType.FREE,
        name="Free Plan",
        monthly_price=Decimal("0.00"),
        yearly_price=Decimal("0.00"),
        features={
            "basic_tax_calc": True,
            "ocr": False,
            "ai_assistant": False,
            "e1_generation": False,
        },
        quotas={
            "transactions": 50,
            "ocr_scans": 0,
            "ai_conversations": 0,
        },
    )
    db_session.add(plan)
    db_session.commit()
    db_session.refresh(plan)
    return plan


@pytest.fixture
def sample_plus_plan(db_session: Session):
    """Create a sample PLUS plan for testing"""
    plan = Plan(
        plan_type=PlanType.PLUS,
        name="Plus Plan",
        monthly_price=Decimal("4.90"),
        yearly_price=Decimal("49.00"),
        features={
            "basic_tax_calc": True,
            "full_tax_calc": True,
            "ocr": True,
            "ai_classification": True,
            "csv_import": True,
            "multi_language": True,
            "ai_assistant": False,
            "e1_generation": False,
        },
        quotas={
            "transactions": -1,  # unlimited
            "ocr_scans": 20,
            "ai_conversations": 0,
        },
    )
    db_session.add(plan)
    db_session.commit()
    db_session.refresh(plan)
    return plan


class TestGetPlan:
    """Tests for get_plan method"""
    
    def test_get_existing_plan(self, plan_service: PlanService, sample_free_plan: Plan):
        """Test retrieving an existing plan by ID"""
        plan = plan_service.get_plan(sample_free_plan.id)
        
        assert plan is not None
        assert plan.id == sample_free_plan.id
        assert plan.plan_type == PlanType.FREE
        assert plan.name == "Free Plan"
    
    def test_get_nonexistent_plan(self, plan_service: PlanService):
        """Test retrieving a non-existent plan returns None"""
        plan = plan_service.get_plan(99999)
        
        assert plan is None


class TestGetPlanByType:
    """Tests for get_plan_by_type method"""
    
    def test_get_plan_by_type_success(
        self, plan_service: PlanService, sample_free_plan: Plan
    ):
        """Test retrieving a plan by plan type"""
        plan = plan_service.get_plan_by_type(PlanType.FREE)
        
        assert plan is not None
        assert plan.plan_type == PlanType.FREE
        assert plan.id == sample_free_plan.id
    
    def test_get_plan_by_type_not_found(self, plan_service: PlanService):
        """Test retrieving a non-existent plan type returns None"""
        plan = plan_service.get_plan_by_type(PlanType.PRO)
        
        assert plan is None


class TestListPlans:
    """Tests for list_plans method"""
    
    def test_list_empty_plans(self, plan_service: PlanService):
        """Test listing plans when none exist"""
        plans = plan_service.list_plans()
        
        assert plans == []
    
    def test_list_multiple_plans(
        self,
        plan_service: PlanService,
        sample_free_plan: Plan,
        sample_plus_plan: Plan,
    ):
        """Test listing multiple plans ordered by price"""
        plans = plan_service.list_plans()
        
        assert len(plans) == 2
        # Should be ordered by monthly_price (Free: 0.00, Plus: 4.90)
        assert plans[0].plan_type == PlanType.FREE
        assert plans[1].plan_type == PlanType.PLUS


class TestCreatePlan:
    """Tests for create_plan method"""
    
    def test_create_plan_success(self, plan_service: PlanService):
        """Test creating a new plan successfully"""
        plan_data = PlanCreate(
            plan_type=PlanType.PRO,
            name="Pro Plan",
            monthly_price=Decimal("9.90"),
            yearly_price=Decimal("99.00"),
            features={
                "basic_tax_calc": True,
                "full_tax_calc": True,
                "ocr": True,
                "ai_assistant": True,
                "e1_generation": True,
            },
            quotas={
                "transactions": -1,
                "ocr_scans": -1,
                "ai_conversations": -1,
            },
        )
        
        plan = plan_service.create_plan(plan_data)
        
        assert plan.id is not None
        assert plan.plan_type == PlanType.PRO
        assert plan.name == "Pro Plan"
        assert plan.monthly_price == Decimal("9.90")
        assert plan.yearly_price == Decimal("99.00")
        assert plan.features["ai_assistant"] is True
        assert plan.quotas["transactions"] == -1
    
    def test_create_duplicate_plan_type(
        self, plan_service: PlanService, sample_free_plan: Plan
    ):
        """Test creating a plan with duplicate plan_type raises error"""
        plan_data = PlanCreate(
            plan_type=PlanType.FREE,
            name="Another Free Plan",
            monthly_price=Decimal("0.00"),
            yearly_price=Decimal("0.00"),
            features={},
            quotas={},
        )
        
        with pytest.raises(ValueError, match="Plan with type .* already exists"):
            plan_service.create_plan(plan_data)
    
    def test_create_plan_invalid_features(self, plan_service: PlanService):
        """Test creating a plan with invalid features raises error"""
        plan_data = PlanCreate(
            plan_type=PlanType.PRO,
            name="Pro Plan",
            monthly_price=Decimal("9.90"),
            yearly_price=Decimal("99.00"),
            features={"invalid_feature": "not_a_boolean"},  # Invalid: not boolean
            quotas={},
        )
        
        with pytest.raises(ValueError, match="Invalid features"):
            plan_service.create_plan(plan_data)
    
    def test_create_plan_invalid_quotas(self, plan_service: PlanService):
        """Test creating a plan with invalid quotas raises error"""
        plan_data = PlanCreate(
            plan_type=PlanType.PRO,
            name="Pro Plan",
            monthly_price=Decimal("9.90"),
            yearly_price=Decimal("99.00"),
            features={},
            quotas={"transactions": -2},  # Invalid: must be >= -1
        )
        
        with pytest.raises(ValueError, match="Invalid quotas"):
            plan_service.create_plan(plan_data)


class TestUpdatePlan:
    """Tests for update_plan method"""
    
    def test_update_plan_name(
        self, plan_service: PlanService, sample_free_plan: Plan
    ):
        """Test updating plan name"""
        update_data = PlanUpdate(name="Updated Free Plan")
        
        updated_plan = plan_service.update_plan(sample_free_plan.id, update_data)
        
        assert updated_plan.name == "Updated Free Plan"
        assert updated_plan.plan_type == PlanType.FREE  # Unchanged
    
    def test_update_plan_pricing(
        self, plan_service: PlanService, sample_plus_plan: Plan
    ):
        """Test updating plan pricing"""
        update_data = PlanUpdate(
            monthly_price=Decimal("5.90"), yearly_price=Decimal("59.00")
        )
        
        updated_plan = plan_service.update_plan(sample_plus_plan.id, update_data)
        
        assert updated_plan.monthly_price == Decimal("5.90")
        assert updated_plan.yearly_price == Decimal("59.00")
    
    def test_update_plan_features(
        self, plan_service: PlanService, sample_free_plan: Plan
    ):
        """Test updating plan features"""
        update_data = PlanUpdate(
            features={
                "basic_tax_calc": True,
                "ocr": True,  # Enable OCR
            }
        )
        
        updated_plan = plan_service.update_plan(sample_free_plan.id, update_data)
        
        assert updated_plan.features["ocr"] is True
        assert updated_plan.features["basic_tax_calc"] is True
    
    def test_update_plan_quotas(
        self, plan_service: PlanService, sample_free_plan: Plan
    ):
        """Test updating plan quotas"""
        update_data = PlanUpdate(quotas={"transactions": 100, "ocr_scans": 10})
        
        updated_plan = plan_service.update_plan(sample_free_plan.id, update_data)
        
        assert updated_plan.quotas["transactions"] == 100
        assert updated_plan.quotas["ocr_scans"] == 10
    
    def test_update_nonexistent_plan(self, plan_service: PlanService):
        """Test updating a non-existent plan raises error"""
        update_data = PlanUpdate(name="Updated Plan")
        
        with pytest.raises(ValueError, match="Plan with id .* not found"):
            plan_service.update_plan(99999, update_data)
    
    def test_update_plan_invalid_features(
        self, plan_service: PlanService, sample_free_plan: Plan
    ):
        """Test updating with invalid features raises error"""
        update_data = PlanUpdate(features={"invalid": "not_boolean"})
        
        with pytest.raises(ValueError, match="Invalid features"):
            plan_service.update_plan(sample_free_plan.id, update_data)
    
    def test_update_plan_invalid_quotas(
        self, plan_service: PlanService, sample_free_plan: Plan
    ):
        """Test updating with invalid quotas raises error"""
        update_data = PlanUpdate(quotas={"transactions": -5})  # Invalid
        
        with pytest.raises(ValueError, match="Invalid quotas"):
            plan_service.update_plan(sample_free_plan.id, update_data)


class TestGetPlanFeatures:
    """Tests for get_plan_features method"""
    
    def test_get_plan_features_success(
        self, plan_service: PlanService, sample_plus_plan: Plan
    ):
        """Test retrieving plan features"""
        features = plan_service.get_plan_features(sample_plus_plan.id)
        
        assert isinstance(features, dict)
        assert features["basic_tax_calc"] is True
        assert features["full_tax_calc"] is True
        assert features["ocr"] is True
        assert features["ai_assistant"] is False
    
    def test_get_plan_features_nonexistent_plan(self, plan_service: PlanService):
        """Test retrieving features for non-existent plan raises error"""
        with pytest.raises(ValueError, match="Plan with id .* not found"):
            plan_service.get_plan_features(99999)


class TestGetPlanQuotas:
    """Tests for get_plan_quotas method"""
    
    def test_get_plan_quotas_success(
        self, plan_service: PlanService, sample_plus_plan: Plan
    ):
        """Test retrieving plan quotas"""
        quotas = plan_service.get_plan_quotas(sample_plus_plan.id)
        
        assert isinstance(quotas, dict)
        assert quotas["transactions"] == -1  # unlimited
        assert quotas["ocr_scans"] == 20
        assert quotas["ai_conversations"] == 0
    
    def test_get_plan_quotas_nonexistent_plan(self, plan_service: PlanService):
        """Test retrieving quotas for non-existent plan raises error"""
        with pytest.raises(ValueError, match="Plan with id .* not found"):
            plan_service.get_plan_quotas(99999)


class TestCheckFeatureAccess:
    """Tests for check_feature_access method"""
    
    def test_check_feature_access_has_feature(
        self, plan_service: PlanService, sample_plus_plan: Plan
    ):
        """Test checking access to a feature the plan has"""
        has_access = plan_service.check_feature_access(sample_plus_plan.id, "ocr")
        
        assert has_access is True
    
    def test_check_feature_access_no_feature(
        self, plan_service: PlanService, sample_plus_plan: Plan
    ):
        """Test checking access to a feature the plan doesn't have"""
        has_access = plan_service.check_feature_access(
            sample_plus_plan.id, "ai_assistant"
        )
        
        assert has_access is False
    
    def test_check_feature_access_undefined_feature(
        self, plan_service: PlanService, sample_plus_plan: Plan
    ):
        """Test checking access to an undefined feature returns False"""
        has_access = plan_service.check_feature_access(
            sample_plus_plan.id, "nonexistent_feature"
        )
        
        assert has_access is False
    
    def test_check_feature_access_nonexistent_plan(self, plan_service: PlanService):
        """Test checking feature access for non-existent plan raises error"""
        with pytest.raises(ValueError, match="Plan with id .* not found"):
            plan_service.check_feature_access(99999, "ocr")


class TestGetQuotaLimit:
    """Tests for get_quota_limit method"""
    
    def test_get_quota_limit_defined(
        self, plan_service: PlanService, sample_plus_plan: Plan
    ):
        """Test getting quota limit for a defined resource"""
        limit = plan_service.get_quota_limit(sample_plus_plan.id, "ocr_scans")
        
        assert limit == 20
    
    def test_get_quota_limit_unlimited(
        self, plan_service: PlanService, sample_plus_plan: Plan
    ):
        """Test getting quota limit for unlimited resource"""
        limit = plan_service.get_quota_limit(sample_plus_plan.id, "transactions")
        
        assert limit == -1
    
    def test_get_quota_limit_undefined(
        self, plan_service: PlanService, sample_plus_plan: Plan
    ):
        """Test getting quota limit for undefined resource returns 0"""
        limit = plan_service.get_quota_limit(
            sample_plus_plan.id, "nonexistent_resource"
        )
        
        assert limit == 0
    
    def test_get_quota_limit_nonexistent_plan(self, plan_service: PlanService):
        """Test getting quota limit for non-existent plan raises error"""
        with pytest.raises(ValueError, match="Plan with id .* not found"):
            plan_service.get_quota_limit(99999, "transactions")
