"""Unit tests for AccountCancellationService"""
import hashlib
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch, call

from app.models.audit_log import AuditLog, AuditEntityType, AuditOperationType
from app.models.document import Document
from app.models.payment_event import PaymentEvent
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.transaction import Transaction
from app.models.tax_report import TaxReport
from app.models.property import Property
from app.models.user import User
from app.models.account_deletion_log import AccountDeletionLog
from app.services.account_cancellation_service import (
    AccountCancellationService,
    COOLING_OFF_DAYS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(**overrides):
    """Create a minimal User-like object for testing."""
    defaults = dict(
        id=1,
        email="test@example.com",
        password_hash="hashed_pw",
        account_status="active",
        deactivated_at=None,
        scheduled_deletion_at=None,
        cancellation_reason=None,
        deletion_retry_count=0,
    )
    defaults.update(overrides)
    user = Mock(spec=User)
    for k, v in defaults.items():
        setattr(user, k, v)
    return user


# ===================================================================
# get_cancellation_impact
# ===================================================================

class TestGetCancellationImpact:
    """Tests for AccountCancellationService.get_cancellation_impact"""

    def _setup_db(self, user, txn_count=0, doc_count=0, report_count=0,
                  prop_count=0, subscription=None):
        db = Mock()
        # user query
        db.query.return_value.filter.return_value.first.return_value = user

        # count queries — each call to db.query(func.count(...)).filter(...).scalar()
        scalar_mock = Mock()
        scalar_mock.side_effect = [txn_count, doc_count, report_count, prop_count]
        filter_mock = Mock()
        filter_mock.scalar = scalar_mock

        # subscription query (last .first() call)
        sub_filter = Mock()
        sub_filter.first.return_value = subscription

        call_count = {"n": 0}
        original_query = db.query

        def query_side_effect(*args, **kwargs):
            call_count["n"] += 1
            m = Mock()
            if call_count["n"] == 1:
                # User query
                m.filter.return_value.first.return_value = user
            elif call_count["n"] <= 5:
                # count queries
                m.filter.return_value.scalar.return_value = [
                    txn_count, doc_count, report_count, prop_count
                ][call_count["n"] - 2]
            else:
                # subscription query
                m.filter.return_value.first.return_value = subscription
            return m

        db.query.side_effect = query_side_effect
        return db

    def test_returns_correct_counts(self):
        user = _make_user()
        db = self._setup_db(user, txn_count=5, doc_count=3, report_count=2, prop_count=1)

        result = AccountCancellationService.get_cancellation_impact(1, db)

        assert result["transaction_count"] == 5
        assert result["document_count"] == 3
        assert result["tax_report_count"] == 2
        assert result["property_count"] == 1
        assert result["cooling_off_days"] == COOLING_OFF_DAYS

    def test_no_active_subscription(self):
        user = _make_user()
        db = self._setup_db(user, subscription=None)

        result = AccountCancellationService.get_cancellation_impact(1, db)

        assert result["has_active_subscription"] is False
        assert result["subscription_days_remaining"] is None

    def test_with_active_subscription(self):
        user = _make_user()
        sub = Mock(spec=Subscription)
        sub.days_until_expiry.return_value = 15
        db = self._setup_db(user, subscription=sub)

        result = AccountCancellationService.get_cancellation_impact(1, db)

        assert result["has_active_subscription"] is True
        assert result["subscription_days_remaining"] == 15

    def test_user_not_found_raises(self):
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(ValueError, match="User not found"):
            AccountCancellationService.get_cancellation_impact(999, db)


class TestAuditLogEnumConfiguration:
    """Regression coverage for enum values persisted to PostgreSQL."""

    def test_uses_lowercase_database_values(self):
        assert AuditLog.__table__.c.operation_type.type.enums == [
            enum.value for enum in AuditOperationType
        ]
        assert AuditLog.__table__.c.entity_type.type.enums == [
            enum.value for enum in AuditEntityType
        ]


# ===================================================================
# deactivate_account
# ===================================================================

class TestDeactivateAccount:
    """Tests for AccountCancellationService.deactivate_account"""

    def _setup_db(self, user, subscription=None):
        db = Mock()
        call_count = {"n": 0}

        def query_side_effect(*args, **kwargs):
            call_count["n"] += 1
            m = Mock()
            if call_count["n"] == 1:
                m.filter.return_value.first.return_value = user
            else:
                m.filter.return_value.first.return_value = subscription
            return m

        db.query.side_effect = query_side_effect
        return db

    @patch("app.services.account_cancellation_service.verify_password", return_value=True)
    def test_deactivate_success(self, mock_verify):
        user = _make_user()
        db = self._setup_db(user, subscription=None)

        result = AccountCancellationService.deactivate_account(
            user_id=1, password="pw", reason="leaving",
            confirmation_word="DELETE", two_factor_code=None, db=db,
        )

        assert user.account_status == "deactivated"
        assert user.deactivated_at is not None
        assert user.scheduled_deletion_at is not None
        assert user.cancellation_reason == "leaving"
        assert result["account_status"] == "deactivated"
        assert result["cooling_off_days"] == COOLING_OFF_DAYS
        db.add.assert_called_once()  # audit log
        db.commit.assert_called_once()

    @patch("app.services.account_cancellation_service.verify_password", return_value=False)
    def test_deactivate_wrong_password(self, mock_verify):
        user = _make_user()
        db = self._setup_db(user)

        with pytest.raises(PermissionError, match="Invalid password"):
            AccountCancellationService.deactivate_account(
                user_id=1, password="wrong", reason=None,
                confirmation_word="DELETE", two_factor_code=None, db=db,
            )

    @patch("app.services.account_cancellation_service.verify_password", return_value=True)
    def test_deactivate_wrong_confirmation(self, mock_verify):
        user = _make_user()
        db = self._setup_db(user)

        with pytest.raises(ValueError, match="DELETE"):
            AccountCancellationService.deactivate_account(
                user_id=1, password="pw", reason=None,
                confirmation_word="WRONG", two_factor_code=None, db=db,
            )

    @patch("app.services.account_cancellation_service.verify_password", return_value=True)
    def test_deactivate_already_deactivated(self, mock_verify):
        user = _make_user(account_status="deactivated")
        db = self._setup_db(user)

        with pytest.raises(ValueError, match="already deactivated"):
            AccountCancellationService.deactivate_account(
                user_id=1, password="pw", reason=None,
                confirmation_word="DELETE", two_factor_code=None, db=db,
            )

    @patch("app.services.account_cancellation_service.verify_password", return_value=True)
    def test_deactivate_cancels_active_subscription(self, mock_verify):
        user = _make_user()
        sub = Mock(spec=Subscription)
        sub.status = SubscriptionStatus.ACTIVE
        sub.cancel_at_period_end = False
        db = self._setup_db(user, subscription=sub)

        AccountCancellationService.deactivate_account(
            user_id=1, password="pw", reason=None,
            confirmation_word="DELETE", two_factor_code=None, db=db,
        )

        assert sub.status == SubscriptionStatus.CANCELED
        assert sub.cancel_at_period_end is True

    def test_deactivate_user_not_found(self):
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(ValueError, match="User not found"):
            AccountCancellationService.deactivate_account(
                user_id=999, password="pw", reason=None,
                confirmation_word="DELETE", two_factor_code=None, db=db,
            )


# ===================================================================
# reactivate_account
# ===================================================================

class TestReactivateAccount:
    """Tests for AccountCancellationService.reactivate_account"""

    def test_reactivate_success(self):
        user = _make_user(
            account_status="deactivated",
            scheduled_deletion_at=datetime.utcnow() + timedelta(days=10),
        )
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = user

        result = AccountCancellationService.reactivate_account(1, db)

        assert user.account_status == "active"
        assert user.deactivated_at is None
        assert user.scheduled_deletion_at is None
        assert result["account_status"] == "active"
        db.commit.assert_called_once()

    def test_reactivate_not_deactivated(self):
        user = _make_user(account_status="active")
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = user

        with pytest.raises(ValueError, match="Only deactivated"):
            AccountCancellationService.reactivate_account(1, db)

    def test_reactivate_expired_cooling_off(self):
        user = _make_user(
            account_status="deactivated",
            scheduled_deletion_at=datetime.utcnow() - timedelta(days=1),
        )
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = user

        with pytest.raises(ValueError, match="expired"):
            AccountCancellationService.reactivate_account(1, db)

    def test_reactivate_user_not_found(self):
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(ValueError, match="User not found"):
            AccountCancellationService.reactivate_account(999, db)


# ===================================================================
# hard_delete_account
# ===================================================================

class TestHardDeleteAccount:
    """Tests for AccountCancellationService.hard_delete_account"""

    @patch("app.services.account_cancellation_service.redis.Redis")
    @patch("app.services.account_cancellation_service.StorageService")
    def test_hard_delete_success(self, MockStorage, MockRedis):
        user = _make_user()
        doc = Mock(spec=Document)
        doc.file_path = "docs/1/receipt.pdf"

        db = Mock()
        call_count = {"n": 0}

        def query_side_effect(*args, **kwargs):
            call_count["n"] += 1
            m = Mock()
            if call_count["n"] == 1:
                # User query
                m.filter.return_value.first.return_value = user
            elif call_count["n"] == 2:
                # Documents query
                m.filter.return_value.all.return_value = [doc]
            elif call_count["n"] <= 4:
                # PaymentEvent / AuditLog update
                m.filter.return_value.update.return_value = 1
            else:
                # Transaction/TaxReport/Property existence checks
                m.filter.return_value.first.return_value = Mock()
            return m

        db.query.side_effect = query_side_effect

        # Redis mock
        redis_instance = MockRedis.return_value
        redis_instance.scan.return_value = (0, [])

        result = AccountCancellationService.hard_delete_account(1, "system", db)

        assert result["message"] == "Account permanently deleted"
        assert "anonymous_user_hash" in result
        assert len(result["anonymous_user_hash"]) == 64  # SHA-256 hex
        db.delete.assert_called_once_with(user)
        db.flush.assert_called_once()
        db.add.assert_called_once()  # AccountDeletionLog
        db.commit.assert_called_once()
        MockStorage.return_value.delete_file.assert_called_once_with("docs/1/receipt.pdf")

    @patch("app.services.account_cancellation_service.redis.Redis")
    @patch("app.services.account_cancellation_service.StorageService")
    def test_hard_delete_admin_sets_deletion_method(self, MockStorage, MockRedis):
        user = _make_user()
        db = Mock()
        call_count = {"n": 0}

        def query_side_effect(*args, **kwargs):
            call_count["n"] += 1
            m = Mock()
            if call_count["n"] == 1:
                m.filter.return_value.first.return_value = user
            elif call_count["n"] == 2:
                m.filter.return_value.all.return_value = []
            elif call_count["n"] <= 4:
                m.filter.return_value.update.return_value = 0
            else:
                m.filter.return_value.first.return_value = None
            return m

        db.query.side_effect = query_side_effect
        redis_instance = MockRedis.return_value
        redis_instance.scan.return_value = (0, [])

        result = AccountCancellationService.hard_delete_account(1, "admin", db)

        # Verify the AccountDeletionLog was created with admin_manual method
        added_obj = db.add.call_args[0][0]
        assert added_obj.deletion_method == "admin_manual"
        assert added_obj.initiated_by == "admin"

    def test_hard_delete_user_not_found(self):
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(ValueError, match="User not found"):
            AccountCancellationService.hard_delete_account(999, "system", db)

    @patch("app.services.account_cancellation_service.redis.Redis")
    @patch("app.services.account_cancellation_service.StorageService")
    def test_hard_delete_hash_is_deterministic(self, MockStorage, MockRedis):
        """Same user_id + secret should always produce the same hash."""
        user = _make_user(id=42)
        db = Mock()
        call_count = {"n": 0}

        def query_side_effect(*args, **kwargs):
            call_count["n"] += 1
            m = Mock()
            if call_count["n"] == 1:
                m.filter.return_value.first.return_value = user
            elif call_count["n"] == 2:
                m.filter.return_value.all.return_value = []
            elif call_count["n"] <= 4:
                m.filter.return_value.update.return_value = 0
            else:
                m.filter.return_value.first.return_value = None
            return m

        db.query.side_effect = query_side_effect
        redis_instance = MockRedis.return_value
        redis_instance.scan.return_value = (0, [])

        result = AccountCancellationService.hard_delete_account(42, "user", db)

        from app.core.config import settings
        expected = hashlib.sha256(f"42{settings.SECRET_KEY}".encode()).hexdigest()
        assert result["anonymous_user_hash"] == expected


# ===================================================================
# get_admin_cancellation_stats
# ===================================================================

class TestGetAdminCancellationStats:
    """Tests for AccountCancellationService.get_admin_cancellation_stats"""

    def test_returns_expected_keys(self):
        db = Mock()
        call_count = {"n": 0}

        def query_side_effect(*args, **kwargs):
            call_count["n"] += 1
            m = Mock()
            if call_count["n"] == 1:
                # monthly deactivated count
                m.filter.return_value.scalar.return_value = 3
            elif call_count["n"] == 2:
                # monthly hard-deleted count
                m.filter.return_value.scalar.return_value = 1
            elif call_count["n"] == 3:
                # reason distribution
                m.filter.return_value.group_by.return_value.all.return_value = [
                    ("too_expensive", 2),
                    ("not_specified", 1),
                ]
            elif call_count["n"] == 4:
                # total_ever_deactivated
                m.filter.return_value.scalar.return_value = 10
            elif call_count["n"] == 5:
                # reactivated_count
                m.filter.return_value.scalar.return_value = 2
            else:
                # avg lifetime
                m.filter.return_value.scalar.return_value = 180.5
            return m

        db.query.side_effect = query_side_effect

        result = AccountCancellationService.get_admin_cancellation_stats(db)

        assert result["monthly_cancellations"] == 4  # 3 + 1
        assert result["cancellation_reasons"] == {
            "too_expensive": 2,
            "not_specified": 1,
        }
        assert result["reactivation_rate"] == 0.2  # 2/10
        assert result["average_user_lifetime_days"] == 180.5

    def test_zero_deactivations_returns_zero_rate(self):
        db = Mock()
        call_count = {"n": 0}

        def query_side_effect(*args, **kwargs):
            call_count["n"] += 1
            m = Mock()
            if call_count["n"] <= 2:
                m.filter.return_value.scalar.return_value = 0
            elif call_count["n"] == 3:
                m.filter.return_value.group_by.return_value.all.return_value = []
            elif call_count["n"] <= 5:
                m.filter.return_value.scalar.return_value = 0
            else:
                m.filter.return_value.scalar.return_value = None
            return m

        db.query.side_effect = query_side_effect

        result = AccountCancellationService.get_admin_cancellation_stats(db)

        assert result["monthly_cancellations"] == 0
        assert result["cancellation_reasons"] == {}
        assert result["reactivation_rate"] == 0.0
        assert result["average_user_lifetime_days"] == 0.0
