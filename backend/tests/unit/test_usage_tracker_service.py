"""Unit tests for UsageTrackerService"""
import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime, timedelta

from app.services.usage_tracker_service import UsageTrackerService, QuotaExceededError
from app.models.usage_record import UsageRecord, ResourceType
from app.models.subscription import Subscription
from app.models.plan import Plan, PlanType


class TestUsageTrackerService:
    """Test UsageTrackerService methods"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.mock_db = Mock()
        self.mock_redis = Mock()
        self.service = UsageTrackerService(self.mock_db, self.mock_redis)
    
    def test_increment_usage_success(self):
        """Test increment_usage successfully increments count"""
        now = datetime.utcnow()
        mock_usage = UsageRecord(
            id=1,
            user_id=1,
            resource_type=ResourceType.TRANSACTIONS,
            count=10,
            period_start=now,
            period_end=now + timedelta(days=30)
        )
        mock_plan = Plan(
            id=1,
            plan_type=PlanType.FREE,
            name="Free",
            monthly_price=0,
            yearly_price=0,
            features={},
            quotas={"transactions": 50}
        )
        mock_subscription = Subscription(id=1, user_id=1, plan_id=1)
        mock_subscription.plan = mock_plan
        
        self.mock_db.query().filter().first.side_effect = [mock_usage, mock_subscription]
        
        result = self.service.increment_usage(1, ResourceType.TRANSACTIONS)
        
        assert result["current"] == 11
        assert result["limit"] == 50
        self.mock_db.commit.assert_called_once()
    
    def test_increment_usage_quota_exceeded(self):
        """Test increment_usage raises QuotaExceededError when limit reached"""
        now = datetime.utcnow()
        mock_usage = UsageRecord(
            id=1,
            user_id=1,
            resource_type=ResourceType.TRANSACTIONS,
            count=50,
            period_start=now,
            period_end=now + timedelta(days=30)
        )
        mock_plan = Plan(
            id=1,
            plan_type=PlanType.FREE,
            name="Free",
            monthly_price=0,
            yearly_price=0,
            features={},
            quotas={"transactions": 50}
        )
        mock_subscription = Subscription(id=1, user_id=1, plan_id=1)
        mock_subscription.plan = mock_plan
        
        self.mock_db.query().filter().first.side_effect = [mock_usage, mock_subscription]
        
        with pytest.raises(QuotaExceededError) as exc_info:
            self.service.increment_usage(1, ResourceType.TRANSACTIONS)
        
        assert exc_info.value.resource_type == "transactions"
        assert exc_info.value.current == 50
        assert exc_info.value.limit == 50
    
    def test_increment_usage_unlimited_quota(self):
        """Test increment_usage works with unlimited quota"""
        now = datetime.utcnow()
        mock_usage = UsageRecord(
            id=1,
            user_id=1,
            resource_type=ResourceType.TRANSACTIONS,
            count=1000,
            period_start=now,
            period_end=now + timedelta(days=30)
        )
        mock_plan = Plan(
            id=2,
            plan_type=PlanType.PRO,
            name="Pro",
            monthly_price=9.90,
            yearly_price=99.00,
            features={},
            quotas={"transactions": -1}  # Unlimited
        )
        mock_subscription = Subscription(id=1, user_id=1, plan_id=2)
        mock_subscription.plan = mock_plan
        
        self.mock_db.query().filter().first.side_effect = [mock_usage, mock_subscription]
        
        result = self.service.increment_usage(1, ResourceType.TRANSACTIONS)
        
        assert result["current"] == 1001
        assert result["limit"] == -1
        self.mock_db.commit.assert_called_once()
    
    def test_get_current_usage(self):
        """Test get_current_usage returns usage details"""
        now = datetime.utcnow()
        mock_usage = UsageRecord(
            id=1,
            user_id=1,
            resource_type=ResourceType.OCR_SCANS,
            count=15,
            period_start=now,
            period_end=now + timedelta(days=30)
        )
        mock_plan = Plan(
            id=2,
            plan_type=PlanType.PLUS,
            name="Plus",
            monthly_price=4.90,
            yearly_price=49.00,
            features={},
            quotas={"ocr_scans": 20}
        )
        mock_subscription = Subscription(id=1, user_id=1, plan_id=2)
        mock_subscription.plan = mock_plan
        
        self.mock_db.query().filter().first.side_effect = [mock_usage, mock_subscription]
        
        result = self.service.get_current_usage(1, ResourceType.OCR_SCANS)
        
        assert result["current"] == 15
        assert result["limit"] == 20
        assert result["percentage"] == 75.0
        assert result["is_warning"] is False  # Below 80%
    
    def test_get_current_usage_warning_threshold(self):
        """Test get_current_usage shows warning at 80% threshold"""
        now = datetime.utcnow()
        mock_usage = UsageRecord(
            id=1,
            user_id=1,
            resource_type=ResourceType.OCR_SCANS,
            count=16,
            period_start=now,
            period_end=now + timedelta(days=30)
        )
        mock_plan = Plan(
            id=2,
            plan_type=PlanType.PLUS,
            name="Plus",
            monthly_price=4.90,
            yearly_price=49.00,
            features={},
            quotas={"ocr_scans": 20}
        )
        mock_subscription = Subscription(id=1, user_id=1, plan_id=2)
        mock_subscription.plan = mock_plan
        
        self.mock_db.query().filter().first.side_effect = [mock_usage, mock_subscription]
        
        result = self.service.get_current_usage(1, ResourceType.OCR_SCANS)
        
        assert result["is_warning"] is True  # At 80%
    
    def test_check_quota_limit_within_quota(self):
        """Test check_quota_limit returns True when within quota"""
        now = datetime.utcnow()
        mock_usage = UsageRecord(
            id=1,
            user_id=1,
            resource_type=ResourceType.TRANSACTIONS,
            count=30,
            period_start=now,
            period_end=now + timedelta(days=30)
        )
        mock_plan = Plan(
            id=1,
            plan_type=PlanType.FREE,
            name="Free",
            monthly_price=0,
            yearly_price=0,
            features={},
            quotas={"transactions": 50}
        )
        mock_subscription = Subscription(id=1, user_id=1, plan_id=1)
        mock_subscription.plan = mock_plan
        
        self.mock_db.query().filter().first.side_effect = [mock_usage, mock_subscription]
        
        result = self.service.check_quota_limit(1, ResourceType.TRANSACTIONS, amount=10)
        
        assert result is True
    
    def test_check_quota_limit_would_exceed(self):
        """Test check_quota_limit returns False when would exceed"""
        now = datetime.utcnow()
        mock_usage = UsageRecord(
            id=1,
            user_id=1,
            resource_type=ResourceType.TRANSACTIONS,
            count=45,
            period_start=now,
            period_end=now + timedelta(days=30)
        )
        mock_plan = Plan(
            id=1,
            plan_type=PlanType.FREE,
            name="Free",
            monthly_price=0,
            yearly_price=0,
            features={},
            quotas={"transactions": 50}
        )
        mock_subscription = Subscription(id=1, user_id=1, plan_id=1)
        mock_subscription.plan = mock_plan
        
        self.mock_db.query().filter().first.side_effect = [mock_usage, mock_subscription]
        
        result = self.service.check_quota_limit(1, ResourceType.TRANSACTIONS, amount=10)
        
        assert result is False
    
    def test_check_quota_limit_unlimited(self):
        """Test check_quota_limit returns True for unlimited quota"""
        now = datetime.utcnow()
        mock_usage = UsageRecord(
            id=1,
            user_id=1,
            resource_type=ResourceType.TRANSACTIONS,
            count=1000,
            period_start=now,
            period_end=now + timedelta(days=30)
        )
        mock_plan = Plan(
            id=2,
            plan_type=PlanType.PRO,
            name="Pro",
            monthly_price=9.90,
            yearly_price=99.00,
            features={},
            quotas={"transactions": -1}
        )
        mock_subscription = Subscription(id=1, user_id=1, plan_id=2)
        mock_subscription.plan = mock_plan
        
        self.mock_db.query().filter().first.side_effect = [mock_usage, mock_subscription]
        
        result = self.service.check_quota_limit(1, ResourceType.TRANSACTIONS, amount=1000)
        
        assert result is True
    
    def test_reset_usage_for_period(self):
        """Test reset_usage_for_period resets count"""
        now = datetime.utcnow()
        new_start = now
        new_end = now + timedelta(days=30)
        
        mock_usage = UsageRecord(
            id=1,
            user_id=1,
            resource_type=ResourceType.TRANSACTIONS,
            count=50,
            period_start=now - timedelta(days=30),
            period_end=now
        )
        
        self.mock_db.query().filter().first.return_value = mock_usage
        
        self.service.reset_usage_for_period(1, ResourceType.TRANSACTIONS, new_start, new_end)
        
        assert mock_usage.count == 0
        assert mock_usage.period_start == new_start
        assert mock_usage.period_end == new_end
        self.mock_db.commit.assert_called_once()
    
    def test_get_usage_summary(self):
        """Test get_usage_summary returns all resource types"""
        now = datetime.utcnow()
        
        # Mock usage records for all resource types
        def mock_query_side_effect(*args):
            resource_type = args[0] if args else ResourceType.TRANSACTIONS
            return UsageRecord(
                id=1,
                user_id=1,
                resource_type=resource_type,
                count=10,
                period_start=now,
                period_end=now + timedelta(days=30)
            )
        
        mock_plan = Plan(
            id=1,
            plan_type=PlanType.FREE,
            name="Free",
            monthly_price=0,
            yearly_price=0,
            features={},
            quotas={"transactions": 50, "ocr_scans": 0, "ai_conversations": 0}
        )
        mock_subscription = Subscription(id=1, user_id=1, plan_id=1)
        mock_subscription.plan = mock_plan
        
        # Setup complex mock behavior
        self.mock_db.query().filter().first.side_effect = [
            mock_query_side_effect(ResourceType.TRANSACTIONS), mock_subscription,
            mock_query_side_effect(ResourceType.OCR_SCANS), mock_subscription,
            mock_query_side_effect(ResourceType.AI_CONVERSATIONS), mock_subscription
        ]
        
        result = self.service.get_usage_summary(1)
        
        assert "transactions" in result
        assert "ocr_scans" in result
        assert "ai_conversations" in result
    
    def test_apply_new_quota_limits(self):
        """Test apply_new_quota_limits clears cache"""
        self.service.apply_new_quota_limits(1)
        
        # Should clear cache for all resource types
        assert self.mock_redis.delete.call_count == len(ResourceType)
