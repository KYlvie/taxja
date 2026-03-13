"""Unit tests for PaymentEvent model"""
import pytest
from datetime import datetime
from unittest.mock import Mock
from app.models.payment_event import PaymentEvent


class TestPaymentEventModel:
    """Test PaymentEvent model methods"""
    
    def test_payment_event_creation(self):
        """Test creating a payment event"""
        event = PaymentEvent(
            stripe_event_id="evt_test_123",
            event_type="checkout.session.completed",
            user_id=1,
            payload={"data": {"object": {"id": "cs_test_123"}}}
        )
        
        assert event.stripe_event_id == "evt_test_123"
        assert event.event_type == "checkout.session.completed"
        assert event.user_id == 1
        assert event.payload is not None
    
    def test_is_duplicate_true(self):
        """Test is_duplicate returns True for existing event"""
        # Mock session
        mock_session = Mock()
        mock_query = Mock()
        mock_filter = Mock()
        
        # Setup mock chain
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_filter
        mock_filter.first.return_value = PaymentEvent(
            stripe_event_id="evt_test_123",
            event_type="test",
            payload={}
        )
        
        result = PaymentEvent.is_duplicate(mock_session, "evt_test_123")
        assert result is True
    
    def test_is_duplicate_false(self):
        """Test is_duplicate returns False for new event"""
        # Mock session
        mock_session = Mock()
        mock_query = Mock()
        mock_filter = Mock()
        
        # Setup mock chain
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_filter
        mock_filter.first.return_value = None
        
        result = PaymentEvent.is_duplicate(mock_session, "evt_test_new")
        assert result is False
    
    def test_get_event_data_existing_key(self):
        """Test get_event_data returns value for existing key"""
        event = PaymentEvent(
            stripe_event_id="evt_test_123",
            event_type="test",
            payload={"key1": "value1", "key2": "value2"}
        )
        
        assert event.get_event_data("key1") == "value1"
        assert event.get_event_data("key2") == "value2"
    
    def test_get_event_data_missing_key(self):
        """Test get_event_data returns default for missing key"""
        event = PaymentEvent(
            stripe_event_id="evt_test_123",
            event_type="test",
            payload={"key1": "value1"}
        )
        
        assert event.get_event_data("missing_key") is None
        assert event.get_event_data("missing_key", "default") == "default"
    
    def test_get_event_data_empty_payload(self):
        """Test get_event_data returns default for empty payload"""
        event = PaymentEvent(
            stripe_event_id="evt_test_123",
            event_type="test",
            payload=None
        )
        
        assert event.get_event_data("any_key") is None
        assert event.get_event_data("any_key", "default") == "default"
    
    def test_get_customer_id_direct(self):
        """Test get_customer_id with direct customer field"""
        event = PaymentEvent(
            stripe_event_id="evt_test_123",
            event_type="checkout.session.completed",
            payload={
                "data": {
                    "object": {
                        "customer": "cus_test_123"
                    }
                }
            }
        )
        
        assert event.get_customer_id() == "cus_test_123"
    
    def test_get_customer_id_nested_in_subscription(self):
        """Test get_customer_id nested in subscription object"""
        event = PaymentEvent(
            stripe_event_id="evt_test_123",
            event_type="invoice.payment_succeeded",
            payload={
                "data": {
                    "object": {
                        "subscription": {
                            "customer": "cus_test_456"
                        }
                    }
                }
            }
        )
        
        assert event.get_customer_id() == "cus_test_456"
    
    def test_get_customer_id_not_found(self):
        """Test get_customer_id returns None when not found"""
        event = PaymentEvent(
            stripe_event_id="evt_test_123",
            event_type="test",
            payload={"data": {"object": {}}}
        )
        
        assert event.get_customer_id() is None
    
    def test_get_customer_id_empty_payload(self):
        """Test get_customer_id returns None for empty payload"""
        event = PaymentEvent(
            stripe_event_id="evt_test_123",
            event_type="test",
            payload=None
        )
        
        assert event.get_customer_id() is None
    
    def test_get_subscription_id_string(self):
        """Test get_subscription_id with string subscription field"""
        event = PaymentEvent(
            stripe_event_id="evt_test_123",
            event_type="invoice.payment_succeeded",
            payload={
                "data": {
                    "object": {
                        "subscription": "sub_test_123"
                    }
                }
            }
        )
        
        assert event.get_subscription_id() == "sub_test_123"
    
    def test_get_subscription_id_object(self):
        """Test get_subscription_id with subscription object"""
        event = PaymentEvent(
            stripe_event_id="evt_test_123",
            event_type="invoice.payment_succeeded",
            payload={
                "data": {
                    "object": {
                        "subscription": {
                            "id": "sub_test_456"
                        }
                    }
                }
            }
        )
        
        assert event.get_subscription_id() == "sub_test_456"
    
    def test_get_subscription_id_subscription_event(self):
        """Test get_subscription_id for subscription event"""
        event = PaymentEvent(
            stripe_event_id="evt_test_123",
            event_type="customer.subscription.updated",
            payload={
                "data": {
                    "object": {
                        "object": "subscription",
                        "id": "sub_test_789"
                    }
                }
            }
        )
        
        assert event.get_subscription_id() == "sub_test_789"
    
    def test_get_subscription_id_not_found(self):
        """Test get_subscription_id returns None when not found"""
        event = PaymentEvent(
            stripe_event_id="evt_test_123",
            event_type="test",
            payload={"data": {"object": {}}}
        )
        
        assert event.get_subscription_id() is None
    
    def test_get_subscription_id_empty_payload(self):
        """Test get_subscription_id returns None for empty payload"""
        event = PaymentEvent(
            stripe_event_id="evt_test_123",
            event_type="test",
            payload=None
        )
        
        assert event.get_subscription_id() is None
    
    def test_event_types(self):
        """Test various event types"""
        event_types = [
            "checkout.session.completed",
            "invoice.payment_succeeded",
            "invoice.payment_failed",
            "customer.subscription.updated",
            "customer.subscription.deleted"
        ]
        
        for event_type in event_types:
            event = PaymentEvent(
                stripe_event_id=f"evt_test_{event_type}",
                event_type=event_type,
                payload={}
            )
            assert event.event_type == event_type
    
    def test_complex_payload_structure(self):
        """Test handling complex nested payload"""
        event = PaymentEvent(
            stripe_event_id="evt_test_complex",
            event_type="checkout.session.completed",
            payload={
                "id": "evt_test_complex",
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": "cs_test_123",
                        "customer": "cus_test_123",
                        "subscription": "sub_test_123",
                        "amount_total": 490,
                        "currency": "eur",
                        "metadata": {
                            "user_id": "1",
                            "plan_type": "plus"
                        }
                    }
                }
            }
        )
        
        assert event.get_customer_id() == "cus_test_123"
        assert event.get_subscription_id() == "sub_test_123"
        assert event.get_event_data("type") == "checkout.session.completed"
        
        # Test nested data access
        data = event.payload.get("data", {})
        obj = data.get("object", {})
        assert obj.get("amount_total") == 490
        assert obj.get("currency") == "eur"
