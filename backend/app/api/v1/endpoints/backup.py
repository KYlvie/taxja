"""
Backup management API endpoints.
Admin-only endpoints for creating and managing backups.
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.api.deps import get_current_admin_user, get_db
from app.core.exceptions import BackupError
from app.models.user import User
from app.schemas.backup import (
    BackupInfo,
    BackupListResponse,
    BackupTriggerResponse,
    RestoreRequest,
    RestoreResponse,
)
from app.services.backup_service import BackupService
from app.services.restore_service import RestoreService
from app.tasks.backup_tasks import (
    cleanup_old_backups,
    create_daily_backup,
    create_database_backup,
    create_documents_backup,
)

router = APIRouter()


@router.post("/trigger/full", response_model=BackupTriggerResponse)
def trigger_full_backup(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Trigger a full backup (database + documents).
    Admin only.
    """
    try:
        # Trigger async backup task
        task = create_daily_backup.delay()

        return BackupTriggerResponse(
            task_id=task.id,
            status="triggered",
            message="Full backup task started",
        )

    except Exception as e:
        logger.exception("Failed to trigger full backup")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="backup_operation_failed",
        )


@router.post("/trigger/database", response_model=BackupTriggerResponse)
def trigger_database_backup(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Trigger a database-only backup.
    Admin only.
    """
    try:
        task = create_database_backup.delay()

        return BackupTriggerResponse(
            task_id=task.id,
            status="triggered",
            message="Database backup task started",
        )

    except Exception as e:
        logger.exception("Failed to trigger database backup")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="backup_operation_failed",
        )


@router.post("/trigger/documents", response_model=BackupTriggerResponse)
def trigger_documents_backup(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Trigger a documents-only backup.
    Admin only.
    """
    try:
        task = create_documents_backup.delay()

        return BackupTriggerResponse(
            task_id=task.id,
            status="triggered",
            message="Documents backup task started",
        )

    except Exception as e:
        logger.exception("Failed to trigger documents backup")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="backup_operation_failed",
        )


@router.get("/list", response_model=BackupListResponse)
def list_backups(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    List all available backups.
    Admin only.
    """
    try:
        backup_service = BackupService(db)
        backups = backup_service.list_backups()

        return BackupListResponse(
            backups=backups,
            total=len(backups),
        )

    except Exception as e:
        logger.exception("Failed to list backups")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="backup_operation_failed",
        )


@router.post("/cleanup", response_model=BackupTriggerResponse)
def trigger_backup_cleanup(
    keep_days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Trigger cleanup of old backups.
    Admin only.
    
    Args:
        keep_days: Number of days to keep backups (default: 30)
    """
    try:
        task = cleanup_old_backups.delay(keep_days)

        return BackupTriggerResponse(
            task_id=task.id,
            status="triggered",
            message=f"Backup cleanup task started (keep last {keep_days} days)",
        )

    except Exception as e:
        logger.exception("Failed to trigger backup cleanup")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="backup_operation_failed",
        )



@router.post("/restore", response_model=RestoreResponse)
def restore_from_backup(
    restore_request: RestoreRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Restore data from a backup.
    Admin only. WARNING: This will overwrite existing data!
    
    Args:
        restore_request: Restore configuration
    """
    try:
        restore_service = RestoreService(db)

        restore_info = restore_service.restore_from_backup(
            backup_name=restore_request.backup_name,
            restore_database=restore_request.restore_database,
            restore_documents=restore_request.restore_documents,
            validate_integrity=restore_request.validate_integrity,
        )

        return RestoreResponse(
            backup_name=restore_info["backup_name"],
            timestamp=restore_info.get("timestamp", ""),
            database_restored=restore_info["database_restored"],
            documents_restored=restore_info["documents_restored"],
            validation_passed=restore_info["validation_passed"],
            status=restore_info["status"],
            message="Restore completed successfully",
        )

    except Exception as e:
        logger.exception("Failed to restore from backup")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="backup_operation_failed",
        )


@router.post("/restore/database", response_model=RestoreResponse)
def restore_database_only(
    backup_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Restore database only from a backup.
    Admin only. WARNING: This will overwrite existing database!
    
    Args:
        backup_name: Name of backup to restore
    """
    try:
        restore_service = RestoreService(db)
        restore_info = restore_service.restore_database_only(backup_name)

        return RestoreResponse(
            backup_name=restore_info["backup_name"],
            timestamp="",
            database_restored=restore_info["database_restored"],
            documents_restored=False,
            validation_passed=False,
            status=restore_info["status"],
            message="Database restore completed successfully",
        )

    except Exception as e:
        logger.exception("Failed to restore database")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="backup_operation_failed",
        )
