"""TopupPurchase model for tracking top-up credit purchases and expiry"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey, Numeric,
)
from sqlalchemy.orm import relationship
from app.db.base import Base


class TopupPurchase(Base):
    """Tracks individual top-up credit purchases with expiry (12 months)"""
    __tablename__ = "topup_purchases"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    credits_purchased = Column(Integer, nullable=False)
    credits_remaining = Column(Integer, nullable=False)
    price_paid = Column(Numeric(10, 2), nullable=False)
    stripe_payment_id = Column(String(255), nullable=True)
    purchased_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    is_expired = Column(Boolean, nullable=False, default=False)

    user = relationship("User", back_populates="topup_purchases")

    def __repr__(self):
        return (
            f"<TopupPurchase(id={self.id}, user_id={self.user_id}, "
            f"purchased={self.credits_purchased}, remaining={self.credits_remaining})>"
        )
