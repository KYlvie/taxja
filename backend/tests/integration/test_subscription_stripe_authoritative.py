from datetime import datetime, timedelta
from decimal import Decimal

from app.api.v1.endpoints import subscriptions as subscriptions_endpoint
from app.core.config import settings
from app.models.plan import BillingCycle, Plan, PlanType
from app.models.subscription import Subscription, SubscriptionStatus
from app.services.stripe_payment_service import StripePaymentService


def _create_plan(db, plan_type: PlanType, monthly_price: str, yearly_price: str) -> Plan:
    plan = Plan(
        plan_type=plan_type,
        name=plan_type.value.title(),
        monthly_price=Decimal(monthly_price),
        yearly_price=Decimal(yearly_price),
        features={},
        quotas={},
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def _create_stripe_backed_subscription(db, user_id: int, plan_id: int) -> Subscription:
    subscription = Subscription(
        user_id=user_id,
        plan_id=plan_id,
        status=SubscriptionStatus.ACTIVE,
        billing_cycle=BillingCycle.MONTHLY,
        stripe_subscription_id="sub_test_123",
        stripe_customer_id="cus_test_123",
        current_period_start=datetime.utcnow(),
        current_period_end=datetime.utcnow() + timedelta(days=30),
        cancel_at_period_end=False,
    )
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    return subscription


def test_cancel_subscription_uses_stripe_for_stripe_backed_subscription(
    authenticated_client, db, test_user, monkeypatch
):
    plus_plan = _create_plan(db, PlanType.PLUS, "4.90", "49.00")
    subscription = _create_stripe_backed_subscription(db, test_user["id"], plus_plan.id)

    monkeypatch.setattr(subscriptions_endpoint, "_is_stripe_configured", lambda: True)

    def fake_schedule(self, user_id: int):
        assert user_id == test_user["id"]
        subscription.cancel_at_period_end = True
        db.commit()
        db.refresh(subscription)
        return subscription

    monkeypatch.setattr(
        StripePaymentService,
        "schedule_subscription_cancellation",
        fake_schedule,
    )

    response = authenticated_client.post("/api/v1/subscriptions/cancel")

    assert response.status_code == 200
    assert response.json()["cancel_at_period_end"] is True


def test_reactivate_subscription_uses_stripe_for_stripe_backed_subscription(
    authenticated_client, db, test_user, monkeypatch
):
    plus_plan = _create_plan(db, PlanType.PLUS, "4.90", "49.00")
    subscription = _create_stripe_backed_subscription(db, test_user["id"], plus_plan.id)
    subscription.cancel_at_period_end = True
    db.commit()
    db.refresh(subscription)

    monkeypatch.setattr(subscriptions_endpoint, "_is_stripe_configured", lambda: True)

    def fake_reactivate(self, user_id: int):
        assert user_id == test_user["id"]
        subscription.cancel_at_period_end = False
        db.commit()
        db.refresh(subscription)
        return subscription

    monkeypatch.setattr(
        StripePaymentService,
        "resume_scheduled_cancellation",
        fake_reactivate,
    )

    response = authenticated_client.post("/api/v1/subscriptions/reactivate")

    assert response.status_code == 200
    assert response.json()["cancel_at_period_end"] is False


def test_upgrade_subscription_uses_stripe_for_stripe_backed_subscription(
    authenticated_client, db, test_user, monkeypatch
):
    plus_plan = _create_plan(db, PlanType.PLUS, "4.90", "49.00")
    pro_plan = _create_plan(db, PlanType.PRO, "12.90", "129.00")
    subscription = _create_stripe_backed_subscription(db, test_user["id"], plus_plan.id)

    monkeypatch.setattr(subscriptions_endpoint, "_is_stripe_configured", lambda: True)

    def fake_switch(self, user_id: int, plan_id: int, billing_cycle: BillingCycle):
        assert user_id == test_user["id"]
        assert plan_id == pro_plan.id
        assert billing_cycle == BillingCycle.MONTHLY
        subscription.plan_id = pro_plan.id
        subscription.billing_cycle = BillingCycle.MONTHLY
        db.commit()
        db.refresh(subscription)
        return subscription

    monkeypatch.setattr(
        StripePaymentService,
        "switch_subscription_plan",
        fake_switch,
    )

    response = authenticated_client.post(
        "/api/v1/subscriptions/upgrade",
        params={"plan_id": pro_plan.id, "billing_cycle": "monthly"},
    )

    assert response.status_code == 200
    assert response.json()["plan_id"] == pro_plan.id


def test_customer_portal_defaults_to_configured_frontend_pricing_url(
    authenticated_client, db, test_user, monkeypatch
):
    plus_plan = _create_plan(db, PlanType.PLUS, "4.90", "49.00")
    _create_stripe_backed_subscription(db, test_user["id"], plus_plan.id)

    monkeypatch.setattr(subscriptions_endpoint, "_is_stripe_configured", lambda: True)
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://taxja.at")

    def fake_create_customer_portal_session(
        self,
        user_id: int,
        return_url: str,
        target_plan_id=None,
        billing_cycle=None,
    ):
        assert user_id == test_user["id"]
        assert return_url == "https://taxja.at/pricing"
        assert target_plan_id is None
        assert billing_cycle is None
        return {"url": "https://billing.stripe.com/session/test"}

    monkeypatch.setattr(
        StripePaymentService,
        "create_customer_portal_session",
        fake_create_customer_portal_session,
    )

    response = authenticated_client.post("/api/v1/subscriptions/customer-portal")

    assert response.status_code == 200
    assert response.json()["url"] == "https://billing.stripe.com/session/test"


def test_customer_portal_can_target_a_plan_switch(
    authenticated_client, db, test_user, monkeypatch
):
    plus_plan = _create_plan(db, PlanType.PLUS, "4.90", "49.00")
    pro_plan = _create_plan(db, PlanType.PRO, "12.90", "129.00")
    _create_stripe_backed_subscription(db, test_user["id"], plus_plan.id)

    monkeypatch.setattr(subscriptions_endpoint, "_is_stripe_configured", lambda: True)
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://taxja.at")

    def fake_create_customer_portal_session(
        self,
        user_id: int,
        return_url: str,
        target_plan_id=None,
        billing_cycle=None,
    ):
        assert user_id == test_user["id"]
        assert return_url == "https://taxja.at/pricing"
        assert target_plan_id == pro_plan.id
        assert billing_cycle == BillingCycle.YEARLY
        return {"url": "https://billing.stripe.com/session/upgrade"}

    monkeypatch.setattr(
        StripePaymentService,
        "create_customer_portal_session",
        fake_create_customer_portal_session,
    )

    response = authenticated_client.post(
        "/api/v1/subscriptions/customer-portal",
        params={"target_plan_id": pro_plan.id, "billing_cycle": "yearly"},
    )

    assert response.status_code == 200
    assert response.json()["url"] == "https://billing.stripe.com/session/upgrade"


def test_subscription_updated_webhook_syncs_plan_and_billing_cycle(db, test_user, monkeypatch):
    free_plan = _create_plan(db, PlanType.FREE, "0", "0")
    pro_plan = _create_plan(db, PlanType.PRO, "12.90", "129.00")
    subscription = Subscription(
        user_id=test_user["id"],
        plan_id=free_plan.id,
        status=SubscriptionStatus.ACTIVE,
        billing_cycle=BillingCycle.MONTHLY,
        stripe_subscription_id="sub_test_123",
        stripe_customer_id="cus_test_123",
        current_period_start=datetime.utcnow(),
        current_period_end=datetime.utcnow() + timedelta(days=30),
        cancel_at_period_end=False,
    )
    db.add(subscription)
    db.commit()
    db.refresh(subscription)

    monkeypatch.setattr(
        "app.services.stripe_payment_service.REVERSE_PRICE_MAP",
        {"price_pro_yearly": ("pro", "yearly")},
    )

    service = StripePaymentService(db)
    service._on_subscription_updated(
        {
            "data": {
                "object": {
                    "id": "sub_test_123",
                    "customer": "cus_test_123",
                    "status": "active",
                    "cancel_at_period_end": False,
                    "current_period_start": int(datetime.utcnow().timestamp()),
                    "current_period_end": int((datetime.utcnow() + timedelta(days=365)).timestamp()),
                    "items": {
                        "data": [
                            {
                                "price": {
                                    "id": "price_pro_yearly",
                                }
                            }
                        ]
                    },
                }
            }
        }
    )

    db.refresh(subscription)
    assert subscription.plan_id == pro_plan.id
    assert subscription.billing_cycle == BillingCycle.YEARLY
