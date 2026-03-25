"""Subscription management API endpoints"""
from typing import List
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Header, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.plan import Plan, PlanType, BillingCycle
from app.models.subscription import Subscription, SubscriptionStatus
from app.schemas.subscription import (
    PlanResponse,
    SubscriptionResponse,
    CheckoutSessionRequest,
    CheckoutSessionResponse,
    UsageQuotaResponse
)
from app.services.plan_service import PlanService
from app.services.subscription_service import SubscriptionService
from app.services.usage_tracker_service import UsageTrackerService
from app.services.feature_gate_service import FeatureGateService
from app.services.credit_service import CreditService
from app.schemas.subscription import SubscriptionCreditInfo
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


def _is_stripe_configured() -> bool:
    """Check if Stripe API keys are properly configured (not placeholder values)."""
    from app.core.config import settings
    key = settings.STRIPE_SECRET_KEY
    if not key:
        return False
    if "your_" in key or key.startswith("sk_test_your"):
        return False
    return True


def _build_subscription_response_with_credits(
    subscription: Subscription,
    current_user: User,
    db: Session,
) -> SubscriptionResponse:
    response = SubscriptionResponse.model_validate(subscription)
    try:
        credit_service = CreditService(db)
        balance_info = credit_service.get_balance(current_user.id)
        response.credit_balance = SubscriptionCreditInfo(
            plan_balance=balance_info.plan_balance,
            topup_balance=balance_info.topup_balance,
            total_balance=balance_info.total_balance,
            available_without_overage=balance_info.available_without_overage,
            monthly_credits=balance_info.monthly_credits,
            overage_enabled=balance_info.overage_enabled,
            overage_credits_used=balance_info.overage_credits_used,
            overage_price_per_credit=balance_info.overage_price_per_credit,
            estimated_overage_cost=balance_info.estimated_overage_cost,
            has_unpaid_overage=balance_info.has_unpaid_overage,
            reset_date=balance_info.reset_date,
        )
    except Exception:
        logger.warning(f"Failed to fetch credit balance for user {current_user.id}", exc_info=True)
    return response


@router.get("/plans", response_model=List[PlanResponse])
def list_plans(
    db: Session = Depends(get_db)
):
    """
    List all available subscription plans with features and quotas.
    
    Per Requirement 6.1: Public endpoint to view plans.
    """
    plan_service = PlanService(db)
    plans = plan_service.list_plans()
    
    return [
        PlanResponse(
            id=plan.id,
            plan_type=plan.plan_type,
            name=plan.name,
            monthly_price=plan.monthly_price,
            yearly_price=plan.yearly_price,
            features=plan.features,
            quotas=plan.quotas,
            created_at=plan.created_at,
            updated_at=plan.updated_at
        )
        for plan in plans
    ]


@router.get("/current", response_model=SubscriptionResponse)
def get_current_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current user's subscription details.
    Admin users get a virtual Pro subscription (no DB record needed).
    Auto-creates a Free plan subscription for regular users if none exists.
    Expired/canceled subscriptions are auto-downgraded to Free.
    """
    subscription_service = SubscriptionService(db)
    subscription = subscription_service.get_user_subscription(current_user.id)

    # Auto-downgrade expired/canceled subscriptions to Free
    if subscription and subscription.status == SubscriptionStatus.CANCELED and subscription.is_expired():
        free_plan = db.query(Plan).filter(Plan.plan_type == "free").first()
        if free_plan and subscription.plan_id != free_plan.id:
            old_plan_type = subscription.plan.plan_type if subscription.plan else "unknown"
            subscription.plan_id = free_plan.id
            subscription.status = SubscriptionStatus.ACTIVE
            subscription.current_period_start = datetime.utcnow()
            subscription.current_period_end = None  # Free tier has no expiration
            subscription.cancel_at_period_end = False
            # Reset credit balance to Free plan level
            try:
                from app.models.credit_balance import CreditBalance
                credit_balance = db.query(CreditBalance).filter(
                    CreditBalance.user_id == current_user.id
                ).first()
                if credit_balance:
                    credit_balance.plan_balance = free_plan.monthly_credits or 100
                    credit_balance.overage_credits_used = 0
                    credit_balance.overage_enabled = False
                # Invalidate Redis credit cache
                try:
                    from app.core.config import settings
                    import redis as redis_lib
                    r = redis_lib.from_url(settings.REDIS_URL)
                    r.delete(f"credit_balance:{current_user.id}")
                except Exception:
                    pass
            except Exception:
                logger.warning(f"Failed to reset credit balance for user {current_user.id}", exc_info=True)
            db.commit()
            db.refresh(subscription)
            logger.info(
                f"Auto-downgraded expired subscription for user {current_user.id}: "
                f"{old_plan_type} -> free"
            )

    if not subscription:
        # Auto-create free subscription for the user (including admin)
        free_plan = db.query(Plan).filter(Plan.plan_type == "free").first()
        if free_plan:
            try:
                subscription = subscription_service.create_subscription(
                    user_id=current_user.id,
                    plan_id=free_plan.id,
                    status=SubscriptionStatus.ACTIVE,
                )
                logger.info(f"Auto-created free subscription for user {current_user.id}")
            except ValueError:
                pass
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active subscription found"
        )
    
    return _build_subscription_response_with_credits(subscription, current_user, db)


@router.post("/checkout", response_model=CheckoutSessionResponse)
def create_checkout_session(
    request: CheckoutSessionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create checkout session for subscription.
    
    In dev mode (Stripe not configured): directly activates the subscription
    and returns a redirect URL to the success page.
    
    In production (Stripe configured): creates a real Stripe checkout session.
    """
    # Verify plan exists and is not free
    plan = db.query(Plan).filter(Plan.id == request.plan_id).first()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan {request.plan_id} not found"
        )
    if plan.plan_type == "free":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create checkout for free plan"
        )

    if not _is_stripe_configured():
        # DEV MODE: directly activate subscription without Stripe
        logger.info(
            f"Dev mode checkout: activating {plan.plan_type} for user {current_user.id}"
        )
        subscription_service = SubscriptionService(db)
        previous = subscription_service.get_user_subscription(current_user.id)
        previous_plan_type = previous.plan.plan_type if previous and previous.plan else None

        # Check for existing subscription
        existing = previous
        if existing:
            # Update existing subscription
            existing.plan_id = plan.id
            existing.status = SubscriptionStatus.ACTIVE
            existing.billing_cycle = request.billing_cycle
            existing.current_period_start = datetime.utcnow()
            if request.billing_cycle == BillingCycle.YEARLY:
                existing.current_period_end = datetime.utcnow() + timedelta(days=365)
            else:
                existing.current_period_end = datetime.utcnow() + timedelta(days=30)
            existing.cancel_at_period_end = False
            db.commit()
            db.refresh(existing)
        else:
            subscription_service.create_subscription(
                user_id=current_user.id,
                plan_id=plan.id,
                billing_cycle=request.billing_cycle,
                status=SubscriptionStatus.ACTIVE,
            )

        if previous_plan_type in {None, PlanType.FREE}:
            CreditService(db).grant_plan_allowance_for_activation(
                current_user.id,
                reason=f"subscription_activation:{(previous_plan_type.value if previous_plan_type else 'none')}->{plan.plan_type.value}",
            )

        # Build success redirect URL
        success_url = request.success_url
        separator = "&" if "?" in success_url else "?"
        redirect_url = f"{success_url}{separator}session_id=dev_mode_{current_user.id}"

        return CheckoutSessionResponse(
            session_id=f"dev_mode_{current_user.id}",
            url=redirect_url,
        )

    # PRODUCTION MODE: use Stripe
    from app.services.stripe_payment_service import StripePaymentService

    stripe_service = StripePaymentService(db)
    try:
        session_data = stripe_service.create_checkout_session(
            user_id=current_user.id,
            plan_id=request.plan_id,
            billing_cycle=request.billing_cycle,
            success_url=request.success_url,
            cancel_url=request.cancel_url,
        )
        return CheckoutSessionResponse(
            session_id=session_data["session_id"],
            url=session_data["url"],
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/checkout/sync", response_model=SubscriptionResponse)
def sync_checkout_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Reconcile a completed checkout session into local state.

    Useful on the checkout success page so local/dev environments remain
    correct even when Stripe webhooks are delayed or not reachable.
    """
    subscription_service = SubscriptionService(db)

    if not _is_stripe_configured():
        subscription = subscription_service.get_user_subscription(current_user.id)
        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active subscription found",
            )
        return _build_subscription_response_with_credits(subscription, current_user, db)

    from app.services.stripe_payment_service import StripePaymentService

    stripe_service = StripePaymentService(db)
    try:
        subscription = stripe_service.sync_checkout_session(
            session_id=session_id,
            user_id=current_user.id,
        )
        return _build_subscription_response_with_credits(subscription, current_user, db)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/customer-portal")
def create_customer_portal_session(
    return_url: str | None = None,
    target_plan_id: int | None = None,
    billing_cycle: BillingCycle | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a Stripe Customer Portal session.
    Users can manage billing, cancel, change payment method, view invoices.
    """
    if not _is_stripe_configured():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Stripe is not configured. Manage subscription from settings.",
        )

    from app.services.stripe_payment_service import StripePaymentService
    from app.core.config import settings

    stripe_service = StripePaymentService(db)
    effective_return_url = return_url or f"{settings.FRONTEND_URL.rstrip('/')}/pricing"
    if (target_plan_id is None) != (billing_cycle is None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="target_plan_id and billing_cycle must be provided together",
        )
    try:
        result = stripe_service.create_customer_portal_session(
            user_id=current_user.id,
            return_url=effective_return_url,
            target_plan_id=target_plan_id,
            billing_cycle=billing_cycle,
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/upgrade", response_model=SubscriptionResponse)
def upgrade_subscription(
    plan_id: int,
    billing_cycle: BillingCycle,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upgrade subscription plan with proration."""
    subscription_service = SubscriptionService(db)
    feature_gate_service = FeatureGateService(db)
    current_subscription = subscription_service.get_user_subscription(current_user.id)

    if (
        _is_stripe_configured()
        and current_subscription
        and current_subscription.stripe_subscription_id
    ):
        from app.services.stripe_payment_service import StripePaymentService

        stripe_service = StripePaymentService(db)
        try:
            subscription = stripe_service.switch_subscription_plan(
                user_id=current_user.id,
                plan_id=plan_id,
                billing_cycle=billing_cycle,
            )
            feature_gate_service.invalidate_user_plan_cache(current_user.id)
            return _build_subscription_response_with_credits(subscription, current_user, db)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )
    
    try:
        result = subscription_service.upgrade_subscription(
            user_id=current_user.id,
            new_plan_id=plan_id,
        )
        feature_gate_service.invalidate_user_plan_cache(current_user.id)
        return result["subscription"]
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/downgrade", response_model=SubscriptionResponse)
def downgrade_subscription(
    plan_id: int,
    billing_cycle: BillingCycle | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Downgrade subscription plan (effective at period end)."""
    subscription_service = SubscriptionService(db)
    feature_gate_service = FeatureGateService(db)
    current_subscription = subscription_service.get_user_subscription(current_user.id)

    if (
        _is_stripe_configured()
        and current_subscription
        and current_subscription.stripe_subscription_id
    ):
        from app.services.stripe_payment_service import StripePaymentService

        effective_billing_cycle = (
            billing_cycle
            or current_subscription.billing_cycle
            or BillingCycle.MONTHLY
        )
        stripe_service = StripePaymentService(db)
        try:
            subscription = stripe_service.switch_subscription_plan(
                user_id=current_user.id,
                plan_id=plan_id,
                billing_cycle=effective_billing_cycle,
            )
            feature_gate_service.invalidate_user_plan_cache(current_user.id)
            return _build_subscription_response_with_credits(subscription, current_user, db)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )
    
    try:
        result = subscription_service.downgrade_subscription(
            user_id=current_user.id,
            new_plan_id=plan_id
        )
        return result["subscription"]
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/cancel", response_model=SubscriptionResponse)
def cancel_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cancel subscription (effective at period end)."""
    subscription_service = SubscriptionService(db)
    current_subscription = subscription_service.get_user_subscription(current_user.id)

    if (
        _is_stripe_configured()
        and current_subscription
        and current_subscription.stripe_subscription_id
    ):
        from app.services.stripe_payment_service import StripePaymentService

        stripe_service = StripePaymentService(db)
        try:
            return stripe_service.schedule_subscription_cancellation(current_user.id)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )
    
    try:
        result = subscription_service.cancel_subscription(current_user.id)
        return result["subscription"]
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/reactivate", response_model=SubscriptionResponse)
def reactivate_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Reactivate a canceled subscription."""
    subscription_service = SubscriptionService(db)
    current_subscription = subscription_service.get_user_subscription(current_user.id)

    if (
        _is_stripe_configured()
        and current_subscription
        and current_subscription.stripe_subscription_id
    ):
        from app.services.stripe_payment_service import StripePaymentService

        stripe_service = StripePaymentService(db)
        try:
            return stripe_service.resume_scheduled_cancellation(current_user.id)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )
    
    try:
        subscription = subscription_service.reactivate_subscription(current_user.id)
        return subscription
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
