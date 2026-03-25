from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

from app.models.plan import BillingCycle, Plan, PlanType
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.user import User
from app.services.stripe_payment_service import StripePaymentService


def _build_subscription(plan_type: PlanType, name: str) -> Subscription:
    plan = Plan(
        id=4 if plan_type == PlanType.PRO else 3,
        plan_type=plan_type,
        name=name,
        monthly_price=Decimal("12.90") if plan_type == PlanType.PRO else Decimal("4.90"),
        yearly_price=Decimal("129.00") if plan_type == PlanType.PRO else Decimal("49.00"),
    )
    return Subscription(
        id=18,
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


def _build_user() -> User:
    return User(
        id=46,
        email="fenghong.zhang@hotmail.com",
        name="Fenghong Zhang",
        password_hash="hashed",
        language="zh",
    )


def _query_returning(value):
    query = Mock()
    query.filter.return_value.first.return_value = value
    return query


def test_checkout_completed_sends_activation_email():
    db = Mock()
    service = StripePaymentService(db)
    subscription = _build_subscription(PlanType.PRO, "Pro")
    db.query.side_effect = [_query_returning(_build_user())]

    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_123",
                "metadata": {"user_id": "46", "plan_id": "4"},
            }
        },
    }

    with patch.object(
        service,
        "_activate_subscription_from_checkout_session",
        return_value=subscription,
    ):
        with patch("app.services.stripe_payment_service.send_subscription_activated_email") as send_email:
            result = service._on_checkout_completed(event)

    assert result == {"status": "processed", "action": "subscription_activated"}
    send_email.assert_called_once()
    assert send_email.call_args.kwargs["email"] == "fenghong.zhang@hotmail.com"
    assert send_email.call_args.kwargs["plan_name"] == "Pro"
    assert send_email.call_args.kwargs["language"] == "zh"


def test_invoice_paid_sends_renewal_email_for_subscription_cycle():
    db = Mock()
    service = StripePaymentService(db)
    subscription = _build_subscription(PlanType.PLUS, "Plus")
    db.query.side_effect = [
        _query_returning(subscription),
        _query_returning(_build_user()),
    ]

    event = {
        "type": "invoice.paid",
        "data": {
            "object": {
                "subscription": "sub_test_123",
                "billing_reason": "subscription_cycle",
                "amount_paid": 490,
                "currency": "eur",
                "hosted_invoice_url": "https://stripe.test/in_123",
            }
        },
    }

    with patch("app.services.stripe_payment_service.send_subscription_renewal_email") as send_email:
        result = service._on_payment_succeeded(event)

    assert result == {"status": "processed", "action": "payment_confirmed"}
    send_email.assert_called_once()
    assert send_email.call_args.kwargs["plan_name"] == "Plus"
    assert send_email.call_args.kwargs["amount_paid_cents"] == 490


def test_invoice_paid_does_not_send_renewal_email_for_initial_subscription_invoice():
    db = Mock()
    service = StripePaymentService(db)
    subscription = _build_subscription(PlanType.PRO, "Pro")
    db.query.side_effect = [_query_returning(subscription)]

    event = {
        "type": "invoice.paid",
        "data": {
            "object": {
                "subscription": "sub_test_123",
                "billing_reason": "subscription_create",
                "amount_paid": 1290,
                "currency": "eur",
            }
        },
    }

    with patch("app.services.stripe_payment_service.send_subscription_renewal_email") as send_email:
        result = service._on_payment_succeeded(event)

    assert result == {"status": "processed", "action": "payment_confirmed"}
    send_email.assert_not_called()


def test_invoice_payment_succeeded_does_not_send_duplicate_renewal_email():
    db = Mock()
    service = StripePaymentService(db)
    subscription = _build_subscription(PlanType.PRO, "Pro")
    db.query.side_effect = [_query_returning(subscription)]

    event = {
        "type": "invoice.payment_succeeded",
        "data": {
            "object": {
                "subscription": "sub_test_123",
                "billing_reason": "subscription_cycle",
                "amount_paid": 1290,
                "currency": "eur",
            }
        },
    }

    with patch("app.services.stripe_payment_service.send_subscription_renewal_email") as send_email:
        result = service._on_payment_succeeded(event)

    assert result == {"status": "processed", "action": "payment_confirmed"}
    send_email.assert_not_called()


def test_invoice_payment_failed_sends_failed_payment_email():
    db = Mock()
    service = StripePaymentService(db)
    subscription = _build_subscription(PlanType.PRO, "Pro")
    db.query.side_effect = [
        _query_returning(subscription),
        _query_returning(_build_user()),
    ]

    event = {
        "type": "invoice.payment_failed",
        "data": {
            "object": {
                "subscription": "sub_test_123",
                "amount_due": 1290,
                "currency": "eur",
                "hosted_invoice_url": "https://stripe.test/in_456",
            }
        },
    }

    with patch("app.services.stripe_payment_service.send_subscription_payment_failed_email") as send_email:
        result = service._on_payment_failed(event)

    assert result == {"status": "processed", "action": "payment_failed_grace_period"}
    assert subscription.status == SubscriptionStatus.PAST_DUE
    send_email.assert_called_once()
    assert send_email.call_args.kwargs["amount_due_cents"] == 1290
