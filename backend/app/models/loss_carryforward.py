"""Loss carryforward model for multi-year loss tracking"""
from datetime import datetime
from decimal import Decimal
from sqlalchemy import Column, Integer, Numeric, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.db.base import Base


class LossCarryforward(Base):
    """Loss carryforward model for tracking losses across tax years"""
    __tablename__ = "loss_carryforwards"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign key to user
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Loss year (the year the loss occurred)
    loss_year = Column(Integer, nullable=False, index=True)
    
    # Loss amount (original loss amount)
    loss_amount = Column(Numeric(12, 2), nullable=False)
    
    # Used amount (amount already used in subsequent years)
    used_amount = Column(Numeric(12, 2), nullable=False, default=0.00)
    
    # Remaining amount (loss_amount - used_amount)
    remaining_amount = Column(Numeric(12, 2), nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="loss_carryforwards")
    
    # Unique constraint: one loss carryforward record per user per year
    __table_args__ = (
        UniqueConstraint('user_id', 'loss_year', name='uq_user_loss_year'),
    )
    
    def __repr__(self):
        return f"<LossCarryforward(user_id={self.user_id}, year={self.loss_year}, remaining={self.remaining_amount})>"
