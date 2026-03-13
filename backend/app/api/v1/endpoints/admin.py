"""Admin endpoints for subscription management"""
from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.db.base import get_db
from app.api.deps import get_current_admin
from app.models.user import User
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.plan import Plan, PlanType
from app.models.payment_event import PaymentEvent
from app.schemas.subscription import SubscriptionResponse
from app.schemas.plan import PlanResponse, PlanCreate, PlanUpdate
from app.services.subscription_service import SubscriptionService

router = APIRouter()


@router.get("/subscriptions", response_model=List[SubscriptionResponse])
def list_all_subscriptions(
    status: Optional[SubscriptionStatus] = None,
    plan_type: Optional[PlanType] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """
    List all subscriptions with optional filters.
    
    Admin only endpoint.
    """
    query = db.query(Subscription)
    
    if status:
        query = query.filter(Subscription.status == status)
    
    if plan_type:
        query = query.join(Plan).filter(Plan.plan_type == plan_type)
    
    subscriptions = query.offset(skip).limit(limit).all()
    return subscriptions


@router.get("/subscriptions/{user_id}", response_model=SubscriptionResponse)
def get_user_subscription_admin(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """
    Get subscription details for a specific user.
    
    Admin only endpoint.
    """
    subscription = db.query(Subscription).filter(Subscription.user_id == user_id).first()
    
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    return subscription


@router.post("/subscriptions/{user_id}/grant-trial")
def grant_trial(
    user_id: int,
    days: int = Query(14, ge=1, le=90),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """
    Grant trial period to a user.
    
    Admin only endpoint.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if user already used trial
    if user.trial_used:
        raise HTTPException(status_code=400, detail="User has already used trial")
    
    # Get Pro plan
    pro_plan = db.query(Plan).filter(Plan.plan_type == PlanType.PRO).first()
    if not pro_plan:
        raise HTTPException(status_code=404, detail="Pro plan not found")
    
    # Create or update subscription
    subscription = db.query(Subscription).filter(Subscription.user_id == user_id).first()
    
    trial_end = datetime.utcnow() + timedelta(days=days)
    
    if not subscription:
        subscription = Subscription(
            user_id=user_id,
            plan_id=pro_plan.id,
            status=SubscriptionStatus.TRIALING,
            current_period_start=datetime.utcnow(),
            current_period_end=trial_end
        )
        db.add(subscription)
    else:
        subscription.plan_id = pro_plan.id
        subscription.status = SubscriptionStatus.TRIALING
        subscription.current_period_end = trial_end
    
    # Update user trial status
    user.trial_used = True
    user.trial_end_date = trial_end
    
    db.commit()
    db.refresh(subscription)
    
    return {
        "message": f"Trial granted for {days} days",
        "subscription_id": subscription.id,
        "trial_end_date": trial_end
    }


@router.put("/subscriptions/{user_id}/change-plan")
def change_user_plan(
    user_id: int,
    plan_type: PlanType,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """
    Change user's subscription plan.
    
    Admin only endpoint. Bypasses payment.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    plan = db.query(Plan).filter(Plan.plan_type == plan_type).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    subscription_service = SubscriptionService(db)
    subscription = subscription_service.get_user_subscription(user_id)
    
    if not subscription:
        # Create new subscription
        subscription = Subscription(
            user_id=user_id,
            plan_id=plan.id,
            status=SubscriptionStatus.ACTIVE,
            current_period_start=datetime.utcnow(),
            current_period_end=datetime.utcnow() + timedelta(days=30)
        )
        db.add(subscription)
    else:
        # Update existing subscription
        subscription.plan_id = plan.id
        subscription.status = SubscriptionStatus.ACTIVE
    
    db.commit()
    db.refresh(subscription)
    
    return {
        "message": f"Plan changed to {plan_type.value}",
        "subscription": subscription
    }


@router.post("/subscriptions/{user_id}/extend")
def extend_subscription(
    user_id: int,
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """
    Extend user's subscription period.
    
    Admin only endpoint.
    """
    subscription = db.query(Subscription).filter(Subscription.user_id == user_id).first()
    
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    subscription.current_period_end += timedelta(days=days)
    db.commit()
    
    return {
        "message": f"Subscription extended by {days} days",
        "new_end_date": subscription.current_period_end
    }


@router.get("/analytics/revenue")
def get_revenue_analytics(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """
    Get revenue analytics (MRR, ARR).
    
    Admin only endpoint.
    """
    # Calculate MRR (Monthly Recurring Revenue)
    active_subscriptions = (
        db.query(Subscription, Plan)
        .join(Plan)
        .filter(Subscription.status == SubscriptionStatus.ACTIVE)
        .all()
    )
    
    mrr = sum(
        sub.plan.monthly_price 
        for sub, plan in active_subscriptions
    )
    
    arr = mrr * 12
    
    # Count subscriptions by plan
    plan_counts = (
        db.query(Plan.plan_type, func.count(Subscription.id))
        .join(Subscription)
        .filter(Subscription.status == SubscriptionStatus.ACTIVE)
        .group_by(Plan.plan_type)
        .all()
    )
    
    return {
        "mrr": float(mrr),
        "arr": float(arr),
        "active_subscriptions": len(active_subscriptions),
        "plan_distribution": {
            plan_type.value: count 
            for plan_type, count in plan_counts
        }
    }


@router.get("/analytics/subscriptions")
def get_subscription_analytics(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """
    Get subscription counts by plan and status.
    
    Admin only endpoint.
    """
    # Count by status
    status_counts = (
        db.query(Subscription.status, func.count(Subscription.id))
        .group_by(Subscription.status)
        .all()
    )
    
    # Count by plan
    plan_counts = (
        db.query(Plan.plan_type, func.count(Subscription.id))
        .join(Subscription)
        .group_by(Plan.plan_type)
        .all()
    )
    
    return {
        "by_status": {
            status.value: count 
            for status, count in status_counts
        },
        "by_plan": {
            plan_type.value: count 
            for plan_type, count in plan_counts
        }
    }


@router.get("/analytics/conversion")
def get_conversion_analytics(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """
    Get trial to paid conversion rate.
    
    Admin only endpoint.
    """
    # Count users who used trial
    trial_users = db.query(User).filter(User.trial_used == True).count()
    
    # Count users who converted to paid
    converted_users = (
        db.query(User)
        .join(Subscription)
        .join(Plan)
        .filter(
            and_(
                User.trial_used == True,
                Plan.plan_type != PlanType.FREE,
                Subscription.status == SubscriptionStatus.ACTIVE
            )
        )
        .count()
    )
    
    conversion_rate = (converted_users / trial_users * 100) if trial_users > 0 else 0
    
    return {
        "trial_users": trial_users,
        "converted_users": converted_users,
        "conversion_rate": round(conversion_rate, 2)
    }


@router.get("/analytics/churn")
def get_churn_analytics(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """
    Get churn rate by plan.
    
    Admin only endpoint.
    """
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Count canceled subscriptions in period
    canceled = (
        db.query(Plan.plan_type, func.count(Subscription.id))
        .join(Subscription)
        .filter(
            and_(
                Subscription.status == SubscriptionStatus.CANCELED,
                Subscription.updated_at >= start_date
            )
        )
        .group_by(Plan.plan_type)
        .all()
    )
    
    # Count total active at start of period
    total_active = (
        db.query(Plan.plan_type, func.count(Subscription.id))
        .join(Subscription)
        .filter(Subscription.status == SubscriptionStatus.ACTIVE)
        .group_by(Plan.plan_type)
        .all()
    )
    
    churn_by_plan = {}
    for plan_type, active_count in total_active:
        canceled_count = next(
            (count for pt, count in canceled if pt == plan_type),
            0
        )
        churn_rate = (canceled_count / active_count * 100) if active_count > 0 else 0
        churn_by_plan[plan_type.value] = {
            "canceled": canceled_count,
            "active": active_count,
            "churn_rate": round(churn_rate, 2)
        }
    
    return {
        "period_days": days,
        "churn_by_plan": churn_by_plan
    }


@router.post("/plans", response_model=PlanResponse)
def create_plan_admin(
    plan: PlanCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """
    Create a new subscription plan.
    
    Admin only endpoint.
    """
    # Check if plan already exists
    existing = db.query(Plan).filter(Plan.plan_type == plan.plan_type).first()
    if existing:
        raise HTTPException(status_code=400, detail="Plan already exists")
    
    db_plan = Plan(**plan.dict())
    db.add(db_plan)
    db.commit()
    db.refresh(db_plan)
    
    return db_plan


@router.put("/plans/{plan_id}", response_model=PlanResponse)
def update_plan_admin(
    plan_id: int,
    plan_update: PlanUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """
    Update plan configuration.
    
    Admin only endpoint. Only affects new subscriptions.
    """
    db_plan = db.query(Plan).filter(Plan.id == plan_id).first()
    if not db_plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    update_data = plan_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_plan, field, value)
    
    db.commit()
    db.refresh(db_plan)
    
    return db_plan


@router.get("/payment-events")
def list_payment_events(
    event_type: Optional[str] = None,
    user_id: Optional[int] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """
    List payment events with filters.
    
    Admin only endpoint.
    """
    query = db.query(PaymentEvent)
    
    if event_type:
        query = query.filter(PaymentEvent.event_type == event_type)
    
    if user_id:
        query = query.filter(PaymentEvent.user_id == user_id)
    
    events = query.order_by(PaymentEvent.created_at.desc()).offset(skip).limit(limit).all()
    
    return {
        "total": query.count(),
        "events": [
            {
                "id": event.id,
                "stripe_event_id": event.stripe_event_id,
                "event_type": event.event_type,
                "user_id": event.user_id,
                "created_at": event.created_at,
                "payload": event.payload
            }
            for event in events
        ]
    }
