"""Unit tests for FeatureGateService"""
import pytest
from unittest.mock import Mock, MagicMock
import json

from app.services.feature_gate_service import FeatureGateService, Feature
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.plan import Plan, PlanType


class TestFeatureGateService:
    """Test FeatureGateService methods"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.mock_db = Mock()
        self.mock_redis = Mock()
        self.service = FeatureGateService(self.mock_db, self.mock_redis)
    
    def test_check_feature_access_with_feature(self):
        """Test check_feature_access returns True when user has feature"""
        mock_plan = Plan(
            id=2,
            plan_type=PlanType.PRO,
            name="Pro",
            monthly_price=9.90,
            yearly_price=99.00,
            features={Feature.AI_ASSISTANT.value: True},
            quotas={}
        )
        mock_subscription = Subscription(
            id=1,
            user_id=1,
            plan_id=2,
            status=SubscriptionStatus.ACTIVE
        )
        mock_subscription.plan = mock_plan
        
        # Mock Redis cache miss
        self.mock_redis.get.return_value = None
        self.mock_db.query().filter().first.return_value = mock_subscription
        
        result = self.service.check_feature_access(1, Feature.AI_ASSISTANT)
        
        assert result is True
    
    def test_check_feature_access_without_feature(self):
        """Test check_feature_access returns False when user doesn't have feature"""
        mock_plan = Plan(
            id=1,
            plan_type=PlanType.FREE,
            name="Free",
            monthly_price=0,
            yearly_price=0,
            features={Feature.BASIC_TAX_CALC.value: True},
            quotas={}
        )
        mock_subscription = Subscription(
            id=1,
            user_id=1,
            plan_id=1,
            status=SubscriptionStatus.ACTIVE
        )
        mock_subscription.plan = mock_plan
        
        self.mock_redis.get.return_value = None
        self.mock_db.query().filter().first.return_value = mock_subscription
        
        result = self.service.check_feature_access(1, Feature.AI_ASSISTANT)
        
        assert result is False
    
    def test_get_user_plan_from_cache(self):
        """Test get_user_plan returns plan from Redis cache"""
        cached_data = json.dumps({
            "id": 2,
            "plan_type": "pro",
            "name": "Pro",
            "features": {Feature.AI_ASSISTANT.value: True},
            "quotas": {"transactions": -1}
        })
        self.mock_redis.get.return_value = cached_data
        
        result = self.service.get_user_plan(1)
        
        assert result.plan_type == PlanType.PRO
        assert result.features[Feature.AI_ASSISTANT.value] is True
        # Should not query database
        self.mock_db.query.assert_not_called()
    
    def test_get_user_plan_from_database(self):
        """Test get_user_plan queries database on cache miss"""
        mock_plan = Plan(
            id=1,
            plan_type=PlanType.PLUS,
            name="Plus",
            monthly_price=4.90,
            yearly_price=49.00,
            features={Feature.OCR_SCANNING.value: True},
            quotas={}
        )
        mock_subscription = Subscription(
            id=1,
            user_id=1,
            plan_id=1,
            status=SubscriptionStatus.ACTIVE
        )
        mock_subscription.plan = mock_plan
        
        self.mock_redis.get.return_value = None
        self.mock_db.query().filter().first.return_value = mock_subscription
        
        result = self.service.get_user_plan(1)
        
        assert result == mock_plan
        # Should cache the result
        self.mock_redis.setex.assert_called_once()
    
    def test_get_user_plan_no_subscription(self):
        """Test get_user_plan returns Free plan when no subscription"""
        mock_free_plan = Plan(
            id=1,
            plan_type=PlanType.FREE,
            name="Free",
            monthly_price=0,
            yearly_price=0,
            features={},
            quotas={}
        )
        
        self.mock_redis.get.return_value = None
        self.mock_db.query().filter().first.side_effect = [None, mock_free_plan]
        
        result = self.service.get_user_plan(1)
        
        assert result.plan_type == PlanType.FREE
    
    def test_invalidate_user_plan_cache(self):
        """Test invalidate_user_plan_cache clears Redis cache"""
        self.service.invalidate_user_plan_cache(1)
        
        expected_key = f"{self.service.CACHE_KEY_PREFIX}1"
        self.mock_redis.delete.assert_called_once_with(expected_key)
    
    def test_get_required_plan_for_feature_pro(self):
        """Test get_required_plan_for_feature returns PRO for Pro features"""
        result = self.service.get_required_plan_for_feature(Feature.AI_ASSISTANT)
        assert result == PlanType.PRO
        
        result = self.service.get_required_plan_for_feature(Feature.E1_GENERATION)
        assert result == PlanType.PRO
    
    def test_get_required_plan_for_feature_plus(self):
        """Test get_required_plan_for_feature returns PLUS for Plus features"""
        result = self.service.get_required_plan_for_feature(Feature.OCR_SCANNING)
        assert result == PlanType.PLUS
        
        result = self.service.get_required_plan_for_feature(Feature.FULL_TAX_CALC)
        assert result == PlanType.PLUS
    
    def test_get_required_plan_for_feature_free(self):
        """Test get_required_plan_for_feature returns FREE for basic features"""
        result = self.service.get_required_plan_for_feature(Feature.BASIC_TAX_CALC)
        assert result == PlanType.FREE
        
        result = self.service.get_required_plan_for_feature(Feature.TRANSACTION_ENTRY)
        assert result == PlanType.FREE
    
    def test_check_feature_access_expired_subscription(self):
        """Test check_feature_access treats expired subscription as Free tier"""
        from datetime import datetime, timedelta
        
        mock_plan = Plan(
            id=2,
            plan_type=PlanType.PRO,
            name="Pro",
            monthly_price=9.90,
            yearly_price=99.00,
            features={Feature.AI_ASSISTANT.value: True},
            quotas={}
        )
        mock_subscription = Subscription(
            id=1,
            user_id=1,
            plan_id=2,
            status=SubscriptionStatus.ACTIVE,
            current_period_end=datetime.utcnow() - timedelta(days=1)
        )
        mock_subscription.plan = mock_plan
        
        mock_free_plan = Plan(
            id=1,
            plan_type=PlanType.FREE,
            name="Free",
            monthly_price=0,
            yearly_price=0,
            features={Feature.BASIC_TAX_CALC.value: True},
            quotas={}
        )
        
        self.mock_redis.get.return_value = None
        self.mock_db.query().filter().first.side_effect = [mock_subscription, mock_free_plan]
        
        # Should not have Pro feature
        result = self.service.check_feature_access(1, Feature.AI_ASSISTANT)
        assert result is False
        
        # Should have Free feature
        result = self.service.check_feature_access(1, Feature.BASIC_TAX_CALC)
        assert result is True
