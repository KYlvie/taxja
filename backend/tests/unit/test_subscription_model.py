"""Unit tests for Subscription model"""
import pytest
from datetime import datetime, timedelta
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.plan import BillingCycle


class TestSubscriptionModel:
    """Test Subscription model methods"""
    
    def test_subscription_creation(self):
        """Test creating a subscription"""
        now = datetime.utcnow()
        subscription = Subscription(
            user_id=1,
            plan_id=1,
            status=SubscriptionStatus.ACTIVE,
            billing_cycle=BillingCycle.MONTHLY,
            current_period_start=now,
            current_period_end=now + timedelta(days=30)
        )
        
        assert subscription.user_id == 1
        assert subscription.plan_id == 1
        assert subscription.status == SubscriptionStatus.ACTIVE
        assert subscription.billing_cycle == BillingCycle.MONTHLY
    
    def test_is_active_true(self):
        """Test is_active returns True for active subscription"""
        now = datetime.utcnow()
        subscription = Subscription(
            user_id=1,
            plan_id=1,
            status=SubscriptionStatus.ACTIVE,
            billing_cycle=BillingCycle.MONTHLY,
            current_period_start=now,
            current_period_end=now + timedelta(days=30)
        )
        
        assert subscription.is_active() is True
    
    def test_is_active_false_canceled(self):
        """Test is_active returns False for canceled subscription"""
        now = datetime.utcnow()
        subscription = Subscription(
            user_id=1,
            plan_id=1,
            status=SubscriptionStatus.CANCELED,
            billing_cycle=BillingCycle.MONTHLY,
            current_period_start=now - timedelta(days=30),
            current_period_end=now - timedelta(days=1)
        )
        
        assert subscription.is_active() is False
    
    def test_is_active_false_past_due(self):
        """Test is_active returns False for past_due subscription"""
        now = datetime.utcnow()
        subscription = Subscription(
            user_id=1,
            plan_id=1,
            status=SubscriptionStatus.PAST_DUE,
            billing_cycle=BillingCycle.MONTHLY,
            current_period_start=now - timedelta(days=30),
            current_period_end=now - timedelta(days=1)
        )
        
        assert subscription.is_active() is False
    
    def test_is_trialing_true(self):
        """Test is_trialing returns True for trialing subscription"""
        now = datetime.utcnow()
        subscription = Subscription(
            user_id=1,
            plan_id=1,
            status=SubscriptionStatus.TRIALING,
            billing_cycle=BillingCycle.MONTHLY,
            current_period_start=now,
            current_period_end=now + timedelta(days=14)
        )
        
        assert subscription.is_trialing() is True
    
    def test_is_trialing_false(self):
        """Test is_trialing returns False for non-trialing subscription"""
        now = datetime.utcnow()
        subscription = Subscription(
            user_id=1,
            plan_id=1,
            status=SubscriptionStatus.ACTIVE,
            billing_cycle=BillingCycle.MONTHLY,
            current_period_start=now,
            current_period_end=now + timedelta(days=30)
        )
        
        assert subscription.is_trialing() is False
    
    def test_is_expired_true(self):
        """Test is_expired returns True for expired subscription"""
        now = datetime.utcnow()
        subscription = Subscription(
            user_id=1,
            plan_id=1,
            status=SubscriptionStatus.CANCELED,
            billing_cycle=BillingCycle.MONTHLY,
            current_period_start=now - timedelta(days=60),
            current_period_end=now - timedelta(days=30)
        )
        
        assert subscription.is_expired() is True
    
    def test_is_expired_false(self):
        """Test is_expired returns False for active subscription"""
        now = datetime.utcnow()
        subscription = Subscription(
            user_id=1,
            plan_id=1,
            status=SubscriptionStatus.ACTIVE,
            billing_cycle=BillingCycle.MONTHLY,
            current_period_start=now,
            current_period_end=now + timedelta(days=30)
        )
        
        assert subscription.is_expired() is False
    
    def test_days_until_renewal(self):
        """Test days_until_renewal calculation"""
        now = datetime.utcnow()
        subscription = Subscription(
            user_id=1,
            plan_id=1,
            status=SubscriptionStatus.ACTIVE,
            billing_cycle=BillingCycle.MONTHLY,
            current_period_start=now,
            current_period_end=now + timedelta(days=15)
        )
        
        days = subscription.days_until_renewal()
        assert 14 <= days <= 15  # Allow for timing differences
    
    def test_cancel_at_period_end(self):
        """Test cancel_at_period_end flag"""
        now = datetime.utcnow()
        subscription = Subscription(
            user_id=1,
            plan_id=1,
            status=SubscriptionStatus.ACTIVE,
            billing_cycle=BillingCycle.MONTHLY,
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            cancel_at_period_end=True
        )
        
        assert subscription.cancel_at_period_end is True
        assert subscription.is_active() is True  # Still active until period end
    
    def test_status_transitions(self):
        """Test subscription status transitions"""
        now = datetime.utcnow()
        subscription = Subscription(
            user_id=1,
            plan_id=1,
            status=SubscriptionStatus.TRIALING,
            billing_cycle=BillingCycle.MONTHLY,
            current_period_start=now,
            current_period_end=now + timedelta(days=14)
        )
        
        # Trial to Active
        subscription.status = SubscriptionStatus.ACTIVE
        assert subscription.status == SubscriptionStatus.ACTIVE
        
        # Active to Past Due
        subscription.status = SubscriptionStatus.PAST_DUE
        assert subscription.status == SubscriptionStatus.PAST_DUE
        
        # Past Due to Canceled
        subscription.status = SubscriptionStatus.CANCELED
        assert subscription.status == SubscriptionStatus.CANCELED
