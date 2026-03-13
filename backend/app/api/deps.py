"""
API Dependencies

Common dependencies for API endpoints including authentication and database sessions.
"""

from typing import Generator
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.core.config import settings
from app.models.user import User


security = HTTPBearer()


# Re-export get_db from app.db.base for backward compatibility
# (ai_assistant.py and other modules import from here)


def get_current_user(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    """Get current authenticated user"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        token = credentials.credentials
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception

    return user


def get_current_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current user and verify admin privileges"""
    if not getattr(current_user, "is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user


# Alias for backward compatibility
get_current_admin_user = get_current_admin


# Feature gate dependencies
from app.services.feature_gate_service import Feature, FeatureGateService
from app.services.usage_tracker_service import UsageTrackerService, QuotaExceededError
from app.models.usage_record import ResourceType
from app.models.plan import PlanType
import redis
from typing import Optional


def get_redis_client() -> Optional[redis.Redis]:
    """Get Redis client for caching"""
    try:
        redis_client = redis.Redis(
            host=getattr(settings, 'REDIS_HOST', 'localhost'),
            port=getattr(settings, 'REDIS_PORT', 6379),
            db=getattr(settings, 'REDIS_DB', 0),
            decode_responses=True
        )
        # Test connection
        redis_client.ping()
        return redis_client
    except Exception:
        # Redis not available, continue without caching
        return None


def require_feature(feature: Feature):
    """
    Dependency factory for feature-based access control.
    
    Per Requirement 2.1: Enforce feature access based on subscription.
    Per Requirement 2.2: Return 403 with upgrade prompt if access denied.
    
    Usage:
        @router.get("/endpoint", dependencies=[Depends(require_feature(Feature.AI_ASSISTANT))])
    
    Args:
        feature: Feature required for access
        
    Returns:
        Dependency function that checks feature access
    """
    def check_feature_access(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ) -> User:
        redis_client = get_redis_client()
        feature_gate = FeatureGateService(db, redis_client)
        
        has_access = feature_gate.check_feature_access(current_user.id, feature)
        
        if not has_access:
            required_plan = feature_gate.get_required_plan_for_feature(feature)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "feature_not_available",
                    "message": f"This feature requires {required_plan.value.title()} plan or higher",
                    "feature": feature.value,
                    "required_plan": required_plan.value,
                    "upgrade_url": "/pricing"
                }
            )
        
        return current_user
    
    return check_feature_access


def require_plan(min_plan: PlanType):
    """
    Dependency factory for plan-level access control.
    
    Per Requirement 2.3: Enforce plan-level restrictions.
    
    Usage:
        @router.get("/endpoint", dependencies=[Depends(require_plan(PlanType.PRO))])
    
    Args:
        min_plan: Minimum plan type required
        
    Returns:
        Dependency function that checks plan level
    """
    def check_plan_level(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ) -> User:
        redis_client = get_redis_client()
        feature_gate = FeatureGateService(db, redis_client)
        
        user_plan = feature_gate.get_user_plan(current_user.id)
        
        if not user_plan:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "plan_required",
                    "message": f"This endpoint requires {min_plan.value.title()} plan or higher",
                    "required_plan": min_plan.value,
                    "upgrade_url": "/pricing"
                }
            )
        
        # Check plan hierarchy: FREE < PLUS < PRO
        plan_hierarchy = {
            PlanType.FREE: 0,
            PlanType.PLUS: 1,
            PlanType.PRO: 2
        }
        
        user_level = plan_hierarchy.get(user_plan.plan_type, 0)
        required_level = plan_hierarchy.get(min_plan, 0)
        
        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "insufficient_plan",
                    "message": f"This endpoint requires {min_plan.value.title()} plan or higher",
                    "current_plan": user_plan.plan_type.value,
                    "required_plan": min_plan.value,
                    "upgrade_url": "/pricing"
                }
            )
        
        return current_user
    
    return check_plan_level


def check_quota(resource_type: ResourceType, amount: int = 1):
    """
    Dependency factory for quota checking before resource usage.
    
    Per Requirement 3.2: Check quota before allowing operation.
    Per Requirement 3.3: Return 429 with usage details if quota exceeded.
    
    Usage:
        @router.post("/endpoint", dependencies=[Depends(check_quota(ResourceType.OCR_SCANS))])
    
    Args:
        resource_type: Type of resource to check
        amount: Amount of resource to check (default: 1)
        
    Returns:
        Dependency function that checks quota
    """
    def verify_quota(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ) -> User:
        redis_client = get_redis_client()
        usage_tracker = UsageTrackerService(db, redis_client)
        
        # Check if user can use the resource
        can_use = usage_tracker.check_quota_limit(current_user.id, resource_type, amount)
        
        if not can_use:
            # Get current usage details
            usage_data = usage_tracker.get_current_usage(current_user.id, resource_type)
            
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "quota_exceeded",
                    "message": f"You have exceeded your {resource_type.value} quota",
                    "resource_type": resource_type.value,
                    "current": usage_data['current'],
                    "limit": usage_data['limit'],
                    "reset_date": usage_data['reset_date'],
                    "upgrade_url": "/pricing"
                }
            )
        
        return current_user
    
    return verify_quota
