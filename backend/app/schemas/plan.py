"""Plan schemas for API requests and responses"""
from typing import Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from app.models.plan import PlanType


class PlanBase(BaseModel):
    """Base plan schema"""
    plan_type: PlanType
    name: str
    monthly_price: float = Field(ge=0)
    yearly_price: float = Field(ge=0)
    features: Dict[str, Any] = Field(default_factory=dict)
    quotas: Dict[str, Any] = Field(default_factory=dict)


class PlanCreate(PlanBase):
    """Schema for creating a new plan"""
    pass


class PlanUpdate(BaseModel):
    """Schema for updating a plan"""
    name: str | None = None
    monthly_price: float | None = Field(None, ge=0)
    yearly_price: float | None = Field(None, ge=0)
    features: Dict[str, Any] | None = None
    quotas: Dict[str, Any] | None = None


class PlanResponse(PlanBase):
    """Schema for plan response"""
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
