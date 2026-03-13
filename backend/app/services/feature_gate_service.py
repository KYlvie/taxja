"""Feature gate service for subscription-based access control"""
from typing import Optional
from enum import Enum
from sqlalchemy.orm import Session
import logging
import redis
import json

from app.models.subscription import Subscription, SubscriptionStatus
from app.models.plan import Plan, PlanType
from app.core.config import settings


logger = logging.getLogger(__name__)


class Feature(str, Enum):
    """Feature enumeration for gated features"""
    # Basic features (Free tier)
    BASIC_TAX_CALC = "basic_tax_calc"
    TRANSACTION_ENTRY = "transaction_entry"
    
    # Plus tier features
    UNLIMITED_TRANSACTIONS = "unlimited_transactions"
    OCR_SCANNING = "ocr_scanning"
    FULL_TAX_CALC = "full_tax_calc"
    MULTI_LANGUAGE = "multi_language"
    VAT_CALC = "vat_calc"
    SVS_CALC = "svs_calc"
    
    # Pro tier features
    UNLIMITED_OCR = "unlimited_ocr"
    AI_ASSISTANT = "ai_assistant"
    E1_GENERATION = "e1_generation"
    ADVANCED_REPORTS = "advanced_reports"
    PRIORITY_SUPPORT = "priority_support"
    API_ACCESS = "api_access"


class FeatureGateService:
    """Service for feature-based access control with Redis caching"""
    
    CACHE_TTL = 300  # 5 minutes
    CACHE_KEY_PREFIX = "feature_gate:user:"
    
    def __init__(self, db: Session, redis_client: Optional[redis.Redis] = None):
        """
        Initialize feature gate service.
        
        Args:
            db: SQLAlchemy database session
            redis_client: Redis client for caching (optional)
        """
        self.db = db
        self.redis_client = redis_client
    
    def check_feature_access(self, user_id: int, feature: Feature) -> bool:
        """
        Check if user has access to a specific feature.
        
        Per Requirement 2.1: Feature access based on subscription plan.
        Per Requirement 2.5: Use Redis cache for performance.
        
        Args:
            user_id: ID of the user
            feature: Feature to check access for
            
        Returns:
            True if user has access to feature, False otherwise
        """
        try:
            # Get user's plan (with caching)
            plan = self.get_user_plan(user_id)
            
            if not plan:
                logger.warning(f"No plan found for user {user_id}, defaulting to Free tier")
                # Default to Free tier if no plan found
                plan = self._get_free_plan()
            
            # Check if plan has the feature
            has_access = plan.has_feature(feature.value)
            
            logger.debug(
                f"Feature access check: user={user_id}, feature={feature.value}, "
                f"plan={plan.plan_type.value}, access={has_access}"
            )
            
            return has_access
            
        except Exception as e:
            logger.error(f"Error checking feature access for user {user_id}: {e}")
            # Fail open to Free tier features on error
            return feature in [Feature.BASIC_TAX_CALC, Feature.TRANSACTION_ENTRY]
    
    def get_user_plan(self, user_id: int) -> Optional[Plan]:
        """
        Get user's current plan with Redis caching.
        
        Per Requirement 2.5: Cache plan data in Redis (TTL: 5 minutes).
        
        Args:
            user_id: ID of the user
            
        Returns:
            Plan instance if found, None otherwise
        """
        # Try to get from cache first
        if self.redis_client:
            cache_key = f"{self.CACHE_KEY_PREFIX}{user_id}"
            try:
                cached_data = self.redis_client.get(cache_key)
                if cached_data:
                    plan_data = json.loads(cached_data)
                    logger.debug(f"Cache hit for user {user_id} plan")
                    # Reconstruct plan from cached data
                    return self._plan_from_cache(plan_data)
            except Exception as e:
                logger.warning(f"Redis cache read error: {e}")
        
        # Cache miss or no Redis - query database
        subscription = self._get_active_subscription(user_id)
        
        if not subscription:
            logger.info(f"No active subscription for user {user_id}")
            plan = self._get_free_plan()
        else:
            plan = subscription.plan
        
        # Cache the result
        if self.redis_client and plan:
            self._cache_user_plan(user_id, plan)
        
        return plan
    
    def invalidate_user_plan_cache(self, user_id: int) -> None:
        """
        Invalidate cached plan data for a user.
        
        Call this when user's subscription changes.
        
        Args:
            user_id: ID of the user
        """
        if not self.redis_client:
            return
        
        cache_key = f"{self.CACHE_KEY_PREFIX}{user_id}"
        try:
            self.redis_client.delete(cache_key)
            logger.info(f"Invalidated plan cache for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to invalidate cache for user {user_id}: {e}")
    
    def get_required_plan_for_feature(self, feature: Feature) -> PlanType:
        """
        Get the minimum plan type required for a feature.
        
        Args:
            feature: Feature to check
            
        Returns:
            Minimum PlanType required for the feature
        """
        # Pro tier features
        pro_features = [
            Feature.UNLIMITED_OCR,
            Feature.AI_ASSISTANT,
            Feature.E1_GENERATION,
            Feature.ADVANCED_REPORTS,
            Feature.PRIORITY_SUPPORT,
            Feature.API_ACCESS,
        ]
        
        # Plus tier features
        plus_features = [
            Feature.UNLIMITED_TRANSACTIONS,
            Feature.OCR_SCANNING,
            Feature.FULL_TAX_CALC,
            Feature.MULTI_LANGUAGE,
            Feature.VAT_CALC,
            Feature.SVS_CALC,
        ]
        
        if feature in pro_features:
            return PlanType.PRO
        elif feature in plus_features:
            return PlanType.PLUS
        else:
            return PlanType.FREE
    
    def _get_active_subscription(self, user_id: int) -> Optional[Subscription]:
        """
        Get user's active subscription.
        
        Per Requirement 2.4: Treat expired subscriptions as Free tier.
        
        Args:
            user_id: ID of the user
            
        Returns:
            Active Subscription instance or None
        """
        subscription = (
            self.db.query(Subscription)
            .filter(Subscription.user_id == user_id)
            .first()
        )
        
        if not subscription:
            return None
        
        # Check if subscription can access features
        if not subscription.can_access_features():
            logger.info(
                f"User {user_id} subscription cannot access features: "
                f"status={subscription.status.value}"
            )
            return None
        
        # Check if subscription is expired
        if subscription.is_expired():
            logger.info(f"User {user_id} subscription has expired")
            return None
        
        return subscription
    
    def _get_free_plan(self) -> Plan:
        """
        Get the Free plan.
        
        Returns:
            Free Plan instance
        """
        plan = self.db.query(Plan).filter(Plan.plan_type == PlanType.FREE).first()
        
        if not plan:
            logger.error("Free plan not found in database!")
            # Create a minimal free plan as fallback
            plan = Plan(
                plan_type=PlanType.FREE,
                name="Free",
                monthly_price=0,
                yearly_price=0,
                features={
                    Feature.BASIC_TAX_CALC.value: True,
                    Feature.TRANSACTION_ENTRY.value: True,
                },
                quotas={"transactions": 50}
            )
        
        return plan
    
    def _cache_user_plan(self, user_id: int, plan: Plan) -> None:
        """
        Cache user's plan data in Redis.
        
        Args:
            user_id: ID of the user
            plan: Plan to cache
        """
        if not self.redis_client:
            return
        
        cache_key = f"{self.CACHE_KEY_PREFIX}{user_id}"
        plan_data = {
            "id": plan.id,
            "plan_type": plan.plan_type.value,
            "name": plan.name,
            "features": plan.features,
            "quotas": plan.quotas,
        }
        
        try:
            self.redis_client.setex(
                cache_key,
                self.CACHE_TTL,
                json.dumps(plan_data)
            )
            logger.debug(f"Cached plan for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to cache plan for user {user_id}: {e}")
    
    def _plan_from_cache(self, plan_data: dict) -> Plan:
        """
        Reconstruct Plan object from cached data.
        
        Args:
            plan_data: Cached plan data
            
        Returns:
            Plan instance
        """
        plan = Plan(
            id=plan_data["id"],
            plan_type=PlanType(plan_data["plan_type"]),
            name=plan_data["name"],
            monthly_price=0,  # Not needed for feature checks
            yearly_price=0,   # Not needed for feature checks
            features=plan_data["features"],
            quotas=plan_data["quotas"],
        )
        return plan
