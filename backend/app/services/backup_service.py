"""
Data backup service for database and document storage.
Creates daily backups and stores them in remote location.
"""

import logging
import os
import subprocess
import tarfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import BackupError
from app.services.minio_service import MinioService

logger = logging.getLogger(__name__)


class BackupService:
    """Service for creating and managing backups"""

    def __init__(self, db: Session):
        self.db = db
        self.minio_service = MinioService()
        self.backup_bucket = "taxja-backups"
        self.backup_dir = Path("/tmp/taxja_backups")
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def create_full_backup(self) -> Dict[str, str]:
        """
        Create a full backup of database and documents.
        
        Returns:
            Dictionary with backup information
            
        Raises:
            BackupError: If backup fails
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_name = f"taxja_backup_{timestamp}"

        try:
            logger.info(f"Starting full backup: {backup_name}")

            # Create backup directory
            backup_path = self.backup_dir / backup_name
            backup_path.mkdir(parents=True, exist_ok=True)

            # Backup database
            db_backup_file = self._backup_database(backup_path, timestamp)
            logger.info(f"Database backup created: {db_backup_file}")

            # Backup documents from MinIO
            docs_backup_file = self._backup_documents(backup_path, timestamp)
            logger.info(f"Documents backup created: {docs_backup_file}")

            # Create tarball
            tarball_path = self._create_tarball(backup_path, backup_name)
            logger.info(f"Backup tarball created: {tarball_path}")

            # Upload to remote storage (MinIO backup bucket)
            remote_path = self._upload_to_remote(tarball_path, backup_name)
            logger.info(f"Backup uploaded to remote storage: {remote_path}")

            # Cleanup local files
            self._cleanup_local_backup(backup_path, tarball_path)

            backup_info = {
                "backup_name": backup_name,
                "timestamp": timestamp,
                "database_backup": db_backup_file.name,
                "documents_backup": docs_backup_file.name,
                "remote_path": remote_path,
                "status": "success",
            }

            logger.info(f"Full backup completed successfully: {backup_name}")
            return backup_info

        except Exception as e:
            logger.error(f"Backup failed: {str(e)}")
            raise BackupError(
                message=f"Failed to create backup: {str(e)}",
                details={"backup_name": backup_name, "error": str(e)},
            )

    def create_database_backup(self) -> Dict[str, str]:
        """
        Create a database-only backup.
        
        Returns:
            Dictionary with backup information
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        backup_name = f"taxja_db_backup_{timestamp}"

        try:
            logger.info(f"Starting database backup: {backup_name}")

            backup_path = self.backup_dir / backup_name
            backup_path.mkdir(parents=True, exist_ok=True)

            db_backup_file = self._backup_database(backup_path, timestamp)

            # Upload to remote storage
            remote_path = self._upload_file_to_remote(db_backup_file, f"{backup_name}.sql")

            backup_info = {
                "backup_name": backup_name,
                "timestamp": timestamp,
                "backup_file": db_backup_file.name,
                "remote_path": remote_path,
                "status": "success",
            }

            logger.info(f"Database backup completed: {backup_name}")
            return backup_info

        except Exception as e:
            logger.error(f"Database backup failed: {str(e)}")
            raise BackupError(
                message=f"Failed to create database backup: {str(e)}",
                details={"backup_name": backup_name, "error": str(e)},
            )

    def create_documents_backup(self) -> Dict[str, str]:
        """
        Create a documents-only backup.
        
        Returns:
            Dictionary with backup information
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_name = f"taxja_docs_backup_{timestamp}"

        try:
            logger.info(f"Starting documents backup: {backup_name}")

            backup_path = self.backup_dir / backup_name
            backup_path.mkdir(parents=True, exist_ok=True)

            docs_backup_file = self._backup_documents(backup_path, timestamp)

            # Upload to remote storage
            remote_path = self._upload_file_to_remote(
                docs_backup_file, f"{backup_name}.tar.gz"
            )

            backup_info = {
                "backup_name": backup_name,
                "timestamp": timestamp,
                "backup_file": docs_backup_file.name,
                "remote_path": remote_path,
                "status": "success",
            }

            logger.info(f"Documents backup completed: {backup_name}")
            return backup_info

        except Exception as e:
            logger.error(f"Documents backup failed: {str(e)}")
            raise BackupError(
                message=f"Failed to create documents backup: {str(e)}",
                details={"backup_name": backup_name, "error": str(e)},
            )

    def _backup_database(self, backup_path: Path, timestamp: str) -> Path:
        """
        Backup PostgreSQL database using pg_dump.
        
        Args:
            backup_path: Directory to store backup
            timestamp: Timestamp for backup file
            
        Returns:
            Path to backup file
        """
        backup_file = backup_path / f"database_{timestamp}.sql"

        # Build pg_dump command
        pg_dump_cmd = [
            "pg_dump",
            "-h", settings.POSTGRES_SERVER,
            "-p", str(settings.POSTGRES_PORT),
            "-U", settings.POSTGRES_USER,
            "-d", settings.POSTGRES_DB,
            "-F", "c",  # Custom format (compressed)
            "-f", str(backup_file),
        ]

        # Set password via environment variable
        env = os.environ.copy()
        env["PGPASSWORD"] = settings.POSTGRES_PASSWORD

        try:
            result = subprocess.run(
                pg_dump_cmd,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            logger.info(f"pg_dump completed successfully")
            return backup_file

        except subprocess.CalledProcessError as e:
            logger.error(f"pg_dump failed: {e.stderr}")
            raise BackupError(
                message="Database backup failed",
                details={"error": e.stderr},
            )

    def _backup_documents(self, backup_path: Path, timestamp: str) -> Path:
        """
        Backup documents from MinIO storage.
        
        Args:
            backup_path: Directory to store backup
            timestamp: Timestamp for backup file
            
        Returns:
            Path to backup file
        """
        docs_dir = backup_path / "documents"
        docs_dir.mkdir(parents=True, exist_ok=True)

        # Download all documents from MinIO
        try:
            # List all objects in documents bucket
            objects = self.minio_service.list_objects("taxja-documents")

            for obj in objects:
                # Download each object
                local_path = docs_dir / obj.object_name
                local_path.parent.mkdir(parents=True, exist_ok=True)

                self.minio_service.download_file(
                    bucket_name="taxja-documents",
                    object_name=obj.object_name,
                    file_path=str(local_path),
                )

            # Create tarball of documents
            tarball_path = backup_path / f"documents_{timestamp}.tar.gz"
            with tarfile.open(tarball_path, "w:gz") as tar:
                tar.add(docs_dir, arcname="documents")

            return tarball_path

        except Exception as e:
            logger.error(f"Documents backup failed: {str(e)}")
            raise BackupError(
                message="Documents backup failed",
                details={"error": str(e)},
            )

    def _create_tarball(self, backup_path: Path, backup_name: str) -> Path:
        """
        Create a compressed tarball of the backup.
        
        Args:
            backup_path: Directory containing backup files
            backup_name: Name for the tarball
            
        Returns:
            Path to tarball
        """
        tarball_path = self.backup_dir / f"{backup_name}.tar.gz"

        with tarfile.open(tarball_path, "w:gz") as tar:
            tar.add(backup_path, arcname=backup_name)

        return tarball_path

    def _upload_to_remote(self, tarball_path: Path, backup_name: str) -> str:
        """
        Upload backup tarball to remote storage.
        
        Args:
            tarball_path: Path to tarball
            backup_name: Name of backup
            
        Returns:
            Remote path
        """
        # Ensure backup bucket exists
        if not self.minio_service.bucket_exists(self.backup_bucket):
            self.minio_service.create_bucket(self.backup_bucket)

        # Upload tarball
        object_name = f"{backup_name}.tar.gz"
        self.minio_service.upload_file(
            bucket_name=self.backup_bucket,
            object_name=object_name,
            file_path=str(tarball_path),
        )

        return f"{self.backup_bucket}/{object_name}"

    def _upload_file_to_remote(self, file_path: Path, object_name: str) -> str:
        """
        Upload a single file to remote storage.
        
        Args:
            file_path: Path to file
            object_name: Name for object in storage
            
        Returns:
            Remote path
        """
        # Ensure backup bucket exists
        if not self.minio_service.bucket_exists(self.backup_bucket):
            self.minio_service.create_bucket(self.backup_bucket)

        # Upload file
        self.minio_service.upload_file(
            bucket_name=self.backup_bucket,
            object_name=object_name,
            file_path=str(file_path),
        )

        return f"{self.backup_bucket}/{object_name}"

    def _cleanup_local_backup(self, backup_path: Path, tarball_path: Path) -> None:
        """
        Clean up local backup files after upload.
        
        Args:
            backup_path: Directory containing backup files
            tarball_path: Path to tarball
        """
        try:
            # Remove backup directory
            import shutil
            shutil.rmtree(backup_path)

            # Remove tarball
            tarball_path.unlink()

            logger.info("Local backup files cleaned up")

        except Exception as e:
            logger.warning(f"Failed to cleanup local backup files: {str(e)}")

    def list_backups(self) -> list:
        """
        List all available backups.
        
        Returns:
            List of backup information
        """
        try:
            if not self.minio_service.bucket_exists(self.backup_bucket):
                return []

            objects = self.minio_service.list_objects(self.backup_bucket)

            backups = []
            for obj in objects:
                backups.append(
                    {
                        "name": obj.object_name,
                        "size": obj.size,
                        "last_modified": obj.last_modified.isoformat(),
                    }
                )

            return backups

        except Exception as e:
            logger.error(f"Failed to list backups: {str(e)}")
            return []

    def delete_old_backups(self, keep_days: int = 30) -> int:
        """
        Delete backups older than specified days.
        
        Args:
            keep_days: Number of days to keep backups
            
        Returns:
            Number of backups deleted
        """
        try:
            if not self.minio_service.bucket_exists(self.backup_bucket):
                return 0

            cutoff_date = datetime.utcnow().timestamp() - (keep_days * 86400)
            objects = self.minio_service.list_objects(self.backup_bucket)

            deleted_count = 0
            for obj in objects:
                if obj.last_modified.timestamp() < cutoff_date:
                    self.minio_service.delete_file(self.backup_bucket, obj.object_name)
                    deleted_count += 1
                    logger.info(f"Deleted old backup: {obj.object_name}")

            logger.info(f"Deleted {deleted_count} old backups")
            return deleted_count

        except Exception as e:
            logger.error(f"Failed to delete old backups: {str(e)}")
            return 0


def get_backup_service(db: Session) -> BackupService:
    """Get backup service instance"""
    return BackupService(db)
