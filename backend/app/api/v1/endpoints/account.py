"""Account management API endpoints for cancellation, reactivation, and data export."""
import logging
from datetime import datetime

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException, Query, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.core.config import settings
from app.core.security import get_current_user
from app.db.base import get_db
from app.models.user import User
from app.schemas.account import (
    CancellationImpactResponse,
    DataExportRequest,
    DataExportStatusResponse,
    DeactivateAccountRequest,
    ReactivateAccountResponse,
)
from app.services.account_cancellation_service import AccountCancellationService
from app.tasks.data_export_tasks import async_export_user_data

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/cancellation-impact", response_model=CancellationImpactResponse)
def get_cancellation_impact(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a summary of data that would be affected by account cancellation."""
    impact = AccountCancellationService.get_cancellation_impact(
        user_id=current_user.id, db=db
    )
    return impact


@router.post("/deactivate")
def deactivate_account(
    request: DeactivateAccountRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Deactivate (soft-delete) the current user's account.

    Requires password verification and the confirmation word "DELETE".
    """
    try:
        result = AccountCancellationService.deactivate_account(
            user_id=current_user.id,
            password=request.password,
            reason=request.reason,
            confirmation_word=request.confirmation_word,
            two_factor_code=request.two_factor_code,
            db=db,
        )
        return result
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/reactivate", response_model=ReactivateAccountResponse)
def reactivate_account(
    reactivation_token: str = Query(..., description="JWT token containing user_id for reactivation"),
    db: Session = Depends(get_db),
):
    """Reactivate a deactivated account using a token link (no login required).

    The reactivation_token is a JWT that contains the user_id in the 'sub' claim.
    """
    try:
        payload = jwt.decode(
            reactivation_token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        user_id_str: str = payload.get("sub")
        if user_id_str is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid reactivation token",
            )
        user_id = int(user_id_str)
    except (JWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reactivation token",
        )

    try:
        result = AccountCancellationService.reactivate_account(
            user_id=user_id, db=db
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/export-data")
def request_data_export(
    request: DataExportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Export user data synchronously and return a download URL.

    For small-to-medium data volumes this completes in seconds.
    Falls back to Celery async if CELERY_EXPORT=true is set.
    """
    import os

    use_celery = os.getenv("CELERY_EXPORT", "false").lower() == "true"

    if use_celery:
        task = async_export_user_data.delay(
            user_id=current_user.id,
            encryption_password=request.encryption_password,
        )
        return {"task_id": task.id, "status": "pending"}

    # Synchronous export — no Celery needed
    try:
        from app.services.data_export_service import DataExportService

        download_url = DataExportService.export_user_data(
            user_id=current_user.id,
            encryption_password=request.encryption_password,
            db=db,
        )
        # Return a fake task_id so the frontend flow still works
        import uuid

        fake_task_id = str(uuid.uuid4())
        # Store result in Redis so poll endpoint can find it
        try:
            import json
            import redis as sync_redis

            from app.core.config import settings

            r = sync_redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                decode_responses=True,
            )
            r.setex(
                f"export_result:{fake_task_id}",
                86400,  # 24h TTL
                json.dumps({"status": "ready", "download_url": download_url}),
            )
            r.close()
        except Exception:
            logger.warning("Could not cache export result in Redis")

        return {
            "task_id": fake_task_id,
            "status": "ready",
            "download_url": download_url,
        }
    except Exception as e:
        logger.exception("Sync data export failed for user %s", current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Data export failed: {str(e)}",
        )


@router.get("/export-status/{task_id}", response_model=DataExportStatusResponse)
def get_export_status(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Check the status of a data export task (async Celery or sync cached)."""
    # First check Redis for sync export results
    try:
        import json
        import redis as sync_redis

        from app.core.config import settings

        r = sync_redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True,
        )
        cached = r.get(f"export_result:{task_id}")
        r.close()
        if cached:
            data = json.loads(cached)
            return DataExportStatusResponse(
                status=data.get("status", "ready"),
                download_url=data.get("download_url"),
            )
    except Exception:
        pass

    # Fall back to Celery AsyncResult
    result = AsyncResult(task_id, app=celery_app)

    if result.state == "PENDING":
        return DataExportStatusResponse(status="pending")
    elif result.state == "STARTED" or result.state == "RETRY":
        return DataExportStatusResponse(status="processing")
    elif result.state == "SUCCESS":
        task_result = result.result or {}
        export_status = task_result.get("status", "ready")
        download_url = task_result.get("download_url")
        return DataExportStatusResponse(
            status=export_status,
            download_url=download_url,
        )
    elif result.state == "FAILURE":
        return DataExportStatusResponse(status="failed")
    else:
        return DataExportStatusResponse(status="processing")
