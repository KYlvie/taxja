"""
Unit tests for backup Celery tasks.

Tests cover:
- Daily backup task execution
- Database backup task
- Documents backup task
- Old backup cleanup task
- Task retry logic
- Error handling
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from app.tasks.backup_tasks import (
    create_daily_backup,
    create_database_backup,
    create_documents_backup,
    cleanup_old_backups,
)
from app.core.exceptions import BackupError


@pytest.fixture
def mock_session_local():
    """Mock SessionLocal for database session"""
    mock_db = Mock()
    mock_db.close = Mock()
    
    with patch("app.tasks.backup_tasks.SessionLocal") as mock_session:
        mock_session.return_value = mock_db
        yield mock_session, mock_db


@pytest.fixture
def mock_backup_service():
    """Mock BackupService"""
    service = Mock()
    service.create_full_backup.return_value = {
        "backup_name": "taxja_backup_20250101_120000",
        "timestamp": "20250101_120000",
        "database_backup": "database_20250101_120000.sql",
        "documents_backup": "documents_20250101_120000.tar.gz",
        "remote_path": "taxja-backups/taxja_backup_20250101_120000.tar.gz",
        "status": "success",
    }
    service.create_database_backup.return_value = {
        "backup_name": "taxja_db_backup_20250101_120000",
        "timestamp": "20250101_120000",
        "backup_file": "database_20250101_120000.sql",
        "remote_path": "taxja-backups/taxja_db_backup_20250101_120000.sql",
        "status": "success",
    }
    service.create_documents_backup.return_value = {
        "backup_name": "taxja_docs_backup_20250101_120000",
        "timestamp": "20250101_120000",
        "backup_file": "documents_20250101_120000.tar.gz",
        "remote_path": "taxja-backups/taxja_docs_backup_20250101_120000.tar.gz",
        "status": "success",
    }
    service.delete_old_backups.return_value = 5
    return service


class TestCreateDailyBackup:
    """Test create_daily_backup task"""

    def test_create_daily_backup_success(self, mock_session_local, mock_backup_service):
        """Test successful daily backup creation"""
        mock_session, mock_db = mock_session_local
        
        with patch("app.tasks.backup_tasks.BackupService", return_value=mock_backup_service):
            result = create_daily_backup()
            
            # Verify BackupService was instantiated with db
            assert result is not None
            assert result["backup_name"] == "taxja_backup_20250101_120000"
            assert result["status"] == "success"
            
            # Verify database session was closed
            mock_db.close.assert_called_once()
            
            # Verify backup service method was called
            mock_backup_service.create_full_backup.assert_called_once()

    def test_create_daily_backup_handles_error(self, mock_session_local, mock_backup_service):
        """Test daily backup handles errors and closes db session"""
        mock_session, mock_db = mock_session_local
        mock_backup_service.create_full_backup.side_effect = BackupError(
            message="Backup failed",
            details={"error": "Connection error"}
        )
        
        with patch("app.tasks.backup_tasks.BackupService", return_value=mock_backup_service):
            with pytest.raises(BackupError):
                create_daily_backup()
            
            # Verify database session was closed even on error
            mock_db.close.assert_called_once()

    def test_create_daily_backup_logs_info(self, mock_session_local, mock_backup_service):
        """Test daily backup logs appropriate messages"""
        mock_session, mock_db = mock_session_local
        
        with patch("app.tasks.backup_tasks.BackupService", return_value=mock_backup_service):
            with patch("app.tasks.backup_tasks.logger") as mock_logger:
                result = create_daily_backup()
                
                # Verify logging
                assert mock_logger.info.call_count >= 2
                mock_logger.info.assert_any_call("Starting scheduled daily backup")
                
                # Check that backup name was logged
                log_calls = [str(call) for call in mock_logger.info.call_args_list]
                assert any("Daily backup completed" in str(call) for call in log_calls)


class TestCreateDatabaseBackup:
    """Test create_database_backup task"""

    def test_create_database_backup_success(self, mock_session_local, mock_backup_service):
        """Test successful database backup creation"""
        mock_session, mock_db = mock_session_local
        
        with patch("app.tasks.backup_tasks.BackupService", return_value=mock_backup_service):
            result = create_database_backup()
            
            # Verify result
            assert result is not None
            assert result["backup_name"] == "taxja_db_backup_20250101_120000"
            assert result["status"] == "success"
            assert "database" in result["backup_file"]
            
            # Verify database session was closed
            mock_db.close.assert_called_once()
            
            # Verify backup service method was called
            mock_backup_service.create_database_backup.assert_called_once()

    def test_create_database_backup_handles_error(self, mock_session_local, mock_backup_service):
        """Test database backup handles errors"""
        mock_session, mock_db = mock_session_local
        mock_backup_service.create_database_backup.side_effect = Exception("pg_dump failed")
        
        with patch("app.tasks.backup_tasks.BackupService", return_value=mock_backup_service):
            with pytest.raises(Exception, match="pg_dump failed"):
                create_database_backup()
            
            # Verify database session was closed
            mock_db.close.assert_called_once()

    def test_create_database_backup_logs_progress(self, mock_session_local, mock_backup_service):
        """Test database backup logs progress"""
        mock_session, mock_db = mock_session_local
        
        with patch("app.tasks.backup_tasks.BackupService", return_value=mock_backup_service):
            with patch("app.tasks.backup_tasks.logger") as mock_logger:
                result = create_database_backup()
                
                # Verify logging
                mock_logger.info.assert_any_call("Starting database backup")
                
                # Check completion log
                log_calls = [str(call) for call in mock_logger.info.call_args_list]
                assert any("Database backup completed" in str(call) for call in log_calls)


class TestCreateDocumentsBackup:
    """Test create_documents_backup task"""

    def test_create_documents_backup_success(self, mock_session_local, mock_backup_service):
        """Test successful documents backup creation"""
        mock_session, mock_db = mock_session_local
        
        with patch("app.tasks.backup_tasks.BackupService", return_value=mock_backup_service):
            result = create_documents_backup()
            
            # Verify result
            assert result is not None
            assert result["backup_name"] == "taxja_docs_backup_20250101_120000"
            assert result["status"] == "success"
            assert "documents" in result["backup_file"]
            
            # Verify database session was closed
            mock_db.close.assert_called_once()
            
            # Verify backup service method was called
            mock_backup_service.create_documents_backup.assert_called_once()

    def test_create_documents_backup_handles_error(self, mock_session_local, mock_backup_service):
        """Test documents backup handles errors"""
        mock_session, mock_db = mock_session_local
        mock_backup_service.create_documents_backup.side_effect = Exception("MinIO connection failed")
        
        with patch("app.tasks.backup_tasks.BackupService", return_value=mock_backup_service):
            with pytest.raises(Exception, match="MinIO connection failed"):
                create_documents_backup()
            
            # Verify database session was closed
            mock_db.close.assert_called_once()

    def test_create_documents_backup_logs_progress(self, mock_session_local, mock_backup_service):
        """Test documents backup logs progress"""
        mock_session, mock_db = mock_session_local
        
        with patch("app.tasks.backup_tasks.BackupService", return_value=mock_backup_service):
            with patch("app.tasks.backup_tasks.logger") as mock_logger:
                result = create_documents_backup()
                
                # Verify logging
                mock_logger.info.assert_any_call("Starting documents backup")
                
                # Check completion log
                log_calls = [str(call) for call in mock_logger.info.call_args_list]
                assert any("Documents backup completed" in str(call) for call in log_calls)


class TestCleanupOldBackups:
    """Test cleanup_old_backups task"""

    def test_cleanup_old_backups_default_retention(self, mock_session_local, mock_backup_service):
        """Test cleanup with default 30-day retention"""
        mock_session, mock_db = mock_session_local
        
        with patch("app.tasks.backup_tasks.BackupService", return_value=mock_backup_service):
            result = cleanup_old_backups()
            
            # Verify result
            assert result is not None
            assert result["deleted_count"] == 5
            assert result["keep_days"] == 30
            assert "timestamp" in result
            
            # Verify database session was closed
            mock_db.close.assert_called_once()
            
            # Verify backup service method was called with default
            mock_backup_service.delete_old_backups.assert_called_once_with(30)

    def test_cleanup_old_backups_custom_retention(self, mock_session_local, mock_backup_service):
        """Test cleanup with custom retention period"""
        mock_session, mock_db = mock_session_local
        mock_backup_service.delete_old_backups.return_value = 10
        
        with patch("app.tasks.backup_tasks.BackupService", return_value=mock_backup_service):
            result = cleanup_old_backups(keep_days=7)
            
            # Verify result
            assert result["deleted_count"] == 10
            assert result["keep_days"] == 7
            
            # Verify backup service method was called with custom value
            mock_backup_service.delete_old_backups.assert_called_once_with(7)

    def test_cleanup_old_backups_no_deletions(self, mock_session_local, mock_backup_service):
        """Test cleanup when no backups need deletion"""
        mock_session, mock_db = mock_session_local
        mock_backup_service.delete_old_backups.return_value = 0
        
        with patch("app.tasks.backup_tasks.BackupService", return_value=mock_backup_service):
            result = cleanup_old_backups()
            
            # Verify result
            assert result["deleted_count"] == 0
            assert result["keep_days"] == 30

    def test_cleanup_old_backups_handles_error(self, mock_session_local, mock_backup_service):
        """Test cleanup handles errors"""
        mock_session, mock_db = mock_session_local
        mock_backup_service.delete_old_backups.side_effect = Exception("Cleanup failed")
        
        with patch("app.tasks.backup_tasks.BackupService", return_value=mock_backup_service):
            with pytest.raises(Exception, match="Cleanup failed"):
                cleanup_old_backups()
            
            # Verify database session was closed
            mock_db.close.assert_called_once()

    def test_cleanup_old_backups_logs_progress(self, mock_session_local, mock_backup_service):
        """Test cleanup logs progress"""
        mock_session, mock_db = mock_session_local
        
        with patch("app.tasks.backup_tasks.BackupService", return_value=mock_backup_service):
            with patch("app.tasks.backup_tasks.logger") as mock_logger:
                result = cleanup_old_backups(keep_days=30)
                
                # Verify logging
                mock_logger.info.assert_any_call(
                    "Starting backup cleanup (keep last 30 days)"
                )
                
                # Check completion log
                log_calls = [str(call) for call in mock_logger.info.call_args_list]
                assert any("Backup cleanup completed" in str(call) for call in log_calls)


class TestTaskErrorHandling:
    """Test error handling across all backup tasks"""

    def test_all_tasks_close_db_on_success(self, mock_session_local, mock_backup_service):
        """Test all tasks close database session on success"""
        mock_session, mock_db = mock_session_local
        
        with patch("app.tasks.backup_tasks.BackupService", return_value=mock_backup_service):
            # Test each task
            create_daily_backup()
            create_database_backup()
            create_documents_backup()
            cleanup_old_backups()
            
            # Verify db.close was called 4 times (once per task)
            assert mock_db.close.call_count == 4

    def test_all_tasks_close_db_on_error(self, mock_session_local, mock_backup_service):
        """Test all tasks close database session on error"""
        mock_session, mock_db = mock_session_local
        
        # Make all methods raise errors
        mock_backup_service.create_full_backup.side_effect = Exception("Error")
        mock_backup_service.create_database_backup.side_effect = Exception("Error")
        mock_backup_service.create_documents_backup.side_effect = Exception("Error")
        mock_backup_service.delete_old_backups.side_effect = Exception("Error")
        
        with patch("app.tasks.backup_tasks.BackupService", return_value=mock_backup_service):
            # Test each task raises and closes db
            with pytest.raises(Exception):
                create_daily_backup()
            
            with pytest.raises(Exception):
                create_database_backup()
            
            with pytest.raises(Exception):
                create_documents_backup()
            
            with pytest.raises(Exception):
                cleanup_old_backups()
            
            # Verify db.close was called 4 times (once per task)
            assert mock_db.close.call_count == 4

    def test_tasks_log_errors(self, mock_session_local, mock_backup_service):
        """Test tasks log errors appropriately"""
        mock_session, mock_db = mock_session_local
        mock_backup_service.create_full_backup.side_effect = Exception("Test error")
        
        with patch("app.tasks.backup_tasks.BackupService", return_value=mock_backup_service):
            with patch("app.tasks.backup_tasks.logger") as mock_logger:
                with pytest.raises(Exception):
                    create_daily_backup()
                
                # Verify error was logged
                mock_logger.error.assert_called()
                error_calls = [str(call) for call in mock_logger.error.call_args_list]
                assert any("failed" in str(call).lower() for call in error_calls)


class TestTaskReturnValues:
    """Test task return value structures"""

    def test_create_daily_backup_return_structure(self, mock_session_local, mock_backup_service):
        """Test daily backup returns correct structure"""
        mock_session, mock_db = mock_session_local
        
        with patch("app.tasks.backup_tasks.BackupService", return_value=mock_backup_service):
            result = create_daily_backup()
            
            # Verify all required fields are present
            required_fields = ["backup_name", "timestamp", "database_backup", 
                             "documents_backup", "remote_path", "status"]
            for field in required_fields:
                assert field in result, f"Missing field: {field}"

    def test_create_database_backup_return_structure(self, mock_session_local, mock_backup_service):
        """Test database backup returns correct structure"""
        mock_session, mock_db = mock_session_local
        
        with patch("app.tasks.backup_tasks.BackupService", return_value=mock_backup_service):
            result = create_database_backup()
            
            # Verify all required fields are present
            required_fields = ["backup_name", "timestamp", "backup_file", 
                             "remote_path", "status"]
            for field in required_fields:
                assert field in result, f"Missing field: {field}"

    def test_create_documents_backup_return_structure(self, mock_session_local, mock_backup_service):
        """Test documents backup returns correct structure"""
        mock_session, mock_db = mock_session_local
        
        with patch("app.tasks.backup_tasks.BackupService", return_value=mock_backup_service):
            result = create_documents_backup()
            
            # Verify all required fields are present
            required_fields = ["backup_name", "timestamp", "backup_file", 
                             "remote_path", "status"]
            for field in required_fields:
                assert field in result, f"Missing field: {field}"

    def test_cleanup_old_backups_return_structure(self, mock_session_local, mock_backup_service):
        """Test cleanup returns correct structure"""
        mock_session, mock_db = mock_session_local
        
        with patch("app.tasks.backup_tasks.BackupService", return_value=mock_backup_service):
            result = cleanup_old_backups()
            
            # Verify all required fields are present
            required_fields = ["deleted_count", "keep_days", "timestamp"]
            for field in required_fields:
                assert field in result, f"Missing field: {field}"
            
            # Verify timestamp is valid ISO format
            datetime.fromisoformat(result["timestamp"])


class TestTaskIntegration:
    """Test task integration scenarios"""

    def test_daily_backup_creates_full_backup(self, mock_session_local, mock_backup_service):
        """Test daily backup task creates full backup (db + docs)"""
        mock_session, mock_db = mock_session_local
        
        with patch("app.tasks.backup_tasks.BackupService", return_value=mock_backup_service):
            result = create_daily_backup()
            
            # Verify full backup was created (not just db or docs)
            assert "database_backup" in result
            assert "documents_backup" in result
            mock_backup_service.create_full_backup.assert_called_once()

    def test_cleanup_respects_retention_period(self, mock_session_local, mock_backup_service):
        """Test cleanup respects the specified retention period"""
        mock_session, mock_db = mock_session_local
        
        with patch("app.tasks.backup_tasks.BackupService", return_value=mock_backup_service):
            # Test different retention periods
            cleanup_old_backups(keep_days=7)
            mock_backup_service.delete_old_backups.assert_called_with(7)
            
            cleanup_old_backups(keep_days=90)
            mock_backup_service.delete_old_backups.assert_called_with(90)
