"""Stripe payment service for subscription management"""
from typing import Dict, Optional, Any
from datetime import datetime
import logging
import stripe
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.plan import Plan, BillingCycle
from app.models.payment_event import PaymentEvent
from app.models.user import User


logger = logging.getLogger(__name__)

# Initialize Stripe with API key
stripe.api_key = getattr(settings, 'STRIPE_SECRET_KEY', None)


class StripePaymentService:
    """Service for Stripe payment integration"""
    
    def __init__(self, db: Session):
        """
        Initialize Stripe payment service.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        
        if not stripe.api_key:
            logger.warning("Stripe API key not configured")
    
    def create_checkout_session(
        self,
        user_id: int,
        plan_id: int,
        billing_cycle: BillingCycle,
        success_url: str,
        cancel_url: str
    ) -> Dict[str, str]:
        """
        Create Stripe checkout session for subscription.
        
        Per Requirement 4.2: Create checkout session for monthly/yearly billing.
        
        Args:
            user_id: ID of the user
            plan_id: ID of the plan to subscribe to
            billing_cycle: Monthly or yearly billing
            success_url: URL to redirect on success
            cancel_url: URL to redirect on cancel
            
        Returns:
            Dictionary with checkout session ID and URL
            
        Raises:
            ValueError: If plan not found or Stripe API error
        """
        try:
            # Get user and plan
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError(f"User {user_id} not found")
            
            plan = self.db.query(Plan).filter(Plan.id == plan_id).first()
            if not plan:
                raise ValueError(f"Plan {plan_id} not found")
            
            # Get or create Stripe customer
            customer_id = self._get_or_create_customer(user)
            
            # Determine price based on billing cycle
            price_amount = (
                int(plan.monthly_price * 100) if billing_cycle == BillingCycle.MONTHLY
                else int(plan.yearly_price * 100)
            )
            
            # Create checkout session
            session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=['card', 'sepa_debit'],
                line_items=[{
                    'price_data': {
                        'currency': 'eur',
                        'product_data': {
                            'name': plan.name,
                            'description': f"{plan.plan_type.value.title()} Plan"
                        },
                        'unit_amount': price_amount,
                        'recurring': {
                            'interval': 'month' if billing_cycle == BillingCycle.MONTHLY else 'year'
                        }
                    },
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    'user_id': str(user_id),
                    'plan_id': str(plan_id),
                    'billing_cycle': billing_cycle.value
                }
            )
            
            logger.info(
                f"Created checkout session for user {user_id}: "
                f"session_id={session.id}, plan={plan.plan_type.value}"
            )
            
            return {
                'session_id': session.id,
                'url': session.url
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe API error creating checkout session: {e}")
            raise ValueError(f"Payment processing error: {str(e)}")
        except Exception as e:
            logger.error(f"Error creating checkout session: {e}")
            raise
    
    def _get_or_create_customer(self, user: User) -> str:
        """
        Get existing Stripe customer or create new one.
        
        Args:
            user: User instance
            
        Returns:
            Stripe customer ID
        """
        # Check if user already has a Stripe customer ID
        subscription = (
            self.db.query(Subscription)
            .filter(Subscription.user_id == user.id)
            .first()
        )
        
        if subscription and subscription.stripe_customer_id:
            return subscription.stripe_customer_id
        
        # Create new Stripe customer
        try:
            customer = stripe.Customer.create(
                email=user.email,
                metadata={'user_id': str(user.id)}
            )
            
            logger.info(f"Created Stripe customer for user {user.id}: {customer.id}")
            return customer.id
            
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create Stripe customer: {e}")
            raise ValueError(f"Failed to create customer: {str(e)}")
    
    def create_subscription(
        self,
        customer_id: str,
        price_id: str,
        metadata: Optional[Dict[str, str]] = None
    ) -> stripe.Subscription:
        """
        Create Stripe subscription.
        
        Args:
            customer_id: Stripe customer ID
            price_id: Stripe price ID
            metadata: Optional metadata
            
        Returns:
            Stripe Subscription object
        """
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{'price': price_id}],
                metadata=metadata or {}
            )
            
            logger.info(f"Created Stripe subscription: {subscription.id}")
            return subscription
            
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create subscription: {e}")
            raise ValueError(f"Failed to create subscription: {str(e)}")
    
    def cancel_subscription(self, stripe_subscription_id: str) -> stripe.Subscription:
        """
        Cancel Stripe subscription at period end.
        
        Args:
            stripe_subscription_id: Stripe subscription ID
            
        Returns:
            Updated Stripe Subscription object
        """
        try:
            subscription = stripe.Subscription.modify(
                stripe_subscription_id,
                cancel_at_period_end=True
            )
            
            logger.info(f"Canceled Stripe subscription: {stripe_subscription_id}")
            return subscription
            
        except stripe.error.StripeError as e:
            logger.error(f"Failed to cancel subscription: {e}")
            raise ValueError(f"Failed to cancel subscription: {str(e)}")
    
    def handle_webhook_event(self, payload: bytes, sig_header: str) -> Dict[str, Any]:
        """
        Handle Stripe webhook event with signature verification.
        
        Per Requirement 4.3: Verify webhook signature before processing.
        Per Requirement 4.4-4.6: Handle various webhook events.
        
        Args:
            payload: Raw webhook payload
            sig_header: Stripe signature header
            
        Returns:
            Dictionary with processing result
            
        Raises:
            ValueError: If signature verification fails
        """
        webhook_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', None)
        
        if not webhook_secret:
            logger.error("Stripe webhook secret not configured")
            raise ValueError("Webhook secret not configured")
        
        try:
            # Verify webhook signature
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            
            logger.info(f"Received Stripe webhook: {event['type']}")
            
            # Check for duplicate event (idempotency)
            if PaymentEvent.is_duplicate(self.db, event['id']):
                logger.info(f"Duplicate webhook event ignored: {event['id']}")
                return {'status': 'duplicate', 'event_id': event['id']}
            
            # Log the event
            self._log_payment_event(event)
            
            # Handle different event types
            result = self._process_webhook_event(event)
            
            return result
            
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Webhook signature verification failed: {e}")
            raise ValueError("Invalid webhook signature")
        except Exception as e:
            logger.error(f"Error processing webhook: {e}")
            raise
    
    def _process_webhook_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process different types of webhook events.
        
        Args:
            event: Stripe event object
            
        Returns:
            Processing result
        """
        event_type = event['type']
        
        handlers = {
            'checkout.session.completed': self._handle_checkout_completed,
            'invoice.payment_succeeded': self._handle_payment_succeeded,
            'invoice.payment_failed': self._handle_payment_failed,
            'customer.subscription.updated': self._handle_subscription_updated,
            'customer.subscription.deleted': self._handle_subscription_deleted,
        }
        
        handler = handlers.get(event_type)
        
        if handler:
            return handler(event)
        else:
            logger.info(f"Unhandled webhook event type: {event_type}")
            return {'status': 'unhandled', 'event_type': event_type}
    
    def _handle_checkout_completed(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Handle checkout.session.completed event"""
        session = event['data']['object']
        user_id = int(session['metadata'].get('user_id'))
        
        logger.info(f"Checkout completed for user {user_id}")
        
        # Subscription will be activated by subscription.created event
        return {'status': 'processed', 'action': 'checkout_completed'}
    
    def _handle_payment_succeeded(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Handle invoice.payment_succeeded event"""
        invoice = event['data']['object']
        subscription_id = invoice.get('subscription')
        
        logger.info(f"Payment succeeded for subscription {subscription_id}")
        
        # Update subscription status to active if needed
        subscription = (
            self.db.query(Subscription)
            .filter(Subscription.stripe_subscription_id == subscription_id)
            .first()
        )
        
        if subscription and subscription.status == SubscriptionStatus.PAST_DUE:
            subscription.status = SubscriptionStatus.ACTIVE
            self.db.commit()
            logger.info(f"Reactivated subscription {subscription.id} after payment")
        
        return {'status': 'processed', 'action': 'payment_confirmed'}
    
    def _handle_payment_failed(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Handle invoice.payment_failed event - 7 day grace period"""
        invoice = event['data']['object']
        subscription_id = invoice.get('subscription')
        
        logger.warning(f"Payment failed for subscription {subscription_id}")
        
        # Mark subscription as past_due (7-day grace period)
        subscription = (
            self.db.query(Subscription)
            .filter(Subscription.stripe_subscription_id == subscription_id)
            .first()
        )
        
        if subscription:
            subscription.status = SubscriptionStatus.PAST_DUE
            self.db.commit()
            logger.info(f"Marked subscription {subscription.id} as past_due")
        
        return {'status': 'processed', 'action': 'payment_failed'}
    
    def _handle_subscription_updated(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Handle customer.subscription.updated event"""
        stripe_sub = event['data']['object']
        
        logger.info(f"Subscription updated: {stripe_sub['id']}")
        
        # Sync subscription changes from Stripe
        subscription = (
            self.db.query(Subscription)
            .filter(Subscription.stripe_subscription_id == stripe_sub['id'])
            .first()
        )
        
        if subscription:
            subscription.current_period_start = datetime.fromtimestamp(
                stripe_sub['current_period_start']
            )
            subscription.current_period_end = datetime.fromtimestamp(
                stripe_sub['current_period_end']
            )
            self.db.commit()
        
        return {'status': 'processed', 'action': 'subscription_synced'}
    
    def _handle_subscription_deleted(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Handle customer.subscription.deleted event - downgrade to Free"""
        stripe_sub = event['data']['object']
        
        logger.info(f"Subscription deleted: {stripe_sub['id']}")
        
        # Downgrade to Free tier
        subscription = (
            self.db.query(Subscription)
            .filter(Subscription.stripe_subscription_id == stripe_sub['id'])
            .first()
        )
        
        if subscription:
            free_plan = self.db.query(Plan).filter(Plan.plan_type == 'free').first()
            if free_plan:
                subscription.plan_id = free_plan.id
                subscription.status = SubscriptionStatus.CANCELED
                self.db.commit()
                logger.info(f"Downgraded subscription {subscription.id} to Free tier")
        
        return {'status': 'processed', 'action': 'downgraded_to_free'}
    
    def _log_payment_event(self, event: Dict[str, Any]) -> None:
        """Log payment event for audit trail"""
        try:
            payment_event = PaymentEvent(
                stripe_event_id=event['id'],
                event_type=event['type'],
                payload=event,
                user_id=None  # Will be populated if we can extract it
            )
            
            self.db.add(payment_event)
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Failed to log payment event: {e}")
            self.db.rollback()
