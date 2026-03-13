"""
Tests for Property Error Tracker

Tests the error tracking and logging functionality for property management.
"""
import pytest
import logging
from app.services.property_error_tracker import (
    PropertyErrorTracker,
    ErrorSeverity,
    ErrorCategory
)


def test_track_error_basic(caplog):
    """Test basic error tracking."""
    with caplog.at_level(logging.WARNING):
        PropertyErrorTracker.track_error(
            error_category=ErrorCategory.VALIDATION,
            error_message="Test validation error",
            severity=ErrorSeverity.MEDIUM
        )
    
    assert "Test validation error" in caplog.text
    assert "MEDIUM SEVERITY" in caplog.text


def test_track_error_with_context(caplog):
    """Test error tracking with context."""
    with caplog.at_level(logging.WARNING):
        PropertyErrorTracker.track_error(
            error_category=ErrorCategory.DATABASE,
            error_message="Database connection failed",
            severity=ErrorSeverity.HIGH,
            context={
                "user_id": 123,
                "property_id": "550e8400-e29b-41d4-a716-446655440000"
            }
        )
    
    assert "Database connection failed" in caplog.text
    assert "HIGH SEVERITY" in caplog.text


def test_track_error_with_exception(caplog):
    """Test error tracking with exception."""
    try:
        raise ValueError("Test exception")
    except ValueError as e:
        with caplog.at_level(logging.ERROR):
            PropertyErrorTracker.track_error(
                error_category=ErrorCategory.CALCULATION,
                error_message="Calculation failed",
                severity=ErrorSeverity.HIGH,
                exception=e
            )
    
    assert "Calculation failed" in caplog.text
    assert "ValueError" in caplog.text


def test_track_critical_error(caplog):
    """Test tracking critical error."""
    with caplog.at_level(logging.CRITICAL):
        PropertyErrorTracker.track_error(
            error_category=ErrorCategory.DATABASE,
            error_message="Critical database failure",
            severity=ErrorSeverity.CRITICAL
        )
    
    assert "CRITICAL ERROR" in caplog.text
    assert "Critical database failure" in caplog.text


def test_track_low_severity_error(caplog):
    """Test tracking low severity error."""
    with caplog.at_level(logging.INFO):
        PropertyErrorTracker.track_error(
            error_category=ErrorCategory.VALIDATION,
            error_message="Minor validation issue",
            severity=ErrorSeverity.LOW
        )
    
    assert "LOW SEVERITY" in caplog.text
    assert "Minor validation issue" in caplog.text


def test_track_validation_error(caplog):
    """Test tracking validation error."""
    with caplog.at_level(logging.INFO):
        PropertyErrorTracker.track_validation_error(
            field_name="purchase_price",
            error_message="Must be greater than 0",
            user_id=123
        )
    
    assert "purchase_price" in caplog.text
    assert "Must be greater than 0" in caplog.text


def test_track_depreciation_generation_failure(caplog):
    """Test tracking depreciation generation failure."""
    with caplog.at_level(logging.ERROR):
        PropertyErrorTracker.track_depreciation_generation_failure(
            property_id="550e8400-e29b-41d4-a716-446655440000",
            year=2026,
            error_message="Building value exceeded"
        )
    
    assert "Depreciation generation failed" in caplog.text
    assert "550e8400-e29b-41d4-a716-446655440000" in caplog.text
    assert "2026" in caplog.text


def test_track_backfill_failure(caplog):
    """Test tracking backfill failure."""
    with caplog.at_level(logging.ERROR):
        PropertyErrorTracker.track_backfill_failure(
            property_id="550e8400-e29b-41d4-a716-446655440000",
            user_id=123,
            years_attempted=5,
            error_message="Transaction creation failed"
        )
    
    assert "Historical backfill failed" in caplog.text
    assert "550e8400-e29b-41d4-a716-446655440000" in caplog.text


def test_track_database_error(caplog):
    """Test tracking database error."""
    with caplog.at_level(logging.CRITICAL):
        PropertyErrorTracker.track_database_error(
            operation="property_creation",
            error_message="Connection timeout",
            context={"user_id": 123}
        )
    
    assert "Database error during property_creation" in caplog.text
    assert "Connection timeout" in caplog.text


def test_track_permission_error(caplog):
    """Test tracking permission error."""
    with caplog.at_level(logging.WARNING):
        PropertyErrorTracker.track_permission_error(
            user_id=123,
            property_id="550e8400-e29b-41d4-a716-446655440000",
            operation="update"
        )
    
    assert "Permission denied" in caplog.text
    assert "user 123" in caplog.text


def test_track_not_found_error(caplog):
    """Test tracking not found error."""
    with caplog.at_level(logging.INFO):
        PropertyErrorTracker.track_not_found_error(
            resource_type="Property",
            resource_id="550e8400-e29b-41d4-a716-446655440000",
            user_id=123
        )
    
    assert "Property not found" in caplog.text
    assert "550e8400-e29b-41d4-a716-446655440000" in caplog.text


def test_track_conflict_error(caplog):
    """Test tracking conflict error."""
    with caplog.at_level(logging.WARNING):
        PropertyErrorTracker.track_conflict_error(
            conflict_type="duplicate_depreciation",
            error_message="Depreciation already exists for year 2026",
            context={"property_id": "550e8400-e29b-41d4-a716-446655440000"}
        )
    
    assert "Conflict detected" in caplog.text
    assert "duplicate_depreciation" in caplog.text


def test_track_calculation_error(caplog):
    """Test tracking calculation error."""
    with caplog.at_level(logging.ERROR):
        PropertyErrorTracker.track_calculation_error(
            calculation_type="depreciation",
            error_message="Invalid depreciation rate",
            context={"property_id": "550e8400-e29b-41d4-a716-446655440000"}
        )
    
    assert "Calculation error in depreciation" in caplog.text
    assert "Invalid depreciation rate" in caplog.text


def test_error_categories():
    """Test all error categories."""
    categories = [
        ErrorCategory.VALIDATION,
        ErrorCategory.DATABASE,
        ErrorCategory.CALCULATION,
        ErrorCategory.PERMISSION,
        ErrorCategory.NOT_FOUND,
        ErrorCategory.CONFLICT,
        ErrorCategory.EXTERNAL_SERVICE,
        ErrorCategory.UNKNOWN
    ]
    
    for category in categories:
        assert category.value in [
            "validation", "database", "calculation", "permission",
            "not_found", "conflict", "external_service", "unknown"
        ]


def test_error_severities():
    """Test all error severity levels."""
    severities = [
        ErrorSeverity.LOW,
        ErrorSeverity.MEDIUM,
        ErrorSeverity.HIGH,
        ErrorSeverity.CRITICAL
    ]
    
    for severity in severities:
        assert severity.value in ["low", "medium", "high", "critical"]
