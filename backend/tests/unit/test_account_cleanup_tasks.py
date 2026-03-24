"""Unit tests for account cleanup Celery tasks."""
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch

from app.models.user import User

_GS = "app.tasks.account_cleanup_tasks._get_session"
_HD = "app.tasks.account_cleanup_tasks._hard_delete"


def _make_user(**overrides):
    defaults = dict(
        id=1, email="test@example.com", account_status="active",
        deactivated_at=None, scheduled_deletion_at=None,
        deletion_retry_count=0, cancellation_reason=None,
    )
    defaults.update(overrides)
    user = Mock(spec=User)
    for k, v in defaults.items():
        setattr(user, k, v)
    return user


def _db_with_filters(*filter_results):
    db = MagicMock()
    idx = {"n": 0}

    def _filter(*a, **kw):
        chain = MagicMock()
        i = idx["n"]
        idx["n"] += 1
        data = filter_results[i] if i < len(filter_results) else []
        chain.all.return_value = data
        chain.first.return_value = data[0] if data else None
        return chain

    db.query.return_value.filter.side_effect = _filter
    return db


class TestCleanupExpiredAccounts:

    @patch(_HD)
    @patch(_GS)
    def test_deletes_expired_deactivated(self, mock_gs, mock_hd):
        from app.tasks.account_cleanup_tasks import cleanup_expired_accounts
        now = datetime.utcnow()
        user = _make_user(
            id=10, account_status="deactivated",
            scheduled_deletion_at=now - timedelta(days=1),
        )
        db = _db_with_filters([user], [], [])
        mock_gs.return_value = db
        result = cleanup_expired_accounts()
        assert result["accounts_deleted"] == 1
        assert result["accounts_failed"] == 0
        mock_hd.assert_called_once_with(user_id=10, initiated_by="system", db=db)
        db.close.assert_called_once()

    @patch(_HD)
    @patch(_GS)
    def test_retries_pending(self, mock_gs, mock_hd):
        from app.tasks.account_cleanup_tasks import cleanup_expired_accounts
        user = _make_user(id=20, account_status="deletion_pending", deletion_retry_count=1)
        db = _db_with_filters([], [user], [])
        mock_gs.return_value = db
        result = cleanup_expired_accounts()
        assert result["accounts_retried"] == 1
        assert result["accounts_deleted"] == 1
        mock_hd.assert_called_once_with(user_id=20, initiated_by="system", db=db)

    @patch(_HD)
    @patch(_GS)
    def test_alerts_stuck(self, mock_gs, mock_hd):
        from app.tasks.account_cleanup_tasks import cleanup_expired_accounts
        user = _make_user(
            id=30, account_status="deletion_pending",
            deletion_retry_count=3, email="stuck@example.com",
        )
        db = _db_with_filters([], [], [user])
        mock_gs.return_value = db
        result = cleanup_expired_accounts()
        assert result["accounts_alerted"] == 1
        assert result["accounts_deleted"] == 0
        mock_hd.assert_not_called()

    @patch(_HD)
    @patch(_GS)
    def test_failure_marks_pending(self, mock_gs, mock_hd):
        from app.tasks.account_cleanup_tasks import cleanup_expired_accounts
        now = datetime.utcnow()
        user = _make_user(
            id=40, account_status="deactivated",
            scheduled_deletion_at=now - timedelta(days=1),
            deletion_retry_count=0,
        )
        mock_hd.side_effect = RuntimeError("MinIO down")
        # Filter calls: 1=expired, 2=re-fetch after rollback, 3=pending, 4=stuck
        db = _db_with_filters([user], [user], [], [])
        mock_gs.return_value = db
        result = cleanup_expired_accounts()
        assert result["accounts_failed"] == 1
        assert result["accounts_deleted"] == 0
        # After failure, the task sets account_status and increments retry count
        # on the re-fetched user (same mock object via _db_with_filters .first())
        assert user.account_status == "deletion_pending"
        assert user.deletion_retry_count == 1

    @patch(_GS)
    def test_empty_returns_zeros(self, mock_gs):
        from app.tasks.account_cleanup_tasks import cleanup_expired_accounts
        db = _db_with_filters([], [], [])
        mock_gs.return_value = db
        result = cleanup_expired_accounts()
        assert result["accounts_checked"] == 0
        assert result["accounts_deleted"] == 0
        assert result["accounts_failed"] == 0
        assert result["accounts_retried"] == 0
        assert result["accounts_alerted"] == 0
        assert "run_at" in result


class TestSendDeletionReminders:

    @patch(_GS)
    def test_sends_reminders(self, mock_gs):
        from app.tasks.account_cleanup_tasks import send_deletion_reminders
        now = datetime.utcnow()
        user = _make_user(
            id=50, account_status="deactivated",
            deactivated_at=now - timedelta(days=23),
            scheduled_deletion_at=now + timedelta(days=7),
            email="reminder@example.com",
        )
        db = MagicMock()
        mock_gs.return_value = db
        db.query.return_value.filter.return_value.all.return_value = [user]
        result = send_deletion_reminders()
        assert result["reminders_sent"] == 1
        assert "run_at" in result
        db.close.assert_called_once()

    @patch(_GS)
    def test_no_matching_users(self, mock_gs):
        from app.tasks.account_cleanup_tasks import send_deletion_reminders
        db = MagicMock()
        mock_gs.return_value = db
        db.query.return_value.filter.return_value.all.return_value = []
        result = send_deletion_reminders()
        assert result["reminders_sent"] == 0

    @patch(_GS)
    def test_user_without_scheduled_deletion(self, mock_gs):
        from app.tasks.account_cleanup_tasks import send_deletion_reminders
        now = datetime.utcnow()
        user = _make_user(
            id=60, account_status="deactivated",
            deactivated_at=now - timedelta(days=23),
            scheduled_deletion_at=None,
        )
        db = MagicMock()
        mock_gs.return_value = db
        db.query.return_value.filter.return_value.all.return_value = [user]
        result = send_deletion_reminders()
        assert result["reminders_sent"] == 1


class TestBeatScheduleRegistration:

    def test_cleanup_at_2am(self):
        from app.celery_app import celery_app
        entry = celery_app.conf.beat_schedule["cleanup-expired-accounts"]
        assert entry["task"] == "app.tasks.account_cleanup_tasks.cleanup_expired_accounts"
        assert entry["schedule"]["hour"] == "2"
        assert entry["schedule"]["minute"] == "0"

    def test_reminders_at_9am(self):
        from app.celery_app import celery_app
        entry = celery_app.conf.beat_schedule["send-deletion-reminders"]
        assert entry["task"] == "app.tasks.account_cleanup_tasks.send_deletion_reminders"
        assert entry["schedule"]["hour"] == "9"
        assert entry["schedule"]["minute"] == "0"
