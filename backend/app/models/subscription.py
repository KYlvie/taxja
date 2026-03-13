"""Subscription model for user subscriptions"""
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum as SQLEnum, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.models.plan import BillingCycle


class SubscriptionStatus(str, Enum):
    """Subscription status enumeration"""
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    TRIALING = "trialing"


class Subscription(Base):
    """User subscription model"""
    __tablename__ = "subscriptions"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign keys
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    plan_id = Column(Integer, ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False, index=True)
    
    # Subscription status
    status = Column(
        SQLEnum(SubscriptionStatus, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False, index=True
    )
    
    # Billing cycle
    billing_cycle = Column(
        SQLEnum(BillingCycle, values_callable=lambda obj: [e.value for e in obj]),
        nullable=True
    )
    
    # Stripe integration
    stripe_subscription_id = Column(String(255), nullable=True, unique=True, index=True)
    stripe_customer_id = Column(String(255), nullable=True, index=True)
    
    # Subscription period
    current_period_start = Column(DateTime, nullable=True)
    current_period_end = Column(DateTime, nullable=True, index=True)
    
    # Cancellation flag
    cancel_at_period_end = Column(Boolean, nullable=False, default=False)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="subscription", foreign_keys=[user_id])
    plan = relationship("Plan", back_populates="subscriptions")
    
    def is_active(self) -> bool:
        """Check if subscription is currently active
        
        Returns:
            True if subscription is active or trialing, False otherwise
        """
        return self.status in [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING]
    
    def is_trialing(self) -> bool:
        """Check if subscription is in trial period
        
        Returns:
            True if subscription status is trialing, False otherwise
        """
        return self.status == SubscriptionStatus.TRIALING
    
    def is_expired(self) -> bool:
        """Check if subscription has expired
        
        Returns:
            True if subscription period has ended, False otherwise
        """
        if not self.current_period_end:
            return False
        return datetime.utcnow() > self.current_period_end
    
    def is_in_grace_period(self) -> bool:
        """Check if subscription is in grace period (past_due but not expired)
        
        Returns:
            True if subscription is past_due, False otherwise
        """
        return self.status == SubscriptionStatus.PAST_DUE
    
    def can_access_features(self) -> bool:
        """Check if user can access paid features
        
        Returns:
            True if subscription allows feature access, False otherwise
        """
        # Active and trialing subscriptions have full access
        # Past due subscriptions have grace period access
        return self.status in [
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.TRIALING,
            SubscriptionStatus.PAST_DUE
        ]
    
    def days_until_expiry(self) -> int:
        """Calculate days until subscription expires
        
        Returns:
            Number of days until expiry, 0 if already expired, -1 if no end date
        """
        if not self.current_period_end:
            return -1
        
        delta = self.current_period_end - datetime.utcnow()
        days = delta.days
        return max(0, days)
    
    def days_until_renewal(self) -> int:
        """Calculate days until subscription renews (alias for days_until_expiry)
        
        Returns:
            Number of days until renewal, 0 if already expired, -1 if no end date
        """
        return self.days_until_expiry()
    
    def __repr__(self):
        return f"<Subscription(id={self.id}, user_id={self.user_id}, status={self.status})>"
