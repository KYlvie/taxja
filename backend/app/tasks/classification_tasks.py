"""
Celery tasks for ML classification model retraining.

Periodic task checks if enough new corrections have accumulated
(default threshold: 50) and triggers ML model retraining automatically.
LLM classifications feed into ClassificationCorrection records, which
are used as training data — so the LLM gradually "teaches" the ML model.
"""
import logging
from datetime import datetime
from typing import Dict, Optional

from celery import Task
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)


class DatabaseTask(Task):
    """Base task with database session management."""
    _db: Optional[Session] = None

    @property
    def db(self) -> Session:
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    def after_return(self, *args, **kwargs):
        if self._db is not None:
            self._db.close()
            self._db = None


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="classification.auto_retrain",
    max_retries=2,
    default_retry_delay=300,
)
def auto_retrain_classification_model(self) -> Dict:
    """
    Check if enough new corrections have accumulated and retrain
    the ML classification model if the threshold is met.

    This task is scheduled to run daily via Celery Beat.
    It is safe to call multiple times — it only retrains when
    new corrections exceed the configured threshold (default 50).

    Returns:
        Dict with retraining status and statistics.
    """
    try:
        from app.services.classification_learning import ClassificationLearningService

        logger.info("Auto-retrain task started: checking correction count")

        service = ClassificationLearningService(db=self.db)
        new_count = service.get_corrections_since_last_training()

        if not service.should_retrain():
            logger.info(
                "Auto-retrain skipped: %d new corrections (threshold: %d)",
                new_count,
                service.min_corrections_for_retrain,
            )
            return {
                "retrained": False,
                "reason": "not_enough_corrections",
                "new_corrections": new_count,
                "threshold": service.min_corrections_for_retrain,
                "checked_at": datetime.now().isoformat(),
            }

        # Retrain
        result = service.auto_retrain_if_needed()

        if result.get("retrained"):
            logger.info(
                "Auto-retrain succeeded: trained on %d corrections",
                result.get("corrections_count", 0),
            )
        else:
            logger.warning("Auto-retrain failed: %s", result.get("reason"))

        result["checked_at"] = datetime.now().isoformat()
        result["task_id"] = self.request.id
        return result

    except Exception as exc:
        logger.error("Auto-retrain task error: %s", exc, exc_info=True)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        return {
            "retrained": False,
            "error": str(exc),
            "task_id": self.request.id,
            "failed_at": datetime.now().isoformat(),
        }
