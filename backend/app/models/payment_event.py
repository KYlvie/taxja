"""PaymentEvent model for Stripe webhook event logging"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from app.db.base import Base


class PaymentEvent(Base):
    """Payment event model for Stripe webhook logging"""
    __tablename__ = "payment_events"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Stripe event ID (unique for idempotency)
    stripe_event_id = Column(String(255), nullable=False, unique=True, index=True)
    
    # Event type (e.g., checkout.session.completed, invoice.payment_failed)
    event_type = Column(String(100), nullable=False, index=True)
    
    # Foreign key to user (nullable as some events may not have user context yet)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Event payload (full Stripe event data)
    payload = Column(JSONB, nullable=False)
    
    # Processing timestamp
    processed_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    # Creation timestamp
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="payment_events")
    
    @classmethod
    def is_duplicate(cls, session, stripe_event_id: str) -> bool:
        """Check if event has already been processed (idempotency check)
        
        Args:
            session: SQLAlchemy session
            stripe_event_id: Stripe event ID to check
            
        Returns:
            True if event already exists, False otherwise
        """
        existing = session.query(cls).filter(
            cls.stripe_event_id == stripe_event_id
        ).first()
        return existing is not None
    
    def get_event_data(self, key: str, default=None):
        """Get specific data from event payload
        
        Args:
            key: Key to retrieve from payload
            default: Default value if key not found
            
        Returns:
            Value from payload or default
        """
        if not self.payload:
            return default
        return self.payload.get(key, default)
    
    def get_customer_id(self) -> str | None:
        """Extract Stripe customer ID from payload
        
        Returns:
            Stripe customer ID or None
        """
        if not self.payload:
            return None
        
        # Try different payload structures
        data = self.payload.get('data', {})
        obj = data.get('object', {})
        
        # Direct customer field
        customer = obj.get('customer')
        if customer:
            return customer
        
        # Nested in subscription
        subscription = obj.get('subscription')
        if isinstance(subscription, dict):
            return subscription.get('customer')
        
        return None
    
    def get_subscription_id(self) -> str | None:
        """Extract Stripe subscription ID from payload
        
        Returns:
            Stripe subscription ID or None
        """
        if not self.payload:
            return None
        
        data = self.payload.get('data', {})
        obj = data.get('object', {})
        
        # Direct subscription field
        subscription = obj.get('subscription')
        if isinstance(subscription, str):
            return subscription
        elif isinstance(subscription, dict):
            return subscription.get('id')
        
        # For subscription events, object itself is the subscription
        if obj.get('object') == 'subscription':
            return obj.get('id')
        
        return None
    
    def __repr__(self):
        return f"<PaymentEvent(id={self.id}, stripe_event_id={self.stripe_event_id}, event_type={self.event_type})>"
