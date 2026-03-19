"""Celery tasks for asynchronous data export."""
import logging
from typing import Dict, Any

from app.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, soft_time_limit=600, time_limit=660)
def async_export_user_data(self, user_id: int, encryption_password: str) -> Dict[str, Any]:
    """Export user data asynchronously and store the download URL on completion.

    This task wraps :meth:`DataExportService.export_user_data` so the
    potentially long-running export (querying, zipping, uploading) runs
    outside the request/response cycle.

    The Celery result backend stores the returned dict so the API can poll
    ``AsyncResult(task_id)`` for the download URL.

    Args:
        user_id: ID of the user whose data to export.
        encryption_password: Password for AES-256 ZIP encryption.

    Returns:
        Dict with ``status``, ``download_url``, and metadata on success,
        or ``status="failed"`` with an ``error`` message on failure.
    """
    from app.db.base import SessionLocal
    from app.services.data_export_service import DataExportService

    db = SessionLocal()
    try:
        logger.info("Starting async data export for user %s (task %s)", user_id, self.request.id)

        download_url = DataExportService.export_user_data(
            user_id=user_id,
            encryption_password=encryption_password,
            db=db,
        )

        logger.info("Async data export completed for user %s", user_id)

        return {
            "status": "ready",
            "download_url": download_url,
            "user_id": user_id,
        }
    except Exception as e:
        logger.exception("Async data export failed for user %s: %s", user_id, e)
        return {
            "status": "failed",
            "error": str(e),
            "user_id": user_id,
        }
    finally:
        db.close()
