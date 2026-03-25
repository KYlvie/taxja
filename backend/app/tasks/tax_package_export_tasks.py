"""Celery tasks for asynchronous tax package export."""

from __future__ import annotations

import logging
from typing import Any

from app.celery_app import celery_app
from app.db.base import SessionLocal
from app.models.user import User
from app.services.tax_package_export_service import (
    TaxPackageExportService,
    cache_tax_package_export_state,
)

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, soft_time_limit=1800, time_limit=1980)
def async_export_tax_package(
    self,
    user_id: int,
    tax_year: int,
    language: str = "de",
    include_foundation_materials: bool = False,
) -> dict[str, Any]:
    """Prepare a tax package in the background and upload parts to storage."""

    db = SessionLocal()
    export_id = self.request.id
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"User {user_id} not found")

        cache_tax_package_export_state(
            export_id,
            {
                "export_id": export_id,
                "user_id": user_id,
                "status": "processing",
                "tax_year": tax_year,
                "language": language,
                "include_foundation_materials": include_foundation_materials,
            },
        )

        service = TaxPackageExportService(
            db=db,
            user=user,
            tax_year=tax_year,
            language=language,
            include_foundation_materials=include_foundation_materials,
        )
        result = service.export_to_storage(export_id)
        logger.info("Tax package export completed for user %s (%s)", user_id, export_id)
        return result
    except Exception as exc:
        logger.exception("Tax package export failed for user %s (%s): %s", user_id, export_id, exc)
        failure = {
            "export_id": export_id,
            "user_id": user_id,
            "status": "failed",
            "tax_year": tax_year,
            "language": language,
            "include_foundation_materials": include_foundation_materials,
            "failure": {
                "reason": str(exc),
            },
        }
        cache_tax_package_export_state(export_id, failure)
        return failure
    finally:
        db.close()
