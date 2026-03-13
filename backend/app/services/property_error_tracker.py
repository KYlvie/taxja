"""
Property Error Tracking Service

Tracks and logs errors in property management operations for monitoring and alerting.
Provides structured error logging with context for debugging and analysis.
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from enum import Enum


logger = logging.getLogger(__name__)


class ErrorSeverity(str, Enum):
    """Error severity levels for alerting."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(str, Enum):
    """Categories of errors in property management."""
    VALIDATION = "validation"
    DATABASE = "database"
    CALCULATION = "calculation"
    PERMISSION = "permission"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    EXTERNAL_SERVICE = "external_service"
    UNKNOWN = "unknown"


class PropertyErrorTracker:
    """
    Service for tracking and logging property management errors.
    
    Provides structured error logging with context, severity levels,
    and integration with monitoring systems.
    """
    
    @staticmethod
    def track_error(
        error_category: ErrorCategory,
        error_message: str,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        context: Optional[Dict[str, Any]] = None,
        exception: Optional[Exception] = None
    ):
        """
        Track an error with full context.
        
        Args:
            error_category: Category of the error
            error_message: Human-readable error message
            severity: Severity level for alerting
            context: Additional context (user_id, property_id, etc.)
            exception: Original exception if available
        """
        error_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "category": error_category.value,
            "error_msg": error_message,
            "severity": severity.value,
            "context": context or {}
        }
        
        if exception:
            error_data["exception_type"] = type(exception).__name__
            error_data["exception_message"] = str(exception)
        
        # Log based on severity
        if severity == ErrorSeverity.CRITICAL:
            logger.critical(
                f"CRITICAL ERROR: {error_message}",
                extra=error_data,
                exc_info=exception
            )
        elif severity == ErrorSeverity.HIGH:
            logger.error(
                f"HIGH SEVERITY: {error_message}",
                extra=error_data,
                exc_info=exception
            )
        elif severity == ErrorSeverity.MEDIUM:
            logger.warning(
                f"MEDIUM SEVERITY: {error_message}",
                extra=error_data
            )
        else:
            logger.info(
                f"LOW SEVERITY: {error_message}",
                extra=error_data
            )
    
    @staticmethod
    def track_validation_error(
        field_name: str,
        error_message: str,
        user_id: Optional[int] = None,
        property_data: Optional[Dict[str, Any]] = None
    ):
        """Track a validation error."""
        PropertyErrorTracker.track_error(
            error_category=ErrorCategory.VALIDATION,
            error_message=f"Validation failed for {field_name}: {error_message}",
            severity=ErrorSeverity.LOW,
            context={
                "field_name": field_name,
                "user_id": user_id,
                "property_data": property_data
            }
        )
    
    @staticmethod
    def track_depreciation_generation_failure(
        property_id: str,
        year: int,
        error_message: str,
        exception: Optional[Exception] = None
    ):
        """Track a depreciation generation failure."""
        PropertyErrorTracker.track_error(
            error_category=ErrorCategory.CALCULATION,
            error_message=f"Depreciation generation failed for property {property_id}, year {year}",
            severity=ErrorSeverity.HIGH,
            context={
                "property_id": property_id,
                "year": year,
                "error_details": error_message
            },
            exception=exception
        )
    
    @staticmethod
    def track_backfill_failure(
        property_id: str,
        user_id: int,
        years_attempted: int,
        error_message: str,
        exception: Optional[Exception] = None
    ):
        """Track a historical backfill failure."""
        PropertyErrorTracker.track_error(
            error_category=ErrorCategory.CALCULATION,
            error_message=f"Historical backfill failed for property {property_id}",
            severity=ErrorSeverity.HIGH,
            context={
                "property_id": property_id,
                "user_id": user_id,
                "years_attempted": years_attempted,
                "error_details": error_message
            },
            exception=exception
        )
    
    @staticmethod
    def track_database_error(
        operation: str,
        error_message: str,
        context: Optional[Dict[str, Any]] = None,
        exception: Optional[Exception] = None
    ):
        """Track a database operation error."""
        PropertyErrorTracker.track_error(
            error_category=ErrorCategory.DATABASE,
            error_message=f"Database error during {operation}: {error_message}",
            severity=ErrorSeverity.CRITICAL,
            context=context or {},
            exception=exception
        )
    
    @staticmethod
    def track_permission_error(
        user_id: int,
        property_id: str,
        operation: str
    ):
        """Track a permission/authorization error."""
        PropertyErrorTracker.track_error(
            error_category=ErrorCategory.PERMISSION,
            error_message=f"Permission denied for user {user_id} on property {property_id}",
            severity=ErrorSeverity.MEDIUM,
            context={
                "user_id": user_id,
                "property_id": property_id,
                "operation": operation
            }
        )
    
    @staticmethod
    def track_not_found_error(
        resource_type: str,
        resource_id: str,
        user_id: Optional[int] = None
    ):
        """Track a resource not found error."""
        PropertyErrorTracker.track_error(
            error_category=ErrorCategory.NOT_FOUND,
            error_message=f"{resource_type} not found: {resource_id}",
            severity=ErrorSeverity.LOW,
            context={
                "resource_type": resource_type,
                "resource_id": resource_id,
                "user_id": user_id
            }
        )
    
    @staticmethod
    def track_conflict_error(
        conflict_type: str,
        error_message: str,
        context: Optional[Dict[str, Any]] = None
    ):
        """Track a conflict error (e.g., duplicate depreciation)."""
        PropertyErrorTracker.track_error(
            error_category=ErrorCategory.CONFLICT,
            error_message=f"Conflict detected: {conflict_type} - {error_message}",
            severity=ErrorSeverity.MEDIUM,
            context=context or {}
        )
    
    @staticmethod
    def track_calculation_error(
        calculation_type: str,
        error_message: str,
        context: Optional[Dict[str, Any]] = None,
        exception: Optional[Exception] = None
    ):
        """Track a calculation error."""
        PropertyErrorTracker.track_error(
            error_category=ErrorCategory.CALCULATION,
            error_message=f"Calculation error in {calculation_type}: {error_message}",
            severity=ErrorSeverity.HIGH,
            context=context or {},
            exception=exception
        )
