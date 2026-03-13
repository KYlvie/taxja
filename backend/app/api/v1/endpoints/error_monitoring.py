"""
Error Monitoring API Endpoints

Provides endpoints for viewing error statistics and recent errors.
Admin-only endpoints for monitoring system health.
"""

from fastapi import APIRouter, Depends, Query, HTTPException, status
from typing import Optional
from datetime import datetime, timedelta

from app.models.user import User
from app.api.deps import get_current_user, get_current_admin_user
from app.services.error_tracker import ErrorTracker, ErrorCategory, ErrorSeverity


router = APIRouter()


@router.get("/errors/statistics")
def get_error_statistics(
    category: Optional[ErrorCategory] = Query(None, description="Filter by error category"),
    hours: int = Query(24, description="Time window in hours", ge=1, le=168),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Get error statistics for monitoring.
    
    **Admin only endpoint**
    
    **Query Parameters:**
    - **category**: Optional error category filter
    - **hours**: Time window in hours (default: 24, max: 168/7 days)
    
    **Returns:**
    - Total error count
    - Errors by category
    - Errors by severity
    - Errors by type
    - Recent errors (last 10)
    
    **Example Request:**
    ```
    GET /api/v1/monitoring/errors/statistics?category=depreciation_generation&hours=24
    ```
    
    **Example Response:**
    ```json
    {
      "total_errors": 15,
      "since": "2026-03-07T10:00:00",
      "by_category": {
        "depreciation_generation": 8,
        "validation": 5,
        "backfill": 2
      },
      "by_severity": {
        "high": 10,
        "low": 5
      },
      "by_error_type": {
        "ValueError": 5,
        "RuntimeError": 3,
        "PermissionError": 2
      },
      "recent_errors": [...]
    }
    ```
    """
    since = datetime.utcnow() - timedelta(hours=hours)
    
    stats = ErrorTracker.get_error_statistics(
        category=category,
        since=since
    )
    
    return stats


@router.get("/errors/recent")
def get_recent_errors(
    category: Optional[ErrorCategory] = Query(None, description="Filter by error category"),
    limit: int = Query(50, description="Maximum number of errors to return", ge=1, le=200),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Get recent errors for debugging.
    
    **Admin only endpoint**
    
    **Query Parameters:**
    - **category**: Optional error category filter
    - **limit**: Maximum number of errors (default: 50, max: 200)
    
    **Returns:**
    - List of recent errors with full details
    
    **Example Request:**
    ```
    GET /api/v1/monitoring/errors/recent?category=validation&limit=20
    ```
    
    **Example Response:**
    ```json
    [
      {
        "timestamp": "2026-03-08T14:30:00",
        "category": "validation",
        "severity": "low",
        "error_type": "value_error",
        "field": "purchase_price",
        "value": "-1000",
        "message": "purchase_price must be greater than 0",
        "user_id": 123,
        "property_id": "550e8400-e29b-41d4-a716-446655440000",
        "context": {}
      }
    ]
    ```
    """
    errors = ErrorTracker.get_recent_errors(
        category=category,
        limit=limit
    )
    
    return {
        "total": len(errors),
        "errors": errors
    }


@router.post("/errors/clear-old")
def clear_old_errors(
    days: int = Query(7, description="Clear errors older than this many days", ge=1, le=90),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Clear old errors from tracking system.
    
    **Admin only endpoint**
    
    **Query Parameters:**
    - **days**: Clear errors older than this many days (default: 7, max: 90)
    
    **Returns:**
    - Number of errors cleared
    
    **Example Request:**
    ```
    POST /api/v1/monitoring/errors/clear-old?days=30
    ```
    
    **Example Response:**
    ```json
    {
      "cleared_count": 1523,
      "older_than_days": 30
    }
    ```
    """
    cleared_count = ErrorTracker.clear_old_errors(
        older_than=timedelta(days=days)
    )
    
    return {
        "cleared_count": cleared_count,
        "older_than_days": days
    }


@router.get("/errors/health")
def get_error_health_status(
    current_user: User = Depends(get_current_admin_user)
):
    """
    Get overall error health status.
    
    **Admin only endpoint**
    
    Checks error rates and returns health status with alerts.
    
    **Returns:**
    - Overall health status (healthy, warning, critical)
    - Active alerts
    - Error rate statistics
    
    **Example Response:**
    ```json
    {
      "status": "warning",
      "alerts": [
        {
          "type": "high_depreciation_failure_rate",
          "severity": "high",
          "message": "High depreciation failure rate - 5 failures in last hour",
          "count": 5,
          "threshold": 3
        }
      ],
      "error_rates": {
        "validation_errors_per_hour": 2.5,
        "depreciation_failures_per_hour": 5.0,
        "critical_errors_per_hour": 0.0
      }
    }
    ```
    """
    # Get statistics for last hour
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    stats = ErrorTracker.get_error_statistics(since=one_hour_ago)
    
    # Determine health status
    alerts = []
    status_level = "healthy"
    
    # Check validation error rate
    validation_count = stats["by_category"].get(ErrorCategory.VALIDATION, 0)
    if validation_count >= ErrorTracker.VALIDATION_ERROR_THRESHOLD:
        alerts.append({
            "type": "high_validation_error_rate",
            "severity": "medium",
            "message": f"High validation error rate - {validation_count} errors in last hour",
            "count": validation_count,
            "threshold": ErrorTracker.VALIDATION_ERROR_THRESHOLD
        })
        status_level = "warning"
    
    # Check depreciation failure rate
    depreciation_count = stats["by_category"].get(ErrorCategory.DEPRECIATION_GENERATION, 0)
    if depreciation_count >= ErrorTracker.DEPRECIATION_FAILURE_THRESHOLD:
        alerts.append({
            "type": "high_depreciation_failure_rate",
            "severity": "high",
            "message": f"High depreciation failure rate - {depreciation_count} failures in last hour",
            "count": depreciation_count,
            "threshold": ErrorTracker.DEPRECIATION_FAILURE_THRESHOLD
        })
        status_level = "critical"
    
    # Check critical errors
    critical_count = stats["by_severity"].get(ErrorSeverity.CRITICAL, 0)
    if critical_count > 0:
        alerts.append({
            "type": "critical_errors",
            "severity": "critical",
            "message": f"Critical errors detected - {critical_count} in last hour",
            "count": critical_count,
            "threshold": ErrorTracker.CRITICAL_ERROR_THRESHOLD
        })
        status_level = "critical"
    
    return {
        "status": status_level,
        "alerts": alerts,
        "error_rates": {
            "validation_errors_per_hour": validation_count,
            "depreciation_failures_per_hour": depreciation_count,
            "critical_errors_per_hour": critical_count
        },
        "total_errors_last_hour": stats["total_errors"]
    }
