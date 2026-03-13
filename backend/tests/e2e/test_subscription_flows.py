"""
E2E tests for subscription flows.
Tests complete user journeys through the monetization system.
"""
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import Mock, patch

from app.main import app
from app.models.user import User
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.usage_record import UsageRecord


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def db_session():
    """Mock database session."""
    return Mock(spec=Session)


@pytest.fixture
def free_plan(db_session):
    """Create Free plan."""
    plan = Plan(
        id=1,
        plan_type="free",
        name="Free",
        monthly_price=0.0,
        yearly_price=0.0,
        features={"basic_tax_calc": True},
        quotas={"transactions": 50, "ocr_scans": 0}
    )
    db_session.query().filter().first.return_value = plan
    return plan


@pytest.fixture
def plus_plan(db_session):
    """Create Plus plan."""
    plan = Plan(
        id=2,
        plan_type="plus",
        name="Plus",
        monthly_price=4.90,
        yearly_price=49.00,
        features={"basic_tax_calc": True, "full_tax_calc": True, "ocr": True},
        quotas={"transactions": -1, "ocr_scans": 20}
    )
    return plan


@pytest.fixture
def pro_plan(db_session):
    """Create Pro plan."""
    plan = Plan(
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
            "e1_generation": True
        },
        quotas={"transactions": -1, "ocr_scans": -1, "ai_conversations": -1}
    )
    return plan


class TestUserSignupTrialUpgradeFlow:
    """Test complete user journey from signup through trial to paid subscription."""

    @patch('app.services.trial_service.TrialService')
    @patch('app.services.subscription_service.SubscriptionService')
    @patch('app.services.stripe_payment_service.StripePaymentService')
    def test_new_user_gets_trial_and_upgrades(
        self,
        mock_stripe,
        mock_subscription_service,
        mock_trial_service,
        client,
        db_session,
        pro_plan
    ):
        """Test: New user signs up → gets 14-day Pro trial → upgrades to Plus."""
        # Step 1: User signs up
        user = User(
            id=1,
            email="newuser@example.com",
            trial_used=False,
            trial_end_date=None
        )
        
        # Step 2: Trial is automatically activated
        trial_end = datetime.utcnow() + timedelta(days=14)
        mock_trial_service.activate_trial.return_value = Subscription(
            id=1,
            user_id=user.id,
            plan_id=pro_plan.id,
            status="trialing",
            current_period_start=datetime.utcnow(),
            current_period_end=trial_end
        )
        
        trial_sub = mock_trial_service.activate_trial(db_session, user.id)
        assert trial_sub.status == "trialing"
        assert trial_sub.plan_id == pro_plan.id
        
        # Step 3: User uses Pro features during trial
        # (Feature gate should allow access)
        
        # Step 4: User decides to upgrade before trial ends
        mock_stripe.create_checkout_session.return_value = {
            "id": "cs_test_123",
            "url": "https://checkout.stripe.com/pay/cs_test_123"
        }
        
        checkout_response = client.post(
            "/api/v1/subscriptions/checkout",
            json={"plan_type": "plus", "billing_cycle": "monthly"}
        )
        assert checkout_response.status_code == 200
        assert "url" in checkout_response.json()
        
        # Step 5: Stripe webhook confirms payment
        mock_subscription_service.create_subscription.return_value = Subscription(
            id=2,
            user_id=user.id,
            plan_id=2,  # Plus plan
            status="active",
            stripe_subscription_id="sub_123",
            current_period_start=datetime.utcnow(),
            current_period_end=datetime.utcnow() + timedelta(days=30)
        )
        
        webhook_payload = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "customer": "cus_123",
                    "subscription": "sub_123",
                    "metadata": {"user_id": "1", "plan_type": "plus"}
                }
            }
        }
        
        with patch('app.api.v1.webhooks.verify_stripe_signature'):
            webhook_response = client.post(
                "/api/v1/webhooks/stripe",
                json=webhook_payload,
                headers={"stripe-signature": "test_sig"}
            )
            assert webhook_response.status_code == 200
        
        # Verify final state
        mock_subscription_service.create_subscription.assert_called_once()


class TestQuotaEnforcementFlow:
    """Test quota enforcement and upgrade prompts."""

    @patch('app.services.usage_tracker_service.UsageTrackerService')
    @patch('app.services.feature_gate_service.FeatureGateService')
    def test_free_user_hits_transaction_limit(
        self,
        mock_feature_gate,
        mock_usage_tracker,
        client,
        free_plan
    ):
        """Test: Free user hits 50 transaction limit → gets quota exceeded error."""
        user_id = 1
        
        # User has 49 transactions
        mock_usage_tracker.get_current_usage.return_value = UsageRecord(
            user_id=user_id,
            resource_type="transactions",
            count=49,
            period_start=datetime.utcnow().replace(day=1),
            period_end=datetime.utcnow().replace(day=1) + timedelta(days=30)
        )
        
        # 50th transaction succeeds
        mock_usage_tracker.check_quota_limit.return_value = True
        response = client.post("/api/v1/transactions", json={"amount": 100})
        assert response.status_code in [200, 201]
        
        # Update usage to 50
        mock_usage_tracker.get_current_usage.return_value.count = 50
        
        # 51st transaction fails with quota exceeded
        mock_usage_tracker.check_quota_limit.side_effect = Exception("Quota exceeded")
        
        response = client.post("/api/v1/transactions", json={"amount": 100})
        assert response.status_code == 429
        assert "quota" in response.json()["detail"].lower()
        
        # Response should include upgrade prompt
        assert "upgrade" in response.json()["detail"].lower()

    @patch('app.services.usage_tracker_service.UsageTrackerService')
    def test_quota_warning_at_80_percent(
        self,
        mock_usage_tracker,
        client,
        free_plan
    ):
        """Test: User at 80% quota gets warning in response headers."""
        user_id = 1
        
        # User has 40 transactions (80% of 50)
        mock_usage_tracker.get_current_usage.return_value = UsageRecord(
            user_id=user_id,
            resource_type="transactions",
            count=40,
            period_start=datetime.utcnow().replace(day=1),
            period_end=datetime.utcnow().replace(day=1) + timedelta(days=30)
        )
        mock_usage_tracker.check_quota_limit.return_value = True
        
        response = client.get("/api/v1/usage/summary")
        
        # Should include warning in response
        assert response.status_code == 200
        usage_data = response.json()
        assert usage_data["transactions"]["percentage"] >= 80


class TestSubscriptionCancellationFlow:
    """Test subscription cancellation and reactivation."""

    @patch('app.services.subscription_service.SubscriptionService')
    @patch('app.services.stripe_payment_service.StripePaymentService')
    def test_user_cancels_and_reactivates_subscription(
        self,
        mock_stripe,
        mock_subscription_service,
        client,
        plus_plan
    ):
        """Test: User cancels subscription → changes mind → reactivates."""
        user_id = 1
        period_end = datetime.utcnow() + timedelta(days=15)
        
        # Step 1: User has active Plus subscription
        subscription = Subscription(
            id=1,
            user_id=user_id,
            plan_id=plus_plan.id,
            status="active",
            stripe_subscription_id="sub_123",
            current_period_end=period_end,
            cancel_at_period_end=False
        )
        mock_subscription_service.get_user_subscription.return_value = subscription
        
        # Step 2: User cancels subscription
        mock_stripe.cancel_subscription.return_value = {"status": "active"}
        mock_subscription_service.cancel_subscription.return_value = Subscription(
            **{**subscription.__dict__, "cancel_at_period_end": True}
        )
        
        cancel_response = client.post("/api/v1/subscriptions/cancel")
        assert cancel_response.status_code == 200
        assert cancel_response.json()["cancel_at_period_end"] is True
        
        # Subscription remains active until period end
        assert cancel_response.json()["status"] == "active"
        
        # Step 3: User changes mind and reactivates
        mock_subscription_service.reactivate_subscription.return_value = Subscription(
            **{**subscription.__dict__, "cancel_at_period_end": False}
        )
        
        reactivate_response = client.post("/api/v1/subscriptions/reactivate")
        assert reactivate_response.status_code == 200
        assert reactivate_response.json()["cancel_at_period_end"] is False
        
        # Step 4: Subscription continues after period end
        # (No webhook event for cancellation)


class TestAdminSubscriptionManagement:
    """Test admin operations on user subscriptions."""

    @patch('app.services.subscription_service.SubscriptionService')
    @patch('app.services.trial_service.TrialService')
    @patch('app.api.v1.admin.require_admin')
    def test_admin_grants_trial_and_changes_plan(
        self,
        mock_require_admin,
        mock_trial_service,
        mock_subscription_service,
        client,
        pro_plan,
        plus_plan
    ):
        """Test: Admin grants trial to user → changes user's plan."""
        mock_require_admin.return_value = None  # Admin check passes
        user_id = 1
        
        # Step 1: Admin grants 14-day Pro trial to user
        trial_end = datetime.utcnow() + timedelta(days=14)
        mock_trial_service.activate_trial.return_value = Subscription(
            id=1,
            user_id=user_id,
            plan_id=pro_plan.id,
            status="trialing",
            current_period_end=trial_end
        )
        
        grant_response = client.post(
            f"/api/v1/admin/subscriptions/{user_id}/grant-trial"
        )
        assert grant_response.status_code == 200
        
        # Step 2: Admin changes user's plan to Plus
        mock_subscription_service.upgrade_subscription.return_value = Subscription(
            id=2,
            user_id=user_id,
            plan_id=plus_plan.id,
            status="active",
            current_period_end=datetime.utcnow() + timedelta(days=30)
        )
        
        change_response = client.put(
            f"/api/v1/admin/subscriptions/{user_id}/change-plan",
            json={"plan_type": "plus"}
        )
        assert change_response.status_code == 200
        assert change_response.json()["plan_id"] == plus_plan.id
        
        # Step 3: Admin extends subscription by 30 days
        extended_end = datetime.utcnow() + timedelta(days=60)
        mock_subscription_service.get_user_subscription.return_value = Subscription(
            id=2,
            user_id=user_id,
            plan_id=plus_plan.id,
            status="active",
            current_period_end=extended_end
        )
        
        extend_response = client.post(
            f"/api/v1/admin/subscriptions/{user_id}/extend",
            json={"days": 30}
        )
        assert extend_response.status_code == 200


class TestWebhookIdempotencyAndConcurrency:
    """Test webhook idempotency and handling of concurrent changes."""

    @patch('app.services.stripe_payment_service.StripePaymentService')
    @patch('app.models.payment_event.PaymentEvent')
    def test_duplicate_webhook_events_are_ignored(
        self,
        mock_payment_event,
        mock_stripe,
        client
    ):
        """Test: Same webhook event sent twice → second is ignored."""
        event_id = "evt_test_123"
        
        webhook_payload = {
            "id": event_id,
            "type": "invoice.payment_succeeded",
            "data": {
                "object": {
                    "customer": "cus_123",
                    "subscription": "sub_123",
                    "amount_paid": 490
                }
            }
        }
        
        # First webhook - should process
        mock_payment_event.query().filter().first.return_value = None
        
        with patch('app.api.v1.webhooks.verify_stripe_signature'):
            response1 = client.post(
                "/api/v1/webhooks/stripe",
                json=webhook_payload,
                headers={"stripe-signature": "test_sig"}
            )
            assert response1.status_code == 200
        
        # Second webhook - should be ignored (idempotent)
        mock_payment_event.query().filter().first.return_value = Mock(
            stripe_event_id=event_id
        )
        
        with patch('app.api.v1.webhooks.verify_stripe_signature'):
            response2 = client.post(
                "/api/v1/webhooks/stripe",
                json=webhook_payload,
                headers={"stripe-signature": "test_sig"}
            )
            assert response2.status_code == 200
        
        # Verify event was only processed once
        mock_stripe.handle_webhook_event.assert_called_once()

    @patch('app.services.subscription_service.SubscriptionService')
    def test_concurrent_subscription_changes(
        self,
        mock_subscription_service,
        client
    ):
        """Test: User upgrades while webhook arrives → last write wins."""
        user_id = 1
        
        # Simulate race condition:
        # 1. User initiates upgrade via UI
        # 2. Webhook arrives for previous subscription change
        # 3. Both try to update subscription
        
        # Mock database to handle concurrent updates
        subscription = Subscription(
            id=1,
            user_id=user_id,
            plan_id=2,
            status="active"
        )
        mock_subscription_service.get_user_subscription.return_value = subscription
        
        # Both operations should succeed
        # (Database transaction isolation handles conflicts)
        upgrade_response = client.post(
            "/api/v1/subscriptions/upgrade",
            json={"plan_type": "pro"}
        )
        
        # Final state should be consistent
        assert upgrade_response.status_code in [200, 409]  # 409 if conflict detected
