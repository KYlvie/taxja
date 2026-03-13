"""Trial service for managing 14-day Pro trial"""
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import logging

from app.models.user import User
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.plan import Plan, PlanType
from app.services.subscription_service import SubscriptionService
from app.services.notification_service import NotificationService


logger = logging.getLogger(__name__)


class TrialService:
    """Service for managing trial subscriptions"""
    
    TRIAL_DURATION_DAYS = 14
    REMINDER_DAYS_BEFORE_EXPIRY = 3
    
    def __init__(self, db: Session):
        """
        Initialize trial service.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.subscription_service = SubscriptionService(db)
        self.notification_service = NotificationService(db)
    
    def activate_trial(self, user_id: int) -> Subscription:
        """
        Activate 14-day Pro trial for new user.
        
        Per Requirement 5.1: New users get 14-day Pro trial.
        Per Requirement 5.2: Only one trial per user.
        
        Args:
            user_id: ID of the user
            
        Returns:
            Created trial Subscription instance
            
        Raises:
            ValueError: If user not found or trial already used
        """
        # Get user
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"User {user_id} not found")
        
        # Check if trial already used
        if user.trial_used:
            raise ValueError(f"User {user_id} has already used their trial")
        
        # Check if user already has a subscription
        existing_sub = self.subscription_service.get_user_subscription(user_id)
        if existing_sub:
            raise ValueError(f"User {user_id} already has an active subscription")
        
        # Get Pro plan
        pro_plan = self.db.query(Plan).filter(Plan.plan_type == PlanType.PRO).first()
        if not pro_plan:
            raise ValueError("Pro plan not found in database")
        
        # Calculate trial period
        trial_start = datetime.utcnow()
        trial_end = trial_start + timedelta(days=self.TRIAL_DURATION_DAYS)
        
        # Create trial subscription
        subscription = self.subscription_service.create_subscription(
            user_id=user_id,
            plan_id=pro_plan.id,
            status=SubscriptionStatus.TRIALING,
            current_period_start=trial_start,
            current_period_end=trial_end
        )
        
        # Mark trial as used
        user.trial_used = True
        user.trial_end_date = trial_end
        
        try:
            self.db.commit()
            self.db.refresh(subscription)
            
            logger.info(
                f"Activated 14-day Pro trial for user {user_id}: "
                f"expires {trial_end.strftime('%Y-%m-%d')}"
            )
            
            # Send welcome email with trial info
            self._send_trial_welcome_notification(user, trial_end)
            
            return subscription
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to activate trial: {e}")
            raise
    
    def check_trial_status(self, user_id: int) -> Dict[str, Any]:
        """
        Check trial status for a user.
        
        Args:
            user_id: ID of the user
            
        Returns:
            Dictionary with trial status information
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"User {user_id} not found")
        
        subscription = self.subscription_service.get_user_subscription(user_id)
        
        if not subscription or subscription.status != SubscriptionStatus.TRIALING:
            return {
                'is_trial': False,
                'trial_used': user.trial_used,
                'trial_available': not user.trial_used
            }
        
        days_remaining = subscription.days_until_expiry()
        
        return {
            'is_trial': True,
            'trial_used': user.trial_used,
            'trial_available': False,
            'trial_end_date': subscription.current_period_end.isoformat(),
            'days_remaining': days_remaining,
            'is_expiring_soon': days_remaining <= self.REMINDER_DAYS_BEFORE_EXPIRY
        }
    
    def ensure_single_trial_per_user(self, user_id: int) -> bool:
        """
        Validate that user hasn't already used their trial.
        
        Per Requirement 5.2: Enforce single trial per user.
        
        Args:
            user_id: ID of the user
            
        Returns:
            True if user can start trial, False if already used
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return False
        
        return not user.trial_used
    
    def send_trial_expiration_reminder(self, user_id: int) -> None:
        """
        Send reminder email 3 days before trial expires.
        
        Per Requirement 5.3: Send reminder 3 days before expiry.
        
        Args:
            user_id: ID of the user
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.error(f"User {user_id} not found for trial reminder")
            return
        
        subscription = self.subscription_service.get_user_subscription(user_id)
        
        if not subscription or subscription.status != SubscriptionStatus.TRIALING:
            logger.warning(f"User {user_id} is not in trial status")
            return
        
        days_remaining = subscription.days_until_expiry()
        
        if days_remaining != self.REMINDER_DAYS_BEFORE_EXPIRY:
            logger.info(
                f"Trial reminder not sent for user {user_id}: "
                f"{days_remaining} days remaining (expected {self.REMINDER_DAYS_BEFORE_EXPIRY})"
            )
            return
        
        # Send reminder notification
        try:
            self.notification_service.create_notification(
                user_id=user_id,
                title="Your Pro Trial is Expiring Soon",
                message=(
                    f"Your 14-day Pro trial will expire in {days_remaining} days. "
                    "Upgrade now to keep access to all Pro features!"
                ),
                notification_type="trial_expiring",
                priority="high"
            )
            
            logger.info(f"Sent trial expiration reminder to user {user_id}")
            
        except Exception as e:
            logger.error(f"Failed to send trial reminder to user {user_id}: {e}")
    
    def handle_trial_end(self, user_id: int) -> Optional[Subscription]:
        """
        Handle trial expiration - downgrade to Free tier.
        
        Per Requirement 5.4: Downgrade to Free tier when trial expires.
        
        Args:
            user_id: ID of the user
            
        Returns:
            Updated Subscription instance or None
        """
        # Delegate to SubscriptionService which has the logic
        return self.subscription_service.handle_trial_expiration(user_id)
    
    def get_trial_eligible_users(self) -> list:
        """
        Get list of users eligible for trial activation.
        
        Returns:
            List of User instances eligible for trial
        """
        users = (
            self.db.query(User)
            .filter(User.trial_used == False)
            .filter(~User.subscription.has())  # No existing subscription
            .all()
        )
        
        return users
    
    def get_expiring_trials(self, days_threshold: int = 3) -> list:
        """
        Get list of trials expiring within threshold days.
        
        Args:
            days_threshold: Number of days before expiry
            
        Returns:
            List of Subscription instances expiring soon
        """
        threshold_date = datetime.utcnow() + timedelta(days=days_threshold)
        
        subscriptions = (
            self.db.query(Subscription)
            .filter(Subscription.status == SubscriptionStatus.TRIALING)
            .filter(Subscription.current_period_end <= threshold_date)
            .filter(Subscription.current_period_end > datetime.utcnow())
            .all()
        )
        
        return subscriptions
    
    def get_expired_trials(self) -> list:
        """
        Get list of expired trials that need to be downgraded.
        
        Returns:
            List of expired trial Subscription instances
        """
        now = datetime.utcnow()
        
        subscriptions = (
            self.db.query(Subscription)
            .filter(Subscription.status == SubscriptionStatus.TRIALING)
            .filter(Subscription.current_period_end < now)
            .all()
        )
        
        return subscriptions
    
    def _send_trial_welcome_notification(self, user: User, trial_end: datetime) -> None:
        """Send welcome notification for trial activation"""
        try:
            self.notification_service.create_notification(
                user_id=user.id,
                title="Welcome to Your 14-Day Pro Trial!",
                message=(
                    f"Your Pro trial is active until {trial_end.strftime('%B %d, %Y')}. "
                    "Enjoy unlimited access to all Pro features including AI Assistant, "
                    "unlimited OCR scanning, and E1 form generation!"
                ),
                notification_type="trial_started",
                priority="normal"
            )
            
            logger.info(f"Sent trial welcome notification to user {user.id}")
            
        except Exception as e:
            logger.error(f"Failed to send trial welcome notification: {e}")
