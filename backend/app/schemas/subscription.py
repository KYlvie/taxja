"""Subscription schemas for request/response validation"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
from app.models.plan import PlanType, BillingCycle
from app.models.subscription import SubscriptionStatus
from app.models.usage_record import ResourceType


# ============================================================================
# Plan Schemas
# ============================================================================

class PlanBase(BaseModel):
    """Base plan schema"""
    plan_type: PlanType
    name: str = Field(..., min_length=1, max_length=100)
    monthly_price: Decimal = Field(..., ge=0)
    yearly_price: Decimal = Field(..., ge=0)
    features: Dict[str, bool] = Field(default_factory=dict)
    quotas: Dict[str, int] = Field(default_factory=dict)
    
    @field_validator('features')
    @classmethod
    def validate_features(cls, v: Dict[str, bool]) -> Dict[str, bool]:
        """Validate that all feature values are boolean"""
        if not isinstance(v, dict):
            raise ValueError('Features must be a dictionary')
        for key, value in v.items():
            if not isinstance(value, bool):
                raise ValueError(f'Feature {key} must be a boolean value')
        return v
    
    @field_validator('quotas')
    @classmethod
    def validate_quotas(cls, v: Dict[str, int]) -> Dict[str, int]:
        """Validate that all quota values are integers >= -1"""
        if not isinstance(v, dict):
            raise ValueError('Quotas must be a dictionary')
        for key, value in v.items():
            if not isinstance(value, int):
                raise ValueError(f'Quota {key} must be an integer')
            if value < -1:
                raise ValueError(f'Quota {key} must be >= -1 (-1 for unlimited)')
        return v


class PlanCreate(PlanBase):
    """Schema for creating a new plan"""
    pass


class PlanUpdate(BaseModel):
    """Schema for updating an existing plan"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    monthly_price: Optional[Decimal] = Field(None, ge=0)
    yearly_price: Optional[Decimal] = Field(None, ge=0)
    features: Optional[Dict[str, bool]] = None
    quotas: Optional[Dict[str, int]] = None
    
    @field_validator('features')
    @classmethod
    def validate_features(cls, v: Optional[Dict[str, bool]]) -> Optional[Dict[str, bool]]:
        """Validate that all feature values are boolean"""
        if v is None:
            return v
        if not isinstance(v, dict):
            raise ValueError('Features must be a dictionary')
        for key, value in v.items():
            if not isinstance(value, bool):
                raise ValueError(f'Feature {key} must be a boolean value')
        return v
    
    @field_validator('quotas')
    @classmethod
    def validate_quotas(cls, v: Optional[Dict[str, int]]) -> Optional[Dict[str, int]]:
        """Validate that all quota values are integers >= -1"""
        if v is None:
            return v
        if not isinstance(v, dict):
            raise ValueError('Quotas must be a dictionary')
        for key, value in v.items():
            if not isinstance(value, int):
                raise ValueError(f'Quota {key} must be an integer')
            if value < -1:
                raise ValueError(f'Quota {key} must be >= -1 (-1 for unlimited)')
        return v


class PlanResponse(PlanBase):
    """Schema for plan response"""
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# ============================================================================
# Subscription Schemas
# ============================================================================

class SubscriptionBase(BaseModel):
    """Base subscription schema"""
    plan_id: int
    status: SubscriptionStatus
    billing_cycle: Optional[BillingCycle] = None


class SubscriptionCreate(SubscriptionBase):
    """Schema for creating a new subscription"""
    user_id: int
    stripe_subscription_id: Optional[str] = Field(None, max_length=255)
    stripe_customer_id: Optional[str] = Field(None, max_length=255)
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: bool = False


class SubscriptionUpdate(BaseModel):
    """Schema for updating an existing subscription"""
    plan_id: Optional[int] = None
    status: Optional[SubscriptionStatus] = None
    billing_cycle: Optional[BillingCycle] = None
    stripe_subscription_id: Optional[str] = Field(None, max_length=255)
    stripe_customer_id: Optional[str] = Field(None, max_length=255)
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: Optional[bool] = None


class SubscriptionCreditInfo(BaseModel):
    """Credit balance info embedded in subscription response (transition period)."""
    plan_balance: int
    topup_balance: int
    total_balance: int
    available_without_overage: int
    monthly_credits: int
    overage_enabled: bool
    overage_credits_used: int
    overage_price_per_credit: Optional[Decimal] = None
    estimated_overage_cost: Decimal = Decimal(0)
    has_unpaid_overage: bool = False
    reset_date: Optional[datetime] = None


class SubscriptionResponse(BaseModel):
    """Schema for subscription response"""
    id: int
    user_id: int
    plan_id: int
    status: SubscriptionStatus
    billing_cycle: Optional[BillingCycle] = None
    stripe_subscription_id: Optional[str] = None
    stripe_customer_id: Optional[str] = None
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: bool = False
    created_at: datetime
    updated_at: datetime
    credit_balance: Optional[SubscriptionCreditInfo] = None
    
    class Config:
        from_attributes = True


# ============================================================================
# Usage Record Schemas
# ============================================================================

class UsageRecordResponse(BaseModel):
    """Schema for usage record response"""
    id: int
    user_id: int
    resource_type: ResourceType
    count: int
    period_start: datetime
    period_end: datetime
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class UsageQuotaResponse(BaseModel):
    """Schema for usage quota summary response"""
    resource_type: ResourceType
    current_usage: int
    quota_limit: int  # -1 for unlimited
    usage_percentage: float
    is_exceeded: bool
    is_near_limit: bool  # >= 80%
    period_start: datetime
    period_end: datetime
    
    @field_validator('usage_percentage')
    @classmethod
    def validate_percentage(cls, v: float) -> float:
        """Ensure percentage is between 0 and 100"""
        return max(0.0, min(100.0, v))


# ============================================================================
# Checkout and Payment Schemas
# ============================================================================

class CheckoutSessionRequest(BaseModel):
    """Schema for creating a Stripe checkout session"""
    plan_id: int = Field(..., gt=0)
    billing_cycle: BillingCycle
    success_url: str = Field(..., min_length=1)
    cancel_url: str = Field(..., min_length=1)


class CheckoutSessionResponse(BaseModel):
    """Schema for checkout session response"""
    session_id: str
    url: str


class PaymentEventResponse(BaseModel):
    """Schema for payment event response"""
    id: int
    stripe_event_id: str
    event_type: str
    user_id: Optional[int] = None
    payload: Dict[str, Any]
    processed_at: datetime
    created_at: datetime
    
    class Config:
        from_attributes = True
