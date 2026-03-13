"""
Tests for Error Tracking Service

Tests validation error tracking, depreciation failure tracking,
critical error alerting, and error statistics.
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from decimal import Decimal

from app.services.error_tracker import ErrorTracker, ErrorCategory, ErrorSeverity


@pytest.fixture(autouse=True)
def reset_error_tracker():
    """Reset error tracker before each test"""
    ErrorTracker.reset()
    yield
    ErrorTracker.reset()


class TestValidationErrorTracking:
    """Test validation error tracking"""
    
    def test_track_validation_error(self):
        """Test tracking a validation error"""
        property_id = uuid4()
        user_id = 123
        
        ErrorTracker.track_validation_error(
            error_type="value_error",
            field="purchase_price",
            value="-1000",
            message="purchase_price must be greater than 0",
            user_id=user_id,
            property_id=property_id,
            context={"operation": "create_property"}
        )
        
        # Check error was stored
        errors = ErrorTracker.get_recent_errors(category=ErrorCategory.VALIDATION)
        assert len(errors) == 1
        
        error = errors[0]
        assert error["category"] == ErrorCategory.VALIDATION
        assert error["severity"] == ErrorSeverity.LOW
        assert error["error_type"] == "value_error"
        assert error["field"] == "purchase_price"
        assert error["value"] == "-1000"
        assert error["message"] == "purchase_price must be greater than 0"
        assert error["user_id"] == user_id
        assert error["property_id"] == str(property_id)
        assert error["context"]["operation"] == "create_property"
    
    def test_validation_error_threshold_alert(self):
        """Test that validation errors trigger alert when threshold exceeded"""
        # Track multiple validation errors
        for i in range(ErrorTracker.VALIDATION_ERROR_THRESHOLD + 1):
            ErrorTracker.track_validation_error(
                error_type="value_error",
                field=f"field_{i}",
                value="invalid",
                message=f"Validation error {i}",
                user_id=123
            )
        
        # Check that errors were tracked
        errors = ErrorTracker.get_recent_errors(category=ErrorCategory.VALIDATION)
        assert len(errors) == ErrorTracker.VALIDATION_ERROR_THRESHOLD + 1
        
        # In production, this would trigger an alert
        # We verify the count exceeds threshold
        stats = ErrorTracker.get_error_statistics(
            category=ErrorCategory.VALIDATION,
            since=datetime.utcnow() - timedelta(hours=1)
        )
        assert stats["total_errors"] >= ErrorTracker.VALIDATION_ERROR_THRESHOLD


class TestDepreciationFailureTracking:
    """Test depreciation failure tracking"""
    
    def test_track_depreciation_failure(self):
        """Test tracking a depreciation generation failure"""
        property_id = uuid4()
        user_id = 456
        year = 2026
        error = ValueError("Building value cannot be negative")
        
        ErrorTracker.track_depreciation_failure(
            property_id=property_id,
            year=year,
            error=error,
            user_id=user_id,
            property_address="Hauptstraße 123, 1010 Wien",
            context={
                "building_value": "-1000",
                "depreciation_rate": "0.02"
            }
        )
        
        # Check error was stored
        errors = ErrorTracker.get_recent_errors(category=ErrorCategory.DEPRECIATION_GENERATION)
        assert len(errors) == 1
        
        error_data = errors[0]
        assert error_data["category"] == ErrorCategory.DEPRECIATION_GENERATION
        assert error_data["severity"] == ErrorSeverity.HIGH
        assert error_data["property_id"] == str(property_id)
        assert error_data["year"] == year
        assert error_data["error_type"] == "ValueError"
        assert "Building value cannot be negative" in error_data["error_message"]
        assert error_data["user_id"] == user_id
        assert error_data["property_address"] == "Hauptstraße 123, 1010 Wien"
    
    def test_depreciation_failure_threshold_alert(self):
        """Test that depreciation failures trigger alert when threshold exceeded"""
        property_id = uuid4()
        
        # Track multiple depreciation failures
        for i in range(ErrorTracker.DEPRECIATION_FAILURE_THRESHOLD + 1):
            ErrorTracker.track_depreciation_failure(
                property_id=property_id,
                year=2026,
                error=RuntimeError(f"Failure {i}"),
                user_id=123
            )
        
        # Check that failures were tracked
        errors = ErrorTracker.get_recent_errors(category=ErrorCategory.DEPRECIATION_GENERATION)
        assert len(errors) == ErrorTracker.DEPRECIATION_FAILURE_THRESHOLD + 1
        
        # Verify count exceeds threshold
        stats = ErrorTracker.get_error_statistics(
            category=ErrorCategory.DEPRECIATION_GENERATION,
            since=datetime.utcnow() - timedelta(hours=1)
        )
        assert stats["total_errors"] >= ErrorTracker.DEPRECIATION_FAILURE_THRESHOLD


class TestBackfillFailureTracking:
    """Test backfill failure tracking"""
    
    def test_track_backfill_failure(self):
        """Test tracking a backfill operation failure"""
        property_id = uuid4()
        user_id = 789
        years_attempted = [2020, 2021, 2022, 2023, 2024, 2025]
        error = RuntimeError("Database connection lost during backfill")
        
        ErrorTracker.track_backfill_failure(
            property_id=property_id,
            error=error,
            user_id=user_id,
            years_attempted=years_attempted,
            context={"confirm": True}
        )
        
        # Check error was stored
        errors = ErrorTracker.get_recent_errors(category=ErrorCategory.BACKFILL)
        assert len(errors) == 1
        
        error_data = errors[0]
        assert error_data["category"] == ErrorCategory.BACKFILL
        assert error_data["severity"] == ErrorSeverity.HIGH
        assert error_data["property_id"] == str(property_id)
        assert error_data["error_type"] == "RuntimeError"
        assert "Database connection lost" in error_data["error_message"]
        assert error_data["user_id"] == user_id
        assert error_data["years_attempted"] == years_attempted


class TestCriticalErrorTracking:
    """Test critical error tracking and alerting"""
    
    def test_track_critical_error(self):
        """Test tracking a critical error"""
        property_id = uuid4()
        user_id = 999
        error = Exception("Database corruption detected")
        
        ErrorTracker.track_critical_error(
            category=ErrorCategory.DATABASE,
            error=error,
            message="Critical database error in property service",
            user_id=user_id,
            property_id=property_id,
            context={"operation": "update_property"}
        )
        
        # Check error was stored
        errors = ErrorTracker.get_recent_errors(category=ErrorCategory.DATABASE)
        assert len(errors) == 1
        
        error_data = errors[0]
        assert error_data["category"] == ErrorCategory.DATABASE
        assert error_data["severity"] == ErrorSeverity.CRITICAL
        assert error_data["error_type"] == "Exception"
        assert "Database corruption detected" in error_data["error_message"]
        assert error_data["alert_message"] == "Critical database error in property service"
        assert error_data["user_id"] == user_id
        assert error_data["property_id"] == str(property_id)
    
    def test_critical_error_immediate_alert(self):
        """Test that critical errors trigger immediate alert"""
        # Track a critical error
        ErrorTracker.track_critical_error(
            category=ErrorCategory.SYSTEM,
            error=Exception("System failure"),
            message="Critical system error",
            user_id=123
        )
        
        # Verify error was tracked with critical severity
        stats = ErrorTracker.get_error_statistics()
        assert stats["by_severity"][ErrorSeverity.CRITICAL] == 1


class TestErrorStatistics:
    """Test error statistics and reporting"""
    
    def test_get_error_statistics_all_categories(self):
        """Test getting statistics for all error categories"""
        # Track various errors
        ErrorTracker.track_validation_error(
            error_type="value_error",
            field="test",
            value="invalid",
            message="Test error 1",
            user_id=123
        )
        
        ErrorTracker.track_depreciation_failure(
            property_id=uuid4(),
            year=2026,
            error=ValueError("Test error 2"),
            user_id=123
        )
        
        ErrorTracker.track_backfill_failure(
            property_id=uuid4(),
            error=RuntimeError("Test error 3"),
            user_id=123
        )
        
        # Get statistics
        stats = ErrorTracker.get_error_statistics()
        
        assert stats["total_errors"] == 3
        assert stats["by_category"][ErrorCategory.VALIDATION] == 1
        assert stats["by_category"][ErrorCategory.DEPRECIATION_GENERATION] == 1
        assert stats["by_category"][ErrorCategory.BACKFILL] == 1
        assert stats["by_severity"][ErrorSeverity.LOW] == 1
        assert stats["by_severity"][ErrorSeverity.HIGH] == 2
    
    def test_get_error_statistics_filtered_by_category(self):
        """Test getting statistics filtered by category"""
        # Track errors in different categories
        for i in range(5):
            ErrorTracker.track_validation_error(
                error_type="value_error",
                field=f"field_{i}",
                value="invalid",
                message=f"Error {i}",
                user_id=123
            )
        
        for i in range(3):
            ErrorTracker.track_depreciation_failure(
                property_id=uuid4(),
                year=2026,
                error=ValueError(f"Error {i}"),
                user_id=123
            )
        
        # Get statistics for validation only
        stats = ErrorTracker.get_error_statistics(category=ErrorCategory.VALIDATION)
        assert stats["total_errors"] == 5
        
        # Get statistics for depreciation only
        stats = ErrorTracker.get_error_statistics(category=ErrorCategory.DEPRECIATION_GENERATION)
        assert stats["total_errors"] == 3
    
    def test_get_error_statistics_time_filtered(self):
        """Test getting statistics filtered by time"""
        # Track an error
        ErrorTracker.track_validation_error(
            error_type="value_error",
            field="test",
            value="invalid",
            message="Recent error",
            user_id=123
        )
        
        # Get statistics for last hour
        stats = ErrorTracker.get_error_statistics(
            since=datetime.utcnow() - timedelta(hours=1)
        )
        assert stats["total_errors"] == 1
        
        # Get statistics for last minute (should be 1)
        stats = ErrorTracker.get_error_statistics(
            since=datetime.utcnow() - timedelta(minutes=1)
        )
        assert stats["total_errors"] == 1
        
        # Get statistics for future (should be 0)
        stats = ErrorTracker.get_error_statistics(
            since=datetime.utcnow() + timedelta(hours=1)
        )
        assert stats["total_errors"] == 0


class TestRecentErrors:
    """Test retrieving recent errors"""
    
    def test_get_recent_errors_all_categories(self):
        """Test getting recent errors across all categories"""
        # Track errors
        for i in range(10):
            ErrorTracker.track_validation_error(
                error_type="value_error",
                field=f"field_{i}",
                value="invalid",
                message=f"Error {i}",
                user_id=123
            )
        
        # Get recent errors
        errors = ErrorTracker.get_recent_errors(limit=5)
        assert len(errors) == 5
        
        # Verify they're sorted by timestamp (most recent first)
        timestamps = [datetime.fromisoformat(e["timestamp"]) for e in errors]
        assert timestamps == sorted(timestamps, reverse=True)
    
    def test_get_recent_errors_filtered_by_category(self):
        """Test getting recent errors filtered by category"""
        # Track errors in different categories
        for i in range(5):
            ErrorTracker.track_validation_error(
                error_type="value_error",
                field=f"field_{i}",
                value="invalid",
                message=f"Validation error {i}",
                user_id=123
            )
        
        for i in range(3):
            ErrorTracker.track_depreciation_failure(
                property_id=uuid4(),
                year=2026,
                error=ValueError(f"Depreciation error {i}"),
                user_id=123
            )
        
        # Get validation errors only
        validation_errors = ErrorTracker.get_recent_errors(
            category=ErrorCategory.VALIDATION,
            limit=10
        )
        assert len(validation_errors) == 5
        assert all(e["category"] == ErrorCategory.VALIDATION for e in validation_errors)
        
        # Get depreciation errors only
        depreciation_errors = ErrorTracker.get_recent_errors(
            category=ErrorCategory.DEPRECIATION_GENERATION,
            limit=10
        )
        assert len(depreciation_errors) == 3
        assert all(e["category"] == ErrorCategory.DEPRECIATION_GENERATION for e in depreciation_errors)


class TestErrorCleanup:
    """Test error cleanup functionality"""
    
    def test_clear_old_errors(self):
        """Test clearing old errors"""
        # Track some errors
        for i in range(10):
            ErrorTracker.track_validation_error(
                error_type="value_error",
                field=f"field_{i}",
                value="invalid",
                message=f"Error {i}",
                user_id=123
            )
        
        # Verify errors exist
        errors_before = ErrorTracker.get_recent_errors()
        assert len(errors_before) == 10
        
        # Clear errors older than 1 day (should clear none since they're recent)
        cleared = ErrorTracker.clear_old_errors(older_than=timedelta(days=1))
        assert cleared == 0
        
        # Verify errors still exist
        errors_after = ErrorTracker.get_recent_errors()
        assert len(errors_after) == 10
        
        # Clear errors older than 0 seconds (should clear all)
        cleared = ErrorTracker.clear_old_errors(older_than=timedelta(seconds=0))
        assert cleared == 10
        
        # Verify errors were cleared
        errors_final = ErrorTracker.get_recent_errors()
        assert len(errors_final) == 0


class TestErrorCounts:
    """Test error counting functionality"""
    
    def test_error_counts_increment(self):
        """Test that error counts increment correctly"""
        # Track multiple errors of same type
        for i in range(5):
            ErrorTracker.track_validation_error(
                error_type="value_error",
                field="purchase_price",
                value="-1000",
                message="Invalid value",
                user_id=123
            )
        
        # Check count
        count_key = f"{ErrorCategory.VALIDATION}:value_error"
        assert ErrorTracker._error_counts[count_key] == 5
    
    def test_error_counts_different_types(self):
        """Test error counts for different error types"""
        # Track different error types
        ErrorTracker.track_validation_error(
            error_type="value_error",
            field="field1",
            value="invalid",
            message="Error 1",
            user_id=123
        )
        
        ErrorTracker.track_validation_error(
            error_type="type_error",
            field="field2",
            value="invalid",
            message="Error 2",
            user_id=123
        )
        
        # Check counts
        assert ErrorTracker._error_counts[f"{ErrorCategory.VALIDATION}:value_error"] == 1
        assert ErrorTracker._error_counts[f"{ErrorCategory.VALIDATION}:type_error"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
