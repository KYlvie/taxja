"""Account cancellation service for deactivation, reactivation, and hard deletion.

Handles the full account lifecycle: soft-delete (deactivation with 30-day
cooling-off period), reactivation within that window, and permanent hard
deletion that removes PII while preserving anonymised audit records.
"""
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional

import redis
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import verify_password
from app.models.account_deletion_log import AccountDeletionLog
from app.models.audit_log import AuditLog
from app.models.document import Document
from app.models.payment_event import PaymentEvent
from app.models.property import Property
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.tax_report import TaxReport
from app.models.transaction import Transaction
from app.models.user import User
from app.services.storage_service import StorageService

logger = logging.getLogger(__name__)

COOLING_OFF_DAYS = 30


class AccountCancellationService:
    """Orchestrates account deactivation, reactivation, and permanent deletion."""

    # ------------------------------------------------------------------
    # 1. Cancellation impact summary
    # ------------------------------------------------------------------

    @staticmethod
    def get_cancellation_impact(user_id: int, db: Session) -> dict:
        """Return a summary of data that would be affected by account cancellation.

        Queries counts of the user's transactions, documents, tax reports and
        properties, plus subscription status.
        """
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")

        transaction_count = (
            db.query(func.count(Transaction.id))
            .filter(Transaction.user_id == user_id)
            .scalar()
            or 0
        )
        document_count = (
            db.query(func.count(Document.id))
            .filter(Document.user_id == user_id)
            .scalar()
            or 0
        )
        tax_report_count = (
            db.query(func.count(TaxReport.id))
            .filter(TaxReport.user_id == user_id)
            .scalar()
            or 0
        )
        property_count = (
            db.query(func.count(Property.id))
            .filter(Property.user_id == user_id)
            .scalar()
            or 0
        )

        # Check subscription status
        subscription = (
            db.query(Subscription)
            .filter(
                Subscription.user_id == user_id,
                Subscription.status.in_([
                    SubscriptionStatus.ACTIVE,
                    SubscriptionStatus.TRIALING,
                ]),
            )
            .first()
        )
        has_active_subscription = subscription is not None
        subscription_days_remaining = (
            subscription.days_until_expiry() if subscription else None
        )

        return {
            "transaction_count": transaction_count,
            "document_count": document_count,
            "tax_report_count": tax_report_count,
            "property_count": property_count,
            "has_active_subscription": has_active_subscription,
            "subscription_days_remaining": subscription_days_remaining,
            "cooling_off_days": COOLING_OFF_DAYS,
        }

    # ------------------------------------------------------------------
    # 2. Deactivate account (soft delete)
    # ------------------------------------------------------------------

    @staticmethod
    def deactivate_account(
        user_id: int,
        password: str,
        reason: Optional[str],
        confirmation_word: str,
        two_factor_code: Optional[str],
        db: Session,
    ) -> dict:
        """Soft-delete an account after verifying credentials.

        Sets account_status to 'deactivated', records the deactivation time,
        schedules hard deletion after the cooling-off period, cancels any
        active subscription, and creates an audit log entry.
        """
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")

        # Password verification
        if not verify_password(password, user.password_hash):
            raise PermissionError("Invalid password")

        # Confirmation word must be exactly "DELETE"
        if confirmation_word != "DELETE":
            raise ValueError('Confirmation word must be exactly "DELETE"')

        if user.account_status != "active":
            raise ValueError(f"Account is already {user.account_status}")

        now = datetime.utcnow()
        user.account_status = "deactivated"
        user.deactivated_at = now
        user.scheduled_deletion_at = now + timedelta(days=COOLING_OFF_DAYS)
        user.cancellation_reason = reason

        # Cancel active subscription if one exists
        active_sub = (
            db.query(Subscription)
            .filter(
                Subscription.user_id == user_id,
                Subscription.status.in_([
                    SubscriptionStatus.ACTIVE,
                    SubscriptionStatus.TRIALING,
                ]),
            )
            .first()
        )
        if active_sub:
            active_sub.status = SubscriptionStatus.CANCELED
            active_sub.cancel_at_period_end = True

        # Audit log entry
        audit = AuditLog(
            user_id=user_id,
            operation_type="delete",
            entity_type="property",  # reuse existing enum; closest match
            entity_id=str(user_id),
            details={
                "action": "account_deactivated",
                "reason": reason,
                "scheduled_deletion_at": user.scheduled_deletion_at.isoformat(),
            },
        )
        db.add(audit)
        try:
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("Failed to deactivate account %s", user_id)
            raise

        logger.info("Account %s deactivated, deletion scheduled for %s", user_id, user.scheduled_deletion_at)

        return {
            "message": "Account deactivated successfully",
            "account_status": user.account_status,
            "scheduled_deletion_at": user.scheduled_deletion_at.isoformat(),
            "cooling_off_days": COOLING_OFF_DAYS,
        }

    # ------------------------------------------------------------------
    # 3. Reactivate account
    # ------------------------------------------------------------------

    @staticmethod
    def reactivate_account(user_id: int, db: Session) -> dict:
        """Restore a deactivated account to active within the cooling-off period."""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")

        if user.account_status != "deactivated":
            raise ValueError(
                f"Only deactivated accounts can be reactivated (current: {user.account_status})"
            )

        now = datetime.utcnow()
        if user.scheduled_deletion_at and user.scheduled_deletion_at <= now:
            raise ValueError("Cooling-off period has expired; account cannot be reactivated")

        user.account_status = "active"
        user.deactivated_at = None
        user.scheduled_deletion_at = None
        # Note: cancellation_reason is intentionally preserved so that
        # get_admin_cancellation_stats can compute the reactivation rate.
        db.commit()

        logger.info("Account %s reactivated", user_id)

        return {
            "message": "Account reactivated successfully",
            "account_status": user.account_status,
        }

    # ------------------------------------------------------------------
    # 4. Hard delete account
    # ------------------------------------------------------------------

    @staticmethod
    def hard_delete_account(user_id: int, initiated_by: str, db: Session) -> dict:
        """Anonymize user PII while retaining tax-relevant data per BAO §132.

        Austrian BAO §132 requires 7-year retention of tax-relevant records
        (transactions, documents, tax reports). Instead of cascade-deleting
        everything, we:
        1. Delete MinIO document *files* (binary blobs) but keep Document rows
        2. Anonymize PII on the User record
        3. Anonymize PaymentEvent and AuditLog
        4. Delete non-tax data (chat messages, corrections, notifications)
        5. Purge data older than 7 years (safe to remove)
        6. Clear Redis cache
        7. Create AccountDeletionLog
        """
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")

        now = datetime.utcnow()
        bao_cutoff = now - timedelta(days=7 * 365)  # 7-year retention boundary
        data_actions = []

        # 1. Delete MinIO document files (binary blobs) but keep DB rows
        documents = db.query(Document).filter(Document.user_id == user_id).all()
        if documents:
            try:
                storage = StorageService()
                for doc in documents:
                    if doc.file_path:
                        storage.delete_file(doc.file_path)
                        doc.file_path = None  # Clear path, keep metadata
            except Exception:
                logger.exception("Error deleting MinIO files for user %s", user_id)
            data_actions.append("document_files_deleted")

        # 2. Anonymize PaymentEvent and AuditLog
        payment_count = (
            db.query(PaymentEvent)
            .filter(PaymentEvent.user_id == user_id)
            .update({PaymentEvent.user_id: None})
        )
        if payment_count:
            data_actions.append("payment_events_anonymised")

        audit_count = (
            db.query(AuditLog)
            .filter(AuditLog.user_id == user_id)
            .update({AuditLog.user_id: None})
        )
        if audit_count:
            data_actions.append("audit_logs_anonymised")

        # 3. Delete non-tax-relevant data (chat, corrections, notifications, user rules)
        from app.models.chat_message import ChatMessage
        from app.models.classification_correction import ClassificationCorrection
        from app.models.notification import Notification
        from app.models.user_classification_rule import UserClassificationRule
        for model_cls, label in [
            (ChatMessage, "chat_messages"),
            (ClassificationCorrection, "corrections"),
            (Notification, "notifications"),
            (UserClassificationRule, "classification_rules"),
        ]:
            try:
                count = db.query(model_cls).filter(
                    model_cls.user_id == user_id
                ).delete(synchronize_session=False)
                if count:
                    data_actions.append(f"{label}_deleted")
            except Exception:
                logger.warning("Could not delete %s for user %s", label, user_id)

        # 4. Purge transactions/documents/tax_reports older than 7 years
        old_tx = db.query(Transaction).filter(
            Transaction.user_id == user_id,
            Transaction.transaction_date < bao_cutoff,
        ).delete(synchronize_session=False)
        if old_tx:
            data_actions.append(f"old_transactions_purged:{old_tx}")

        old_docs = db.query(Document).filter(
            Document.user_id == user_id,
            Document.uploaded_at < bao_cutoff,
        ).delete(synchronize_session=False)
        if old_docs:
            data_actions.append(f"old_documents_purged:{old_docs}")

        old_reports = db.query(TaxReport).filter(
            TaxReport.user_id == user_id,
            TaxReport.generated_at < bao_cutoff,
        ).delete(synchronize_session=False)
        if old_reports:
            data_actions.append(f"old_tax_reports_purged:{old_reports}")

        # 5. Anonymize user PII — keep the record for foreign key integrity
        salt = settings.SECRET_KEY
        anonymous_hash = hashlib.sha256(f"{user_id}{salt}".encode()).hexdigest()

        user.email = f"deleted_{anonymous_hash[:16]}@anonymized.local"
        user.name = "Gelöschter Benutzer"
        user.password_hash = "ANONYMIZED"
        user.tax_number = None
        user.vat_number = None
        user.address = None
        user.family_info = {}
        user.commuting_info = {}
        user.two_factor_secret = None
        user.two_factor_enabled = False
        user.account_status = "anonymized"
        user.bao_retention_expiry = now + timedelta(days=7 * 365)
        data_actions.append("user_pii_anonymized")

        # 6. Clear Redis cache
        try:
            redis_client = redis.Redis(
                host=getattr(settings, "REDIS_HOST", "localhost"),
                port=getattr(settings, "REDIS_PORT", 6379),
                db=getattr(settings, "REDIS_DB", 0),
                decode_responses=True,
            )
            for pattern in [f"user:{user_id}:*", f"session:{user_id}:*"]:
                cursor = 0
                while True:
                    cursor, keys = redis_client.scan(cursor=cursor, match=pattern, count=100)
                    if keys:
                        redis_client.delete(*keys)
                    if cursor == 0:
                        break
            redis_client.close()
        except Exception:
            logger.warning("Could not clear Redis cache for user %s", user_id)

        # 7. Create AccountDeletionLog
        deletion_method = "admin_manual" if initiated_by == "admin" else "scheduled"
        deletion_log = AccountDeletionLog(
            anonymous_user_hash=anonymous_hash,
            deleted_at=now,
            data_types_deleted=data_actions,
            deletion_method=deletion_method,
            initiated_by=initiated_by,
        )
        db.add(deletion_log)
        db.commit()

        logger.info(
            "Account %s anonymized per BAO §132 (initiated by %s), "
            "retention until %s",
            user_id, initiated_by, user.bao_retention_expiry,
        )

        return {
            "message": "Account anonymized, tax data retained per BAO §132",
            "data_actions": data_actions,
            "anonymous_user_hash": anonymous_hash,
            "bao_retention_expiry": user.bao_retention_expiry.isoformat(),
        }

    # ------------------------------------------------------------------
    # 4b. Purge expired retained data (BAO §132 expiry)
    # ------------------------------------------------------------------

    @staticmethod
    def purge_expired_retained_data(db: Session) -> dict:
        """Permanently delete anonymized users whose BAO retention has expired.

        Called monthly by the purge_bao_expired_data Celery task.
        After 7 years, all remaining transactions, documents, tax reports,
        properties, and the user record itself are fully deleted.
        """
        now = datetime.utcnow()
        expired_users = (
            db.query(User)
            .filter(
                User.account_status == "anonymized",
                User.bao_retention_expiry.isnot(None),
                User.bao_retention_expiry <= now,
            )
            .all()
        )

        purged_count = 0
        for user in expired_users:
            user_id = user.id
            try:
                # Now safe to cascade-delete everything
                db.delete(user)
                db.flush()
                purged_count += 1
                logger.info(
                    "BAO retention expired — fully purged user %s", user_id
                )
            except Exception:
                db.rollback()
                logger.exception(
                    "Failed to purge expired user %s", user_id
                )

        if purged_count:
            db.commit()

        return {
            "expired_users_found": len(expired_users),
            "purged_count": purged_count,
            "run_at": now.isoformat(),
        }

    # ------------------------------------------------------------------
    # 5. Admin cancellation statistics
    # ------------------------------------------------------------------

    @staticmethod
    def get_admin_cancellation_stats(db: Session) -> dict:
        """Return aggregated cancellation statistics for the admin dashboard.

        Includes monthly cancellation count, reason distribution,
        reactivation rate, and average user lifetime.
        """
        now = datetime.utcnow()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Monthly cancellations: users deactivated this calendar month
        monthly_cancellations = (
            db.query(func.count(User.id))
            .filter(
                User.account_status.in_(["deactivated", "deletion_pending"]),
                User.deactivated_at >= month_start,
            )
            .scalar()
            or 0
        )

        # Also count hard-deleted accounts from this month
        monthly_hard_deleted = (
            db.query(func.count(AccountDeletionLog.id))
            .filter(AccountDeletionLog.deleted_at >= month_start)
            .scalar()
            or 0
        )
        monthly_cancellations += monthly_hard_deleted

        # Reason distribution from currently deactivated users
        reason_rows = (
            db.query(
                func.coalesce(User.cancellation_reason, "not_specified"),
                func.count(User.id),
            )
            .filter(User.account_status.in_(["deactivated", "deletion_pending"]))
            .group_by(func.coalesce(User.cancellation_reason, "not_specified"))
            .all()
        )
        cancellation_reasons: dict[str, int] = {
            reason: count for reason, count in reason_rows
        }

        # Reactivation rate: users who were deactivated then reactivated
        # We approximate this by looking at active users who have a
        # cancellation_reason set (they went through deactivation and came back).
        total_ever_deactivated = (
            db.query(func.count(User.id))
            .filter(
                User.account_status.in_(["deactivated", "deletion_pending", "active"]),
                User.cancellation_reason.isnot(None),
            )
            .scalar()
            or 0
        )
        reactivated_count = (
            db.query(func.count(User.id))
            .filter(
                User.account_status == "active",
                User.cancellation_reason.isnot(None),
            )
            .scalar()
            or 0
        )
        reactivation_rate = (
            reactivated_count / total_ever_deactivated
            if total_ever_deactivated > 0
            else 0.0
        )

        # Average user lifetime in days (across all users with created_at)
        avg_lifetime = (
            db.query(
                func.avg(
                    func.extract("epoch", func.coalesce(User.deactivated_at, now) - User.created_at)
                    / 86400  # seconds → days
                )
            )
            .filter(User.created_at.isnot(None))
            .scalar()
        )
        average_user_lifetime_days = float(avg_lifetime) if avg_lifetime else 0.0

        return {
            "monthly_cancellations": monthly_cancellations,
            "cancellation_reasons": cancellation_reasons,
            "reactivation_rate": round(reactivation_rate, 4),
            "average_user_lifetime_days": round(average_user_lifetime_days, 2),
        }
