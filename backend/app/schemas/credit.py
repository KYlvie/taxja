"""Pydantic schemas for the Credit-Based Billing API (v1)."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class CreditBalanceResponse(BaseModel):
    """Current credit balance and overage status."""

    model_config = ConfigDict(from_attributes=True)

    plan_balance: int
    topup_balance: int
    total_balance: int
    available_without_overage: int
    monthly_credits: int
    overage_enabled: bool
    overage_credits_used: int
    overage_price_per_credit: Optional[Decimal] = None
    estimated_overage_cost: Decimal
    has_unpaid_overage: bool
    reset_date: Optional[datetime] = None


class CreditLedgerResponse(BaseModel):
    """Single credit ledger entry."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    operation: str
    operation_detail: Optional[str] = None
    status: str
    credit_amount: int
    source: str
    plan_balance_after: int
    topup_balance_after: int
    is_overage: bool
    overage_portion: int
    context_type: Optional[str] = None
    context_id: Optional[int] = None
    reason: Optional[str] = None
    pricing_version: int
    created_at: datetime


class CreditCostResponse(BaseModel):
    """Credit cost for a single operation."""

    operation: str
    credit_cost: int
    description: Optional[str] = None


class OverageEstimateResponse(BaseModel):
    """Current-period overage estimate."""

    overage_credits_used: int
    overage_price_per_credit: Optional[Decimal] = None
    estimated_cost: Decimal


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class TopupCheckoutRequest(BaseModel):
    """Request to start a top-up checkout session."""

    package_id: int


class TopupCheckoutResponse(BaseModel):
    """Checkout session details returned after creating a top-up."""

    checkout_url: str
    session_id: str


class OverageUpdateRequest(BaseModel):
    """Toggle overage on or off."""

    enabled: bool


class CreditEstimateRequest(BaseModel):
    """Request to estimate the cost of an operation."""

    operation: str
    quantity: int = Field(default=1, ge=1)


class CreditEstimateResponse(BaseModel):
    """Estimated cost and sufficiency for an operation."""

    operation: str
    cost: int
    sufficient: bool
    sufficient_without_overage: bool
    would_use_overage: bool
