"""
Property Error Tracking Integration

Integrates error tracking into property services without modifying core service logic.
Provides decorators and wrappers for automatic error tracking.
"""

from functools import wraps
from typing import Callable, Any
from uuid import UUID
import logging

from app.services.error_tracker import ErrorTracker, ErrorCategory

logger = logging.getLogger(__name__)


def track_property_errors(category: ErrorCategory):
    """
    Decorator to automatically track errors in property operations.
    
    Args:
        category: Error category for this operation
        
    Example:
        @track_property_errors(ErrorCategory.PROPERTY_CREATION)
        def create_property(self, user_id, property_data):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except ValueError as e:
                # Track validation errors
                user_id = kwargs.get('user_id') or (args[1] if len(args) > 1 else None)
                property_id = kwargs.get('property_id') or (args[1] if len(args) > 1 and isinstance(args[1], UUID) else None)
                
                ErrorTracker.track_validation_error(
                    error_type="value_error",
                    field=func.__name__,
                    value=str(kwargs) if kwargs else str(args),
                    message=str(e),
                    user_id=user_id,
                    property_id=property_id,
                    context={
                        "operation": func.__name__,
                        "category": category
                    }
                )
                raise
            except PermissionError as e:
                # Track permission errors
                user_id = kwargs.get('user_id') or (args[1] if len(args) > 1 else None)
                property_id = kwargs.get('property_id') or (args[1] if len(args) > 1 and isinstance(args[1], UUID) else None)
                
                ErrorTracker.track_critical_error(
                    category=ErrorCategory.PERMISSION,
                    error=e,
                    message=f"Permission denied in {func.__name__}",
                    user_id=user_id,
                    property_id=property_id,
                    context={"operation": func.__name__}
                )
                raise
            except Exception as e:
                # Track critical errors
                user_id = kwargs.get('user_id') or (args[1] if len(args) > 1 else None)
                property_id = kwargs.get('property_id') or (args[1] if len(args) > 1 and isinstance(args[1], UUID) else None)
                
                ErrorTracker.track_critical_error(
                    category=category,
                    error=e,
                    message=f"Unexpected error in {func.__name__}",
                    user_id=user_id,
                    property_id=property_id,
                    context={
                        "operation": func.__name__,
                        "args": str(args),
                        "kwargs": str(kwargs)
                    }
                )
                raise
        
        return wrapper
    return decorator


def track_depreciation_errors(func: Callable) -> Callable:
    """
    Decorator specifically for depreciation calculation errors.
    
    Example:
        @track_depreciation_errors
        def calculate_annual_depreciation(self, property, year):
            ...
    """
    @wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        property = kwargs.get('property') or (args[1] if len(args) > 1 else None)
        year = kwargs.get('year') or (args[2] if len(args) > 2 else None)
        
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # Track depreciation failure
            if property:
                ErrorTracker.track_depreciation_failure(
                    property_id=property.id if hasattr(property, 'id') else None,
                    year=year,
                    error=e,
                    user_id=property.user_id if hasattr(property, 'user_id') else None,
                    property_address=property.address if hasattr(property, 'address') else None,
                    context={
                        "operation": func.__name__,
                        "building_value": str(property.building_value) if hasattr(property, 'building_value') else None,
                        "depreciation_rate": str(property.depreciation_rate) if hasattr(property, 'depreciation_rate') else None
                    }
                )
            raise
    
    return wrapper


def track_backfill_errors(func: Callable) -> Callable:
    """
    Decorator specifically for backfill operation errors.
    
    Example:
        @track_backfill_errors
        def backfill_depreciation(self, property_id, user_id):
            ...
    """
    @wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        property_id = kwargs.get('property_id') or (args[1] if len(args) > 1 else None)
        user_id = kwargs.get('user_id') or (args[2] if len(args) > 2 else None)
        
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # Track backfill failure
            ErrorTracker.track_backfill_failure(
                property_id=property_id,
                error=e,
                user_id=user_id,
                context={
                    "operation": func.__name__,
                    "confirm": kwargs.get('confirm', False)
                }
            )
            raise
    
    return wrapper
