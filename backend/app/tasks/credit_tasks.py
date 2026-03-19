"""Celery tasks and webhook helpers for the Credit-Based Billing system.

- process_period_end_batch: daily batch task that resets credits for
  subscriptions whose current_period_end has passed.
- handle_checkout_completed / handle_overage_invoice_paid /
  handle_overage_invoice_failed: v1 stub helpers called from the Stripe
  webhook endpoint to process credit-related events.
"""
import logging
from datetime import datetime
from typing import Any, Dict

from app.celery_app import celery_app

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_session():
    """Create a new sync DB session. Extracted for testability."""
    from app.db.base import SessionLocal
    return SessionLocal()


# ---------------------------------------------------------------------------
# Celery task: daily period-end batch
# ---------------------------------------------------------------------------

@celery_app.task(bind=True, max_retries=0)
def process_period_end_batch(self) -> Dict[str, Any]:
    """Check all subscriptions whose period has ended and reset credits.

    Runs daily (scheduled via Celery Beat at 00:15 UTC).  For each
    qualifying subscription the task calls
    ``CreditService.process_period_end(user_id)`` which handles overage
    settlement, topup expiry, plan balance reset, and ledger entries
    inside a single DB transaction.
    """
    db = _get_session()
    try:
        now = datetime.utcnow()

        from app.models.subscription import Subscription, SubscriptionStatus

        eligible = (
            db.query(Subscription)
            .filter(
                Subscription.current_period_end <= now,
                Subscription.status.in_([
                    SubscriptionStatus.ACTIVE,
                    SubscriptionStatus.TRIALING,
                    SubscriptionStatus.PAST_DUE,
                ]),
            )
            .all()
        )

        processed = 0
        failed = 0

        for sub in eligible:
            try:
                from app.services.credit_service import CreditService

                svc = CreditService(db, redis_client=None)
                svc.process_period_end(sub.user_id)
                db.commit()
                processed += 1
                logger.info(
                    "Period-end processed for user %s (subscription %s)",
                    sub.user_id,
                    sub.id,
                )
            except Exception:
                db.rollback()
                failed += 1
                logger.exception(
                    "Period-end failed for user %s (subscription %s)",
                    sub.user_id,
                    sub.id,
                )

        report = {
            "eligible": len(eligible),
            "processed": processed,
            "failed": failed,
            "run_at": now.isoformat(),
        }
        logger.info(
            "Period-end batch complete: eligible=%d, processed=%d, failed=%d",
            len(eligible),
            processed,
            failed,
        )
        return report

    except Exception:
        logger.exception("process_period_end_batch task failed unexpectedly")
        db.rollback()
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Webhook helper: checkout.session.completed → top-up credits
# ---------------------------------------------------------------------------

def handle_checkout_completed(db, event_data: Dict[str, Any]) -> Dict[str, Any]:
    """Process a ``checkout.session.completed`` Stripe event.

    Extracts ``user_id``, ``credits`` and ``stripe_payment_id`` from the
    session metadata and delegates to ``CreditService.add_topup_credits``.

    Parameters
    ----------
    db : Session
        An active SQLAlchemy session (caller manages commit/rollback).
    event_data : dict
        The Stripe event ``data.object`` payload (a Checkout Session).

    Returns
    -------
    dict
        Summary of the operation.
    """
    session_obj = event_data.get("object", event_data)
    metadata = session_obj.get("metadata", {})

    user_id = metadata.get("user_id")
    credits_str = metadata.get("credits")
    stripe_payment_id = (
        session_obj.get("payment_intent")
        or session_obj.get("id", "unknown")
    )

    if not user_id or not credits_str:
        logger.warning(
            "checkout.session.completed missing user_id or credits in metadata: %s",
            metadata,
        )
        return {"status": "skipped", "reason": "missing metadata"}

    user_id = int(user_id)
    credits_amount = int(credits_str)

    from app.services.credit_service import CreditService

    svc = CreditService(db, redis_client=None)
    svc.add_topup_credits(
        user_id=user_id,
        amount=credits_amount,
        stripe_payment_id=stripe_payment_id,
    )

    logger.info(
        "Top-up credits added: user_id=%s, credits=%s, payment=%s",
        user_id,
        credits_amount,
        stripe_payment_id,
    )
    return {
        "status": "processed",
        "user_id": user_id,
        "credits": credits_amount,
    }


# ---------------------------------------------------------------------------
# Webhook helper: invoice.paid (overage settlement only)
# ---------------------------------------------------------------------------

def handle_overage_invoice_paid(db, event_data: Dict[str, Any]) -> Dict[str, Any]:
    """Process an ``invoice.paid`` Stripe event for overage settlement.

    Only acts when the invoice metadata contains ``type=overage_settlement``.
    Resets ``has_unpaid_overage`` to False and ``unpaid_overage_periods`` to 0,
    and re-enables overage for paid plans so the customer can continue
    using overage after settling the invoice.

    Parameters
    ----------
    db : Session
        An active SQLAlchemy session (caller manages commit/rollback).
    event_data : dict
        The Stripe event ``data.object`` payload (an Invoice).
    """
    invoice = event_data.get("object", event_data)
    metadata = invoice.get("metadata", {})

    if metadata.get("type") != "overage_settlement":
        return {"status": "skipped", "reason": "not overage_settlement"}

    user_id = metadata.get("user_id")
    if not user_id:
        logger.warning("overage invoice.paid missing user_id in metadata: %s", metadata)
        return {"status": "skipped", "reason": "missing user_id"}

    user_id = int(user_id)

    from app.models.credit_balance import CreditBalance
    from app.models.plan import PlanType
    from app.models.subscription import Subscription, SubscriptionStatus

    balance = (
        db.query(CreditBalance)
        .filter(CreditBalance.user_id == user_id)
        .first()
    )
    if balance is None:
        logger.warning("No CreditBalance found for user %s on overage invoice.paid", user_id)
        return {"status": "skipped", "reason": "no_balance_record"}

    subscription = (
        db.query(Subscription)
        .filter(
            Subscription.user_id == user_id,
            Subscription.status.in_([
                SubscriptionStatus.ACTIVE,
                SubscriptionStatus.TRIALING,
                SubscriptionStatus.PAST_DUE,
            ]),
        )
        .first()
    )

    balance.has_unpaid_overage = False
    balance.unpaid_overage_periods = 0
    if (
        subscription is not None
        and subscription.plan is not None
        and subscription.plan.plan_type != PlanType.FREE
        and subscription.plan.overage_price_per_credit is not None
    ):
        balance.overage_enabled = True
    db.flush()

    logger.info(
        "Overage settlement paid: user_id=%s — unpaid overage cleared, overage_enabled=%s",
        user_id,
        balance.overage_enabled,
    )
    return {
        "status": "processed",
        "user_id": user_id,
        "overage_enabled": balance.overage_enabled,
    }


# ---------------------------------------------------------------------------
# Webhook helper: invoice.payment_failed (overage settlement only)
# ---------------------------------------------------------------------------

def handle_overage_invoice_failed(db, event_data: Dict[str, Any]) -> Dict[str, Any]:
    """Process an ``invoice.payment_failed`` Stripe event for overage settlement.

    Only acts when the invoice metadata contains ``type=overage_settlement``.
    Sets ``has_unpaid_overage`` to True, disables overage immediately,
    and increments ``unpaid_overage_periods`` only once per unresolved
    overage incident.

    Parameters
    ----------
    db : Session
        An active SQLAlchemy session (caller manages commit/rollback).
    event_data : dict
        The Stripe event ``data.object`` payload (an Invoice).
    """
    invoice = event_data.get("object", event_data)
    metadata = invoice.get("metadata", {})

    if metadata.get("type") != "overage_settlement":
        return {"status": "skipped", "reason": "not overage_settlement"}

    user_id = metadata.get("user_id")
    if not user_id:
        logger.warning(
            "overage invoice.payment_failed missing user_id in metadata: %s", metadata
        )
        return {"status": "skipped", "reason": "missing user_id"}

    user_id = int(user_id)

    from app.models.credit_balance import CreditBalance

    balance = (
        db.query(CreditBalance)
        .filter(CreditBalance.user_id == user_id)
        .first()
    )
    if balance is None:
        logger.warning(
            "No CreditBalance found for user %s on overage invoice.payment_failed", user_id
        )
        return {"status": "skipped", "reason": "no_balance_record"}

    if not balance.has_unpaid_overage:
        balance.unpaid_overage_periods += 1
    balance.has_unpaid_overage = True
    balance.overage_enabled = False
    db.flush()

    logger.info(
        "Overage settlement failed: user_id=%s — unpaid_overage_periods=%d, overage disabled",
        user_id,
        balance.unpaid_overage_periods,
    )
    return {
        "status": "processed",
        "user_id": user_id,
        "unpaid_overage_periods": balance.unpaid_overage_periods,
        "overage_enabled": balance.overage_enabled,
    }
