"""Unit tests for TrialService"""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

from app.services.trial_service import TrialService
from app.models.user import User
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.plan import Plan, PlanType


class TestTrialService:
    """Test TrialService methods"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.mock_db = Mock()
        self.service = TrialService(self.mock_db)
    
    def test_activate_trial_success(self):
        """Test activate_trial creates 14-day Pro trial"""
        mock_user = User(id=1, email="test@example.com", trial_used=False)
        mock_pro_plan = Plan(id=3, plan_type=PlanType.PRO, name="Pro")
        
        self.mock_db.query().filter().first.side_effect = [mock_user, None, mock_pro_plan]
        
        with patch.object(self.service.subscription_service, 'create_subscription') as mock_create:
            mock_subscription = Subscription(
                id=1,
                user_id=1,
                plan_id=3,
                status=SubscriptionStatus.TRIALING
            )
            mock_create.return_value = mock_subscription
            
            with patch.object(self.service, '_send_trial_welcome_notification'):
                result = self.service.activate_trial(user_id=1)
        
        assert result.status == SubscriptionStatus.TRIALING
        assert mock_user.trial_used is True
        assert mock_user.trial_end_date is not None
        self.mock_db.commit.assert_called_once()
    
    def test_activate_trial_already_used(self):
        """Test activate_trial raises error when trial already used"""
        mock_user = User(id=1, email="test@example.com", trial_used=True)
        
        self.mock_db.query().filter().first.return_value = mock_user
        
        with pytest.raises(ValueError, match="already used their trial"):
            self.service.activate_trial(user_id=1)
    
    def test_activate_trial_user_not_found(self):
        """Test activate_trial raises error when user not found"""
        self.mock_db.query().filter().first.return_value = None
        
        with pytest.raises(ValueError, match="not found"):
            self.service.activate_trial(user_id=999)
    
    def test_activate_trial_existing_subscription(self):
        """Test activate_trial raises error when user has subscription"""
        mock_user = User(id=1, email="test@example.com", trial_used=False)
        mock_subscription = Subscription(id=1, user_id=1, plan_id=1)
        
        self.mock_db.query().filter().first.side_effect = [mock_user]
        
        with patch.object(self.service.subscription_service, 'get_user_subscription', return_value=mock_subscription):
            with pytest.raises(ValueError, match="already has an active subscription"):
                self.service.activate_trial(user_id=1)
    
    def test_check_trial_status_active_trial(self):
        """Test check_trial_status returns correct info for active trial"""
        now = datetime.utcnow()
        mock_user = User(id=1, email="test@example.com", trial_used=True)
        mock_subscription = Subscription(
            id=1,
            user_id=1,
            plan_id=3,
            status=SubscriptionStatus.TRIALING,
            current_period_end=now + timedelta(days=10)
        )
        
        self.mock_db.query().filter().first.return_value = mock_user
        
        with patch.object(self.service.subscription_service, 'get_user_subscription', return_value=mock_subscription):
            result = self.service.check_trial_status(user_id=1)
        
        assert result['is_trial'] is True
        assert result['trial_used'] is True
        assert result['days_remaining'] >= 9
        assert result['is_expiring_soon'] is False
    
    def test_check_trial_status_expiring_soon(self):
        """Test check_trial_status shows expiring_soon when <= 3 days"""
        now = datetime.utcnow()
        mock_user = User(id=1, email="test@example.com", trial_used=True)
        mock_subscription = Subscription(
            id=1,
            user_id=1,
            plan_id=3,
            status=SubscriptionStatus.TRIALING,
            current_period_end=now + timedelta(days=2)
        )
        
        self.mock_db.query().filter().first.return_value = mock_user
        
        with patch.object(self.service.subscription_service, 'get_user_subscription', return_value=mock_subscription):
            result = self.service.check_trial_status(user_id=1)
        
        assert result['is_expiring_soon'] is True
    
    def test_check_trial_status_no_trial(self):
        """Test check_trial_status returns correct info when no trial"""
        mock_user = User(id=1, email="test@example.com", trial_used=False)
        
        self.mock_db.query().filter().first.return_value = mock_user
        
        with patch.object(self.service.subscription_service, 'get_user_subscription', return_value=None):
            result = self.service.check_trial_status(user_id=1)
        
        assert result['is_trial'] is False
        assert result['trial_used'] is False
        assert result['trial_available'] is True
    
    def test_ensure_single_trial_per_user_available(self):
        """Test ensure_single_trial_per_user returns True when available"""
        mock_user = User(id=1, email="test@example.com", trial_used=False)
        
        self.mock_db.query().filter().first.return_value = mock_user
        
        result = self.service.ensure_single_trial_per_user(user_id=1)
        
        assert result is True
    
    def test_ensure_single_trial_per_user_used(self):
        """Test ensure_single_trial_per_user returns False when used"""
        mock_user = User(id=1, email="test@example.com", trial_used=True)
        
        self.mock_db.query().filter().first.return_value = mock_user
        
        result = self.service.ensure_single_trial_per_user(user_id=1)
        
        assert result is False
    
    def test_send_trial_expiration_reminder_correct_timing(self):
        """Test send_trial_expiration_reminder sends at 3 days before expiry"""
        now = datetime.utcnow()
        mock_user = User(id=1, email="test@example.com")
        mock_subscription = Subscription(
            id=1,
            user_id=1,
            plan_id=3,
            status=SubscriptionStatus.TRIALING,
            current_period_end=now + timedelta(days=3)
        )
        
        self.mock_db.query().filter().first.return_value = mock_user
        
        with patch.object(self.service.subscription_service, 'get_user_subscription', return_value=mock_subscription):
            with patch.object(self.service.notification_service, 'create_notification') as mock_notify:
                self.service.send_trial_expiration_reminder(user_id=1)
                
                mock_notify.assert_called_once()
    
    def test_send_trial_expiration_reminder_wrong_timing(self):
        """Test send_trial_expiration_reminder doesn't send at wrong time"""
        now = datetime.utcnow()
        mock_user = User(id=1, email="test@example.com")
        mock_subscription = Subscription(
            id=1,
            user_id=1,
            plan_id=3,
            status=SubscriptionStatus.TRIALING,
            current_period_end=now + timedelta(days=10)
        )
        
        self.mock_db.query().filter().first.return_value = mock_user
        
        with patch.object(self.service.subscription_service, 'get_user_subscription', return_value=mock_subscription):
            with patch.object(self.service.notification_service, 'create_notification') as mock_notify:
                self.service.send_trial_expiration_reminder(user_id=1)
                
                mock_notify.assert_not_called()
    
    def test_handle_trial_end(self):
        """Test handle_trial_end delegates to subscription service"""
        with patch.object(self.service.subscription_service, 'handle_trial_expiration') as mock_handle:
            mock_subscription = Subscription(id=1, user_id=1, plan_id=1)
            mock_handle.return_value = mock_subscription
            
            result = self.service.handle_trial_end(user_id=1)
            
            assert result == mock_subscription
            mock_handle.assert_called_once_with(1)
    
    def test_get_trial_eligible_users(self):
        """Test get_trial_eligible_users returns users without trial"""
        mock_users = [
            User(id=1, email="user1@example.com", trial_used=False),
            User(id=2, email="user2@example.com", trial_used=False)
        ]
        
        self.mock_db.query().filter().filter().all.return_value = mock_users
        
        result = self.service.get_trial_eligible_users()
        
        assert len(result) == 2
        assert all(not user.trial_used for user in result)
    
    def test_get_expiring_trials(self):
        """Test get_expiring_trials returns trials expiring soon"""
        now = datetime.utcnow()
        mock_subscriptions = [
            Subscription(
                id=1,
                user_id=1,
                plan_id=3,
                status=SubscriptionStatus.TRIALING,
                current_period_end=now + timedelta(days=2)
            ),
            Subscription(
                id=2,
                user_id=2,
                plan_id=3,
                status=SubscriptionStatus.TRIALING,
                current_period_end=now + timedelta(days=1)
            )
        ]
        
        self.mock_db.query().filter().filter().filter().all.return_value = mock_subscriptions
        
        result = self.service.get_expiring_trials(days_threshold=3)
        
        assert len(result) == 2
        assert all(sub.status == SubscriptionStatus.TRIALING for sub in result)
    
    def test_get_expired_trials(self):
        """Test get_expired_trials returns expired trial subscriptions"""
        now = datetime.utcnow()
        mock_subscriptions = [
            Subscription(
                id=1,
                user_id=1,
                plan_id=3,
                status=SubscriptionStatus.TRIALING,
                current_period_end=now - timedelta(days=1)
            ),
            Subscription(
                id=2,
                user_id=2,
                plan_id=3,
                status=SubscriptionStatus.TRIALING,
                current_period_end=now - timedelta(days=5)
            )
        ]
        
        self.mock_db.query().filter().filter().all.return_value = mock_subscriptions
        
        result = self.service.get_expired_trials()
        
        assert len(result) == 2
        assert all(sub.status == SubscriptionStatus.TRIALING for sub in result)
        assert all(sub.current_period_end < now for sub in result)
