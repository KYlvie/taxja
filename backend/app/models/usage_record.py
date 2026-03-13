"""UsageRecord model for tracking resource usage"""
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, Integer, DateTime, Enum as SQLEnum, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base


class ResourceType(str, Enum):
    """Resource type enumeration"""
    TRANSACTIONS = "transactions"
    OCR_SCANS = "ocr_scans"
    AI_CONVERSATIONS = "ai_conversations"


class UsageRecord(Base):
    """Usage tracking model for resource quotas"""
    __tablename__ = "usage_records"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign key
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Resource type
    resource_type = Column(SQLEnum(ResourceType), nullable=False, index=True)
    
    # Usage count
    count = Column(Integer, nullable=False, default=0)
    
    # Period tracking
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="usage_records")
    
    def increment(self, amount: int = 1) -> int:
        """Increment usage count
        
        Args:
            amount: Amount to increment by (default: 1)
            
        Returns:
            New count value after increment
        """
        self.count += amount
        self.updated_at = datetime.utcnow()
        return self.count
    
    def reset(self, new_period_start: datetime, new_period_end: datetime) -> None:
        """Reset usage count for new period
        
        Args:
            new_period_start: Start of new period
            new_period_end: End of new period
        """
        self.count = 0
        self.period_start = new_period_start
        self.period_end = new_period_end
        self.updated_at = datetime.utcnow()
    
    def is_current_period(self) -> bool:
        """Check if this record is for the current period
        
        Returns:
            True if current time is within period, False otherwise
        """
        now = datetime.utcnow()
        return self.period_start <= now <= self.period_end
    
    def get_usage_percentage(self, quota_limit: int) -> float:
        """Calculate usage as percentage of quota
        
        Args:
            quota_limit: Maximum allowed usage (-1 for unlimited)
            
        Returns:
            Usage percentage (0.0 to 100.0), 0.0 for unlimited quotas
        """
        if quota_limit == -1:  # Unlimited
            return 0.0
        if quota_limit == 0:  # No quota defined
            return 0.0
        
        return (self.count / quota_limit) * 100.0
    
    def is_quota_exceeded(self, quota_limit: int) -> bool:
        """Check if usage has exceeded quota
        
        Args:
            quota_limit: Maximum allowed usage (-1 for unlimited)
            
        Returns:
            True if quota exceeded, False otherwise
        """
        if quota_limit == -1:  # Unlimited
            return False
        if quota_limit == 0:  # No quota defined
            return True
        
        return self.count >= quota_limit
    
    def is_near_quota_limit(self, quota_limit: int, threshold: float = 80.0) -> bool:
        """Check if usage is near quota limit
        
        Args:
            quota_limit: Maximum allowed usage (-1 for unlimited)
            threshold: Percentage threshold for warning (default: 80.0)
            
        Returns:
            True if usage is at or above threshold, False otherwise
        """
        if quota_limit == -1:  # Unlimited
            return False
        
        usage_pct = self.get_usage_percentage(quota_limit)
        return usage_pct >= threshold
    
    def __repr__(self):
        return f"<UsageRecord(id={self.id}, user_id={self.user_id}, resource_type={self.resource_type}, count={self.count})>"
