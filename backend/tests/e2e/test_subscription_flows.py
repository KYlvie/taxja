"""
E2E-style tests for subscription and usage flows.

These tests are aligned to the current API contracts:
- subscription endpoints require authenticated users
- checkout uses plan_id/billing_cycle/success_url/cancel_url
- usage endpoints remain deprecated read-only compatibility surfaces
- admin endpoints require admin auth and use query parameters
"""

import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import Mock, patch

from app.main import app
from app.api.deps import get_current_admin, get_current_user as api_get_current_user, get_db
from app.core.security import get_current_user as core_get_current_user
from app.models.user import User, UserType
from app.models.plan import BillingCycle, Plan
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.usage_record import ResourceType


@pytest.fixture
def db_session():
    """Mock database session."""
    return Mock(spec=Session)


@pytest.fixture
def client(db_session):
    """Create test client with mocked DB only."""
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def authenticated_user():
    """Authenticated regular user for endpoint tests."""
    return User(
        id=1,
        email="test@example.com",
        name="Test User",
        user_type=UserType.SELF_EMPLOYED,
        is_admin=False,
    )


@pytest.fixture
def admin_user():
    """Authenticated admin user for admin endpoint tests."""
    return User(
        id=999,
        email="admin@example.com",
        name="Admin User",
        user_type=UserType.SELF_EMPLOYED,
        is_admin=True,
    )


@pytest.fixture
def authenticated_client(db_session, authenticated_user):
    """Create test client with authenticated user + mocked DB."""
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[api_get_current_user] = lambda: authenticated_user
    app.dependency_overrides[core_get_current_user] = lambda: authenticated_user
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def admin_client(db_session, admin_user):
    """Create test client with authenticated admin + mocked DB."""
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[api_get_current_user] = lambda: admin_user
    app.dependency_overrides[core_get_current_user] = lambda: admin_user
    app.dependency_overrides[get_current_admin] = lambda: admin_user
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def plus_plan():
    """Create Plus plan."""
    return Plan(
        id=2,
        plan_type="plus",
        name="Plus",
        monthly_price=4.90,
        yearly_price=49.00,
        features={"basic_tax_calc": True, "full_tax_calc": True, "ocr": True},
        quotas={"transactions": -1, "ocr_scans": 20},
    )


@pytest.fixture
def pro_plan():
    """Create Pro plan."""
    return Plan(
        id=3,
        plan_type="pro",
        name="Pro",
        monthly_price=9.90,
        yearly_price=99.00,
        features={
            "basic_tax_calc": True,
            "full_tax_calc": True,
            "ocr": True,
            "ai_assistant": True,
            "e1_generation": True,
        },
        quotas={"transactions": -1, "ocr_scans": -1, "ai_conversations": -1},
    )


def build_subscription(**overrides) -> Subscription:
    """Construct a subscription object with response-safe defaults."""
    now = datetime.utcnow()
    base = {
        "id": 1,
        "user_id": 1,
        "plan_id": 2,
        "status": SubscriptionStatus.ACTIVE,
        "billing_cycle": BillingCycle.MONTHLY,
        "current_period_start": now,
        "current_period_end": now + timedelta(days=30),
        "cancel_at_period_end": False,
        "created_at": now,
        "updated_at": now,
    }
    base.update(overrides)
    return Subscription(**base)


class TestUserSignupTrialUpgradeFlow:
    """Test complete user journey from trial through checkout and webhook."""

    @patch("app.services.stripe_payment_service.StripePaymentService")
    def test_new_user_gets_trial_and_upgrades(
        self,
        mock_stripe_service,
        authenticated_client,
        db_session,
        pro_plan,
    ):
        """New user receives trial access, checks out, and webhook completes."""
        user = User(
            id=1,
            email="newuser@example.com",
            trial_used=False,
            trial_end_date=None,
        )
        trial_end = datetime.utcnow() + timedelta(days=14)
        trial_sub = build_subscription(
            id=1,
            user_id=user.id,
            plan_id=pro_plan.id,
            status=SubscriptionStatus.TRIALING,
            current_period_end=trial_end,
        )

        assert trial_sub.status == SubscriptionStatus.TRIALING
        assert trial_sub.plan_id == pro_plan.id

        db_session.query.return_value.filter.return_value.first.return_value = pro_plan
        mock_stripe_service.return_value.create_checkout_session.return_value = {
            "session_id": "cs_test_123",
            "url": "https://checkout.stripe.com/pay/cs_test_123",
        }

        with patch("app.api.v1.endpoints.subscriptions._is_stripe_configured", return_value=True):
            checkout_response = authenticated_client.post(
                "/api/v1/subscriptions/checkout",
                json={
                    "plan_id": pro_plan.id,
                    "billing_cycle": "monthly",
                    "success_url": "http://localhost:5173/billing/success",
                    "cancel_url": "http://localhost:5173/billing/cancel",
                },
            )

        assert checkout_response.status_code == 200
        assert checkout_response.json()["session_id"] == "cs_test_123"
        assert "url" in checkout_response.json()

        webhook_payload = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "customer": "cus_123",
                    "subscription": "sub_123",
                    "metadata": {"user_id": "1", "plan_type": "plus"},
                }
            },
        }

        with patch("app.api.v1.endpoints.webhooks.StripePaymentService") as webhook_stripe:
            webhook_stripe.return_value.handle_webhook_event.return_value = {
                "event_type": "checkout.session.completed",
                "status": "processed",
            }
            webhook_response = authenticated_client.post(
                "/api/v1/webhooks/stripe",
                json=webhook_payload,
                headers={"Stripe-Signature": "test_sig"},
            )

        assert webhook_response.status_code == 200
        webhook_stripe.return_value.handle_webhook_event.assert_called_once()


class TestUsageCompatibilityFlow:
    """Test legacy usage surfaces after credit cutover."""

    @patch("app.api.v1.endpoints.usage.UsageTrackerService")
    def test_usage_summary_is_read_only_compatibility(
        self,
        mock_usage_tracker,
        authenticated_client,
    ):
        """Usage summary remains available as deprecated read-only compatibility data."""
        mock_usage_tracker.return_value.get_usage_summary.return_value = {
            "transactions": {
                "current": 50,
                "limit": 50,
                "percentage": 100,
                "is_warning": True,
                "is_exceeded": True,
            }
        }

        response = authenticated_client.get("/api/v1/usage/summary")

        assert response.status_code == 200
        assert response.headers["X-Usage-Compatibility"] == "read-only"
        assert "transactions:50/50" in response.headers["X-Quota-Warning"]
        assert response.json()["transactions"]["is_exceeded"] is True

    @patch("app.api.v1.endpoints.usage.UsageTrackerService")
    def test_resource_usage_endpoint_returns_warning_headers(
        self,
        mock_usage_tracker,
        authenticated_client,
    ):
        """Per-resource usage endpoint still exposes compatibility headers."""
        now = datetime.utcnow()
        mock_usage_tracker.return_value.get_current_usage.return_value = {
            "resource_type": ResourceType.TRANSACTIONS,
            "current_usage": 40,
            "quota_limit": 50,
            "usage_percentage": 80,
            "is_exceeded": False,
            "is_near_limit": True,
            "period_start": now,
            "period_end": now + timedelta(days=30),
            "current": 40,
            "limit": 50,
            "percentage": 80,
            "is_warning": True,
            "reset_date": None,
        }

        response = authenticated_client.get("/api/v1/usage/transactions")

        assert response.status_code == 200
        assert response.headers["X-Usage-Compatibility"] == "read-only"
        assert "transactions:40/50" in response.headers["X-Quota-Warning"]
        assert response.json()["usage_percentage"] >= 80


class TestSubscriptionCancellationFlow:
    """Test subscription cancellation and reactivation."""

    @patch("app.api.v1.endpoints.subscriptions.SubscriptionService")
    def test_user_cancels_and_reactivates_subscription(
        self,
        mock_subscription_service,
        authenticated_client,
        plus_plan,
    ):
        """Authenticated user can cancel and reactivate an active subscription."""
        user_id = 1
        period_end = datetime.utcnow() + timedelta(days=15)
        subscription = build_subscription(
            id=1,
            user_id=user_id,
            plan_id=plus_plan.id,
            status=SubscriptionStatus.ACTIVE,
            stripe_subscription_id="sub_123",
            current_period_end=period_end,
            cancel_at_period_end=False,
        )

        service_instance = mock_subscription_service.return_value
        service_instance.get_user_subscription.return_value = subscription
        service_instance.cancel_subscription.return_value = {
            "subscription": build_subscription(
                id=subscription.id,
                user_id=subscription.user_id,
                plan_id=subscription.plan_id,
                status=SubscriptionStatus.ACTIVE,
                stripe_subscription_id=subscription.stripe_subscription_id,
                current_period_end=period_end,
                cancel_at_period_end=True,
            )
        }
        service_instance.reactivate_subscription.return_value = build_subscription(
            id=subscription.id,
            user_id=subscription.user_id,
            plan_id=subscription.plan_id,
            status=SubscriptionStatus.ACTIVE,
            stripe_subscription_id=subscription.stripe_subscription_id,
            current_period_end=period_end,
            cancel_at_period_end=False,
        )

        cancel_response = authenticated_client.post("/api/v1/subscriptions/cancel")
        assert cancel_response.status_code == 200
        assert cancel_response.json()["cancel_at_period_end"] is True
        assert cancel_response.json()["status"] == "active"

        reactivate_response = authenticated_client.post("/api/v1/subscriptions/reactivate")
        assert reactivate_response.status_code == 200
        assert reactivate_response.json()["cancel_at_period_end"] is False


class TestAdminSubscriptionManagement:
    """Test admin operations on user subscriptions."""

    @patch("app.api.v1.endpoints.admin.SubscriptionService")
    def test_admin_grants_trial_and_changes_plan(
        self,
        mock_subscription_service,
        admin_client,
        db_session,
        pro_plan,
        plus_plan,
    ):
        """Admin grants a trial, changes a plan, and extends the period."""
        user_id = 1
        managed_user = User(
            id=user_id,
            email="managed@example.com",
            name="Managed User",
            user_type=UserType.SELF_EMPLOYED,
            trial_used=False,
            is_admin=False,
        )
        existing_subscription = build_subscription(
            id=2,
            user_id=user_id,
            plan_id=pro_plan.id,
            status=SubscriptionStatus.TRIALING,
        )
        extendable_subscription = build_subscription(
            id=3,
            user_id=user_id,
            plan_id=plus_plan.id,
            status=SubscriptionStatus.ACTIVE,
            current_period_end=datetime.utcnow() + timedelta(days=30),
        )

        db_session.query.return_value.filter.return_value.first.side_effect = [
            managed_user,           # grant-trial -> user
            pro_plan,               # grant-trial -> pro plan
            None,                   # grant-trial -> existing subscription
            managed_user,           # change-plan -> user
            plus_plan,              # change-plan -> plus plan
            extendable_subscription,  # extend -> subscription
        ]
        mock_subscription_service.return_value.get_user_subscription.return_value = existing_subscription

        grant_response = admin_client.post(
            f"/api/v1/admin/subscriptions/{user_id}/grant-trial"
        )
        assert grant_response.status_code == 200
        assert "trial_end_date" in grant_response.json()

        change_response = admin_client.put(
            f"/api/v1/admin/subscriptions/{user_id}/change-plan?plan_type=plus"
        )
        assert change_response.status_code == 200
        assert change_response.json()["subscription"]["plan_id"] == plus_plan.id

        previous_end = extendable_subscription.current_period_end
        extend_response = admin_client.post(
            f"/api/v1/admin/subscriptions/{user_id}/extend?days=30"
        )
        assert extend_response.status_code == 200
        assert extend_response.json()["new_end_date"] is not None
        assert extendable_subscription.current_period_end == previous_end + timedelta(days=30)


class TestWebhookIdempotencyAndConcurrency:
    """Test webhook delivery and concurrent subscription actions."""

    @patch("app.api.v1.endpoints.webhooks.StripePaymentService")
    def test_duplicate_webhook_events_are_accepted(
        self,
        mock_stripe_service,
        client,
    ):
        """Duplicate Stripe deliveries still produce successful responses."""
        event_id = "evt_test_123"
        webhook_payload = {
            "id": event_id,
            "type": "invoice.payment_succeeded",
            "data": {
                "object": {
                    "customer": "cus_123",
                    "subscription": "sub_123",
                    "amount_paid": 490,
                }
            },
        }

        mock_stripe_service.return_value.handle_webhook_event.side_effect = [
            {"status": "processed", "event_id": event_id},
            {"status": "duplicate_ignored", "event_id": event_id},
        ]

        response1 = client.post(
            "/api/v1/webhooks/stripe",
            json=webhook_payload,
            headers={"Stripe-Signature": "test_sig"},
        )
        response2 = client.post(
            "/api/v1/webhooks/stripe",
            json=webhook_payload,
            headers={"Stripe-Signature": "test_sig"},
        )

        assert response1.status_code == 200
        assert response2.status_code == 200
        assert mock_stripe_service.return_value.handle_webhook_event.call_count == 2

    @patch("app.api.v1.endpoints.subscriptions.FeatureGateService")
    @patch("app.api.v1.endpoints.subscriptions.SubscriptionService")
    def test_concurrent_subscription_changes(
        self,
        mock_subscription_service,
        mock_feature_gate_service,
        authenticated_client,
    ):
        """Concurrent upgrade path returns a consistent subscription response."""
        subscription = build_subscription(
            id=1,
            user_id=1,
            plan_id=3,
            status=SubscriptionStatus.ACTIVE,
            billing_cycle=BillingCycle.MONTHLY,
        )
        mock_subscription_service.return_value.get_user_subscription.return_value = subscription
        mock_subscription_service.return_value.upgrade_subscription.return_value = {
            "subscription": subscription
        }

        upgrade_response = authenticated_client.post(
            "/api/v1/subscriptions/upgrade?plan_id=3&billing_cycle=monthly"
        )

        assert upgrade_response.status_code == 200
        assert upgrade_response.json()["plan_id"] == 3
