"""
Celery tasks for automated backups.
Scheduled daily backups of database and documents.
"""

import logging
from datetime import datetime

from celery import shared_task

from app.db.session import SessionLocal
from app.services.backup_service import BackupService

logger = logging.getLogger(__name__)


@shared_task(name="backup.create_daily_backup")
def create_daily_backup() -> dict:
    """
    Create daily full backup (database + documents).
    Scheduled to run at 2 AM UTC daily.
    
    Returns:
        Backup information dictionary
    """
    logger.info("Starting scheduled daily backup")

    db = SessionLocal()
    try:
        backup_service = BackupService(db)

        # Create full backup
        backup_info = backup_service.create_full_backup()

        logger.info(f"Daily backup completed: {backup_info['backup_name']}")
        return backup_info

    except Exception as e:
        logger.error(f"Daily backup failed: {str(e)}")
        raise

    finally:
        db.close()


@shared_task(name="backup.create_database_backup")
def create_database_backup() -> dict:
    """
    Create database-only backup.
    Can be triggered manually or scheduled.
    
    Returns:
        Backup information dictionary
    """
    logger.info("Starting database backup")

    db = SessionLocal()
    try:
        backup_service = BackupService(db)
        backup_info = backup_service.create_database_backup()

        logger.info(f"Database backup completed: {backup_info['backup_name']}")
        return backup_info

    except Exception as e:
        logger.error(f"Database backup failed: {str(e)}")
        raise

    finally:
        db.close()


@shared_task(name="backup.create_documents_backup")
def create_documents_backup() -> dict:
    """
    Create documents-only backup.
    Can be triggered manually or scheduled.
    
    Returns:
        Backup information dictionary
    """
    logger.info("Starting documents backup")

    db = SessionLocal()
    try:
        backup_service = BackupService(db)
        backup_info = backup_service.create_documents_backup()

        logger.info(f"Documents backup completed: {backup_info['backup_name']}")
        return backup_info

    except Exception as e:
        logger.error(f"Documents backup failed: {str(e)}")
        raise

    finally:
        db.close()


@shared_task(name="backup.cleanup_old_backups")
def cleanup_old_backups(keep_days: int = 30) -> dict:
    """
    Delete backups older than specified days.
    Scheduled to run weekly.
    
    Args:
        keep_days: Number of days to keep backups (default: 30)
        
    Returns:
        Cleanup information dictionary
    """
    logger.info(f"Starting backup cleanup (keep last {keep_days} days)")

    db = SessionLocal()
    try:
        backup_service = BackupService(db)
        deleted_count = backup_service.delete_old_backups(keep_days)

        cleanup_info = {
            "deleted_count": deleted_count,
            "keep_days": keep_days,
            "timestamp": datetime.utcnow().isoformat(),
        }

        logger.info(f"Backup cleanup completed: {deleted_count} backups deleted")
        return cleanup_info

    except Exception as e:
        logger.error(f"Backup cleanup failed: {str(e)}")
        raise

    finally:
        db.close()
