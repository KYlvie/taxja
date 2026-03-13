"""Unit tests for SubscriptionService"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session  # noqa: F401

from app.services.subscription_service import SubscriptionService
from app.services.plan_service import PlanService
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.plan import Plan, PlanType, BillingCycle
from app.models.user import User, UserType
from app.models.audit_log import AuditLog, AuditOperationType


@pytest.fixture
def test_user(db):
    """Create a test user"""
    user = User(
        email="test@example.com",
        password_hash="hashed_password",
        name="Test User",
        user_type=UserType.EMPLOYEE,
        language="de",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def test_plans(db):
    """Create test plans"""
    plans = {
        "free": Plan(
            plan_type=PlanType.FREE,
            name="Free Plan",
            monthly_price=Decimal("0.00"),
            yearly_price=Decimal("0.00"),
            features={"basic_tax_calc": True, "ocr": False},
            quotas={"transactions": 50, "ocr_scans": 0},
        ),
        "plus": Plan(
            plan_type=PlanType.PLUS,
            name="Plus Plan",
            monthly_price=Decimal("4.90"),
            yearly_price=Decimal("49.00"),
            features={"basic_tax_calc": True, "ocr": True, "ai_assistant": False},
            quotas={"transactions": -1, "ocr_scans": 20},
        ),
        "pro": Plan(
            plan_type=PlanType.PRO,
            name="Pro Plan",
            monthly_price=Decimal("9.90"),
            yearly_price=Decimal("99.00"),
            features={"basic_tax_calc": True, "ocr": True, "ai_assistant": True},
            quotas={"transactions": -1, "ocr_scans": -1},
        ),
    }
    
    for plan in plans.values():
        db.add(plan)
    
    db.commit()
    
    for plan in plans.values():
        db.refresh(plan)
    
    return plans


@pytest.fixture
def subscription_service(db):
    """Create a SubscriptionService instance"""
    return SubscriptionService(db)


class TestCreateSubscription:
    """Tests for create_subscription method"""
    
    def test_create_subscription_success(
        self, subscription_service: SubscriptionService, test_user: User, test_plans: dict, db
    ):
        """Test successful subscription creation"""
        plan = test_plans["plus"]
        
        subscription = subscription_service.create_subscription(
            user_id=test_user.id,
            plan_id=plan.id,
            billing_cycle=BillingCycle.MONTHLY,
            status=SubscriptionStatus.ACTIVE,
        )
        
        assert subscription.id is not None
        assert subscription.user_id == test_user.id
        assert subscription.plan_id == plan.id
        assert subscription.status == SubscriptionStatus.ACTIVE
        assert subscription.billing_cycle == BillingCycle.MONTHLY
        assert subscription.cancel_at_period_end is False
        assert subscription.current_period_start is not None
        assert subscription.current_period_end is not None
        
        # Verify audit log was created
        audit_log = db.query(AuditLog).filter(
            AuditLog.user_id == test_user.id,
            AuditLog.operation_type == AuditOperationType.CREATE,
        ).first()
        assert audit_log is not None
        assert audit_log.details["plan_type"] == PlanType.PLUS.value
    
    def test_create_subscription_with_stripe_ids(
        self, subscription_service: SubscriptionService, test_user: User, test_plans: dict
    ):
        """Test subscription creation with Stripe IDs"""
        plan = test_plans["pro"]
        
        subscription = subscription_service.create_subscription(
            user_id=test_user.id,
            plan_id=plan.id,
            billing_cycle=BillingCycle.YEARLY,
            stripe_subscription_id="sub_123456",
            stripe_customer_id="cus_123456",
        )
        
        assert subscription.stripe_subscription_id == "sub_123456"
        assert subscription.stripe_customer_id == "cus_123456"
    
    def test_create_subscription_user_not_found(
        self, subscription_service: SubscriptionService, test_plans: dict
    ):
        """Test subscription creation with non-existent user"""
        plan = test_plans["plus"]
        
        with pytest.raises(ValueError, match="User with id 99999 not found"):
            subscription_service.create_subscription(
                user_id=99999,
                plan_id=plan.id,
            )
    
    def test_create_subscription_plan_not_found(
        self, subscription_service: SubscriptionService, test_user: User
    ):
        """Test subscription creation with non-existent plan"""
        with pytest.raises(ValueError, match="Plan with id 99999 not found"):
            subscription_service.create_subscription(
                user_id=test_user.id,
                plan_id=99999,
            )
    
    def test_create_subscription_user_already_has_active(
        self, subscription_service: SubscriptionService, test_user: User, test_plans: dict
    ):
        """Test that user cannot have multiple active subscriptions"""
        plan = test_plans["plus"]
        
        # Create first subscription
        subscription_service.create_subscription(
            user_id=test_user.id,
            plan_id=plan.id,
        )
        
        # Try to create second subscription
        with pytest.raises(ValueError, match="already has an active subscription"):
            subscription_service.create_subscription(
                user_id=test_user.id,
                plan_id=plan.id,
            )


class TestGetUserSubscription:
    """Tests for get_user_subscription method"""
    
    def test_get_user_subscription_exists(
        self, subscription_service: SubscriptionService, test_user: User, test_plans: dict
    ):
        """Test getting existing subscription"""
        plan = test_plans["plus"]
        
        created_subscription = subscription_service.create_subscription(
            user_id=test_user.id,
            plan_id=plan.id,
        )
        
        retrieved_subscription = subscription_service.get_user_subscription(test_user.id)
        
        assert retrieved_subscription is not None
        assert retrieved_subscription.id == created_subscription.id
        assert retrieved_subscription.user_id == test_user.id
    
    def test_get_user_subscription_not_exists(
        self, subscription_service: SubscriptionService, test_user: User
    ):
        """Test getting non-existent subscription"""
        subscription = subscription_service.get_user_subscription(test_user.id)
        assert subscription is None


class TestUpgradeSubscription:
    """Tests for upgrade_subscription method"""
    
    def test_upgrade_subscription_success(
        self, subscription_service: SubscriptionService, test_user: User, test_plans: dict, db
    ):
        """Test successful subscription upgrade"""
        plus_plan = test_plans["plus"]
        pro_plan = test_plans["pro"]
        
        # Create initial subscription
        subscription_service.create_subscription(
            user_id=test_user.id,
            plan_id=plus_plan.id,
            billing_cycle=BillingCycle.MONTHLY,
        )
        
        # Upgrade to Pro
        result = subscription_service.upgrade_subscription(
            user_id=test_user.id,
            new_plan_id=pro_plan.id,
        )
        
        assert result["subscription"].plan_id == pro_plan.id
        assert result["subscription"].status == SubscriptionStatus.ACTIVE
        assert result["effective_immediately"] is True
        assert "proration_amount" in result
        
        # Verify audit log
        audit_log = db.query(AuditLog).filter(
            AuditLog.user_id == test_user.id,
            AuditLog.operation_type == AuditOperationType.UPDATE,
        ).first()
        assert audit_log is not None
        assert audit_log.details["action"] == "upgrade"
        assert audit_log.details["new_plan_type"] == PlanType.PRO.value
    
    def test_upgrade_subscription_proration_calculation(
        self, subscription_service: SubscriptionService, test_user: User, test_plans: dict
    ):
        """Test proration calculation on upgrade"""
        plus_plan = test_plans["plus"]
        pro_plan = test_plans["pro"]
        
        # Create subscription with specific dates
        now = datetime.utcnow()
        period_start = now - timedelta(days=10)
        period_end = now + timedelta(days=20)
        
        subscription = subscription_service.create_subscription(
            user_id=test_user.id,
            plan_id=plus_plan.id,
            billing_cycle=BillingCycle.MONTHLY,
            current_period_start=period_start,
            current_period_end=period_end,
        )
        
        # Upgrade
        result = subscription_service.upgrade_subscription(
            user_id=test_user.id,
            new_plan_id=pro_plan.id,
            prorate=True,
        )
        
        # Proration should be positive (charging more)
        assert result["proration_amount"] > Decimal("0.00")
    
    def test_upgrade_subscription_no_subscription(
        self, subscription_service: SubscriptionService, test_user: User, test_plans: dict
    ):
        """Test upgrade when user has no subscription"""
        pro_plan = test_plans["pro"]
        
        with pytest.raises(ValueError, match="No subscription found"):
            subscription_service.upgrade_subscription(
                user_id=test_user.id,
                new_plan_id=pro_plan.id,
            )
    
    def test_upgrade_subscription_not_higher_price(
        self, subscription_service: SubscriptionService, test_user: User, test_plans: dict
    ):
        """Test that upgrade requires higher price"""
        pro_plan = test_plans["pro"]
        plus_plan = test_plans["plus"]
        
        # Create Pro subscription
        subscription_service.create_subscription(
            user_id=test_user.id,
            plan_id=pro_plan.id,
            billing_cycle=BillingCycle.MONTHLY,
        )
        
        # Try to "upgrade" to Plus (lower price)
        with pytest.raises(ValueError, match="must be higher than current plan price"):
            subscription_service.upgrade_subscription(
                user_id=test_user.id,
                new_plan_id=plus_plan.id,
            )


class TestDowngradeSubscription:
    """Tests for downgrade_subscription method"""
    
    def test_downgrade_subscription_success(
        self, subscription_service: SubscriptionService, test_user: User, test_plans: dict, db
    ):
        """Test successful subscription downgrade"""
        pro_plan = test_plans["pro"]
        plus_plan = test_plans["plus"]
        
        # Create Pro subscription
        subscription_service.create_subscription(
            user_id=test_user.id,
            plan_id=pro_plan.id,
            billing_cycle=BillingCycle.MONTHLY,
        )
        
        # Downgrade to Plus
        result = subscription_service.downgrade_subscription(
            user_id=test_user.id,
            new_plan_id=plus_plan.id,
        )
        
        assert result["new_plan_id"] == plus_plan.id
        assert result["effective_immediately"] is False
        assert result["effective_date"] is not None
        
        # Verify audit log
        audit_log = db.query(AuditLog).filter(
            AuditLog.user_id == test_user.id,
            AuditLog.operation_type == AuditOperationType.UPDATE,
        ).first()
        assert audit_log is not None
        assert audit_log.details["action"] == "downgrade_scheduled"
    
    def test_downgrade_subscription_not_lower_price(
        self, subscription_service: SubscriptionService, test_user: User, test_plans: dict
    ):
        """Test that downgrade requires lower price"""
        plus_plan = test_plans["plus"]
        pro_plan = test_plans["pro"]
        
        # Create Plus subscription
        subscription_service.create_subscription(
            user_id=test_user.id,
            plan_id=plus_plan.id,
            billing_cycle=BillingCycle.MONTHLY,
        )
        
        # Try to "downgrade" to Pro (higher price)
        with pytest.raises(ValueError, match="must be lower than current plan price"):
            subscription_service.downgrade_subscription(
                user_id=test_user.id,
                new_plan_id=pro_plan.id,
            )


class TestCancelSubscription:
    """Tests for cancel_subscription method"""
    
    def test_cancel_subscription_at_period_end(
        self, subscription_service: SubscriptionService, test_user: User, test_plans: dict, db
    ):
        """Test canceling subscription at period end"""
        plan = test_plans["plus"]
        
        subscription_service.create_subscription(
            user_id=test_user.id,
            plan_id=plan.id,
        )
        
        result = subscription_service.cancel_subscription(
            user_id=test_user.id,
            immediate=False,
        )
        
        assert result["subscription"].cancel_at_period_end is True
        assert result["immediate"] is False
        assert result["access_until"] is not None
        
        # Verify audit log
        audit_log = db.query(AuditLog).filter(
            AuditLog.user_id == test_user.id,
            AuditLog.operation_type == AuditOperationType.UPDATE,
        ).first()
        assert audit_log is not None
        assert audit_log.details["action"] == "cancel"
    
    def test_cancel_subscription_immediately(
        self, subscription_service: SubscriptionService, test_user: User, test_plans: dict
    ):
        """Test immediate subscription cancellation"""
        plan = test_plans["plus"]
        
        subscription_service.create_subscription(
            user_id=test_user.id,
            plan_id=plan.id,
        )
        
        result = subscription_service.cancel_subscription(
            user_id=test_user.id,
            immediate=True,
        )
        
        assert result["subscription"].status == SubscriptionStatus.CANCELED
        assert result["subscription"].cancel_at_period_end is False
        assert result["immediate"] is True
    
    def test_cancel_already_canceled(
        self, subscription_service: SubscriptionService, test_user: User, test_plans: dict
    ):
        """Test canceling already canceled subscription"""
        plan = test_plans["plus"]
        
        subscription_service.create_subscription(
            user_id=test_user.id,
            plan_id=plan.id,
        )
        
        # Cancel once
        subscription_service.cancel_subscription(
            user_id=test_user.id,
            immediate=True,
        )
        
        # Try to cancel again
        with pytest.raises(ValueError, match="already canceled"):
            subscription_service.cancel_subscription(
                user_id=test_user.id,
            )


class TestReactivateSubscription:
    """Tests for reactivate_subscription method"""
    
    def test_reactivate_subscription_success(
        self, subscription_service: SubscriptionService, test_user: User, test_plans: dict, db
    ):
        """Test successful subscription reactivation"""
        plan = test_plans["plus"]
        
        subscription_service.create_subscription(
            user_id=test_user.id,
            plan_id=plan.id,
        )
        
        # Cancel subscription
        subscription_service.cancel_subscription(
            user_id=test_user.id,
            immediate=True,
        )
        
        # Reactivate
        subscription = subscription_service.reactivate_subscription(test_user.id)
        
        assert subscription.status == SubscriptionStatus.ACTIVE
        assert subscription.cancel_at_period_end is False
        
        # Verify audit log
        audit_log = db.query(AuditLog).filter(
            AuditLog.user_id == test_user.id,
            AuditLog.operation_type == AuditOperationType.UPDATE,
        ).order_by(AuditLog.created_at.desc()).first()
        assert audit_log is not None
        assert audit_log.details["action"] == "reactivate"
    
    def test_reactivate_scheduled_cancellation(
        self, subscription_service: SubscriptionService, test_user: User, test_plans: dict
    ):
        """Test reactivating subscription with scheduled cancellation"""
        plan = test_plans["plus"]
        
        subscription_service.create_subscription(
            user_id=test_user.id,
            plan_id=plan.id,
        )
        
        # Schedule cancellation
        subscription_service.cancel_subscription(
            user_id=test_user.id,
            immediate=False,
        )
        
        # Reactivate
        subscription = subscription_service.reactivate_subscription(test_user.id)
        
        assert subscription.status == SubscriptionStatus.ACTIVE
        assert subscription.cancel_at_period_end is False
    
    def test_reactivate_not_canceled(
        self, subscription_service: SubscriptionService, test_user: User, test_plans: dict
    ):
        """Test reactivating active subscription"""
        plan = test_plans["plus"]
        
        subscription_service.create_subscription(
            user_id=test_user.id,
            plan_id=plan.id,
        )
        
        with pytest.raises(ValueError, match="not canceled"):
            subscription_service.reactivate_subscription(test_user.id)


class TestCheckSubscriptionStatus:
    """Tests for check_subscription_status method"""
    
    def test_check_status_with_subscription(
        self, subscription_service: SubscriptionService, test_user: User, test_plans: dict
    ):
        """Test checking status with active subscription"""
        plan = test_plans["plus"]
        
        subscription_service.create_subscription(
            user_id=test_user.id,
            plan_id=plan.id,
        )
        
        status = subscription_service.check_subscription_status(test_user.id)
        
        assert status["has_subscription"] is True
        assert status["status"] == SubscriptionStatus.ACTIVE
        assert status["plan_type"] == PlanType.PLUS
        assert status["is_active"] is True
        assert status["is_expired"] is False
    
    def test_check_status_without_subscription(
        self, subscription_service: SubscriptionService, test_user: User
    ):
        """Test checking status without subscription"""
        status = subscription_service.check_subscription_status(test_user.id)
        
        assert status["has_subscription"] is False
        assert status["status"] is None
        assert status["plan_type"] == PlanType.FREE
        assert status["is_active"] is False


class TestHandleTrialExpiration:
    """Tests for handle_trial_expiration method"""
    
    def test_handle_trial_expiration_success(
        self, subscription_service: SubscriptionService, test_user: User, test_plans: dict, db
    ):
        """Test handling expired trial"""
        pro_plan = test_plans["pro"]
        
        # Create trial subscription that has expired
        now = datetime.utcnow()
        subscription_service.create_subscription(
            user_id=test_user.id,
            plan_id=pro_plan.id,
            status=SubscriptionStatus.TRIALING,
            current_period_start=now - timedelta(days=15),
            current_period_end=now - timedelta(days=1),
        )
        
        # Handle expiration
        subscription = subscription_service.handle_trial_expiration(test_user.id)
        
        assert subscription is not None
        assert subscription.plan.plan_type == PlanType.FREE
        assert subscription.status == SubscriptionStatus.ACTIVE
        
        # Verify audit log
        audit_log = db.query(AuditLog).filter(
            AuditLog.user_id == test_user.id,
            AuditLog.operation_type == AuditOperationType.UPDATE,
        ).first()
        assert audit_log is not None
        assert audit_log.details["action"] == "trial_expired"
    
    def test_handle_trial_not_expired(
        self, subscription_service: SubscriptionService, test_user: User, test_plans: dict
    ):
        """Test handling trial that hasn't expired"""
        pro_plan = test_plans["pro"]
        
        # Create trial subscription that hasn't expired
        now = datetime.utcnow()
        subscription_service.create_subscription(
            user_id=test_user.id,
            plan_id=pro_plan.id,
            status=SubscriptionStatus.TRIALING,
            current_period_start=now,
            current_period_end=now + timedelta(days=14),
        )
        
        # Try to handle expiration
        result = subscription_service.handle_trial_expiration(test_user.id)
        
        assert result is None
    
    def test_handle_trial_not_in_trial_status(
        self, subscription_service: SubscriptionService, test_user: User, test_plans: dict
    ):
        """Test handling non-trial subscription"""
        plan = test_plans["plus"]
        
        subscription_service.create_subscription(
            user_id=test_user.id,
            plan_id=plan.id,
            status=SubscriptionStatus.ACTIVE,
        )
        
        result = subscription_service.handle_trial_expiration(test_user.id)
        
        assert result is None
