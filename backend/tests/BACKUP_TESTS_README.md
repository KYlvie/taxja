# Backup System Tests

This document describes the test suite for the backup system (BackupService and backup tasks).

## Test Files

### 1. `test_backup_service.py`
Unit tests for the BackupService class.

**Coverage:**
- Service initialization
- Database backup creation
- Documents backup creation
- Full backup creation (database + documents)
- Backup listing
- Old backup cleanup
- Tarball creation
- Remote upload functionality
- Local cleanup
- Error handling

**Test Classes:**
- `TestBackupServiceInitialization` - Service setup
- `TestDatabaseBackup` - Database backup functionality
- `TestDocumentsBackup` - Documents backup functionality
- `TestFullBackup` - Full backup creation
- `TestDatabaseOnlyBackup` - Database-only backup
- `TestDocumentsOnlyBackup` - Documents-only backup
- `TestBackupListing` - Listing available backups
- `TestBackupCleanup` - Old backup deletion
- `TestTarballCreation` - Tarball compression
- `TestUploadToRemote` - Remote storage upload
- `TestLocalCleanup` - Local file cleanup

**Total Tests:** 30+

### 2. `test_backup_tasks.py`
Unit tests for Celery backup tasks.

**Coverage:**
- Daily backup task execution
- Database backup task
- Documents backup task
- Cleanup task
- Task error handling
- Database session management
- Logging
- Return value structures

**Test Classes:**
- `TestCreateDailyBackup` - Daily backup task
- `TestCreateDatabaseBackup` - Database backup task
- `TestCreateDocumentsBackup` - Documents backup task
- `TestCleanupOldBackups` - Cleanup task
- `TestTaskErrorHandling` - Error scenarios
- `TestTaskReturnValues` - Return value validation
- `TestTaskIntegration` - Integration scenarios

**Total Tests:** 25+

### 3. `test_backup_integration.py`
Integration tests for the complete backup workflow.

**Coverage:**
- End-to-end backup workflow
- Task-to-service integration
- Error recovery
- Concurrent task execution
- Monitoring and logging
- Data integrity

**Test Classes:**
- `TestBackupWorkflow` - Complete workflow
- `TestBackupCleanupWorkflow` - Cleanup workflow
- `TestBackupErrorRecovery` - Error scenarios
- `TestBackupConcurrency` - Concurrent execution
- `TestBackupMonitoring` - Logging and monitoring
- `TestBackupDataIntegrity` - Data integrity checks

**Total Tests:** 15+

### 4. `test_celery_beat_schedule.py` (Updated)
Tests for Celery Beat schedule configuration.

**New Coverage:**
- Backup task availability
- Task naming conventions
- Task importability

## Running the Tests

### Run All Backup Tests
```bash
cd backend
pytest tests/test_backup_service.py tests/test_backup_tasks.py tests/test_backup_integration.py -v
```

### Run Specific Test File
```bash
# Service tests
pytest tests/test_backup_service.py -v

# Task tests
pytest tests/test_backup_tasks.py -v

# Integration tests
pytest tests/test_backup_integration.py -v

# Schedule tests
pytest tests/test_celery_beat_schedule.py -v
```

### Run Specific Test Class
```bash
pytest tests/test_backup_service.py::TestFullBackup -v
pytest tests/test_backup_tasks.py::TestCreateDailyBackup -v
```

### Run Specific Test
```bash
pytest tests/test_backup_service.py::TestFullBackup::test_create_full_backup_success -v
```

### Run with Coverage
```bash
pytest tests/test_backup_*.py --cov=app.services.backup_service --cov=app.tasks.backup_tasks --cov-report=html
```

### Run with Verbose Output
```bash
pytest tests/test_backup_*.py -vv -s
```

## Test Dependencies

The tests use the following mocking strategy:

### Mocked Components
- **Database Session** (`SessionLocal`) - Mocked to avoid database connections
- **MinioService** - Mocked to avoid MinIO/S3 connections
- **subprocess.run** - Mocked to avoid actual pg_dump execution
- **File System** - Uses temporary directories for file operations

### Real Components
- **Path operations** - Real file system operations in temp directories
- **Tarball creation** - Real tarfile operations
- **Datetime operations** - Real datetime calculations

## Test Fixtures

### Common Fixtures
- `mock_db` - Mock database session
- `mock_minio_service` - Mock MinIO service
- `mock_session_local` - Mock SessionLocal factory
- `mock_backup_service` - Mock BackupService instance
- `temp_backup_dir` - Temporary directory for file operations

## Expected Test Results

All tests should pass with the following characteristics:

### Success Criteria
- ✅ All 70+ tests pass
- ✅ No database connection required
- ✅ No MinIO/S3 connection required
- ✅ No actual pg_dump execution
- ✅ Fast execution (< 10 seconds total)
- ✅ No side effects or leftover files

### Coverage Goals
- Service code: > 90%
- Task code: > 95%
- Error paths: 100%

## Continuous Integration

These tests are designed to run in CI/CD pipelines without external dependencies:

```yaml
# Example GitHub Actions workflow
- name: Run Backup Tests
  run: |
    cd backend
    pytest tests/test_backup_*.py --cov --cov-report=xml
```

## Troubleshooting

### Common Issues

**Issue:** Tests fail with "ModuleNotFoundError: No module named 'app'"
```bash
# Solution: Run from backend directory
cd backend
pytest tests/test_backup_*.py
```

**Issue:** Tests fail with MinIO connection errors
```bash
# Solution: Ensure MinioService is properly mocked
# Check that @patch decorators are in correct order
```

**Issue:** Temporary files not cleaned up
```bash
# Solution: Tests use fixtures with cleanup
# Check that temp_backup_dir fixture is used
```

## Adding New Tests

When adding new backup functionality:

1. **Add unit tests** to `test_backup_service.py`
2. **Add task tests** to `test_backup_tasks.py`
3. **Add integration tests** to `test_backup_integration.py`
4. **Update this README** with new test descriptions

### Test Template
```python
def test_new_backup_feature(self, mock_session_local, mock_backup_service):
    """Test description"""
    # Setup
    mock_session, mock_db = mock_session_local
    
    # Execute
    result = new_backup_function()
    
    # Assert
    assert result["status"] == "success"
    mock_db.close.assert_called_once()
```

## Related Documentation

- [BackupService Implementation](../app/services/backup_service.py)
- [Backup Tasks Implementation](../app/tasks/backup_tasks.py)
- [Celery Configuration](../app/celery_app.py)
- [Testing Conventions](../tests/README.md)

## Test Maintenance

### Regular Updates
- Review tests when backup logic changes
- Update mocks when dependencies change
- Add tests for new backup features
- Maintain > 90% coverage

### Performance Monitoring
- Tests should complete in < 10 seconds
- No external network calls
- Minimal file system operations
- Efficient mocking strategy
