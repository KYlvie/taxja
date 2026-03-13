"""Unit tests for SubscriptionService"""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from decimal import Decimal

from app.services.subscription_service import SubscriptionService
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.plan import Plan, PlanType, BillingCycle
from app.models.user import User


class TestSubscriptionService:
    """Test SubscriptionService methods"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.mock_db = Mock()
        self.service = SubscriptionService(self.mock_db)
    
    def test_create_subscription_success(self):
        """Test create_subscription creates new subscription"""
        mock_user = User(id=1, email="test@example.com")
        mock_plan = Plan(id=1, plan_type=PlanType.PLUS, name="Plus")
        
        self.mock_db.query().filter().first.side_effect = [mock_user, mock_plan, None]
        
        result = self.service.create_subscription(
            user_id=1,
            plan_id=1,
            billing_cycle=BillingCycle.MONTHLY
        )
        
        self.mock_db.add.assert_called()
        self.mock_db.commit.assert_called()
    
    def test_create_subscription_user_not_found(self):
        """Test create_subscription raises error when user not found"""
        self.mock_db.query().filter().first.return_value = None
        
        with pytest.raises(ValueError, match="User.*not found"):
            self.service.create_subscription(user_id=999, plan_id=1)
    
    def test_create_subscription_already_active(self):
        """Test create_subscription raises error when user has active subscription"""
        mock_user = User(id=1, email="test@example.com")
        mock_plan = Plan(id=1, plan_type=PlanType.PLUS, name="Plus")
        mock_subscription = Subscription(
            id=1,
            user_id=1,
            plan_id=1,
            status=SubscriptionStatus.ACTIVE
        )
        
        self.mock_db.query().filter().first.side_effect = [mock_user, mock_plan]
        self.mock_db.query().filter().order_by().first.return_value = mock_subscription
        
        with pytest.raises(ValueError, match="already has an active subscription"):
            self.service.create_subscription(user_id=1, plan_id=1)
    
    def test_get_user_subscription(self):
        """Test get_user_subscription returns subscription"""
        mock_subscription = Subscription(id=1, user_id=1, plan_id=1)
        self.mock_db.query().filter().order_by().first.return_value = mock_subscription
        
        result = self.service.get_user_subscription(1)
        
        assert result == mock_subscription
    
    def test_upgrade_subscription_success(self):
        """Test upgrade_subscription upgrades to higher tier"""
        now = datetime.utcnow()
        mock_current_plan = Plan(
            id=1,
            plan_type=PlanType.PLUS,
            name="Plus",
            monthly_price=Decimal("4.90"),
            yearly_price=Decimal("49.00")
        )
        mock_new_plan = Plan(
            id=2,
            plan_type=PlanType.PRO,
            name="Pro",
            monthly_price=Decimal("9.90"),
            yearly_price=Decimal("99.00")
        )
        mock_subscription = Subscription(
            id=1,
            user_id=1,
            plan_id=1,
            status=SubscriptionStatus.ACTIVE,
            billing_cycle=BillingCycle.MONTHLY,
            current_period_start=now,
            current_period_end=now + timedelta(days=30)
        )
        mock_subscription.plan = mock_current_plan
        
        self.mock_db.query().filter().order_by().first.return_value = mock_subscription
        self.mock_db.query().filter().first.return_value = mock_new_plan
        
        result = self.service.upgrade_subscription(user_id=1, new_plan_id=2)
        
        assert result["subscription"].plan_id == 2
        assert result["effective_immediately"] is True
        assert "proration_amount" in result
        self.mock_db.commit.assert_called()
    
    def test_upgrade_subscription_not_higher_price(self):
        """Test upgrade_subscription raises error when not an upgrade"""
        mock_current_plan = Plan(
            id=2,
            plan_type=PlanType.PRO,
            name="Pro",
            monthly_price=Decimal("9.90"),
            yearly_price=Decimal("99.00")
        )
        mock_new_plan = Plan(
            id=1,
            plan_type=PlanType.PLUS,
            name="Plus",
            monthly_price=Decimal("4.90"),
            yearly_price=Decimal("49.00")
        )
        mock_subscription = Subscription(
            id=1,
            user_id=1,
            plan_id=2,
            status=SubscriptionStatus.ACTIVE,
            billing_cycle=BillingCycle.MONTHLY
        )
        mock_subscription.plan = mock_current_plan
        
        self.mock_db.query().filter().order_by().first.return_value = mock_subscription
        self.mock_db.query().filter().first.return_value = mock_new_plan
        
        with pytest.raises(ValueError, match="must be higher"):
            self.service.upgrade_subscription(user_id=1, new_plan_id=1)
    
    def test_downgrade_subscription_success(self):
        """Test downgrade_subscription schedules downgrade"""
        now = datetime.utcnow()
        mock_current_plan = Plan(
            id=2,
            plan_type=PlanType.PRO,
            name="Pro",
            monthly_price=Decimal("9.90"),
            yearly_price=Decimal("99.00")
        )
        mock_new_plan = Plan(
            id=1,
            plan_type=PlanType.PLUS,
            name="Plus",
            monthly_price=Decimal("4.90"),
            yearly_price=Decimal("49.00")
        )
        mock_subscription = Subscription(
            id=1,
            user_id=1,
            plan_id=2,
            status=SubscriptionStatus.ACTIVE,
            billing_cycle=BillingCycle.MONTHLY,
            current_period_end=now + timedelta(days=15)
        )
        mock_subscription.plan = mock_current_plan
        
        self.mock_db.query().filter().order_by().first.return_value = mock_subscription
        self.mock_db.query().filter().first.return_value = mock_new_plan
        
        result = self.service.downgrade_subscription(user_id=1, new_plan_id=1)
        
        assert result["effective_immediately"] is False
        assert result["effective_date"] == mock_subscription.current_period_end
    
    def test_cancel_subscription_at_period_end(self):
        """Test cancel_subscription preserves access until period end"""
        now = datetime.utcnow()
        mock_subscription = Subscription(
            id=1,
            user_id=1,
            plan_id=1,
            status=SubscriptionStatus.ACTIVE,
            current_period_end=now + timedelta(days=15)
        )
        
        self.mock_db.query().filter().order_by().first.return_value = mock_subscription
        
        result = self.service.cancel_subscription(user_id=1, immediate=False)
        
        assert result["immediate"] is False
        assert mock_subscription.cancel_at_period_end is True
        assert result["access_until"] == mock_subscription.current_period_end
        self.mock_db.commit.assert_called()
    
    def test_cancel_subscription_immediate(self):
        """Test cancel_subscription cancels immediately"""
        mock_subscription = Subscription(
            id=1,
            user_id=1,
            plan_id=1,
            status=SubscriptionStatus.ACTIVE
        )
        
        self.mock_db.query().filter().order_by().first.return_value = mock_subscription
        
        result = self.service.cancel_subscription(user_id=1, immediate=True)
        
        assert result["immediate"] is True
        assert mock_subscription.status == SubscriptionStatus.CANCELED
        self.mock_db.commit.assert_called()
    
    def test_reactivate_subscription_success(self):
        """Test reactivate_subscription reactivates canceled subscription"""
        now = datetime.utcnow()
        mock_subscription = Subscription(
            id=1,
            user_id=1,
            plan_id=1,
            status=SubscriptionStatus.CANCELED,
            updated_at=now - timedelta(days=5),
            current_period_end=now - timedelta(days=1),
            billing_cycle=BillingCycle.MONTHLY
        )
        
        self.mock_db.query().filter().order_by().first.return_value = mock_subscription
        
        result = self.service.reactivate_subscription(user_id=1)
        
        assert result.status == SubscriptionStatus.ACTIVE
        assert result.cancel_at_period_end is False
        self.mock_db.commit.assert_called()
    
    def test_reactivate_subscription_past_window(self):
        """Test reactivate_subscription raises error after 30 days"""
        now = datetime.utcnow()
        mock_subscription = Subscription(
            id=1,
            user_id=1,
            plan_id=1,
            status=SubscriptionStatus.CANCELED,
            updated_at=now - timedelta(days=31)
        )
        
        self.mock_db.query().filter().order_by().first.return_value = mock_subscription
        
        with pytest.raises(ValueError, match="after 30 days"):
            self.service.reactivate_subscription(user_id=1)
    
    def test_check_subscription_status_active(self):
        """Test check_subscription_status returns correct status"""
        now = datetime.utcnow()
        mock_plan = Plan(id=1, plan_type=PlanType.PLUS, name="Plus")
        mock_subscription = Subscription(
            id=1,
            user_id=1,
            plan_id=1,
            status=SubscriptionStatus.ACTIVE,
            current_period_end=now + timedelta(days=15)
        )
        mock_subscription.plan = mock_plan
        
        self.mock_db.query().filter().order_by().first.return_value = mock_subscription
        
        result = self.service.check_subscription_status(user_id=1)
        
        assert result["has_subscription"] is True
        assert result["status"] == SubscriptionStatus.ACTIVE
        assert result["plan_type"] == PlanType.PLUS
        assert result["is_active"] is True
    
    def test_check_subscription_status_no_subscription(self):
        """Test check_subscription_status returns Free tier when no subscription"""
        self.mock_db.query().filter().order_by().first.return_value = None
        
        result = self.service.check_subscription_status(user_id=1)
        
        assert result["has_subscription"] is False
        assert result["plan_type"] == PlanType.FREE
        assert result["is_active"] is False
    
    def test_handle_trial_expiration(self):
        """Test handle_trial_expiration downgrades to Free"""
        now = datetime.utcnow()
        mock_pro_plan = Plan(id=2, plan_type=PlanType.PRO, name="Pro")
        mock_free_plan = Plan(id=1, plan_type=PlanType.FREE, name="Free")
        mock_subscription = Subscription(
            id=1,
            user_id=1,
            plan_id=2,
            status=SubscriptionStatus.TRIALING,
            current_period_end=now - timedelta(days=1)
        )
        mock_subscription.plan = mock_pro_plan
        
        self.mock_db.query().filter().order_by().first.return_value = mock_subscription
        self.mock_db.query().filter().first.return_value = mock_free_plan
        
        result = self.service.handle_trial_expiration(user_id=1)
        
        assert result.plan_id == 1
        assert result.status == SubscriptionStatus.ACTIVE
        self.mock_db.commit.assert_called()
