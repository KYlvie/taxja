"""
Error Tracking Service for Property Asset Management

Tracks validation errors, depreciation generation failures, and critical errors
with structured logging and alerting capabilities.

This service provides:
- Validation error tracking with categorization
- Depreciation generation failure tracking
- Critical error alerting
- Error statistics and reporting
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from enum import Enum
from uuid import UUID
from collections import defaultdict

logger = logging.getLogger(__name__)


class ErrorCategory(str, Enum):
    """Categories of errors tracked by the system"""
    VALIDATION = "validation"
    DEPRECIATION_GENERATION = "depreciation_generation"
    BACKFILL = "backfill"
    PROPERTY_CREATION = "property_creation"
    PROPERTY_UPDATE = "property_update"
    PROPERTY_DELETION = "property_deletion"
    TRANSACTION_LINKING = "transaction_linking"
    DATABASE = "database"
    PERMISSION = "permission"
    CALCULATION = "calculation"
    SYSTEM = "system"


class ErrorSeverity(str, Enum):
    """Severity levels for errors"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorTracker:
    """
    Centralized error tracking service for property asset management.
    
    Provides structured error logging, categorization, and alerting.
    """
    
    # In-memory error storage (use external service like Sentry in production)
    _errors: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    _error_counts: Dict[str, int] = defaultdict(int)
    
    # Alert thresholds
    VALIDATION_ERROR_THRESHOLD = 10  # Alert after 10 validation errors in 1 hour
    DEPRECIATION_FAILURE_THRESHOLD = 3  # Alert after 3 failures in 1 hour
    CRITICAL_ERROR_THRESHOLD = 1  # Alert immediately on critical errors
    
    @classmethod
    def track_validation_error(
        cls,
        error_type: str,
        field: str,
        value: Any,
        message: str,
        user_id: Optional[int] = None,
        property_id: Optional[UUID] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Track a validation error.
        
        Args:
            error_type: Type of validation error (e.g., "value_error", "type_error")
            field: Field that failed validation
            value: Value that was rejected
            message: Error message
            user_id: Optional user ID
            property_id: Optional property ID
            context: Additional context information
        """
        error_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "category": ErrorCategory.VALIDATION,
            "severity": ErrorSeverity.LOW,
            "error_type": error_type,
            "field": field,
            "value": str(value),
            "message": message,
            "user_id": user_id,
            "property_id": str(property_id) if property_id else None,
            "context": context or {}
        }
        
        # Store error
        cls._errors[ErrorCategory.VALIDATION].append(error_data)
        cls._error_counts[f"{ErrorCategory.VALIDATION}:{error_type}"] += 1
        
        # Log with structured data
        logger.warning(
            f"Validation error: {field} - {message}",
            extra={
                "error_category": ErrorCategory.VALIDATION,
                "error_type": error_type,
                "field": field,
                "value": str(value),
                "user_id": user_id,
                "property_id": str(property_id) if property_id else None,
                **error_data["context"]
            }
        )
        
        # Check if we should alert
        cls._check_validation_error_threshold()
    
    @classmethod
    def track_depreciation_failure(
        cls,
        property_id: UUID,
        year: int,
        error: Exception,
        user_id: Optional[int] = None,
        property_address: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Track a depreciation generation failure.
        
        Args:
            property_id: UUID of the property
            year: Tax year for depreciation
            error: Exception that occurred
            user_id: Optional user ID
            property_address: Optional property address for context
            context: Additional context information
        """
        error_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "category": ErrorCategory.DEPRECIATION_GENERATION,
            "severity": ErrorSeverity.HIGH,
            "property_id": str(property_id),
            "year": year,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "user_id": user_id,
            "property_address": property_address,
            "context": context or {}
        }
        
        # Store error
        cls._errors[ErrorCategory.DEPRECIATION_GENERATION].append(error_data)
        cls._error_counts[f"{ErrorCategory.DEPRECIATION_GENERATION}:{year}"] += 1
        
        # Log with structured data
        logger.error(
            f"Depreciation generation failed for property {property_id} (year {year}): {error}",
            extra={
                "error_category": ErrorCategory.DEPRECIATION_GENERATION,
                "property_id": str(property_id),
                "year": year,
                "error_type": type(error).__name__,
                "user_id": user_id,
                "property_address": property_address,
                **error_data["context"]
            },
            exc_info=True
        )
        
        # Check if we should alert
        cls._check_depreciation_failure_threshold()
    
    @classmethod
    def track_backfill_failure(
        cls,
        property_id: UUID,
        error: Exception,
        user_id: Optional[int] = None,
        years_attempted: Optional[List[int]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Track a historical depreciation backfill failure.
        
        Args:
            property_id: UUID of the property
            error: Exception that occurred
            user_id: Optional user ID
            years_attempted: List of years that were being backfilled
            context: Additional context information
        """
        error_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "category": ErrorCategory.BACKFILL,
            "severity": ErrorSeverity.HIGH,
            "property_id": str(property_id),
            "error_type": type(error).__name__,
            "error_message": str(error),
            "user_id": user_id,
            "years_attempted": years_attempted or [],
            "context": context or {}
        }
        
        # Store error
        cls._errors[ErrorCategory.BACKFILL].append(error_data)
        cls._error_counts[f"{ErrorCategory.BACKFILL}:{property_id}"] += 1
        
        # Log with structured data
        logger.error(
            f"Backfill failed for property {property_id}: {error}",
            extra={
                "error_category": ErrorCategory.BACKFILL,
                "property_id": str(property_id),
                "error_type": type(error).__name__,
                "user_id": user_id,
                "years_attempted": years_attempted,
                **error_data["context"]
            },
            exc_info=True
        )
    
    @classmethod
    def track_critical_error(
        cls,
        category: ErrorCategory,
        error: Exception,
        message: str,
        user_id: Optional[int] = None,
        property_id: Optional[UUID] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Track a critical error that requires immediate attention.
        
        Args:
            category: Error category
            error: Exception that occurred
            message: Human-readable error message
            user_id: Optional user ID
            property_id: Optional property ID
            context: Additional context information
        """
        error_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "category": category,
            "severity": ErrorSeverity.CRITICAL,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "alert_message": message,  # Renamed from "message" to avoid LogRecord conflict
            "user_id": user_id,
            "property_id": str(property_id) if property_id else None,
            "context": context or {}
        }
        
        # Store error
        cls._errors[category].append(error_data)
        cls._error_counts[f"{category}:critical"] += 1
        
        # Log with CRITICAL level
        logger.critical(
            f"CRITICAL ERROR - {message}: {error}",
            extra={
                "error_category": category,
                "severity": ErrorSeverity.CRITICAL,
                "error_type": type(error).__name__,
                "alert_message": message,  # Use alert_message instead of message
                "user_id": user_id,
                "property_id": str(property_id) if property_id else None,
                **error_data["context"]
            },
            exc_info=True
        )
        
        # Alert immediately on critical errors
        cls._send_critical_alert(error_data)
    
    @classmethod
    def get_error_statistics(
        cls,
        category: Optional[ErrorCategory] = None,
        since: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get error statistics.
        
        Args:
            category: Optional category filter
            since: Optional time filter (only errors after this time)
            
        Returns:
            Dictionary with error statistics
        """
        if since is None:
            since = datetime.utcnow() - timedelta(hours=24)
        
        # Filter errors
        filtered_errors = []
        if category:
            errors_list = cls._errors.get(category, [])
        else:
            errors_list = []
            for cat_errors in cls._errors.values():
                errors_list.extend(cat_errors)
        
        # Filter by time
        for error in errors_list:
            error_time = datetime.fromisoformat(error["timestamp"])
            if error_time >= since:
                filtered_errors.append(error)
        
        # Calculate statistics
        stats = {
            "total_errors": len(filtered_errors),
            "since": since.isoformat(),
            "by_category": defaultdict(int),
            "by_severity": defaultdict(int),
            "by_error_type": defaultdict(int),
            "recent_errors": filtered_errors[-10:]  # Last 10 errors
        }
        
        for error in filtered_errors:
            stats["by_category"][error["category"]] += 1
            stats["by_severity"][error["severity"]] += 1
            stats["by_error_type"][error["error_type"]] += 1
        
        return stats
    
    @classmethod
    def get_recent_errors(
        cls,
        category: Optional[ErrorCategory] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get recent errors.
        
        Args:
            category: Optional category filter
            limit: Maximum number of errors to return
            
        Returns:
            List of error dictionaries
        """
        if category:
            errors = cls._errors.get(category, [])
        else:
            errors = []
            for cat_errors in cls._errors.values():
                errors.extend(cat_errors)
        
        # Sort by timestamp descending
        sorted_errors = sorted(
            errors,
            key=lambda e: e["timestamp"],
            reverse=True
        )
        
        return sorted_errors[:limit]
    
    @classmethod
    def clear_old_errors(cls, older_than: timedelta = timedelta(days=7)) -> int:
        """
        Clear errors older than specified time.
        
        Args:
            older_than: Timedelta for age threshold
            
        Returns:
            Number of errors cleared
        """
        cutoff = datetime.utcnow() - older_than
        cleared_count = 0
        
        for category in list(cls._errors.keys()):
            original_count = len(cls._errors[category])
            cls._errors[category] = [
                error for error in cls._errors[category]
                if datetime.fromisoformat(error["timestamp"]) >= cutoff
            ]
            cleared_count += original_count - len(cls._errors[category])
        
        logger.info(f"Cleared {cleared_count} old errors (older than {older_than})")
        return cleared_count
    
    @classmethod
    def _check_validation_error_threshold(cls) -> None:
        """Check if validation errors exceed threshold and alert if needed"""
        # Count validation errors in last hour
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        recent_errors = [
            error for error in cls._errors.get(ErrorCategory.VALIDATION, [])
            if datetime.fromisoformat(error["timestamp"]) >= one_hour_ago
        ]
        
        if len(recent_errors) >= cls.VALIDATION_ERROR_THRESHOLD:
            logger.warning(
                f"ALERT: High validation error rate - {len(recent_errors)} errors in last hour",
                extra={
                    "alert_type": "high_validation_error_rate",
                    "error_count": len(recent_errors),
                    "threshold": cls.VALIDATION_ERROR_THRESHOLD,
                    "time_window": "1 hour"
                }
            )
    
    @classmethod
    def _check_depreciation_failure_threshold(cls) -> None:
        """Check if depreciation failures exceed threshold and alert if needed"""
        # Count depreciation failures in last hour
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        recent_failures = [
            error for error in cls._errors.get(ErrorCategory.DEPRECIATION_GENERATION, [])
            if datetime.fromisoformat(error["timestamp"]) >= one_hour_ago
        ]
        
        if len(recent_failures) >= cls.DEPRECIATION_FAILURE_THRESHOLD:
            logger.error(
                f"ALERT: High depreciation failure rate - {len(recent_failures)} failures in last hour",
                extra={
                    "alert_type": "high_depreciation_failure_rate",
                    "failure_count": len(recent_failures),
                    "threshold": cls.DEPRECIATION_FAILURE_THRESHOLD,
                    "time_window": "1 hour",
                    "failed_properties": [e["property_id"] for e in recent_failures]
                }
            )
    
    @classmethod
    def _send_critical_alert(cls, error_data: Dict[str, Any]) -> None:
        """
        Send immediate alert for critical errors.
        
        In production, this would integrate with:
        - Email notifications
        - Slack/Teams webhooks
        - PagerDuty
        - Sentry
        
        Args:
            error_data: Error data dictionary
        """
        logger.critical(
            f"CRITICAL ALERT: {error_data['alert_message']}",
            extra={
                "alert_type": "critical_error",
                "requires_immediate_attention": True,
                "alert_message": error_data["alert_message"],
                "error_category": error_data["category"],
                "error_type": error_data["error_type"],
                "error_message": error_data["error_message"],
                "severity": error_data["severity"],
                "user_id": error_data.get("user_id"),
                "property_id": error_data.get("property_id"),
                "timestamp": error_data["timestamp"]
            }
        )
        
        # TODO: Integrate with external alerting service
        # Example: send_email_alert(error_data)
        # Example: send_slack_alert(error_data)
        # Example: create_pagerduty_incident(error_data)
    
    @classmethod
    def reset(cls) -> None:
        """Reset all error tracking (useful for testing)"""
        cls._errors.clear()
        cls._error_counts.clear()
