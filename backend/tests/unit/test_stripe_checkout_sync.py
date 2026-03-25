from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest

from app.models.plan import BillingCycle, Plan, PlanType
from app.models.subscription import Subscription, SubscriptionStatus
from app.services.stripe_payment_service import StripePaymentService


def _subscription(plan: Plan) -> Subscription:
    return Subscription(
        id=11,
        user_id=46,
        plan_id=plan.id,
        plan=plan,
        status=SubscriptionStatus.ACTIVE,
        billing_cycle=BillingCycle.MONTHLY,
        stripe_subscription_id="sub_test_123",
        stripe_customer_id="cus_test_123",
        current_period_start=datetime.utcnow(),
        current_period_end=datetime.utcnow() + timedelta(days=30),
        cancel_at_period_end=False,
    )


def test_sync_checkout_session_activates_subscription_and_grants_initial_allowance():
    db = Mock()
    service = StripePaymentService(db)

    free_plan = Plan(
        id=2,
        plan_type=PlanType.FREE,
        name="Free",
        monthly_price=Decimal("0.00"),
        yearly_price=Decimal("0.00"),
    )
    pro_plan = Plan(
        id=4,
        plan_type=PlanType.PRO,
        name="Pro",
        monthly_price=Decimal("12.90"),
        yearly_price=Decimal("129.00"),
    )

    previous_subscription = _subscription(free_plan)
    synced_subscription = _subscription(pro_plan)

    session_payload = {
        "id": "cs_test_sync_123",
        "mode": "subscription",
        "status": "complete",
        "payment_status": "paid",
        "customer": "cus_test_123",
        "subscription": "sub_test_123",
        "metadata": {
            "user_id": "46",
            "plan_id": "4",
            "billing_cycle": "monthly",
        },
    }

    stripe_subscription = {
        "id": "sub_test_123",
        "customer": "cus_test_123",
        "status": "active",
        "cancel_at_period_end": False,
        "current_period_start": int(datetime.utcnow().timestamp()),
        "current_period_end": int((datetime.utcnow() + timedelta(days=30)).timestamp()),
        "items": {"data": [{"price": {"id": "price_pro_monthly"}}]},
    }

    with patch("app.services.stripe_payment_service.stripe.checkout.Session.retrieve", return_value=session_payload):
        with patch("app.services.stripe_payment_service.stripe.Subscription.retrieve", return_value=stripe_subscription):
            with patch.object(service, "_get_subscription", return_value=previous_subscription):
                with patch.object(service, "_sync_local_subscription_from_stripe", return_value=synced_subscription):
                    with patch("app.services.credit_service.CreditService.grant_plan_allowance_for_activation") as grant_allowance:
                        result = service.sync_checkout_session("cs_test_sync_123", user_id=46)

    assert result is synced_subscription
    grant_allowance.assert_called_once()
    assert grant_allowance.call_args.kwargs["user_id"] == 46


def test_sync_checkout_session_rejects_foreign_checkout_session():
    db = Mock()
    service = StripePaymentService(db)

    session_payload = {
        "id": "cs_test_sync_456",
        "mode": "subscription",
        "status": "complete",
        "payment_status": "paid",
        "metadata": {
            "user_id": "99",
            "plan_id": "4",
            "billing_cycle": "monthly",
        },
    }

    with patch("app.services.stripe_payment_service.stripe.checkout.Session.retrieve", return_value=session_payload):
        with pytest.raises(ValueError, match="does not belong"):
            service.sync_checkout_session("cs_test_sync_456", user_id=46)
