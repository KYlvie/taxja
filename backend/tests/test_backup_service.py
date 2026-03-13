"""
Unit tests for BackupService.

Tests cover:
- Full backup creation (database + documents)
- Database-only backup
- Documents-only backup
- Backup listing
- Old backup cleanup
- Error handling and edge cases
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, call
from pathlib import Path
from datetime import datetime, timedelta
import tarfile
import subprocess

from app.services.backup_service import BackupService, get_backup_service
from app.core.exceptions import BackupError


@pytest.fixture
def mock_db():
    """Mock database session"""
    return Mock()


@pytest.fixture
def mock_minio_service():
    """Mock MinioService"""
    minio = Mock()
    minio.bucket_exists.return_value = True
    minio.list_objects.return_value = []
    minio.upload_file.return_value = None
    minio.download_file.return_value = None
    minio.create_bucket.return_value = None
    minio.delete_file.return_value = None
    return minio


@pytest.fixture
def backup_service(mock_db, mock_minio_service):
    """Create BackupService instance with mocked dependencies"""
    with patch("app.services.backup_service.MinioService", return_value=mock_minio_service):
        service = BackupService(mock_db)
        return service


class TestBackupServiceInitialization:
    """Test BackupService initialization"""

    def test_service_initialization(self, mock_db, mock_minio_service):
        """Test that service initializes correctly"""
        with patch("app.services.backup_service.MinioService", return_value=mock_minio_service):
            service = BackupService(mock_db)
            
            assert service.db == mock_db
            assert service.minio_service == mock_minio_service
            assert service.backup_bucket == "taxja-backups"
            assert service.backup_dir == Path("/tmp/taxja_backups")

    def test_get_backup_service_factory(self, mock_db, mock_minio_service):
        """Test factory function returns BackupService instance"""
        with patch("app.services.backup_service.MinioService", return_value=mock_minio_service):
            service = get_backup_service(mock_db)
            
            assert isinstance(service, BackupService)
            assert service.db == mock_db


class TestDatabaseBackup:
    """Test database backup functionality"""

    @patch("app.services.backup_service.subprocess.run")
    def test_backup_database_success(self, mock_subprocess, backup_service):
        """Test successful database backup"""
        mock_subprocess.return_value = Mock(returncode=0)
        
        backup_path = Path("/tmp/test_backup")
        backup_path.mkdir(parents=True, exist_ok=True)
        timestamp = "20250101_120000"
        
        try:
            result = backup_service._backup_database(backup_path, timestamp)
            
            # Verify pg_dump was called
            assert mock_subprocess.called
            call_args = mock_subprocess.call_args
            
            # Check command includes pg_dump
            assert "pg_dump" in call_args[0][0]
            
            # Verify result is a Path
            assert isinstance(result, Path)
            assert result.name == f"database_{timestamp}.sql"
            
        finally:
            # Cleanup
            import shutil
            if backup_path.exists():
                shutil.rmtree(backup_path)

    @patch("app.services.backup_service.subprocess.run")
    def test_backup_database_failure(self, mock_subprocess, backup_service):
        """Test database backup handles pg_dump failure"""
        mock_subprocess.side_effect = subprocess.CalledProcessError(
            1, "pg_dump", stderr="Connection failed"
        )
        
        backup_path = Path("/tmp/test_backup")
        backup_path.mkdir(parents=True, exist_ok=True)
        timestamp = "20250101_120000"
        
        try:
            with pytest.raises(BackupError) as exc_info:
                backup_service._backup_database(backup_path, timestamp)
            
            assert "Database backup failed" in str(exc_info.value)
            
        finally:
            import shutil
            if backup_path.exists():
                shutil.rmtree(backup_path)


class TestDocumentsBackup:
    """Test documents backup functionality"""

    def test_backup_documents_success(self, backup_service):
        """Test successful documents backup"""
        # Mock MinIO objects
        mock_obj1 = Mock()
        mock_obj1.object_name = "user1/doc1.pdf"
        mock_obj2 = Mock()
        mock_obj2.object_name = "user2/doc2.pdf"
        
        backup_service.minio_service.list_objects.return_value = [mock_obj1, mock_obj2]
        
        backup_path = Path("/tmp/test_backup")
        backup_path.mkdir(parents=True, exist_ok=True)
        timestamp = "20250101_120000"
        
        try:
            result = backup_service._backup_documents(backup_path, timestamp)
            
            # Verify documents were downloaded
            assert backup_service.minio_service.list_objects.called
            assert backup_service.minio_service.download_file.call_count == 2
            
            # Verify tarball was created
            assert isinstance(result, Path)
            assert result.name == f"documents_{timestamp}.tar.gz"
            assert result.exists()
            
        finally:
            import shutil
            if backup_path.exists():
                shutil.rmtree(backup_path)

    def test_backup_documents_empty_bucket(self, backup_service):
        """Test documents backup with no documents"""
        backup_service.minio_service.list_objects.return_value = []
        
        backup_path = Path("/tmp/test_backup")
        backup_path.mkdir(parents=True, exist_ok=True)
        timestamp = "20250101_120000"
        
        try:
            result = backup_service._backup_documents(backup_path, timestamp)
            
            # Should still create tarball even if empty
            assert isinstance(result, Path)
            assert result.exists()
            
        finally:
            import shutil
            if backup_path.exists():
                shutil.rmtree(backup_path)

    def test_backup_documents_minio_failure(self, backup_service):
        """Test documents backup handles MinIO failure"""
        backup_service.minio_service.list_objects.side_effect = Exception("MinIO connection failed")
        
        backup_path = Path("/tmp/test_backup")
        backup_path.mkdir(parents=True, exist_ok=True)
        timestamp = "20250101_120000"
        
        try:
            with pytest.raises(BackupError) as exc_info:
                backup_service._backup_documents(backup_path, timestamp)
            
            assert "Documents backup failed" in str(exc_info.value)
            
        finally:
            import shutil
            if backup_path.exists():
                shutil.rmtree(backup_path)


class TestFullBackup:
    """Test full backup creation"""

    @patch("app.services.backup_service.subprocess.run")
    def test_create_full_backup_success(self, mock_subprocess, backup_service):
        """Test successful full backup creation"""
        mock_subprocess.return_value = Mock(returncode=0)
        backup_service.minio_service.list_objects.return_value = []
        
        with patch.object(backup_service, '_cleanup_local_backup'):
            result = backup_service.create_full_backup()
            
            # Verify result structure
            assert "backup_name" in result
            assert "timestamp" in result
            assert "database_backup" in result
            assert "documents_backup" in result
            assert "remote_path" in result
            assert result["status"] == "success"
            
            # Verify backup was uploaded
            assert backup_service.minio_service.upload_file.called

    @patch("app.services.backup_service.subprocess.run")
    def test_create_full_backup_creates_bucket_if_not_exists(self, mock_subprocess, backup_service):
        """Test that full backup creates bucket if it doesn't exist"""
        mock_subprocess.return_value = Mock(returncode=0)
        backup_service.minio_service.bucket_exists.return_value = False
        backup_service.minio_service.list_objects.return_value = []
        
        with patch.object(backup_service, '_cleanup_local_backup'):
            result = backup_service.create_full_backup()
            
            # Verify bucket was created
            backup_service.minio_service.create_bucket.assert_called_with("taxja-backups")
            assert result["status"] == "success"

    @patch("app.services.backup_service.subprocess.run")
    def test_create_full_backup_handles_failure(self, mock_subprocess, backup_service):
        """Test full backup handles failures gracefully"""
        mock_subprocess.side_effect = Exception("Backup failed")
        
        with pytest.raises(BackupError) as exc_info:
            backup_service.create_full_backup()
        
        assert "Failed to create backup" in str(exc_info.value)


class TestDatabaseOnlyBackup:
    """Test database-only backup"""

    @patch("app.services.backup_service.subprocess.run")
    def test_create_database_backup_success(self, mock_subprocess, backup_service):
        """Test successful database-only backup"""
        mock_subprocess.return_value = Mock(returncode=0)
        
        result = backup_service.create_database_backup()
        
        # Verify result structure
        assert "backup_name" in result
        assert "timestamp" in result
        assert "backup_file" in result
        assert "remote_path" in result
        assert result["status"] == "success"
        assert "taxja_db_backup_" in result["backup_name"]
        
        # Verify file was uploaded
        assert backup_service.minio_service.upload_file.called

    @patch("app.services.backup_service.subprocess.run")
    def test_create_database_backup_handles_failure(self, mock_subprocess, backup_service):
        """Test database backup handles failures"""
        mock_subprocess.side_effect = subprocess.CalledProcessError(
            1, "pg_dump", stderr="Error"
        )
        
        with pytest.raises(BackupError) as exc_info:
            backup_service.create_database_backup()
        
        assert "Failed to create database backup" in str(exc_info.value)


class TestDocumentsOnlyBackup:
    """Test documents-only backup"""

    def test_create_documents_backup_success(self, backup_service):
        """Test successful documents-only backup"""
        backup_service.minio_service.list_objects.return_value = []
        
        result = backup_service.create_documents_backup()
        
        # Verify result structure
        assert "backup_name" in result
        assert "timestamp" in result
        assert "backup_file" in result
        assert "remote_path" in result
        assert result["status"] == "success"
        assert "taxja_docs_backup_" in result["backup_name"]

    def test_create_documents_backup_handles_failure(self, backup_service):
        """Test documents backup handles failures"""
        backup_service.minio_service.list_objects.side_effect = Exception("MinIO error")
        
        with pytest.raises(BackupError) as exc_info:
            backup_service.create_documents_backup()
        
        assert "Failed to create documents backup" in str(exc_info.value)


class TestBackupListing:
    """Test backup listing functionality"""

    def test_list_backups_success(self, backup_service):
        """Test listing backups successfully"""
        # Mock backup objects
        mock_obj1 = Mock()
        mock_obj1.object_name = "backup_20250101.tar.gz"
        mock_obj1.size = 1024000
        mock_obj1.last_modified = datetime(2025, 1, 1, 12, 0, 0)
        
        mock_obj2 = Mock()
        mock_obj2.object_name = "backup_20250102.tar.gz"
        mock_obj2.size = 2048000
        mock_obj2.last_modified = datetime(2025, 1, 2, 12, 0, 0)
        
        backup_service.minio_service.list_objects.return_value = [mock_obj1, mock_obj2]
        
        result = backup_service.list_backups()
        
        # Verify result
        assert len(result) == 2
        assert result[0]["name"] == "backup_20250101.tar.gz"
        assert result[0]["size"] == 1024000
        assert result[1]["name"] == "backup_20250102.tar.gz"

    def test_list_backups_empty(self, backup_service):
        """Test listing backups when none exist"""
        backup_service.minio_service.list_objects.return_value = []
        
        result = backup_service.list_backups()
        
        assert result == []

    def test_list_backups_bucket_not_exists(self, backup_service):
        """Test listing backups when bucket doesn't exist"""
        backup_service.minio_service.bucket_exists.return_value = False
        
        result = backup_service.list_backups()
        
        assert result == []

    def test_list_backups_handles_error(self, backup_service):
        """Test listing backups handles errors gracefully"""
        backup_service.minio_service.list_objects.side_effect = Exception("Connection error")
        
        result = backup_service.list_backups()
        
        # Should return empty list on error
        assert result == []


class TestBackupCleanup:
    """Test old backup cleanup"""

    def test_delete_old_backups_success(self, backup_service):
        """Test deleting old backups successfully"""
        # Create mock objects with different ages
        now = datetime.utcnow()
        
        old_obj = Mock()
        old_obj.object_name = "backup_old.tar.gz"
        old_obj.last_modified = now - timedelta(days=40)
        
        recent_obj = Mock()
        recent_obj.object_name = "backup_recent.tar.gz"
        recent_obj.last_modified = now - timedelta(days=10)
        
        backup_service.minio_service.list_objects.return_value = [old_obj, recent_obj]
        
        deleted_count = backup_service.delete_old_backups(keep_days=30)
        
        # Verify only old backup was deleted
        assert deleted_count == 1
        backup_service.minio_service.delete_file.assert_called_once_with(
            "taxja-backups", "backup_old.tar.gz"
        )

    def test_delete_old_backups_custom_retention(self, backup_service):
        """Test deleting backups with custom retention period"""
        now = datetime.utcnow()
        
        obj1 = Mock()
        obj1.object_name = "backup1.tar.gz"
        obj1.last_modified = now - timedelta(days=8)
        
        obj2 = Mock()
        obj2.object_name = "backup2.tar.gz"
        obj2.last_modified = now - timedelta(days=5)
        
        backup_service.minio_service.list_objects.return_value = [obj1, obj2]
        
        deleted_count = backup_service.delete_old_backups(keep_days=7)
        
        # Only backup older than 7 days should be deleted
        assert deleted_count == 1

    def test_delete_old_backups_none_old(self, backup_service):
        """Test cleanup when no backups are old enough"""
        now = datetime.utcnow()
        
        recent_obj = Mock()
        recent_obj.object_name = "backup_recent.tar.gz"
        recent_obj.last_modified = now - timedelta(days=5)
        
        backup_service.minio_service.list_objects.return_value = [recent_obj]
        
        deleted_count = backup_service.delete_old_backups(keep_days=30)
        
        assert deleted_count == 0
        backup_service.minio_service.delete_file.assert_not_called()

    def test_delete_old_backups_bucket_not_exists(self, backup_service):
        """Test cleanup when bucket doesn't exist"""
        backup_service.minio_service.bucket_exists.return_value = False
        
        deleted_count = backup_service.delete_old_backups()
        
        assert deleted_count == 0

    def test_delete_old_backups_handles_error(self, backup_service):
        """Test cleanup handles errors gracefully"""
        backup_service.minio_service.list_objects.side_effect = Exception("Connection error")
        
        deleted_count = backup_service.delete_old_backups()
        
        # Should return 0 on error
        assert deleted_count == 0


class TestTarballCreation:
    """Test tarball creation"""

    def test_create_tarball(self, backup_service):
        """Test creating tarball from backup directory"""
        # Create test backup directory
        backup_path = Path("/tmp/test_backup_tarball")
        backup_path.mkdir(parents=True, exist_ok=True)
        
        # Create a test file
        test_file = backup_path / "test.txt"
        test_file.write_text("test content")
        
        backup_name = "test_backup"
        
        try:
            result = backup_service._create_tarball(backup_path, backup_name)
            
            # Verify tarball was created
            assert isinstance(result, Path)
            assert result.name == f"{backup_name}.tar.gz"
            assert result.exists()
            
            # Verify tarball contains the file
            with tarfile.open(result, "r:gz") as tar:
                members = tar.getnames()
                assert len(members) > 0
                
        finally:
            # Cleanup
            import shutil
            if backup_path.exists():
                shutil.rmtree(backup_path)
            if result.exists():
                result.unlink()


class TestUploadToRemote:
    """Test remote upload functionality"""

    def test_upload_to_remote_success(self, backup_service):
        """Test uploading tarball to remote storage"""
        # Create test tarball
        tarball_path = Path("/tmp/test_upload.tar.gz")
        tarball_path.write_bytes(b"test data")
        
        backup_name = "test_backup"
        
        try:
            result = backup_service._upload_to_remote(tarball_path, backup_name)
            
            # Verify upload was called
            backup_service.minio_service.upload_file.assert_called_once()
            
            # Verify result format
            assert result == f"taxja-backups/{backup_name}.tar.gz"
            
        finally:
            if tarball_path.exists():
                tarball_path.unlink()

    def test_upload_file_to_remote_success(self, backup_service):
        """Test uploading single file to remote storage"""
        # Create test file
        file_path = Path("/tmp/test_file.sql")
        file_path.write_bytes(b"test data")
        
        object_name = "test_backup.sql"
        
        try:
            result = backup_service._upload_file_to_remote(file_path, object_name)
            
            # Verify upload was called
            backup_service.minio_service.upload_file.assert_called_once()
            
            # Verify result format
            assert result == f"taxja-backups/{object_name}"
            
        finally:
            if file_path.exists():
                file_path.unlink()


class TestLocalCleanup:
    """Test local backup cleanup"""

    def test_cleanup_local_backup(self, backup_service):
        """Test cleaning up local backup files"""
        # Create test files
        backup_path = Path("/tmp/test_cleanup")
        backup_path.mkdir(parents=True, exist_ok=True)
        
        tarball_path = Path("/tmp/test_cleanup.tar.gz")
        tarball_path.write_bytes(b"test")
        
        # Cleanup should not raise errors
        backup_service._cleanup_local_backup(backup_path, tarball_path)
        
        # Verify files were removed
        assert not backup_path.exists()
        assert not tarball_path.exists()

    def test_cleanup_handles_missing_files(self, backup_service):
        """Test cleanup handles missing files gracefully"""
        backup_path = Path("/tmp/nonexistent_backup")
        tarball_path = Path("/tmp/nonexistent.tar.gz")
        
        # Should not raise errors
        backup_service._cleanup_local_backup(backup_path, tarball_path)
