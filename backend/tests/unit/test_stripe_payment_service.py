"""Unit tests for StripePaymentService"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal

from app.services.stripe_payment_service import StripePaymentService
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.plan import Plan, PlanType, BillingCycle
from app.models.user import User
from app.models.payment_event import PaymentEvent


class TestStripePaymentService:
    """Test StripePaymentService methods"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.mock_db = Mock()
        self.service = StripePaymentService(self.mock_db)
    
    @patch('app.services.stripe_payment_service.stripe.checkout.Session.create')
    def test_create_checkout_session_monthly(self, mock_stripe_create):
        """Test create_checkout_session for monthly billing"""
        mock_user = User(id=1, email="test@example.com")
        mock_plan = Plan(
            id=2,
            plan_type=PlanType.PLUS,
            name="Plus",
            monthly_price=Decimal("4.90"),
            yearly_price=Decimal("49.00")
        )
        mock_session = MagicMock()
        mock_session.id = "cs_test_123"
        mock_session.url = "https://checkout.stripe.com/test"
        mock_stripe_create.return_value = mock_session
        
        self.mock_db.query().filter().first.side_effect = [mock_user, mock_plan, None]
        
        with patch.object(self.service, '_get_or_create_customer', return_value='cus_test_123'):
            result = self.service.create_checkout_session(
                user_id=1,
                plan_id=2,
                billing_cycle=BillingCycle.MONTHLY,
                success_url="https://example.com/success",
                cancel_url="https://example.com/cancel"
            )
        
        assert result["session_id"] == "cs_test_123"
        assert result["url"] == "https://checkout.stripe.com/test"
        mock_stripe_create.assert_called_once()
    
    @patch('app.services.stripe_payment_service.stripe.checkout.Session.create')
    def test_create_checkout_session_yearly(self, mock_stripe_create):
        """Test create_checkout_session for yearly billing"""
        mock_user = User(id=1, email="test@example.com")
        mock_plan = Plan(
            id=2,
            plan_type=PlanType.PLUS,
            name="Plus",
            monthly_price=Decimal("4.90"),
            yearly_price=Decimal("49.00")
        )
        mock_session = MagicMock()
        mock_session.id = "cs_test_456"
        mock_session.url = "https://checkout.stripe.com/test"
        mock_stripe_create.return_value = mock_session
        
        self.mock_db.query().filter().first.side_effect = [mock_user, mock_plan, None]
        
        with patch.object(self.service, '_get_or_create_customer', return_value='cus_test_123'):
            result = self.service.create_checkout_session(
                user_id=1,
                plan_id=2,
                billing_cycle=BillingCycle.YEARLY,
                success_url="https://example.com/success",
                cancel_url="https://example.com/cancel"
            )
        
        assert result["session_id"] == "cs_test_456"
        # Verify yearly interval was used
        call_args = mock_stripe_create.call_args
        assert call_args[1]['line_items'][0]['price_data']['recurring']['interval'] == 'year'
    
    @patch('app.services.stripe_payment_service.stripe.Customer.create')
    def test_get_or_create_customer_new(self, mock_stripe_create):
        """Test _get_or_create_customer creates new customer"""
        mock_user = User(id=1, email="test@example.com")
        mock_customer = MagicMock()
        mock_customer.id = "cus_new_123"
        mock_stripe_create.return_value = mock_customer
        
        # No existing subscription
        self.mock_db.query().filter().first.return_value = None
        
        result = self.service._get_or_create_customer(mock_user)
        
        assert result == "cus_new_123"
        mock_stripe_create.assert_called_once()

    @patch('app.services.stripe_payment_service.stripe.billing_portal.Session.create')
    @patch('app.services.stripe_payment_service.stripe.Subscription.retrieve')
    def test_create_customer_portal_session_for_target_plan_switch(
        self,
        mock_retrieve_subscription,
        mock_portal_create,
    ):
        """Test create_customer_portal_session can deep-link to a paid plan switch."""
        mock_user = User(id=1, email="test@example.com")
        mock_subscription = Subscription(
            id=1,
            user_id=1,
            plan_id=3,
            stripe_customer_id="cus_test_123",
            stripe_subscription_id="sub_test_123",
        )
        mock_plan = Plan(
            id=4,
            plan_type=PlanType.PRO,
            name="Pro",
            monthly_price=Decimal("12.90"),
            yearly_price=Decimal("129.00"),
        )
        mock_portal_session = MagicMock()
        mock_portal_session.url = "https://billing.stripe.com/session/test"
        mock_portal_create.return_value = mock_portal_session
        mock_retrieve_subscription.return_value.to_dict_recursive.return_value = {
            "items": {
                "data": [
                    {
                        "id": "si_test_123",
                    }
                ]
            }
        }

        self.mock_db.query().filter().first.side_effect = [
            mock_user,
            mock_subscription,
            mock_plan,
        ]

        with patch.dict(
            'app.services.stripe_payment_service.PRICE_MAP',
            {("pro", "yearly"): "price_pro_yearly_test"},
            clear=False,
        ):
            result = self.service.create_customer_portal_session(
                user_id=1,
                return_url="https://example.com/pricing",
                target_plan_id=4,
                billing_cycle=BillingCycle.YEARLY,
            )

        assert result["url"] == "https://billing.stripe.com/session/test"
        mock_retrieve_subscription.assert_called_once_with("sub_test_123")
        mock_portal_create.assert_called_once_with(
            customer="cus_test_123",
            return_url="https://example.com/pricing",
            flow_data={
                "type": "subscription_update_confirm",
                "subscription_update_confirm": {
                    "subscription": "sub_test_123",
                    "items": [
                        {
                            "id": "si_test_123",
                            "price": "price_pro_yearly_test",
                            "quantity": 1,
                        }
                    ],
                },
            },
        )

    @patch('app.services.stripe_payment_service.stripe.Subscription.modify')
    @patch('app.services.stripe_payment_service.stripe.Subscription.retrieve')
    def test_switch_subscription_plan_updates_existing_subscription_item(
        self,
        mock_retrieve_subscription,
        mock_modify_subscription,
    ):
        """Test switch_subscription_plan updates the existing Stripe subscription item."""
        mock_subscription = Subscription(
            id=1,
            user_id=1,
            plan_id=3,
            stripe_subscription_id="sub_test_123",
            stripe_customer_id="cus_test_123",
            billing_cycle=BillingCycle.MONTHLY,
        )
        mock_plan = Plan(
            id=4,
            plan_type=PlanType.PRO,
            name="Pro",
            monthly_price=Decimal("12.90"),
            yearly_price=Decimal("129.00"),
        )
        mock_retrieve_subscription.return_value.to_dict_recursive.return_value = {
            "items": {
                "data": [
                    {
                        "id": "si_test_123",
                    }
                ]
            }
        }
        mock_modify_subscription.return_value = {
            "id": "sub_test_123",
            "status": "active",
            "cancel_at_period_end": False,
            "current_period_start": 1710000000,
            "current_period_end": 1712592000,
            "customer": "cus_test_123",
            "items": {
                "data": [
                    {
                        "id": "si_test_123",
                        "price": {"id": "price_pro_monthly_test"},
                    }
                ]
            },
        }

        with patch.dict(
            'app.services.stripe_payment_service.PRICE_MAP',
            {("pro", "monthly"): "price_pro_monthly_test"},
            clear=False,
        ):
            with patch.object(self.service, '_get_subscription', return_value=mock_subscription):
                self.mock_db.query().filter().first.return_value = mock_plan
                with patch.object(
                    self.service,
                    '_sync_local_subscription_from_stripe',
                    return_value=mock_subscription,
                ) as mock_sync:
                    result = self.service.switch_subscription_plan(
                        user_id=1,
                        plan_id=4,
                        billing_cycle=BillingCycle.MONTHLY,
                    )

        assert result == mock_subscription
        mock_retrieve_subscription.assert_called_once_with("sub_test_123")
        mock_modify_subscription.assert_called_once_with(
            "sub_test_123",
            items=[
                {
                    "id": "si_test_123",
                    "price": "price_pro_monthly_test",
                    "quantity": 1,
                }
            ],
            proration_behavior="create_prorations",
        )
        mock_sync.assert_called_once()
    
    def test_get_or_create_customer_existing(self):
        """Test _get_or_create_customer returns existing customer ID"""
        mock_user = User(id=1, email="test@example.com")
        mock_subscription = Subscription(
            id=1,
            user_id=1,
            plan_id=1,
            stripe_customer_id="cus_existing_123"
        )
        
        self.mock_db.query().filter().first.return_value = mock_subscription
        
        result = self.service._get_or_create_customer(mock_user)
        
        assert result == "cus_existing_123"
    
    @patch('app.services.stripe_payment_service.stripe.Subscription.create')
    def test_create_subscription(self, mock_stripe_create):
        """Test create_subscription creates Stripe subscription"""
        mock_subscription = MagicMock()
        mock_subscription.id = "sub_test_123"
        mock_stripe_create.return_value = mock_subscription
        
        result = self.service.create_subscription(
            customer_id="cus_test_123",
            price_id="price_test_456",
            metadata={"user_id": "1"}
        )
        
        assert result.id == "sub_test_123"
        mock_stripe_create.assert_called_once()
    
    @patch('app.services.stripe_payment_service.stripe.Subscription.modify')
    def test_cancel_subscription(self, mock_stripe_modify):
        """Test cancel_subscription cancels at period end"""
        mock_subscription = MagicMock()
        mock_subscription.id = "sub_test_123"
        mock_stripe_modify.return_value = mock_subscription
        
        result = self.service.cancel_subscription("sub_test_123")
        
        assert result.id == "sub_test_123"
        mock_stripe_modify.assert_called_once_with(
            "sub_test_123",
            cancel_at_period_end=True
        )
    
    @patch('app.services.stripe_payment_service.stripe.Webhook.construct_event')
    def test_handle_webhook_event_valid_signature(self, mock_construct):
        """Test handle_webhook_event with valid signature"""
        mock_event = {
            'id': 'evt_test_123',
            'type': 'checkout.session.completed',
            'data': {'object': {}}
        }
        mock_construct.return_value = mock_event
        
        # Mock duplicate check
        with patch.object(PaymentEvent, 'is_duplicate', return_value=False):
            with patch.object(self.service, '_process_webhook_event', return_value={'status': 'processed'}):
                result = self.service.handle_webhook_event(
                    payload=b'test_payload',
                    sig_header='test_signature'
                )
        
        assert result['status'] == 'processed'
    
    @patch('app.services.stripe_payment_service.stripe.Webhook.construct_event')
    def test_handle_webhook_event_duplicate(self, mock_construct):
        """Test handle_webhook_event ignores duplicate events"""
        mock_event = {
            'id': 'evt_test_123',
            'type': 'checkout.session.completed',
            'data': {'object': {}}
        }
        mock_construct.return_value = mock_event
        
        # Mock duplicate check returns True
        with patch.object(PaymentEvent, 'is_duplicate', return_value=True):
            result = self.service.handle_webhook_event(
                payload=b'test_payload',
                sig_header='test_signature'
            )
        
        assert result['status'] == 'duplicate'
    
    def test_handle_checkout_completed(self):
        """Test _handle_checkout_completed processes event"""
        event = {
            'type': 'checkout.session.completed',
            'data': {
                'object': {
                    'metadata': {'user_id': '1'}
                }
            }
        }
        
        result = self.service._handle_checkout_completed(event)
        
        assert result['status'] == 'processed'
        assert result['action'] == 'checkout_completed'
    
    def test_handle_payment_succeeded(self):
        """Test _handle_payment_succeeded reactivates past_due subscription"""
        event = {
            'type': 'invoice.payment_succeeded',
            'data': {
                'object': {
                    'subscription': 'sub_test_123'
                }
            }
        }
        
        mock_subscription = Subscription(
            id=1,
            user_id=1,
            plan_id=1,
            stripe_subscription_id='sub_test_123',
            status=SubscriptionStatus.PAST_DUE
        )
        
        self.mock_db.query().filter().first.return_value = mock_subscription
        
        result = self.service._handle_payment_succeeded(event)
        
        assert result['status'] == 'processed'
        assert mock_subscription.status == SubscriptionStatus.ACTIVE
        self.mock_db.commit.assert_called_once()
    
    def test_handle_payment_failed(self):
        """Test _handle_payment_failed marks subscription as past_due"""
        event = {
            'type': 'invoice.payment_failed',
            'data': {
                'object': {
                    'subscription': 'sub_test_123'
                }
            }
        }
        
        mock_subscription = Subscription(
            id=1,
            user_id=1,
            plan_id=1,
            stripe_subscription_id='sub_test_123',
            status=SubscriptionStatus.ACTIVE
        )
        
        self.mock_db.query().filter().first.return_value = mock_subscription
        
        result = self.service._handle_payment_failed(event)
        
        assert result['status'] == 'processed'
        assert mock_subscription.status == SubscriptionStatus.PAST_DUE
        self.mock_db.commit.assert_called_once()
    
    def test_handle_subscription_deleted(self):
        """Test _handle_subscription_deleted downgrades to Free"""
        event = {
            'type': 'customer.subscription.deleted',
            'data': {
                'object': {
                    'id': 'sub_test_123'
                }
            }
        }
        
        mock_free_plan = Plan(id=1, plan_type=PlanType.FREE, name="Free")
        mock_subscription = Subscription(
            id=1,
            user_id=1,
            plan_id=2,
            stripe_subscription_id='sub_test_123',
            status=SubscriptionStatus.ACTIVE
        )
        
        self.mock_db.query().filter().first.side_effect = [mock_subscription, mock_free_plan]
        
        result = self.service._handle_subscription_deleted(event)
        
        assert result['status'] == 'processed'
        assert mock_subscription.plan_id == 1
        assert mock_subscription.status == SubscriptionStatus.CANCELED
        self.mock_db.commit.assert_called_once()
