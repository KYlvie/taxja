"""Simple unit tests for model methods without database"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal


def test_plan_model_methods():
    """Test Plan model methods work correctly"""
    from app.models.plan import Plan, PlanType
    
    # Create a plan instance (not saved to DB)
    plan = Plan()
    plan.plan_type = PlanType.FREE
    plan.name = "Free Plan"
    plan.monthly_price = Decimal("0.00")
    plan.yearly_price = Decimal("0.00")
    plan.features = {"basic_tax_calc": True}
    plan.quotas = {"transactions": 50}
    
    # Test has_feature
    assert plan.has_feature("basic_tax_calc") is True
    assert plan.has_feature("ai_assistant") is False
    
    # Test get_quota
    assert plan.get_quota("transactions") == 50
    assert plan.get_quota("non_existing") == 0
    
    # Test is_unlimited
    assert plan.is_unlimited("transactions") is False
    
    # Test with unlimited quota
    plan.quotas = {"transactions": -1}
    assert plan.is_unlimited("transactions") is True
    assert plan.get_quota("transactions") == -1


def test_subscription_model_methods():
    """Test Subscription model methods work correctly"""
    from app.models.subscription import Subscription, SubscriptionStatus
    from app.models.plan import BillingCycle
    
    # Create a subscription instance (not saved to DB)
    now = datetime.utcnow()
    subscription = Subscription()
    subscription.user_id = 1
    subscription.plan_id = 1
    subscription.status = SubscriptionStatus.ACTIVE
    subscription.billing_cycle = BillingCycle.MONTHLY
    subscription.current_period_start = now
    subscription.current_period_end = now + timedelta(days=30)
    
    # Test is_active
    assert subscription.is_active() is True
    
    # Test is_trialing
    assert subscription.is_trialing() is False
    subscription.status = SubscriptionStatus.TRIALING
    assert subscription.is_trialing() is True
    
    # Test is_expired
    subscription.status = SubscriptionStatus.ACTIVE
    assert subscription.is_expired() is False
    
    # Test days_until_renewal
    days = subscription.days_until_renewal()
    assert 29 <= days <= 30  # Allow for timing differences


def test_usage_record_model_methods():
    """Test UsageRecord model methods work correctly"""
    from app.models.usage_record import UsageRecord, ResourceType
    
    # Create a usage record instance (not saved to DB)
    now = datetime.utcnow()
    usage = UsageRecord()
    usage.user_id = 1
    usage.resource_type = ResourceType.TRANSACTIONS
    usage.count = 25
    usage.period_start = now
    usage.period_end = now + timedelta(days=30)
    
    # Test increment
    new_count = usage.increment()
    assert new_count == 26
    assert usage.count == 26
    
    # Test increment with custom amount
    new_count = usage.increment(5)
    assert new_count == 31
    
    # Test get_usage_percentage
    percentage = usage.get_usage_percentage(50)
    assert percentage == 62.0  # 31/50 * 100
    
    # Test is_quota_exceeded
    assert usage.is_quota_exceeded(50) is False
    assert usage.is_quota_exceeded(30) is True
    
    # Test is_near_quota_limit
    usage.count = 40
    assert usage.is_near_quota_limit(50) is True  # 80%
    usage.count = 35
    assert usage.is_near_quota_limit(50) is False  # 70%
    
    # Test is_current_period
    assert usage.is_current_period() is True


def test_payment_event_model_methods():
    """Test PaymentEvent model methods work correctly"""
    from app.models.payment_event import PaymentEvent
    
    # Create a payment event instance (not saved to DB)
    event = PaymentEvent()
    event.stripe_event_id = "evt_test_123"
    event.event_type = "checkout.session.completed"
    event.payload = {
        "data": {
            "object": {
                "customer": "cus_test_123",
                "subscription": "sub_test_456"
            }
        }
    }
    
    # Test get_event_data
    assert event.get_event_data("data") is not None
    assert event.get_event_data("missing_key") is None
    assert event.get_event_data("missing_key", "default") == "default"
    
    # Test get_customer_id
    assert event.get_customer_id() == "cus_test_123"
    
    # Test get_subscription_id
    assert event.get_subscription_id() == "sub_test_456"


if __name__ == "__main__":
    test_plan_model_methods()
    test_subscription_model_methods()
    test_usage_record_model_methods()
    test_payment_event_model_methods()
    print("All simple model tests passed!")
