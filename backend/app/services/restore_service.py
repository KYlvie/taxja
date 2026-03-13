"""
Data restore service for recovering from backups.
Restores database and documents with integrity validation.
"""

import logging
import os
import subprocess
import tarfile
from pathlib import Path
from typing import Dict, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import RestoreError
from app.services.minio_service import MinioService

logger = logging.getLogger(__name__)


class RestoreService:
    """Service for restoring data from backups"""

    def __init__(self, db: Session):
        self.db = db
        self.minio_service = MinioService()
        self.backup_bucket = "taxja-backups"
        self.restore_dir = Path("/tmp/taxja_restore")
        self.restore_dir.mkdir(parents=True, exist_ok=True)

    def restore_from_backup(
        self,
        backup_name: str,
        restore_database: bool = True,
        restore_documents: bool = True,
        validate_integrity: bool = True,
    ) -> Dict[str, any]:
        """
        Restore data from a backup.
        
        Args:
            backup_name: Name of backup to restore
            restore_database: Whether to restore database
            restore_documents: Whether to restore documents
            validate_integrity: Whether to validate data integrity
            
        Returns:
            Dictionary with restore information
            
        Raises:
            RestoreError: If restore fails
        """
        try:
            logger.info(f"Starting restore from backup: {backup_name}")

            # Download backup from remote storage
            backup_path = self._download_backup(backup_name)
            logger.info(f"Backup downloaded: {backup_path}")

            # Extract backup
            extract_path = self._extract_backup(backup_path)
            logger.info(f"Backup extracted: {extract_path}")

            restore_info = {
                "backup_name": backup_name,
                "database_restored": False,
                "documents_restored": False,
                "validation_passed": False,
            }

            # Restore database
            if restore_database:
                self._restore_database(extract_path)
                restore_info["database_restored"] = True
                logger.info("Database restored successfully")

            # Restore documents
            if restore_documents:
                self._restore_documents(extract_path)
                restore_info["documents_restored"] = True
                logger.info("Documents restored successfully")

            # Validate integrity
            if validate_integrity:
                validation_result = self._validate_integrity()
                restore_info["validation_passed"] = validation_result
                logger.info(f"Data integrity validation: {'passed' if validation_result else 'failed'}")

            # Cleanup
            self._cleanup_restore_files(extract_path, backup_path)

            restore_info["status"] = "success"
            logger.info(f"Restore completed successfully: {backup_name}")

            return restore_info

        except Exception as e:
            logger.error(f"Restore failed: {str(e)}")
            raise RestoreError(
                message=f"Failed to restore from backup: {str(e)}",
                details={"backup_name": backup_name, "error": str(e)},
            )

    def restore_database_only(self, backup_name: str) -> Dict[str, any]:
        """
        Restore database only from a backup.
        
        Args:
            backup_name: Name of backup to restore
            
        Returns:
            Dictionary with restore information
        """
        try:
            logger.info(f"Starting database restore from: {backup_name}")

            # Download backup
            backup_path = self._download_backup(backup_name)

            # If it's a tarball, extract it
            if backup_name.endswith(".tar.gz"):
                extract_path = self._extract_backup(backup_path)
                db_file = self._find_database_file(extract_path)
            else:
                db_file = backup_path

            # Restore database
            self._restore_database_from_file(db_file)

            restore_info = {
                "backup_name": backup_name,
                "database_restored": True,
                "status": "success",
            }

            logger.info("Database restore completed successfully")
            return restore_info

        except Exception as e:
            logger.error(f"Database restore failed: {str(e)}")
            raise RestoreError(
                message=f"Failed to restore database: {str(e)}",
                details={"backup_name": backup_name, "error": str(e)},
            )

    def _download_backup(self, backup_name: str) -> Path:
        """
        Download backup from remote storage.
        
        Args:
            backup_name: Name of backup
            
        Returns:
            Path to downloaded backup
        """
        # Ensure backup exists
        if not self.minio_service.file_exists(self.backup_bucket, backup_name):
            raise RestoreError(
                message=f"Backup not found: {backup_name}",
                details={"backup_name": backup_name},
            )

        # Download backup
        backup_path = self.restore_dir / backup_name
        self.minio_service.download_file(
            bucket_name=self.backup_bucket,
            object_name=backup_name,
            file_path=str(backup_path),
        )

        return backup_path

    def _extract_backup(self, backup_path: Path) -> Path:
        """
        Extract backup tarball.
        
        Args:
            backup_path: Path to backup tarball
            
        Returns:
            Path to extracted directory
        """
        extract_path = self.restore_dir / backup_path.stem

        with tarfile.open(backup_path, "r:gz") as tar:
            tar.extractall(path=extract_path)

        return extract_path

    def _restore_database(self, extract_path: Path) -> None:
        """
        Restore database from extracted backup.
        
        Args:
            extract_path: Path to extracted backup directory
        """
        # Find database backup file
        db_file = self._find_database_file(extract_path)

        if not db_file:
            raise RestoreError(
                message="Database backup file not found in backup",
                details={"extract_path": str(extract_path)},
            )

        self._restore_database_from_file(db_file)

    def _restore_database_from_file(self, db_file: Path) -> None:
        """
        Restore database from a backup file using pg_restore.
        
        Args:
            db_file: Path to database backup file
        """
        # Build pg_restore command
        pg_restore_cmd = [
            "pg_restore",
            "-h", settings.POSTGRES_SERVER,
            "-p", str(settings.POSTGRES_PORT),
            "-U", settings.POSTGRES_USER,
            "-d", settings.POSTGRES_DB,
            "-c",  # Clean (drop) database objects before recreating
            "-F", "c",  # Custom format
            str(db_file),
        ]

        # Set password via environment variable
        env = os.environ.copy()
        env["PGPASSWORD"] = settings.POSTGRES_PASSWORD

        try:
            result = subprocess.run(
                pg_restore_cmd,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            logger.info("pg_restore completed successfully")

        except subprocess.CalledProcessError as e:
            logger.error(f"pg_restore failed: {e.stderr}")
            raise RestoreError(
                message="Database restore failed",
                details={"error": e.stderr},
            )

    def _restore_documents(self, extract_path: Path) -> None:
        """
        Restore documents from extracted backup.
        
        Args:
            extract_path: Path to extracted backup directory
        """
        # Find documents backup file
        docs_tarball = None
        for file in extract_path.rglob("documents_*.tar.gz"):
            docs_tarball = file
            break

        if not docs_tarball:
            raise RestoreError(
                message="Documents backup file not found in backup",
                details={"extract_path": str(extract_path)},
            )

        # Extract documents
        docs_extract_path = self.restore_dir / "documents_restore"
        with tarfile.open(docs_tarball, "r:gz") as tar:
            tar.extractall(path=docs_extract_path)

        # Upload documents to MinIO
        docs_dir = docs_extract_path / "documents"
        if not docs_dir.exists():
            raise RestoreError(
                message="Documents directory not found in backup",
                details={"expected_path": str(docs_dir)},
            )

        # Upload all documents
        for file_path in docs_dir.rglob("*"):
            if file_path.is_file():
                relative_path = file_path.relative_to(docs_dir)
                self.minio_service.upload_file(
                    bucket_name="taxja-documents",
                    object_name=str(relative_path),
                    file_path=str(file_path),
                )

        logger.info("Documents restored to MinIO")

    def _validate_integrity(self) -> bool:
        """
        Validate data integrity after restore.
        
        Returns:
            True if validation passes, False otherwise
        """
        try:
            # Check database connectivity
            self.db.execute(text("SELECT 1"))

            # Check critical tables exist
            critical_tables = ["users", "transactions", "documents", "tax_reports"]
            for table in critical_tables:
                result = self.db.execute(
                    text(f"SELECT COUNT(*) FROM {table}")
                ).scalar()
                logger.info(f"Table {table}: {result} rows")

            # Check MinIO connectivity
            if not self.minio_service.bucket_exists("taxja-documents"):
                logger.warning("Documents bucket does not exist")
                return False

            logger.info("Data integrity validation passed")
            return True

        except Exception as e:
            logger.error(f"Data integrity validation failed: {str(e)}")
            return False

    def _find_database_file(self, extract_path: Path) -> Optional[Path]:
        """
        Find database backup file in extracted backup.
        
        Args:
            extract_path: Path to extracted backup directory
            
        Returns:
            Path to database file or None
        """
        for file in extract_path.rglob("database_*.sql"):
            return file
        return None

    def _cleanup_restore_files(self, extract_path: Path, backup_path: Path) -> None:
        """
        Clean up restore files after restore.
        
        Args:
            extract_path: Path to extracted directory
            backup_path: Path to backup tarball
        """
        try:
            import shutil

            # Remove extracted directory
            if extract_path.exists():
                shutil.rmtree(extract_path)

            # Remove downloaded backup
            if backup_path.exists():
                backup_path.unlink()

            # Remove documents restore directory
            docs_restore = self.restore_dir / "documents_restore"
            if docs_restore.exists():
                shutil.rmtree(docs_restore)

            logger.info("Restore files cleaned up")

        except Exception as e:
            logger.warning(f"Failed to cleanup restore files: {str(e)}")


def get_restore_service(db: Session) -> RestoreService:
    """Get restore service instance"""
    return RestoreService(db)
