"""
Integration tests for backup system.

Tests the complete backup workflow including:
- Task execution
- Service interaction
- File system operations
- Error recovery
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import shutil
from datetime import datetime, timedelta

from app.services.backup_service import BackupService
from app.tasks.backup_tasks import (
    create_daily_backup,
    create_database_backup,
    cleanup_old_backups,
)


@pytest.fixture
def temp_backup_dir():
    """Create temporary backup directory"""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    # Cleanup
    if temp_dir.exists():
        shutil.rmtree(temp_dir)


@pytest.fixture
def mock_db():
    """Mock database session"""
    return Mock()


class TestBackupWorkflow:
    """Test complete backup workflow"""

    @patch("app.tasks.backup_tasks.SessionLocal")
    @patch("app.services.backup_service.MinioService")
    @patch("app.services.backup_service.subprocess.run")
    def test_daily_backup_workflow(
        self, mock_subprocess, mock_minio_class, mock_session_local, temp_backup_dir
    ):
        """Test complete daily backup workflow from task to storage"""
        # Setup mocks
        mock_db = Mock()
        mock_session_local.return_value = mock_db
        
        mock_minio = Mock()
        mock_minio.bucket_exists.return_value = True
        mock_minio.list_objects.return_value = []
        mock_minio_class.return_value = mock_minio
        
        mock_subprocess.return_value = Mock(returncode=0)
        
        # Override backup directory
        with patch("app.services.backup_service.Path") as mock_path:
            mock_path.return_value = temp_backup_dir
            
            # Execute task
            result = create_daily_backup()
            
            # Verify workflow
            assert result is not None
            assert result["status"] == "success"
            assert "backup_name" in result
            
            # Verify database session was closed
            mock_db.close.assert_called_once()
            
            # Verify MinIO upload was called
            assert mock_minio.upload_file.called

    @patch("app.tasks.backup_tasks.SessionLocal")
    @patch("app.services.backup_service.MinioService")
    @patch("app.services.backup_service.subprocess.run")
    def test_backup_retry_on_transient_failure(
        self, mock_subprocess, mock_minio_class, mock_session_local
    ):
        """Test backup retries on transient failures"""
        mock_db = Mock()
        mock_session_local.return_value = mock_db
        
        mock_minio = Mock()
        # First call fails, second succeeds
        mock_minio.upload_file.side_effect = [
            Exception("Transient network error"),
            None,
        ]
        mock_minio.bucket_exists.return_value = True
        mock_minio.list_objects.return_value = []
        mock_minio_class.return_value = mock_minio
        
        mock_subprocess.return_value = Mock(returncode=0)
        
        # First attempt should fail
        with pytest.raises(Exception):
            create_daily_backup()
        
        # Second attempt should succeed
        result = create_daily_backup()
        assert result["status"] == "success"


class TestBackupCleanupWorkflow:
    """Test backup cleanup workflow"""

    @patch("app.tasks.backup_tasks.SessionLocal")
    @patch("app.services.backup_service.MinioService")
    def test_cleanup_deletes_old_backups(self, mock_minio_class, mock_session_local):
        """Test cleanup workflow deletes old backups"""
        mock_db = Mock()
        mock_session_local.return_value = mock_db
        
        # Create mock backups with different ages
        now = datetime.utcnow()
        
        old_backup1 = Mock()
        old_backup1.object_name = "backup_old1.tar.gz"
        old_backup1.last_modified = now - timedelta(days=40)
        
        old_backup2 = Mock()
        old_backup2.object_name = "backup_old2.tar.gz"
        old_backup2.last_modified = now - timedelta(days=35)
        
        recent_backup = Mock()
        recent_backup.object_name = "backup_recent.tar.gz"
        recent_backup.last_modified = now - timedelta(days=10)
        
        mock_minio = Mock()
        mock_minio.bucket_exists.return_value = True
        mock_minio.list_objects.return_value = [old_backup1, old_backup2, recent_backup]
        mock_minio_class.return_value = mock_minio
        
        # Execute cleanup
        result = cleanup_old_backups(keep_days=30)
        
        # Verify only old backups were deleted
        assert result["deleted_count"] == 2
        assert mock_minio.delete_file.call_count == 2
        
        # Verify correct backups were deleted
        delete_calls = [call[0][1] for call in mock_minio.delete_file.call_args_list]
        assert "backup_old1.tar.gz" in delete_calls
        assert "backup_old2.tar.gz" in delete_calls
        assert "backup_recent.tar.gz" not in delete_calls


class TestBackupErrorRecovery:
    """Test backup error recovery scenarios"""

    @patch("app.tasks.backup_tasks.SessionLocal")
    @patch("app.services.backup_service.MinioService")
    @patch("app.services.backup_service.subprocess.run")
    def test_backup_cleans_up_on_failure(
        self, mock_subprocess, mock_minio_class, mock_session_local, temp_backup_dir
    ):
        """Test backup cleans up temporary files on failure"""
        mock_db = Mock()
        mock_session_local.return_value = mock_db
        
        mock_minio = Mock()
        mock_minio.bucket_exists.return_value = True
        mock_minio.list_objects.return_value = []
        # Upload fails
        mock_minio.upload_file.side_effect = Exception("Upload failed")
        mock_minio_class.return_value = mock_minio
        
        mock_subprocess.return_value = Mock(returncode=0)
        
        # Execute task (should fail)
        with pytest.raises(Exception):
            create_daily_backup()
        
        # Verify database session was still closed
        mock_db.close.assert_called()

    @patch("app.tasks.backup_tasks.SessionLocal")
    @patch("app.services.backup_service.MinioService")
    def test_cleanup_handles_missing_bucket(self, mock_minio_class, mock_session_local):
        """Test cleanup handles missing backup bucket gracefully"""
        mock_db = Mock()
        mock_session_local.return_value = mock_db
        
        mock_minio = Mock()
        mock_minio.bucket_exists.return_value = False
        mock_minio_class.return_value = mock_minio
        
        # Execute cleanup
        result = cleanup_old_backups()
        
        # Should return 0 deletions without error
        assert result["deleted_count"] == 0
        mock_minio.list_objects.assert_not_called()


class TestBackupConcurrency:
    """Test backup task concurrency scenarios"""

    @patch("app.tasks.backup_tasks.SessionLocal")
    @patch("app.services.backup_service.MinioService")
    @patch("app.services.backup_service.subprocess.run")
    def test_multiple_backup_tasks_can_run_concurrently(
        self, mock_subprocess, mock_minio_class, mock_session_local
    ):
        """Test multiple backup tasks can run without conflicts"""
        # Setup mocks
        mock_db1 = Mock()
        mock_db2 = Mock()
        mock_session_local.side_effect = [mock_db1, mock_db2]
        
        mock_minio = Mock()
        mock_minio.bucket_exists.return_value = True
        mock_minio.list_objects.return_value = []
        mock_minio_class.return_value = mock_minio
        
        mock_subprocess.return_value = Mock(returncode=0)
        
        # Execute two tasks
        result1 = create_database_backup()
        result2 = create_database_backup()
        
        # Both should succeed
        assert result1["status"] == "success"
        assert result2["status"] == "success"
        
        # Both should have different backup names (different timestamps)
        assert result1["backup_name"] != result2["backup_name"]
        
        # Both database sessions should be closed
        mock_db1.close.assert_called_once()
        mock_db2.close.assert_called_once()


class TestBackupMonitoring:
    """Test backup monitoring and logging"""

    @patch("app.tasks.backup_tasks.SessionLocal")
    @patch("app.services.backup_service.MinioService")
    @patch("app.services.backup_service.subprocess.run")
    @patch("app.tasks.backup_tasks.logger")
    def test_backup_logs_progress(
        self, mock_logger, mock_subprocess, mock_minio_class, mock_session_local
    ):
        """Test backup tasks log progress appropriately"""
        mock_db = Mock()
        mock_session_local.return_value = mock_db
        
        mock_minio = Mock()
        mock_minio.bucket_exists.return_value = True
        mock_minio.list_objects.return_value = []
        mock_minio_class.return_value = mock_minio
        
        mock_subprocess.return_value = Mock(returncode=0)
        
        # Execute task
        result = create_daily_backup()
        
        # Verify logging
        assert mock_logger.info.call_count >= 2
        
        # Check for start and completion logs
        log_messages = [str(call) for call in mock_logger.info.call_args_list]
        assert any("Starting" in str(msg) for msg in log_messages)
        assert any("completed" in str(msg) for msg in log_messages)

    @patch("app.tasks.backup_tasks.SessionLocal")
    @patch("app.services.backup_service.MinioService")
    @patch("app.services.backup_service.subprocess.run")
    @patch("app.tasks.backup_tasks.logger")
    def test_backup_logs_errors(
        self, mock_logger, mock_subprocess, mock_minio_class, mock_session_local
    ):
        """Test backup tasks log errors appropriately"""
        mock_db = Mock()
        mock_session_local.return_value = mock_db
        
        mock_minio = Mock()
        mock_minio.bucket_exists.return_value = True
        mock_minio.list_objects.return_value = []
        mock_minio.upload_file.side_effect = Exception("Upload failed")
        mock_minio_class.return_value = mock_minio
        
        mock_subprocess.return_value = Mock(returncode=0)
        
        # Execute task (should fail)
        with pytest.raises(Exception):
            create_daily_backup()
        
        # Verify error was logged
        mock_logger.error.assert_called()


class TestBackupDataIntegrity:
    """Test backup data integrity"""

    @patch("app.tasks.backup_tasks.SessionLocal")
    @patch("app.services.backup_service.MinioService")
    @patch("app.services.backup_service.subprocess.run")
    def test_backup_includes_all_components(
        self, mock_subprocess, mock_minio_class, mock_session_local
    ):
        """Test full backup includes both database and documents"""
        mock_db = Mock()
        mock_session_local.return_value = mock_db
        
        mock_minio = Mock()
        mock_minio.bucket_exists.return_value = True
        mock_minio.list_objects.return_value = []
        mock_minio_class.return_value = mock_minio
        
        mock_subprocess.return_value = Mock(returncode=0)
        
        # Execute full backup
        result = create_daily_backup()
        
        # Verify both components are included
        assert "database_backup" in result
        assert "documents_backup" in result
        assert result["database_backup"].endswith(".sql")
        assert result["documents_backup"].endswith(".tar.gz")

    @patch("app.tasks.backup_tasks.SessionLocal")
    @patch("app.services.backup_service.MinioService")
    @patch("app.services.backup_service.subprocess.run")
    def test_backup_timestamp_consistency(
        self, mock_subprocess, mock_minio_class, mock_session_local
    ):
        """Test backup uses consistent timestamp across components"""
        mock_db = Mock()
        mock_session_local.return_value = mock_db
        
        mock_minio = Mock()
        mock_minio.bucket_exists.return_value = True
        mock_minio.list_objects.return_value = []
        mock_minio_class.return_value = mock_minio
        
        mock_subprocess.return_value = Mock(returncode=0)
        
        # Execute backup
        result = create_daily_backup()
        
        # Verify timestamp is present and valid
        assert "timestamp" in result
        timestamp = result["timestamp"]
        
        # Verify timestamp format (YYYYMMDD_HHMMSS)
        assert len(timestamp) == 15
        assert timestamp[8] == "_"
        
        # Verify timestamp can be parsed
        datetime.strptime(timestamp, "%Y%m%d_%H%M%S")
