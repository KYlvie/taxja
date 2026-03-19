"""Legacy-compatible admin helpers used by older tests and scripts."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Optional

from fastapi import HTTPException

from app.models import payment_event as payment_event_model
from app.services import plan_service, subscription_service, trial_service


def require_admin(current_user):
    """Legacy helper preserved for direct unit tests."""
    if current_user is None or getattr(current_user, "role", None) != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


def list_subscriptions(*, db, status=None, plan_type=None, current_user):
    require_admin(current_user)
    return subscription_service.SubscriptionService.list_all_subscriptions(
        status=status,
        plan_type=plan_type,
    )


def get_user_subscription_details(*, user_id: int, db, current_user):
    require_admin(current_user)
    return subscription_service.SubscriptionService.get_user_subscription(user_id)


def grant_trial(*, user_id: int, db, current_user):
    require_admin(current_user)
    return trial_service.TrialService.activate_trial(db, user_id)


def change_user_plan(*, user_id: int, plan_type, db, current_user):
    require_admin(current_user)
    return subscription_service.SubscriptionService.upgrade_subscription(user_id, plan_type)


def extend_subscription(*, user_id: int, days: int, db, current_user):
    require_admin(current_user)
    subscription = subscription_service.SubscriptionService.get_user_subscription(user_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    subscription.current_period_end = subscription.current_period_end + timedelta(days=days)
    return subscription


def get_revenue_analytics(*, db, current_user):
    require_admin(current_user)
    return {
        "mrr": subscription_service.SubscriptionService.calculate_mrr(),
        "arr": subscription_service.SubscriptionService.calculate_arr(),
        "growth_rate": subscription_service.SubscriptionService.calculate_growth_rate(),
    }


def get_subscription_analytics(*, db, current_user):
    require_admin(current_user)
    return subscription_service.SubscriptionService.count_by_plan()


def get_conversion_analytics(*, db, current_user):
    require_admin(current_user)
    return {
        "trial_to_paid": subscription_service.SubscriptionService.calculate_trial_conversion(),
        "free_to_paid": subscription_service.SubscriptionService.calculate_free_to_paid_conversion(),
    }


def get_churn_analytics(*, db, current_user):
    require_admin(current_user)
    return subscription_service.SubscriptionService.calculate_churn_rate()


def create_plan(*, plan_data: dict[str, Any], db, current_user):
    require_admin(current_user)
    return plan_service.PlanService.create_plan(plan_data)


def update_plan(*, plan_id: int, update_data: dict[str, Any], db, current_user):
    require_admin(current_user)
    return plan_service.PlanService.update_plan(plan_id, update_data)


def list_payment_events(
    *,
    db,
    event_type: Optional[str],
    user_id: Optional[int],
    date_from,
    date_to,
    page: int,
    limit: int,
    current_user,
):
    require_admin(current_user)
    payment_event = payment_event_model.PaymentEvent
    query = payment_event.query(db)
    if event_type:
        query = query.filter(payment_event.event_type == event_type)
    if user_id is not None:
        query = query.filter(payment_event.user_id == user_id)
    if date_from is not None:
        query = query.filter(payment_event.created_at >= date_from)
    if date_to is not None:
        query = query.filter(payment_event.created_at <= date_to)
    query = query.order_by(payment_event.created_at.desc())
    offset = max(page - 1, 0) * limit
    return query.offset(offset).limit(limit).all()


__all__ = [
    "change_user_plan",
    "create_plan",
    "extend_subscription",
    "get_churn_analytics",
    "get_conversion_analytics",
    "get_revenue_analytics",
    "get_subscription_analytics",
    "get_user_subscription_details",
    "grant_trial",
    "list_payment_events",
    "list_subscriptions",
    "require_admin",
    "update_plan",
]
