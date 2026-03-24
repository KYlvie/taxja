"""Feature gate service for subscription-based access control.

v1 Credit migration: user-side feature access is now determined by credit
sufficiency (via CreditService.check_sufficient), with the old plan-hierarchy
mapping retained as a fallback during the transition period.

System-side processing gates (risk control, quality control) remain unchanged
and are NOT migrated to the credit layer.
"""
from typing import Optional
from enum import Enum
from sqlalchemy.orm import Session
import logging
import redis
import json

from app.models.subscription import Subscription, SubscriptionStatus
from app.models.plan import Plan, PlanType
from app.models.user import User
from app.core.config import settings


logger = logging.getLogger(__name__)


class Feature(str, Enum):
    """Feature enumeration for gated features"""
    # Free tier — basic functionality everyone gets
    BASIC_TAX_CALC = "basic_tax_calc"
    TRANSACTION_ENTRY = "transaction_entry"
    OCR_SCANNING = "ocr_scanning"        # Free users get limited OCR (quota-controlled)
    MULTI_LANGUAGE = "multi_language"     # Language selection is basic UX

    # Plus tier features
    UNLIMITED_TRANSACTIONS = "unlimited_transactions"
    FULL_TAX_CALC = "full_tax_calc"
    VAT_CALC = "vat_calc"
    SVS_CALC = "svs_calc"
    BANK_IMPORT = "bank_import"
    PROPERTY_MANAGEMENT = "property_management"
    RECURRING_SUGGESTIONS = "recurring_suggestions"

    # Pro tier features
    UNLIMITED_OCR = "unlimited_ocr"
    AI_ASSISTANT = "ai_assistant"
    E1_GENERATION = "e1_generation"
    ADVANCED_REPORTS = "advanced_reports"
    PRIORITY_SUPPORT = "priority_support"
    API_ACCESS = "api_access"


class FeatureGateService:
    """Service for feature-based access control with Redis caching.

    v1 Credit migration
    --------------------
    User-side entitlement is now determined by credit sufficiency:
    ``check_feature_access`` delegates to ``CreditService.check_sufficient``.

    The old ``_FEATURE_MIN_PLAN`` hierarchy is retained as a fallback for
    features that have no CreditCostConfig entry yet (transition period).

    System-side processing gates (risk, quality) are separate — see
    ``check_processing_gate``.
    """

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

    # ------------------------------------------------------------------
    # Feature → CreditCostConfig operation mapping
    # ------------------------------------------------------------------
    # Maps Feature enum values to the operation name used in CreditCostConfig.
    # Features not listed here have no credit cost and fall back to the old
    # plan-hierarchy check during the transition period.
    _FEATURE_CREDIT_OPERATION = {
        Feature.OCR_SCANNING: "ocr_scan",
        Feature.UNLIMITED_OCR: "ocr_scan",
        Feature.AI_ASSISTANT: "ai_conversation",
        Feature.TRANSACTION_ENTRY: "transaction_entry",
        Feature.UNLIMITED_TRANSACTIONS: "transaction_entry",
        Feature.BANK_IMPORT: "bank_import",
        Feature.E1_GENERATION: "e1_generation",
        Feature.BASIC_TAX_CALC: "tax_calc",
        Feature.FULL_TAX_CALC: "tax_calc",
        Feature.VAT_CALC: "tax_calc",
        Feature.SVS_CALC: "tax_calc",
    }

    # ------------------------------------------------------------------
    # Legacy plan-hierarchy mapping (fallback during transition)
    # ------------------------------------------------------------------
    _FEATURE_MIN_PLAN = {
        # Free tier — everyone gets these (quota-limited)
        Feature.BASIC_TAX_CALC: PlanType.FREE,
        Feature.TRANSACTION_ENTRY: PlanType.FREE,
        Feature.OCR_SCANNING: PlanType.FREE,      # 5 scans/month
        Feature.MULTI_LANGUAGE: PlanType.FREE,
        Feature.AI_ASSISTANT: PlanType.FREE,       # 10 conversations/month
        # Plus tier
        Feature.UNLIMITED_TRANSACTIONS: PlanType.PLUS,
        Feature.FULL_TAX_CALC: PlanType.PLUS,
        Feature.VAT_CALC: PlanType.PLUS,
        Feature.SVS_CALC: PlanType.PLUS,
        Feature.BANK_IMPORT: PlanType.PLUS,
        Feature.PROPERTY_MANAGEMENT: PlanType.PLUS,
        Feature.RECURRING_SUGGESTIONS: PlanType.PLUS,
        # Pro tier
        Feature.UNLIMITED_OCR: PlanType.PRO,
        Feature.E1_GENERATION: PlanType.PRO,
        Feature.ADVANCED_REPORTS: PlanType.PRO,
        Feature.PRIORITY_SUPPORT: PlanType.PRO,
        Feature.API_ACCESS: PlanType.PRO,
    }

    _PLAN_LEVEL = {
        PlanType.FREE: 0,
        PlanType.PLUS: 1,
        PlanType.PRO: 2,
    }

    def check_feature_access(self, user_id: int, feature: Feature) -> bool:
        """Check if user has access to a specific feature.

        v1 Credit migration: delegates to ``CreditService.check_sufficient``
        when the feature has a corresponding CreditCostConfig operation.
        Falls back to the legacy plan-hierarchy check when no credit
        operation mapping exists (transition period).

        Args:
            user_id: ID of the user
            feature: Feature to check access for

        Returns:
            True if user has access to feature, False otherwise
        """
        try:
            # Admin users have access to all features
            user = self.db.query(User).filter(User.id == user_id).first()
            if user and getattr(user, "is_admin", False):
                return True

            # --- Credit-based check (primary path) ---
            operation = self._FEATURE_CREDIT_OPERATION.get(feature)
            if operation is not None:
                from app.services.credit_service import CreditService

                credit_service = CreditService(self.db, self.redis_client)
                has_access = credit_service.check_sufficient(
                    user_id, operation, quantity=1, allow_overage=True
                )
                logger.debug(
                    "Feature access (credit): user=%s, feature=%s, "
                    "operation=%s, access=%s",
                    user_id, feature.value, operation, has_access,
                )
                return has_access

            # --- Fallback: legacy plan-hierarchy check ---
            return self._check_plan_hierarchy(user_id, feature)

        except Exception as e:
            logger.error(f"Error checking feature access for user {user_id}: {e}")
            # Fail open to Free tier features on error
            return feature in [
                Feature.BASIC_TAX_CALC,
                Feature.TRANSACTION_ENTRY,
                Feature.OCR_SCANNING,
            ]

    def check_processing_gate(self, user_id: int, gate: str) -> bool:
        """System-side processing gate (risk / quality control).

        This is NOT a billing check — it controls automation depth,
        risk gating, and manual review decisions.  Unaffected by the
        credit migration.

        Returns True if the processing gate allows the operation.
        Subclasses or future implementations can override with real logic.
        """
        # v1: always allow — real processing gates live in their
        # respective service modules (e.g. create_asset_auto checks).
        return True

    def _check_plan_hierarchy(self, user_id: int, feature: Feature) -> bool:
        """Legacy plan-hierarchy check (fallback during transition)."""
        plan = self.get_user_plan(user_id)

        if not plan:
            logger.warning(
                f"No plan found for user {user_id}, defaulting to Free tier"
            )
            plan = self._get_free_plan()

        user_level = self._PLAN_LEVEL.get(plan.plan_type, 0)
        required_plan = self._FEATURE_MIN_PLAN.get(feature, PlanType.PRO)
        required_level = self._PLAN_LEVEL.get(required_plan, 2)

        has_access = user_level >= required_level

        logger.debug(
            "Feature access (plan fallback): user=%s, feature=%s, "
            "plan=%s, required=%s, access=%s",
            user_id, feature.value, plan.plan_type.value,
            required_plan.value, has_access,
        )
        return has_access
    
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
        return self._FEATURE_MIN_PLAN.get(feature, PlanType.PRO)
    
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
                    Feature.OCR_SCANNING.value: True,
                    Feature.MULTI_LANGUAGE.value: True,
                },
                quotas={"transactions": 30, "ocr_scans": 3}
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
