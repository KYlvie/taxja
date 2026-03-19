"""Usage tracking API endpoints"""
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.usage_record import ResourceType
from app.schemas.subscription import UsageQuotaResponse
from app.services.usage_tracker_service import UsageTrackerService
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/summary", response_model=Dict[str, Any], deprecated=True)
def get_usage_summary(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get user's usage summary with quotas for all resources.
    
    Per Requirement 3.2: Provide usage summary.
    Per Requirement 3.6: Include quota warnings in response headers at 80% threshold.
    """
    usage_service = UsageTrackerService(db)
    
    try:
        response.headers["X-Usage-Compatibility"] = "read-only"
        summary = usage_service.get_usage_summary(current_user.id)
        
        # Check for quota warnings and add to response headers
        warnings = []
        for resource_type, usage_data in summary.items():
            if usage_data.get('is_warning'):
                warnings.append(
                    f"{resource_type}:{usage_data['current']}/{usage_data['limit']}"
                )
        
        if warnings:
            response.headers['X-Quota-Warning'] = '; '.join(warnings)
            logger.info(f"Quota warning for user {current_user.id}: {warnings}")
        
        return summary
        
    except Exception as e:
        logger.error(f"Error getting usage summary for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve usage summary"
        )


@router.get("/{resource_type}", response_model=UsageQuotaResponse, deprecated=True)
def get_resource_usage(
    resource_type: ResourceType,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get usage for a specific resource type.
    
    Per Requirement 3.3: Get specific resource usage.
    Per Requirement 3.6: Include quota warning in headers at 80% threshold.
    """
    usage_service = UsageTrackerService(db)
    
    try:
        response.headers["X-Usage-Compatibility"] = "read-only"
        usage_data = usage_service.get_current_usage(current_user.id, resource_type)
        
        # Add quota warning header if near limit
        if usage_data.get('is_warning'):
            response.headers['X-Quota-Warning'] = (
                f"{resource_type.value}:{usage_data['current']}/{usage_data['limit']}"
            )
            logger.info(
                f"Quota warning for user {current_user.id}: "
                f"{resource_type.value} at {usage_data['percentage']:.1f}%"
            )
        
        return UsageQuotaResponse(
            resource_type=usage_data['resource_type'],
            current_usage=usage_data['current_usage'],
            quota_limit=usage_data['quota_limit'],
            usage_percentage=usage_data['usage_percentage'],
            is_exceeded=usage_data['is_exceeded'],
            is_near_limit=usage_data['is_near_limit'],
            period_start=usage_data['period_start'],
            period_end=usage_data['period_end'],
        )
        
    except Exception as e:
        logger.error(
            f"Error getting usage for user {current_user.id}, "
            f"resource {resource_type.value}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve usage for {resource_type.value}"
        )
