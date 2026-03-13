"""Plan model for subscription plans"""
from datetime import datetime
from enum import Enum
from typing import Dict, Any, List
from sqlalchemy import Column, Integer, String, Numeric, DateTime, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from app.db.base import Base


class PlanType(str, Enum):
    """Plan type enumeration"""
    FREE = "free"
    PLUS = "plus"
    PRO = "pro"


class BillingCycle(str, Enum):
    """Billing cycle enumeration"""
    MONTHLY = "monthly"
    YEARLY = "yearly"


class Plan(Base):
    """Subscription plan model"""
    __tablename__ = "plans"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Plan type (unique)
    plan_type = Column(
        SQLEnum(PlanType, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False, unique=True, index=True
    )
    
    # Plan name
    name = Column(String(100), nullable=False)
    
    # Pricing
    monthly_price = Column(Numeric(10, 2), nullable=False)
    yearly_price = Column(Numeric(10, 2), nullable=False)
    
    # Features and quotas (stored as JSON)
    features = Column(JSONB, nullable=False, default={})
    quotas = Column(JSONB, nullable=False, default={})
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    subscriptions = relationship("Subscription", back_populates="plan")
    
    def has_feature(self, feature_name: str) -> bool:
        """Check if plan includes a specific feature
        
        Args:
            feature_name: Name of the feature to check
            
        Returns:
            True if feature is included in plan, False otherwise
        """
        if not self.features:
            return False
        return self.features.get(feature_name, False) is True
    
    def get_quota(self, resource_type: str) -> int:
        """Get quota limit for a specific resource type
        
        Args:
            resource_type: Type of resource (e.g., 'transactions', 'ocr_scans')
            
        Returns:
            Quota limit as integer, -1 for unlimited, 0 if not defined
        """
        if not self.quotas:
            return 0
        return self.quotas.get(resource_type, 0)
    
    def is_unlimited(self, resource_type: str) -> bool:
        """Check if a resource has unlimited quota
        
        Args:
            resource_type: Type of resource to check
            
        Returns:
            True if quota is unlimited (-1), False otherwise
        """
        return self.get_quota(resource_type) == -1
    
    def validate_features(self) -> bool:
        """Validate that features is a valid dictionary
        
        Returns:
            True if features is valid, False otherwise
        """
        if not isinstance(self.features, dict):
            return False
        # All feature values should be boolean
        return all(isinstance(v, bool) for v in self.features.values())
    
    def validate_quotas(self) -> bool:
        """Validate that quotas is a valid dictionary
        
        Returns:
            True if quotas is valid, False otherwise
        """
        if not isinstance(self.quotas, dict):
            return False
        # All quota values should be integers
        return all(isinstance(v, int) and v >= -1 for v in self.quotas.values())
    
    def __repr__(self):
        return f"<Plan(id={self.id}, plan_type={self.plan_type}, name={self.name})>"
