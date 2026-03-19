"""Celery tasks for trial subscription management"""
import logging
from celery import shared_task
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.services.trial_service import TrialService

logger = logging.getLogger(__name__)


@shared_task(name="handle_expired_trials")
def handle_expired_trials_task():
    """
    Daily task to downgrade expired trial subscriptions to Free tier.

    Runs daily to find all expired trials and downgrade them.
    """
    db: Session = SessionLocal()

    try:
        trial_service = TrialService(db)

        # Get and handle expired trials
        expired = trial_service.get_expired_trials()
        downgraded = 0

        for subscription in expired:
            try:
                trial_service.handle_trial_end(subscription.user_id)
                downgraded += 1
                logger.info(f"Downgraded expired trial for user {subscription.user_id}")
            except Exception as e:
                logger.error(f"Failed to downgrade trial for user {subscription.user_id}: {e}")

        return {
            "success": True,
            "expired_found": len(expired),
            "downgraded": downgraded,
        }

    except Exception as e:
        logger.error(f"Failed to handle expired trials: {e}")
        return {"success": False, "error": str(e)}

    finally:
        db.close()


@shared_task(name="send_trial_expiration_reminders")
def send_trial_expiration_reminders_task():
    """
    Daily task to send reminders to users whose trials expire in 3 days.
    """
    db: Session = SessionLocal()

    try:
        trial_service = TrialService(db)

        # Get trials expiring within 3 days
        expiring = trial_service.get_expiring_trials(days_threshold=3)
        sent = 0

        for subscription in expiring:
            try:
                trial_service.send_trial_expiration_reminder(subscription.user_id)
                sent += 1
            except Exception as e:
                logger.error(f"Failed to send trial reminder for user {subscription.user_id}: {e}")

        return {
            "success": True,
            "expiring_found": len(expiring),
            "reminders_sent": sent,
        }

    except Exception as e:
        logger.error(f"Failed to send trial reminders: {e}")
        return {"success": False, "error": str(e)}

    finally:
        db.close()
