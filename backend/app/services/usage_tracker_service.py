"""Usage tracker service for monitoring resource quotas"""
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_
import logging
import redis

from app.models.usage_record import UsageRecord, ResourceType
from app.models.subscription import Subscription
from app.services.plan_service import PlanService


logger = logging.getLogger(__name__)


class QuotaExceededError(Exception):
    """Raised when user exceeds their quota limit"""
    def __init__(self, resource_type: str, current: int, limit: int, reset_date: datetime):
        self.resource_type = resource_type
        self.current = current
        self.limit = limit
        self.reset_date = reset_date
        super().__init__(
            f"Quota exceeded for {resource_type}: {current}/{limit}. "
            f"Resets on {reset_date.strftime('%Y-%m-%d')}"
        )


class UsageTrackerService:
    """Service for tracking and enforcing resource usage quotas"""
    
    CACHE_KEY_PREFIX = "usage:"
    WARNING_THRESHOLD = 80.0  # 80% usage triggers warning
    
    def __init__(self, db: Session, redis_client: Optional[redis.Redis] = None):
        """
        Initialize usage tracker service.
        
        Args:
            db: SQLAlchemy database session
            redis_client: Redis client for caching (optional)
        """
        self.db = db
        self.redis_client = redis_client
        self.plan_service = PlanService(db)
    
    def increment_usage(
        self,
        user_id: int,
        resource_type: ResourceType,
        amount: int = 1
    ) -> Dict[str, any]:
        """
        Increment usage count for a resource.
        
        Per Requirement 3.1: Track usage with atomic operations.
        Per Requirement 3.2: Return quota exceeded error with details.
        
        Args:
            user_id: ID of the user
            resource_type: Type of resource being used
            amount: Amount to increment by (default: 1)
            
        Returns:
            Dictionary with usage details
            
        Raises:
            QuotaExceededError: If quota limit is exceeded
        """
        # Get or create usage record for current period
        usage_record = self._get_or_create_usage_record(user_id, resource_type)
        
        # Get quota limit from user's plan
        subscription = self._get_user_subscription(user_id)
        plan = subscription.plan if subscription else self.plan_service.get_plan_by_type("free")
        quota_limit = plan.get_quota(resource_type.value)
        
        # Check if increment would exceed quota
        new_count = usage_record.count + amount
        if quota_limit != -1 and new_count > quota_limit:  # -1 = unlimited
            raise QuotaExceededError(
                resource_type=resource_type.value,
                current=usage_record.count,
                limit=quota_limit,
                reset_date=usage_record.period_end
            )
        
        # Increment usage (atomic in database)
        usage_record.increment(amount)
        
        # Update Redis cache if available
        if self.redis_client:
            self._update_cache(user_id, resource_type, new_count)
        
        try:
            self.db.commit()
            self.db.refresh(usage_record)
            
            logger.info(
                f"Incremented usage for user {user_id}: "
                f"{resource_type.value} = {new_count}/{quota_limit}"
            )
            
            return {
                "resource_type": resource_type.value,
                "current": new_count,
                "limit": quota_limit,
                "percentage": usage_record.get_usage_percentage(quota_limit),
                "is_warning": usage_record.is_near_quota_limit(quota_limit, self.WARNING_THRESHOLD),
                "reset_date": usage_record.period_end.isoformat()
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to increment usage: {e}")
            raise
    
    def get_current_usage(
        self,
        user_id: int,
        resource_type: ResourceType
    ) -> Dict[str, any]:
        """
        Get current usage for a specific resource type.
        
        Args:
            user_id: ID of the user
            resource_type: Type of resource
            
        Returns:
            Dictionary with usage details
        """
        usage_record = self._get_or_create_usage_record(user_id, resource_type)
        
        # Get quota limit
        subscription = self._get_user_subscription(user_id)
        plan = subscription.plan if subscription else self.plan_service.get_plan_by_type("free")
        quota_limit = plan.get_quota(resource_type.value)
        
        return {
            "resource_type": resource_type.value,
            "current": usage_record.count,
            "limit": quota_limit,
            "percentage": usage_record.get_usage_percentage(quota_limit),
            "is_warning": usage_record.is_near_quota_limit(quota_limit, self.WARNING_THRESHOLD),
            "is_exceeded": usage_record.is_quota_exceeded(quota_limit),
            "reset_date": usage_record.period_end.isoformat()
        }
    
    def check_quota_limit(
        self,
        user_id: int,
        resource_type: ResourceType,
        amount: int = 1
    ) -> bool:
        """
        Check if user can use a resource without exceeding quota.
        
        Per Requirement 3.3: Check quota before allowing operation.
        
        Args:
            user_id: ID of the user
            resource_type: Type of resource
            amount: Amount to check (default: 1)
            
        Returns:
            True if within quota, False if would exceed
        """
        usage_record = self._get_or_create_usage_record(user_id, resource_type)
        
        # Get quota limit
        subscription = self._get_user_subscription(user_id)
        plan = subscription.plan if subscription else self.plan_service.get_plan_by_type("free")
        quota_limit = plan.get_quota(resource_type.value)
        
        # Unlimited quota
        if quota_limit == -1:
            return True
        
        # Check if increment would exceed
        return (usage_record.count + amount) <= quota_limit
    
    def reset_usage_for_period(
        self,
        user_id: int,
        resource_type: ResourceType,
        new_period_start: datetime,
        new_period_end: datetime
    ) -> None:
        """
        Reset usage count for a new billing period.
        
        Per Requirement 3.4: Reset usage at billing period start.
        
        Args:
            user_id: ID of the user
            resource_type: Type of resource
            new_period_start: Start of new period
            new_period_end: End of new period
        """
        usage_record = self._get_usage_record(user_id, resource_type)
        
        if usage_record:
            usage_record.reset(new_period_start, new_period_end)
            
            # Clear cache
            if self.redis_client:
                self._clear_cache(user_id, resource_type)
            
            try:
                self.db.commit()
                logger.info(
                    f"Reset usage for user {user_id}: {resource_type.value} "
                    f"for period {new_period_start} to {new_period_end}"
                )
            except Exception as e:
                self.db.rollback()
                logger.error(f"Failed to reset usage: {e}")
                raise
    
    def get_usage_summary(self, user_id: int) -> Dict[str, any]:
        """
        Get usage summary for all resource types.
        
        Per Requirement 3.6: Provide usage summary with quota details.
        
        Args:
            user_id: ID of the user
            
        Returns:
            Dictionary with usage summary for all resources
        """
        summary = {}
        
        for resource_type in ResourceType:
            usage_data = self.get_current_usage(user_id, resource_type)
            summary[resource_type.value] = usage_data
        
        return summary
    
    def apply_new_quota_limits(self, user_id: int) -> None:
        """
        Apply new quota limits immediately after plan upgrade.
        
        Per Requirement 3.5: Apply new limits immediately on upgrade.
        
        Args:
            user_id: ID of the user
        """
        # Clear all cached usage data to force refresh with new limits
        if self.redis_client:
            for resource_type in ResourceType:
                self._clear_cache(user_id, resource_type)
        
        logger.info(f"Applied new quota limits for user {user_id}")
    
    def _get_usage_record(
        self,
        user_id: int,
        resource_type: ResourceType
    ) -> Optional[UsageRecord]:
        """Get existing usage record for current period"""
        now = datetime.utcnow()
        
        return (
            self.db.query(UsageRecord)
            .filter(
                and_(
                    UsageRecord.user_id == user_id,
                    UsageRecord.resource_type == resource_type,
                    UsageRecord.period_start <= now,
                    UsageRecord.period_end >= now
                )
            )
            .first()
        )
    
    def _get_or_create_usage_record(
        self,
        user_id: int,
        resource_type: ResourceType
    ) -> UsageRecord:
        """Get or create usage record for current period"""
        usage_record = self._get_usage_record(user_id, resource_type)
        
        if not usage_record:
            # Create new record for current period
            subscription = self._get_user_subscription(user_id)
            
            if subscription and subscription.current_period_start and subscription.current_period_end:
                period_start = subscription.current_period_start
                period_end = subscription.current_period_end
            else:
                # Default to monthly period for free users
                period_start = datetime.utcnow()
                period_end = period_start + timedelta(days=30)
            
            usage_record = UsageRecord(
                user_id=user_id,
                resource_type=resource_type,
                count=0,
                period_start=period_start,
                period_end=period_end
            )
            
            self.db.add(usage_record)
            self.db.flush()
            
            logger.info(
                f"Created usage record for user {user_id}: {resource_type.value}"
            )
        
        return usage_record
    
    def _get_user_subscription(self, user_id: int) -> Optional[Subscription]:
        """Get user's current subscription"""
        return (
            self.db.query(Subscription)
            .filter(Subscription.user_id == user_id)
            .first()
        )
    
    def _update_cache(
        self,
        user_id: int,
        resource_type: ResourceType,
        count: int
    ) -> None:
        """Update usage count in Redis cache"""
        if not self.redis_client:
            return
        
        cache_key = f"{self.CACHE_KEY_PREFIX}{user_id}:{resource_type.value}"
        try:
            self.redis_client.set(cache_key, count, ex=300)  # 5 minute TTL
        except Exception as e:
            logger.warning(f"Failed to update cache: {e}")
    
    def _clear_cache(self, user_id: int, resource_type: ResourceType) -> None:
        """Clear usage cache for a resource"""
        if not self.redis_client:
            return
        
        cache_key = f"{self.CACHE_KEY_PREFIX}{user_id}:{resource_type.value}"
        try:
            self.redis_client.delete(cache_key)
        except Exception as e:
            logger.warning(f"Failed to clear cache: {e}")
