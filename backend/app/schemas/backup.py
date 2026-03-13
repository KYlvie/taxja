"""
Pydantic schemas for backup operations.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class BackupInfo(BaseModel):
    """Information about a backup"""

    name: str = Field(..., description="Backup file name")
    size: int = Field(..., description="Backup file size in bytes")
    last_modified: str = Field(..., description="Last modified timestamp")


class BackupTriggerResponse(BaseModel):
    """Response when triggering a backup"""

    task_id: str = Field(..., description="Celery task ID")
    status: str = Field(..., description="Task status")
    message: str = Field(..., description="Status message")


class BackupListResponse(BaseModel):
    """Response for listing backups"""

    backups: List[BackupInfo] = Field(..., description="List of available backups")
    total: int = Field(..., description="Total number of backups")


class BackupCreateResponse(BaseModel):
    """Response after creating a backup"""

    backup_name: str = Field(..., description="Name of the backup")
    timestamp: str = Field(..., description="Backup timestamp")
    database_backup: Optional[str] = Field(None, description="Database backup file name")
    documents_backup: Optional[str] = Field(None, description="Documents backup file name")
    remote_path: str = Field(..., description="Remote storage path")
    status: str = Field(..., description="Backup status")


class RestoreRequest(BaseModel):
    """Request to restore from backup"""

    backup_name: str = Field(..., description="Name of backup to restore")
    restore_database: bool = Field(True, description="Restore database")
    restore_documents: bool = Field(True, description="Restore documents")
    validate_integrity: bool = Field(True, description="Validate data integrity after restore")


class RestoreResponse(BaseModel):
    """Response after restore operation"""

    backup_name: str = Field(..., description="Name of restored backup")
    timestamp: str = Field(..., description="Restore timestamp")
    database_restored: bool = Field(..., description="Database restore status")
    documents_restored: bool = Field(..., description="Documents restore status")
    validation_passed: bool = Field(..., description="Data integrity validation status")
    status: str = Field(..., description="Overall restore status")
    message: str = Field(..., description="Status message")
