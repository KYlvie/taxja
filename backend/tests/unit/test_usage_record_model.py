"""Unit tests for UsageRecord model"""
import pytest
from datetime import datetime, timedelta
from app.models.usage_record import UsageRecord, ResourceType


class TestUsageRecordModel:
    """Test UsageRecord model methods"""
    
    def test_usage_record_creation(self):
        """Test creating a usage record"""
        now = datetime.utcnow()
        usage = UsageRecord(
            user_id=1,
            resource_type=ResourceType.TRANSACTIONS,
            count=10,
            period_start=now,
            period_end=now + timedelta(days=30)
        )
        
        assert usage.user_id == 1
        assert usage.resource_type == ResourceType.TRANSACTIONS
        assert usage.count == 10
    
    def test_increment_default(self):
        """Test increment with default amount (1)"""
        now = datetime.utcnow()
        usage = UsageRecord(
            user_id=1,
            resource_type=ResourceType.OCR_SCANS,
            count=5,
            period_start=now,
            period_end=now + timedelta(days=30)
        )
        
        new_count = usage.increment()
        assert new_count == 6
        assert usage.count == 6
    
    def test_increment_custom_amount(self):
        """Test increment with custom amount"""
        now = datetime.utcnow()
        usage = UsageRecord(
            user_id=1,
            resource_type=ResourceType.AI_CONVERSATIONS,
            count=10,
            period_start=now,
            period_end=now + timedelta(days=30)
        )
        
        new_count = usage.increment(5)
        assert new_count == 15
        assert usage.count == 15
    
    def test_reset(self):
        """Test reset for new period"""
        now = datetime.utcnow()
        old_start = now - timedelta(days=30)
        old_end = now
        
        usage = UsageRecord(
            user_id=1,
            resource_type=ResourceType.TRANSACTIONS,
            count=50,
            period_start=old_start,
            period_end=old_end
        )
        
        new_start = now
        new_end = now + timedelta(days=30)
        usage.reset(new_start, new_end)
        
        assert usage.count == 0
        assert usage.period_start == new_start
        assert usage.period_end == new_end
    
    def test_is_current_period_true(self):
        """Test is_current_period returns True for current period"""
        now = datetime.utcnow()
        usage = UsageRecord(
            user_id=1,
            resource_type=ResourceType.TRANSACTIONS,
            count=10,
            period_start=now - timedelta(days=15),
            period_end=now + timedelta(days=15)
        )
        
        assert usage.is_current_period() is True
    
    def test_is_current_period_false_past(self):
        """Test is_current_period returns False for past period"""
        now = datetime.utcnow()
        usage = UsageRecord(
            user_id=1,
            resource_type=ResourceType.TRANSACTIONS,
            count=10,
            period_start=now - timedelta(days=60),
            period_end=now - timedelta(days=30)
        )
        
        assert usage.is_current_period() is False
    
    def test_is_current_period_false_future(self):
        """Test is_current_period returns False for future period"""
        now = datetime.utcnow()
        usage = UsageRecord(
            user_id=1,
            resource_type=ResourceType.TRANSACTIONS,
            count=0,
            period_start=now + timedelta(days=30),
            period_end=now + timedelta(days=60)
        )
        
        assert usage.is_current_period() is False
    
    def test_get_usage_percentage_normal(self):
        """Test get_usage_percentage with normal quota"""
        now = datetime.utcnow()
        usage = UsageRecord(
            user_id=1,
            resource_type=ResourceType.TRANSACTIONS,
            count=25,
            period_start=now,
            period_end=now + timedelta(days=30)
        )
        
        percentage = usage.get_usage_percentage(50)
        assert percentage == 50.0
    
    def test_get_usage_percentage_unlimited(self):
        """Test get_usage_percentage with unlimited quota"""
        now = datetime.utcnow()
        usage = UsageRecord(
            user_id=1,
            resource_type=ResourceType.TRANSACTIONS,
            count=1000,
            period_start=now,
            period_end=now + timedelta(days=30)
        )
        
        percentage = usage.get_usage_percentage(-1)
        assert percentage == 0.0
    
    def test_get_usage_percentage_zero_quota(self):
        """Test get_usage_percentage with zero quota"""
        now = datetime.utcnow()
        usage = UsageRecord(
            user_id=1,
            resource_type=ResourceType.TRANSACTIONS,
            count=10,
            period_start=now,
            period_end=now + timedelta(days=30)
        )
        
        percentage = usage.get_usage_percentage(0)
        assert percentage == 0.0
    
    def test_is_quota_exceeded_true(self):
        """Test is_quota_exceeded returns True when quota exceeded"""
        now = datetime.utcnow()
        usage = UsageRecord(
            user_id=1,
            resource_type=ResourceType.OCR_SCANS,
            count=20,
            period_start=now,
            period_end=now + timedelta(days=30)
        )
        
        assert usage.is_quota_exceeded(20) is True
        assert usage.is_quota_exceeded(15) is True
    
    def test_is_quota_exceeded_false(self):
        """Test is_quota_exceeded returns False when quota not exceeded"""
        now = datetime.utcnow()
        usage = UsageRecord(
            user_id=1,
            resource_type=ResourceType.OCR_SCANS,
            count=15,
            period_start=now,
            period_end=now + timedelta(days=30)
        )
        
        assert usage.is_quota_exceeded(20) is False
    
    def test_is_quota_exceeded_unlimited(self):
        """Test is_quota_exceeded returns False for unlimited quota"""
        now = datetime.utcnow()
        usage = UsageRecord(
            user_id=1,
            resource_type=ResourceType.TRANSACTIONS,
            count=1000,
            period_start=now,
            period_end=now + timedelta(days=30)
        )
        
        assert usage.is_quota_exceeded(-1) is False
    
    def test_is_quota_exceeded_zero_quota(self):
        """Test is_quota_exceeded returns True for zero quota"""
        now = datetime.utcnow()
        usage = UsageRecord(
            user_id=1,
            resource_type=ResourceType.TRANSACTIONS,
            count=1,
            period_start=now,
            period_end=now + timedelta(days=30)
        )
        
        assert usage.is_quota_exceeded(0) is True
    
    def test_is_near_quota_limit_true(self):
        """Test is_near_quota_limit returns True at 80% threshold"""
        now = datetime.utcnow()
        usage = UsageRecord(
            user_id=1,
            resource_type=ResourceType.OCR_SCANS,
            count=16,
            period_start=now,
            period_end=now + timedelta(days=30)
        )
        
        # 16/20 = 80%
        assert usage.is_near_quota_limit(20) is True
        
        # 16/20 = 80%, threshold 70%
        assert usage.is_near_quota_limit(20, threshold=70.0) is True
    
    def test_is_near_quota_limit_false(self):
        """Test is_near_quota_limit returns False below threshold"""
        now = datetime.utcnow()
        usage = UsageRecord(
            user_id=1,
            resource_type=ResourceType.OCR_SCANS,
            count=15,
            period_start=now,
            period_end=now + timedelta(days=30)
        )
        
        # 15/20 = 75%, threshold 80%
        assert usage.is_near_quota_limit(20) is False
    
    def test_is_near_quota_limit_unlimited(self):
        """Test is_near_quota_limit returns False for unlimited quota"""
        now = datetime.utcnow()
        usage = UsageRecord(
            user_id=1,
            resource_type=ResourceType.TRANSACTIONS,
            count=1000,
            period_start=now,
            period_end=now + timedelta(days=30)
        )
        
        assert usage.is_near_quota_limit(-1) is False
    
    def test_resource_types(self):
        """Test all resource types"""
        now = datetime.utcnow()
        
        # Test TRANSACTIONS
        usage1 = UsageRecord(
            user_id=1,
            resource_type=ResourceType.TRANSACTIONS,
            count=0,
            period_start=now,
            period_end=now + timedelta(days=30)
        )
        assert usage1.resource_type == ResourceType.TRANSACTIONS
        
        # Test OCR_SCANS
        usage2 = UsageRecord(
            user_id=1,
            resource_type=ResourceType.OCR_SCANS,
            count=0,
            period_start=now,
            period_end=now + timedelta(days=30)
        )
        assert usage2.resource_type == ResourceType.OCR_SCANS
        
        # Test AI_CONVERSATIONS
        usage3 = UsageRecord(
            user_id=1,
            resource_type=ResourceType.AI_CONVERSATIONS,
            count=0,
            period_start=now,
            period_end=now + timedelta(days=30)
        )
        assert usage3.resource_type == ResourceType.AI_CONVERSATIONS
