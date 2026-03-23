"""Credit API endpoints for the Credit-Based Billing system (v1).

Provides balance queries, ledger history, cost lookup, top-up checkout,
overage management, and cost estimation.
"""

import logging
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.error_messages import get_error_message
from app.core.security import get_current_user
from app.db.base import get_db
from app.models.user import User
from app.schemas.credit import (
    CreditBalanceResponse,
    CreditCostResponse,
    CreditEstimateRequest,
    CreditEstimateResponse,
    CreditLedgerResponse,
    OverageEstimateResponse,
    OverageUpdateRequest,
    TopupCheckoutRequest,
    TopupCheckoutResponse,
)
from app.services.credit_service import (
    CreditService,
    InsufficientCreditsError,
    OverageNotAvailableError,
    OverageSuspendedError,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _credit_service(db: Session) -> CreditService:
    """Build a CreditService with no Redis dependency (v1)."""
    return CreditService(db=db, redis_client=None)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/balance", response_model=CreditBalanceResponse)
def get_balance(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the current user's credit balance and overage status."""
    svc = _credit_service(db)
    info = svc.get_balance(current_user.id)
    return CreditBalanceResponse(
        plan_balance=info.plan_balance,
        topup_balance=info.topup_balance,
        total_balance=info.total_balance,
        available_without_overage=info.available_without_overage,
        monthly_credits=info.monthly_credits,
        overage_enabled=info.overage_enabled,
        overage_credits_used=info.overage_credits_used,
        overage_price_per_credit=info.overage_price_per_credit,
        estimated_overage_cost=info.estimated_overage_cost,
        has_unpaid_overage=info.has_unpaid_overage,
        reset_date=info.reset_date,
    )


@router.get("/history", response_model=List[CreditLedgerResponse])
def get_history(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return paginated credit ledger entries for the current user."""
    svc = _credit_service(db)
    entries = svc.get_ledger(current_user.id, limit=limit, offset=offset)
    return [
        CreditLedgerResponse(
            id=e.id,
            operation=e.operation.value if hasattr(e.operation, "value") else str(e.operation),
            operation_detail=e.operation_detail,
            status=e.status.value if hasattr(e.status, "value") else str(e.status),
            credit_amount=e.credit_amount,
            source=e.source.value if hasattr(e.source, "value") else str(e.source),
            plan_balance_after=e.plan_balance_after,
            topup_balance_after=e.topup_balance_after,
            is_overage=e.is_overage,
            overage_portion=e.overage_portion,
            context_type=e.context_type,
            context_id=e.context_id,
            reason=e.reason,
            pricing_version=e.pricing_version,
            created_at=e.created_at,
        )
        for e in entries
    ]


@router.get("/costs", response_model=List[CreditCostResponse])
def get_costs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return all active operation credit costs."""
    from app.models.credit_cost_config import CreditCostConfig

    configs = (
        db.query(CreditCostConfig)
        .filter(CreditCostConfig.is_active == True)  # noqa: E712
        .all()
    )
    return [
        CreditCostResponse(
            operation=c.operation,
            credit_cost=c.credit_cost,
            description=c.description,
        )
        for c in configs
    ]


@router.post("/topup", response_model=TopupCheckoutResponse)
def create_topup(
    body: TopupCheckoutRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a top-up checkout session.

    v1 stub: in dev mode, directly adds credits and returns a mock checkout URL.
    """
    from app.models.credit_topup_package import CreditTopupPackage

    package = db.query(CreditTopupPackage).filter(
        CreditTopupPackage.id == body.package_id,
        CreditTopupPackage.is_active == True,  # noqa: E712
    ).first()
    if package is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid or inactive package_id: {body.package_id}",
        )

    # v1 dev mode: directly add credits (no real Stripe checkout)
    svc = _credit_service(db)
    fake_payment_id = f"dev_{uuid.uuid4().hex[:16]}"
    try:
        svc.add_topup_credits(
            user_id=current_user.id,
            amount=package.credits,
            stripe_payment_id=fake_payment_id,
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to persist top-up credits for user %s", current_user.id)
        language = getattr(current_user, 'language', 'de') or 'de'
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=get_error_message("failed_add_topup_credits", language),
        )

    return TopupCheckoutResponse(
        checkout_url=f"https://checkout.stripe.com/dev/session/{fake_payment_id}",
        session_id=fake_payment_id,
    )


@router.put("/overage", response_model=CreditBalanceResponse)
def update_overage(
    body: OverageUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Enable or disable overage for the current user."""
    svc = _credit_service(db)
    try:
        info = svc.set_overage_enabled(current_user.id, body.enabled)
        db.commit()
    except OverageNotAvailableError:
        db.rollback()
        language = getattr(current_user, 'language', 'de') or 'de'
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=get_error_message("overage_not_available", language),
        )
    except OverageSuspendedError:
        db.rollback()
        language = getattr(current_user, 'language', 'de') or 'de'
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=get_error_message("overage_suspended", language),
        )
    except Exception:
        db.rollback()
        logger.exception("Failed to update overage for user %s", current_user.id)
        language = getattr(current_user, 'language', 'de') or 'de'
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=get_error_message("failed_update_overage", language),
        )
    return CreditBalanceResponse(
        plan_balance=info.plan_balance,
        topup_balance=info.topup_balance,
        total_balance=info.total_balance,
        available_without_overage=info.available_without_overage,
        monthly_credits=info.monthly_credits,
        overage_enabled=info.overage_enabled,
        overage_credits_used=info.overage_credits_used,
        overage_price_per_credit=info.overage_price_per_credit,
        estimated_overage_cost=info.estimated_overage_cost,
        has_unpaid_overage=info.has_unpaid_overage,
        reset_date=info.reset_date,
    )


@router.get("/overage/estimate", response_model=OverageEstimateResponse)
def get_overage_estimate(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the current period's overage cost estimate."""
    svc = _credit_service(db)
    info = svc.get_balance(current_user.id)
    return OverageEstimateResponse(
        overage_credits_used=info.overage_credits_used,
        overage_price_per_credit=info.overage_price_per_credit,
        estimated_cost=info.estimated_overage_cost,
    )


@router.post("/estimate", response_model=CreditEstimateResponse)
def estimate_cost(
    body: CreditEstimateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Estimate the credit cost of an operation (read-only, no side effects)."""
    svc = _credit_service(db)
    try:
        result = svc.estimate_cost(
            user_id=current_user.id,
            operation=body.operation,
            quantity=body.quantity,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    return CreditEstimateResponse(
        operation=result.operation,
        cost=result.cost,
        sufficient=result.sufficient,
        sufficient_without_overage=result.sufficient_without_overage,
        would_use_overage=result.would_use_overage,
    )
