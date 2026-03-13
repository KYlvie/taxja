"""
Tests for Celery Beat schedule configuration.

Validates that the annual depreciation task is properly scheduled
for year-end execution (December 31 at 23:00 Vienna time).
"""
import pytest
import sys
import os

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_beat_schedule_configuration():
    """
    Test that Celery Beat schedule is properly configured.
    
    This test validates the schedule configuration without requiring
    a full database connection or environment setup.
    """
    # Mock settings to avoid database connection
    from unittest.mock import MagicMock
    import app.core.config as config_module
    
    mock_settings = MagicMock()
    mock_settings.CELERY_BROKER = "redis://localhost:6379/0"
    mock_settings.CELERY_BACKEND = "redis://localhost:6379/0"
    config_module.settings = mock_settings
    
    # Import celery_app after mocking settings
    from app.celery_app import celery_app
    
    # Test beat_schedule exists
    assert hasattr(celery_app.conf, 'beat_schedule')
    assert celery_app.conf.beat_schedule is not None
    assert isinstance(celery_app.conf.beat_schedule, dict)
    
    # Test annual depreciation schedule exists
    assert 'generate-annual-depreciation' in celery_app.conf.beat_schedule
    
    schedule_entry = celery_app.conf.beat_schedule['generate-annual-depreciation']
    
    # Verify task name
    assert schedule_entry['task'] == 'property.generate_annual_depreciation'
    
    # Verify schedule timing (December 31 at 23:00)
    schedule = schedule_entry['schedule']
    assert schedule['minute'] == '0', "Should run at minute 0"
    assert schedule['hour'] == '23', "Should run at 23:00 (11 PM)"
    assert schedule['day_of_month'] == '31', "Should run on day 31"
    assert schedule['month_of_year'] == '12', "Should run in December"
    
    # Verify options
    options = schedule_entry.get('options', {})
    assert 'expires' in options, "Should have expiration configured"
    assert options['expires'] == 3600 * 2, "Should expire after 2 hours"
    assert 'priority' in options, "Should have priority configured"
    assert options['priority'] == 9, "Should have high priority (9)"
    
    # Verify no arguments (uses current year by default)
    assert schedule_entry['args'] == ()
    assert schedule_entry['kwargs'] == {}
    
    # Test timezone configuration
    assert celery_app.conf.timezone == 'Europe/Vienna'
    assert celery_app.conf.enable_utc is True
    
    # Test task tracking
    assert celery_app.conf.task_track_started is True
    
    # Test result backend configuration
    assert celery_app.conf.result_expires == 3600 * 24 * 7  # 7 days
    assert celery_app.conf.result_extended is True
    
    # Test task execution settings
    assert celery_app.conf.task_acks_late is True
    assert celery_app.conf.task_reject_on_worker_lost is True
    assert celery_app.conf.worker_prefetch_multiplier == 1
    
    # Test time limits
    assert celery_app.conf.task_time_limit == 30 * 60  # 30 minutes
    assert celery_app.conf.task_soft_time_limit == 25 * 60  # 25 minutes
    
    print("✓ All Celery Beat schedule configuration tests passed")


def test_backup_tasks_can_be_scheduled():
    """
    Test that backup tasks are available and can be scheduled.
    
    Note: Backup tasks are typically scheduled manually or via external
    cron jobs rather than Celery Beat, but they should be importable
    and executable.
    """
    from unittest.mock import MagicMock
    import app.core.config as config_module
    
    mock_settings = MagicMock()
    mock_settings.CELERY_BROKER = "redis://localhost:6379/0"
    mock_settings.CELERY_BACKEND = "redis://localhost:6379/0"
    config_module.settings = mock_settings
    
    # Test that backup tasks can be imported
    try:
        from app.tasks.backup_tasks import (
            create_daily_backup,
            create_database_backup,
            create_documents_backup,
            cleanup_old_backups,
        )
        
        # Verify tasks are callable
        assert callable(create_daily_backup)
        assert callable(create_database_backup)
        assert callable(create_documents_backup)
        assert callable(cleanup_old_backups)
        
        # Verify tasks have Celery task attributes
        assert hasattr(create_daily_backup, 'name')
        assert hasattr(create_database_backup, 'name')
        assert hasattr(create_documents_backup, 'name')
        assert hasattr(cleanup_old_backups, 'name')
        
        # Verify task names
        assert create_daily_backup.name == 'backup.create_daily_backup'
        assert create_database_backup.name == 'backup.create_database_backup'
        assert create_documents_backup.name == 'backup.create_documents_backup'
        assert cleanup_old_backups.name == 'backup.cleanup_old_backups'
        
        print("✓ All backup tasks are properly configured")
        
    except ImportError as e:
        pytest.fail(f"Failed to import backup tasks: {e}")


def test_monitoring_signal_handlers():
    """Test that monitoring signal handlers are defined"""
    from unittest.mock import MagicMock
    import app.core.config as config_module
    
    mock_settings = MagicMock()
    mock_settings.CELERY_BROKER = "redis://localhost:6379/0"
    mock_settings.CELERY_BACKEND = "redis://localhost:6379/0"
    config_module.settings = mock_settings
    
    # Import celery_app module
    from app import celery_app as celery_module
    
    # Test that signal handlers exist
    signal_handlers = [
        "task_prerun_handler",
        "task_postrun_handler",
        "task_success_handler",
        "task_failure_handler"
    ]
    
    for handler_name in signal_handlers:
        assert hasattr(celery_module, handler_name), f"Missing handler: {handler_name}"
        handler = getattr(celery_module, handler_name)
        assert callable(handler), f"Handler {handler_name} is not callable"
    
    print("✓ All monitoring signal handlers are defined")


if __name__ == "__main__":
    test_beat_schedule_configuration()
    test_backup_tasks_can_be_scheduled()
    test_monitoring_signal_handlers()
    print("\n✓ All tests passed successfully!")

