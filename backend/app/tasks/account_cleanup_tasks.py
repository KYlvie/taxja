"""Celery tasks for scheduled account cleanup and deletion reminders.

- cleanup_expired_accounts: daily hard-deletion of accounts past the
  30-day cooling-off period, plus retries for previously failed deletions.
- send_deletion_reminders: daily reminder for accounts approaching the
  end of the cooling-off period (~day 23).
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any

from app.celery_app import celery_app

logger = logging.getLogger(__name__)


def _get_session():
    """Create a new DB session. Extracted for testability."""
    from app.db.base import SessionLocal
    return SessionLocal()


def _hard_delete(user_id: int, initiated_by: str, db):
    """Delegate to AccountCancellationService. Extracted for testability."""
    from app.services.account_cancellation_service import AccountCancellationService
    return AccountCancellationService.hard_delete_account(
        user_id=user_id, initiated_by=initiated_by, db=db,
    )


@celery_app.task(bind=True, soft_time_limit=600, time_limit=660)
def cleanup_expired_accounts(self) -> Dict[str, Any]:
    """Check for expired deactivated accounts and execute hard deletion.

    Runs daily (scheduled at 02:00 Vienna time via Celery Beat).

    Steps:
    1. Query users with account_status='deactivated' AND
       scheduled_deletion_at < now → execute hard_delete_account for each.
    2. Query users with account_status='deletion_pending' AND
       deletion_retry_count < 3 → retry hard_delete_account, increment
       retry count on failure.
    3. For users with deletion_retry_count >= 3 → log admin alert.
    4. Generate cleanup report log.
    """
    db = _get_session()
    try:
        now = datetime.utcnow()

        accounts_checked = 0
        accounts_deleted = 0
        accounts_failed = 0
        accounts_retried = 0
        accounts_alerted = 0

        # --- 1. Expired deactivated accounts ---
        from app.models.user import User
        expired_users = (
            db.query(User)
            .filter(
                User.account_status == "deactivated",
                User.scheduled_deletion_at < now,
            )
            .all()
        )
        accounts_checked += len(expired_users)

        for user in expired_users:
            try:
                _hard_delete(
                    user_id=user.id,
                    initiated_by="system",
                    db=db,
                )
                accounts_deleted += 1
                logger.info(
                    "Scheduled hard-delete completed for user %s", user.id
                )
            except Exception:
                logger.exception(
                    "Hard-delete failed for expired user %s, marking deletion_pending",
                    user.id,
                )
                # Rollback the failed transaction and mark for retry
                db.rollback()
                # Re-fetch user after rollback
                user = db.query(User).filter(User.id == user.id).first()
                if user:
                    user.account_status = "deletion_pending"
                    user.deletion_retry_count = (user.deletion_retry_count or 0) + 1
                    db.commit()
                accounts_failed += 1

        # --- 2. Retry deletion_pending accounts (retry_count < 3) ---
        pending_users = (
            db.query(User)
            .filter(
                User.account_status == "deletion_pending",
                User.deletion_retry_count < 3,
            )
            .all()
        )
        accounts_checked += len(pending_users)

        for user in pending_users:
            try:
                _hard_delete(
                    user_id=user.id,
                    initiated_by="system",
                    db=db,
                )
                accounts_deleted += 1
                accounts_retried += 1
                logger.info(
                    "Retry hard-delete succeeded for user %s (attempt %s)",
                    user.id,
                    user.deletion_retry_count + 1,
                )
            except Exception:
                logger.exception(
                    "Retry hard-delete failed for user %s (attempt %s)",
                    user.id,
                    user.deletion_retry_count + 1,
                )
                db.rollback()
                user = db.query(User).filter(User.id == user.id).first()
                if user:
                    user.deletion_retry_count = (user.deletion_retry_count or 0) + 1
                    db.commit()
                accounts_failed += 1
                accounts_retried += 1

        # --- 3. Admin alert for accounts with retry_count >= 3 ---
        stuck_users = (
            db.query(User)
            .filter(
                User.account_status == "deletion_pending",
                User.deletion_retry_count >= 3,
            )
            .all()
        )
        for user in stuck_users:
            logger.warning(
                "ADMIN ALERT: Account %s hard-delete failed %s times. "
                "Manual intervention required. Email: %s",
                user.id,
                user.deletion_retry_count,
                user.email,
            )
            accounts_alerted += 1

        # --- 4. Cleanup report ---
        report = {
            "accounts_checked": accounts_checked,
            "accounts_deleted": accounts_deleted,
            "accounts_failed": accounts_failed,
            "accounts_retried": accounts_retried,
            "accounts_alerted": accounts_alerted,
            "run_at": now.isoformat(),
        }
        logger.info(
            "Account cleanup report: checked=%d, deleted=%d, failed=%d, "
            "retried=%d, alerted=%d",
            accounts_checked,
            accounts_deleted,
            accounts_failed,
            accounts_retried,
            accounts_alerted,
        )
        return report

    except Exception:
        logger.exception("cleanup_expired_accounts task failed unexpectedly")
        db.rollback()
        raise
    finally:
        db.close()


@celery_app.task(bind=True, soft_time_limit=600, time_limit=660)
def purge_bao_expired_data(self) -> Dict[str, Any]:
    """Purge data for anonymized users whose BAO §132 7-year retention has expired.

    Runs monthly (1st of each month at 03:00 Vienna time via Celery Beat).
    Fully deletes user records and all remaining associated data once the
    retention period has elapsed.
    """
    db = _get_session()
    try:
        from app.services.account_cancellation_service import AccountCancellationService
        result = AccountCancellationService.purge_expired_retained_data(db)
        logger.info(
            "BAO expiry purge report: found=%d, purged=%d",
            result["expired_users_found"],
            result["purged_count"],
        )
        return result
    except Exception:
        logger.exception("purge_bao_expired_data task failed unexpectedly")
        db.rollback()
        raise
    finally:
        db.close()


@celery_app.task(bind=True, soft_time_limit=120, time_limit=180)
def send_deletion_reminders(self) -> Dict[str, Any]:
    """Send reminders to users whose accounts are ~23 days into the cooling-off period.

    Runs daily (scheduled at 09:00 Vienna time via Celery Beat).

    Queries users with account_status='deactivated' AND deactivated_at
    between 22.5 and 23.5 days ago, then logs a reminder for each
    (in production this would trigger an email notification).
    """
    db = _get_session()
    try:
        now = datetime.utcnow()
        # Window: deactivated between 22.5 and 23.5 days ago
        window_start = now - timedelta(days=23.5)
        window_end = now - timedelta(days=22.5)

        from app.models.user import User
        reminder_users = (
            db.query(User)
            .filter(
                User.account_status == "deactivated",
                User.deactivated_at >= window_start,
                User.deactivated_at <= window_end,
            )
            .all()
        )

        reminders_sent = 0
        for user in reminder_users:
            days_remaining = 0
            if user.scheduled_deletion_at:
                delta = user.scheduled_deletion_at - now
                days_remaining = max(0, delta.days)

            logger.info(
                "DELETION REMINDER: User %s (email: %s) — account will be "
                "permanently deleted in %d days (scheduled: %s)",
                user.id,
                user.email,
                days_remaining,
                user.scheduled_deletion_at.isoformat() if user.scheduled_deletion_at else "N/A",
            )
            reminders_sent += 1

        report = {
            "reminders_sent": reminders_sent,
            "run_at": now.isoformat(),
        }
        logger.info("Deletion reminders report: sent=%d", reminders_sent)
        return report

    except Exception:
        logger.exception("send_deletion_reminders task failed unexpectedly")
        raise
    finally:
        db.close()
