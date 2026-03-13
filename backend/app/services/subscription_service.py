"""Subscription service for managing user subscriptions"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import logging

from app.models.subscription import Subscription, SubscriptionStatus
from app.models.plan import Plan, PlanType, BillingCycle
from app.models.user import User
from app.models.audit_log import AuditLog, AuditOperationType, AuditEntityType
from app.schemas.subscription import SubscriptionCreate, SubscriptionUpdate


logger = logging.getLogger(__name__)


class SubscriptionService:
    """Service for managing user subscriptions"""
    
    def __init__(self, db: Session):
        """
        Initialize subscription service.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
    
    def create_subscription(
        self,
        user_id: int,
        plan_id: int,
        billing_cycle: Optional[BillingCycle] = None,
        stripe_subscription_id: Optional[str] = None,
        stripe_customer_id: Optional[str] = None,
        status: SubscriptionStatus = SubscriptionStatus.ACTIVE,
        current_period_start: Optional[datetime] = None,
        current_period_end: Optional[datetime] = None,
    ) -> Subscription:
        """
        Create a new subscription for a user.
        
        Args:
            user_id: ID of the user
            plan_id: ID of the plan to subscribe to
            billing_cycle: Billing cycle (monthly or yearly)
            stripe_subscription_id: Stripe subscription ID
            stripe_customer_id: Stripe customer ID
            status: Initial subscription status
            current_period_start: Start of current billing period
            current_period_end: End of current billing period
            
        Returns:
            Created Subscription instance
            
        Raises:
            ValueError: If user or plan not found, or user already has active subscription
        """
        # Verify user exists
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"User with id {user_id} not found")
        
        # Verify plan exists
        plan = self.db.query(Plan).filter(Plan.id == plan_id).first()
        if not plan:
            raise ValueError(f"Plan with id {plan_id} not found")
        
        # Check if user already has an active subscription
        existing_subscription = self.get_user_subscription(user_id)
        if existing_subscription and existing_subscription.is_active():
            raise ValueError(f"User {user_id} already has an active subscription")
        
        # Set default period dates if not provided
        if not current_period_start:
            current_period_start = datetime.utcnow()
        
        if not current_period_end:
            # Default to 1 month for monthly, 1 year for yearly
            if billing_cycle == BillingCycle.YEARLY:
                current_period_end = current_period_start + timedelta(days=365)
            else:
                current_period_end = current_period_start + timedelta(days=30)
        
        # Create subscription
        subscription = Subscription(
            user_id=user_id,
            plan_id=plan_id,
            status=status,
            billing_cycle=billing_cycle,
            stripe_subscription_id=stripe_subscription_id,
            stripe_customer_id=stripe_customer_id,
            current_period_start=current_period_start,
            current_period_end=current_period_end,
            cancel_at_period_end=False,
        )
        
        try:
            self.db.add(subscription)
            
            # Update user's subscription_id
            user.subscription_id = subscription.id
            
            self.db.commit()
            self.db.refresh(subscription)
            
            # Create audit log
            self._create_audit_log(
                user_id=user_id,
                operation_type=AuditOperationType.CREATE,
                entity_id=str(subscription.id),
                details={
                    "plan_id": plan_id,
                    "plan_type": plan.plan_type.value,
                    "billing_cycle": billing_cycle.value if billing_cycle else None,
                    "status": status.value,
                }
            )
            
            logger.info(
                f"Created subscription for user {user_id}: "
                f"plan={plan.plan_type}, status={status}"
            )
            
            return subscription
            
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Failed to create subscription: {e}")
            raise ValueError(f"Failed to create subscription: {e}")
    
    def get_user_subscription(self, user_id: int) -> Optional[Subscription]:
        """
        Get the current subscription for a user.
        
        Args:
            user_id: ID of the user
            
        Returns:
            Subscription instance if found, None otherwise
        """
        return (
            self.db.query(Subscription)
            .filter(Subscription.user_id == user_id)
            .order_by(Subscription.created_at.desc())
            .first()
        )
    
    def upgrade_subscription(
        self,
        user_id: int,
        new_plan_id: int,
        prorate: bool = True,
    ) -> Dict[str, Any]:
        """
        Upgrade user's subscription to a higher-tier plan.
        
        Per Requirement 6.1: Upgrades take effect immediately with proration.
        
        Args:
            user_id: ID of the user
            new_plan_id: ID of the new plan
            prorate: Whether to calculate proration (default: True)
            
        Returns:
            Dictionary with subscription and proration details
            
        Raises:
            ValueError: If subscription or plan not found, or not an upgrade
        """
        subscription = self.get_user_subscription(user_id)
        if not subscription:
            raise ValueError(f"No subscription found for user {user_id}")
        
        if not subscription.is_active():
            raise ValueError(f"Cannot upgrade inactive subscription")
        
        # Get current and new plans
        current_plan = subscription.plan
        new_plan = self.db.query(Plan).filter(Plan.id == new_plan_id).first()
        if not new_plan:
            raise ValueError(f"Plan with id {new_plan_id} not found")
        
        # Verify it's an upgrade (higher price)
        current_price = (
            current_plan.yearly_price if subscription.billing_cycle == BillingCycle.YEARLY
            else current_plan.monthly_price
        )
        new_price = (
            new_plan.yearly_price if subscription.billing_cycle == BillingCycle.YEARLY
            else new_plan.monthly_price
        )
        
        if new_price <= current_price:
            raise ValueError(
                f"New plan price ({new_price}) must be higher than current plan price ({current_price})"
            )
        
        # Calculate proration if requested
        proration_amount = Decimal("0.00")
        if prorate and subscription.current_period_end:
            days_remaining = (subscription.current_period_end - datetime.utcnow()).days
            total_days = (subscription.current_period_end - subscription.current_period_start).days
            
            if total_days > 0:
                # Credit for unused time on current plan
                unused_credit = (current_price * days_remaining) / total_days
                
                # Charge for remaining time on new plan
                new_charge = (new_price * days_remaining) / total_days
                
                # Proration is the difference
                proration_amount = new_charge - unused_credit
        
        # Store old plan for audit log
        old_plan_id = subscription.plan_id
        old_plan_type = current_plan.plan_type
        
        # Update subscription
        subscription.plan_id = new_plan_id
        subscription.status = SubscriptionStatus.ACTIVE
        
        try:
            self.db.commit()
            self.db.refresh(subscription)
            
            # Create audit log
            self._create_audit_log(
                user_id=user_id,
                operation_type=AuditOperationType.UPDATE,
                entity_id=str(subscription.id),
                details={
                    "action": "upgrade",
                    "old_plan_id": old_plan_id,
                    "old_plan_type": old_plan_type.value,
                    "new_plan_id": new_plan_id,
                    "new_plan_type": new_plan.plan_type.value,
                    "proration_amount": str(proration_amount),
                    "effective_immediately": True,
                }
            )
            
            logger.info(
                f"Upgraded subscription for user {user_id}: "
                f"{old_plan_type} -> {new_plan.plan_type}, "
                f"proration={proration_amount}"
            )
            
            return {
                "subscription": subscription,
                "proration_amount": proration_amount,
                "effective_immediately": True,
            }
            
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Failed to upgrade subscription: {e}")
            raise ValueError(f"Failed to upgrade subscription: {e}")
    
    def downgrade_subscription(
        self,
        user_id: int,
        new_plan_id: int,
    ) -> Dict[str, Any]:
        """
        Downgrade user's subscription to a lower-tier plan.
        
        Per Requirement 6.2: Downgrades take effect at the end of current billing period.
        
        Args:
            user_id: ID of the user
            new_plan_id: ID of the new plan
            
        Returns:
            Dictionary with subscription and effective date
            
        Raises:
            ValueError: If subscription or plan not found, or not a downgrade
        """
        subscription = self.get_user_subscription(user_id)
        if not subscription:
            raise ValueError(f"No subscription found for user {user_id}")
        
        if not subscription.is_active():
            raise ValueError(f"Cannot downgrade inactive subscription")
        
        # Get current and new plans
        current_plan = subscription.plan
        new_plan = self.db.query(Plan).filter(Plan.id == new_plan_id).first()
        if not new_plan:
            raise ValueError(f"Plan with id {new_plan_id} not found")
        
        # Verify it's a downgrade (lower price)
        current_price = (
            current_plan.yearly_price if subscription.billing_cycle == BillingCycle.YEARLY
            else current_plan.monthly_price
        )
        new_price = (
            new_plan.yearly_price if subscription.billing_cycle == BillingCycle.YEARLY
            else new_plan.monthly_price
        )
        
        if new_price >= current_price:
            raise ValueError(
                f"New plan price ({new_price}) must be lower than current plan price ({current_price})"
            )
        
        # Store old plan for audit log
        old_plan_id = subscription.plan_id
        old_plan_type = current_plan.plan_type
        
        # Schedule downgrade for end of period
        # Note: The actual plan change will happen when the period ends
        # For now, we just mark it in the audit log
        # In a real implementation, you'd store this in a pending_plan_id field
        
        try:
            # Create audit log for scheduled downgrade
            self._create_audit_log(
                user_id=user_id,
                operation_type=AuditOperationType.UPDATE,
                entity_id=str(subscription.id),
                details={
                    "action": "downgrade_scheduled",
                    "old_plan_id": old_plan_id,
                    "old_plan_type": old_plan_type.value,
                    "new_plan_id": new_plan_id,
                    "new_plan_type": new_plan.plan_type.value,
                    "effective_date": subscription.current_period_end.isoformat() if subscription.current_period_end else None,
                    "effective_immediately": False,
                }
            )
            
            logger.info(
                f"Scheduled downgrade for user {user_id}: "
                f"{old_plan_type} -> {new_plan.plan_type}, "
                f"effective at {subscription.current_period_end}"
            )
            
            return {
                "subscription": subscription,
                "new_plan_id": new_plan_id,
                "effective_date": subscription.current_period_end,
                "effective_immediately": False,
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to schedule downgrade: {e}")
            raise ValueError(f"Failed to schedule downgrade: {e}")
    
    def cancel_subscription(
        self,
        user_id: int,
        immediate: bool = False,
    ) -> Dict[str, Any]:
        """
        Cancel user's subscription.
        
        Per Requirement 6.3: Cancellations preserve access until end of billing period.
        
        Args:
            user_id: ID of the user
            immediate: Whether to cancel immediately (default: False)
            
        Returns:
            Dictionary with subscription and cancellation details
            
        Raises:
            ValueError: If subscription not found or already canceled
        """
        subscription = self.get_user_subscription(user_id)
        if not subscription:
            raise ValueError(f"No subscription found for user {user_id}")
        
        if subscription.status == SubscriptionStatus.CANCELED:
            raise ValueError(f"Subscription is already canceled")
        
        old_status = subscription.status
        
        if immediate:
            # Cancel immediately
            subscription.status = SubscriptionStatus.CANCELED
            subscription.cancel_at_period_end = False
            effective_date = datetime.utcnow()
        else:
            # Cancel at end of period
            subscription.cancel_at_period_end = True
            effective_date = subscription.current_period_end
        
        try:
            self.db.commit()
            self.db.refresh(subscription)
            
            # Create audit log
            self._create_audit_log(
                user_id=user_id,
                operation_type=AuditOperationType.UPDATE,
                entity_id=str(subscription.id),
                details={
                    "action": "cancel",
                    "old_status": old_status.value,
                    "immediate": immediate,
                    "effective_date": effective_date.isoformat() if effective_date else None,
                    "cancel_at_period_end": subscription.cancel_at_period_end,
                }
            )
            
            logger.info(
                f"Canceled subscription for user {user_id}: "
                f"immediate={immediate}, effective_date={effective_date}"
            )
            
            return {
                "subscription": subscription,
                "immediate": immediate,
                "effective_date": effective_date,
                "access_until": subscription.current_period_end if not immediate else datetime.utcnow(),
            }
            
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Failed to cancel subscription: {e}")
            raise ValueError(f"Failed to cancel subscription: {e}")
    
    def reactivate_subscription(
        self,
        user_id: int,
    ) -> Subscription:
        """
        Reactivate a canceled subscription.
        
        Per Requirement 6.5: Users can reactivate within 30 days of cancellation.
        
        Args:
            user_id: ID of the user
            
        Returns:
            Reactivated Subscription instance
            
        Raises:
            ValueError: If subscription not found, not canceled, or past reactivation window
        """
        subscription = self.get_user_subscription(user_id)
        if not subscription:
            raise ValueError(f"No subscription found for user {user_id}")
        
        # Check if subscription is canceled or scheduled for cancellation
        if subscription.status != SubscriptionStatus.CANCELED and not subscription.cancel_at_period_end:
            raise ValueError(f"Subscription is not canceled")
        
        # Check if within 30-day reactivation window
        if subscription.status == SubscriptionStatus.CANCELED:
            days_since_cancellation = (datetime.utcnow() - subscription.updated_at).days
            if days_since_cancellation > 30:
                raise ValueError(
                    f"Cannot reactivate subscription after 30 days "
                    f"(canceled {days_since_cancellation} days ago)"
                )
        
        old_status = subscription.status
        
        # Reactivate subscription
        subscription.status = SubscriptionStatus.ACTIVE
        subscription.cancel_at_period_end = False
        
        # Extend period if already expired
        if subscription.is_expired():
            subscription.current_period_start = datetime.utcnow()
            if subscription.billing_cycle == BillingCycle.YEARLY:
                subscription.current_period_end = subscription.current_period_start + timedelta(days=365)
            else:
                subscription.current_period_end = subscription.current_period_start + timedelta(days=30)
        
        try:
            self.db.commit()
            self.db.refresh(subscription)
            
            # Create audit log
            self._create_audit_log(
                user_id=user_id,
                operation_type=AuditOperationType.UPDATE,
                entity_id=str(subscription.id),
                details={
                    "action": "reactivate",
                    "old_status": old_status.value,
                    "new_status": subscription.status.value,
                    "new_period_end": subscription.current_period_end.isoformat() if subscription.current_period_end else None,
                }
            )
            
            logger.info(f"Reactivated subscription for user {user_id}")
            
            return subscription
            
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Failed to reactivate subscription: {e}")
            raise ValueError(f"Failed to reactivate subscription: {e}")
    
    def check_subscription_status(self, user_id: int) -> Dict[str, Any]:
        """
        Check the current status of a user's subscription.
        
        Args:
            user_id: ID of the user
            
        Returns:
            Dictionary with subscription status details
        """
        subscription = self.get_user_subscription(user_id)
        
        if not subscription:
            return {
                "has_subscription": False,
                "status": None,
                "plan_type": PlanType.FREE,
                "is_active": False,
                "is_expired": False,
                "days_until_expiry": -1,
            }
        
        return {
            "has_subscription": True,
            "status": subscription.status,
            "plan_type": subscription.plan.plan_type,
            "is_active": subscription.is_active(),
            "is_expired": subscription.is_expired(),
            "is_in_grace_period": subscription.is_in_grace_period(),
            "can_access_features": subscription.can_access_features(),
            "days_until_expiry": subscription.days_until_expiry(),
            "cancel_at_period_end": subscription.cancel_at_period_end,
            "current_period_end": subscription.current_period_end,
        }
    
    def handle_trial_expiration(self, user_id: int) -> Optional[Subscription]:
        """
        Handle expiration of trial period.
        
        Per Requirement 5.4: Downgrade to Free tier when trial expires.
        
        Args:
            user_id: ID of the user
            
        Returns:
            Updated Subscription instance if trial was active, None otherwise
        """
        subscription = self.get_user_subscription(user_id)
        
        if not subscription:
            logger.warning(f"No subscription found for user {user_id}")
            return None
        
        if subscription.status != SubscriptionStatus.TRIALING:
            logger.info(f"User {user_id} subscription is not in trial status")
            return None
        
        # Check if trial has expired
        if not subscription.is_expired():
            logger.info(f"User {user_id} trial has not expired yet")
            return None
        
        # Get Free plan
        free_plan = self.db.query(Plan).filter(Plan.plan_type == PlanType.FREE).first()
        if not free_plan:
            logger.error("Free plan not found in database")
            raise ValueError("Free plan not found")
        
        old_plan_type = subscription.plan.plan_type
        
        # Downgrade to Free tier
        subscription.plan_id = free_plan.id
        subscription.status = SubscriptionStatus.ACTIVE
        subscription.current_period_start = datetime.utcnow()
        subscription.current_period_end = None  # Free tier has no expiration
        
        try:
            self.db.commit()
            self.db.refresh(subscription)
            
            # Create audit log
            self._create_audit_log(
                user_id=user_id,
                operation_type=AuditOperationType.UPDATE,
                entity_id=str(subscription.id),
                details={
                    "action": "trial_expired",
                    "old_plan_type": old_plan_type.value,
                    "new_plan_type": PlanType.FREE.value,
                    "old_status": SubscriptionStatus.TRIALING.value,
                    "new_status": SubscriptionStatus.ACTIVE.value,
                }
            )
            
            logger.info(f"Trial expired for user {user_id}, downgraded to Free tier")
            
            return subscription
            
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Failed to handle trial expiration: {e}")
            raise ValueError(f"Failed to handle trial expiration: {e}")
    
    def _create_audit_log(
        self,
        user_id: int,
        operation_type: AuditOperationType,
        entity_id: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Create an audit log entry for subscription changes.
        
        Per Requirement 6.4: All subscription changes must be logged.
        
        Args:
            user_id: ID of the user
            operation_type: Type of operation (CREATE, UPDATE, DELETE)
            entity_id: ID of the subscription
            details: Additional details about the change
        """
        audit_log = AuditLog(
            user_id=user_id,
            operation_type=operation_type,
            entity_type=AuditEntityType.TRANSACTION,  # Using TRANSACTION as placeholder
            entity_id=entity_id,
            details=details or {},
        )
        
        self.db.add(audit_log)
        # Note: commit is handled by the calling method
