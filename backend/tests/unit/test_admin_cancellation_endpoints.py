"""
Unit tests for admin account cancellation management endpoints.
Tests user listing, hard deletion, reactivation, and cancellation stats.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from fastapi import HTTPException

from app.api.v1.endpoints.admin import (
    list_users,
    admin_hard_delete_user,
    admin_reactivate_user,
    get_cancellation_stats,
)


@pytest.fixture
def mock_db():
    """Mock database session."""
    return Mock()


@pytest.fixture
def mock_admin_user():
    """Mock admin user."""
    user = Mock()
    user.id = 1
    user.email = "admin@example.com"
    user.is_admin = True
    return user


class TestListUsers:
    """Test GET /admin/users endpoint."""

    def test_list_users_no_filter(self, mock_db, mock_admin_user):
        """Admin can list all users without status filter."""
        now = datetime.utcnow()
        user1 = Mock()
        user1.id = 10
        user1.email = "active@example.com"
        user1.name = "Active User"
        user1.account_status = "active"
        user1.deactivated_at = None
        user1.scheduled_deletion_at = None

        user2 = Mock()
        user2.id = 11
        user2.email = "deactivated@example.com"
        user2.name = "Deactivated User"
        user2.account_status = "deactivated"
        user2.deactivated_at = now - timedelta(days=5)
        user2.scheduled_deletion_at = now + timedelta(days=25)

        mock_query = Mock()
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [user1, user2]
        mock_db.query.return_value = mock_query

        result = list_users(status=None, skip=0, limit=100, db=mock_db, admin=mock_admin_user)

        assert len(result) == 2
        assert result[0]["id"] == 10
        assert result[0]["account_status"] == "active"
        assert result[0]["cooling_off_days_remaining"] == 0
        assert result[1]["id"] == 11
        assert result[1]["account_status"] == "deactivated"
        assert result[1]["cooling_off_days_remaining"] > 0

    def test_list_users_with_status_filter(self, mock_db, mock_admin_user):
        """Admin can filter users by account status."""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query

        result = list_users(
            status="deactivated", skip=0, limit=100, db=mock_db, admin=mock_admin_user
        )

        assert result == []
        mock_query.filter.assert_called_once()

    def test_list_users_returns_expected_fields(self, mock_db, mock_admin_user):
        """Response includes all required fields per Requirement 8 AC 1-2."""
        now = datetime.utcnow()
        user = Mock()
        user.id = 5
        user.email = "test@example.com"
        user.name = "Test"
        user.account_status = "deactivated"
        user.deactivated_at = now - timedelta(days=10)
        user.scheduled_deletion_at = now + timedelta(days=20)

        mock_query = Mock()
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [user]
        mock_db.query.return_value = mock_query

        result = list_users(status=None, skip=0, limit=100, db=mock_db, admin=mock_admin_user)

        entry = result[0]
        assert "id" in entry
        assert "email" in entry
        assert "name" in entry
        assert "account_status" in entry
        assert "deactivated_at" in entry
        assert "scheduled_deletion_at" in entry
        assert "cooling_off_days_remaining" in entry


class TestAdminHardDelete:
    """Test POST /admin/users/{user_id}/hard-delete endpoint."""

    @patch("app.api.v1.endpoints.admin.AccountCancellationService")
    def test_hard_delete_success(self, mock_service, mock_db, mock_admin_user):
        """Admin can trigger hard deletion for a user."""
        mock_service.hard_delete_account.return_value = {
            "message": "Account permanently deleted",
            "data_types_deleted": ["documents", "transactions"],
            "anonymous_user_hash": "abc123",
        }

        result = admin_hard_delete_user(user_id=42, db=mock_db, admin=mock_admin_user)

        assert result["message"] == "Account permanently deleted"
        mock_service.hard_delete_account.assert_called_once_with(42, "admin", mock_db)
        mock_db.add.assert_called()
        mock_db.commit.assert_called()

    @patch("app.api.v1.endpoints.admin.AccountCancellationService")
    def test_hard_delete_user_not_found(self, mock_service, mock_db, mock_admin_user):
        """Hard delete returns 400 when user not found."""
        mock_service.hard_delete_account.side_effect = ValueError("User not found")

        with pytest.raises(HTTPException) as exc_info:
            admin_hard_delete_user(user_id=999, db=mock_db, admin=mock_admin_user)

        assert exc_info.value.status_code == 400
        assert "User not found" in str(exc_info.value.detail)


class TestAdminReactivate:
    """Test POST /admin/users/{user_id}/reactivate endpoint."""

    @patch("app.api.v1.endpoints.admin.AccountCancellationService")
    def test_reactivate_success(self, mock_service, mock_db, mock_admin_user):
        """Admin can reactivate a deactivated user."""
        mock_service.reactivate_account.return_value = {
            "message": "Account reactivated successfully",
            "account_status": "active",
        }

        result = admin_reactivate_user(user_id=42, db=mock_db, admin=mock_admin_user)

        assert result["account_status"] == "active"
        mock_service.reactivate_account.assert_called_once_with(42, mock_db)
        mock_db.add.assert_called()
        mock_db.commit.assert_called()

    @patch("app.api.v1.endpoints.admin.AccountCancellationService")
    def test_reactivate_not_deactivated(self, mock_service, mock_db, mock_admin_user):
        """Reactivate returns 400 when user is not deactivated."""
        mock_service.reactivate_account.side_effect = ValueError(
            "Only deactivated accounts can be reactivated (current: active)"
        )

        with pytest.raises(HTTPException) as exc_info:
            admin_reactivate_user(user_id=42, db=mock_db, admin=mock_admin_user)

        assert exc_info.value.status_code == 400


class TestCancellationStats:
    """Test GET /admin/cancellation-stats endpoint."""

    @patch("app.api.v1.endpoints.admin.AccountCancellationService")
    def test_get_cancellation_stats(self, mock_service, mock_db, mock_admin_user):
        """Admin can retrieve cancellation statistics."""
        mock_service.get_admin_cancellation_stats.return_value = {
            "monthly_cancellations": 5,
            "cancellation_reasons": {"too_expensive": 3, "not_specified": 2},
            "reactivation_rate": 0.2,
            "average_user_lifetime_days": 120.5,
        }

        result = get_cancellation_stats(db=mock_db, admin=mock_admin_user)

        assert result["monthly_cancellations"] == 5
        assert result["reactivation_rate"] == 0.2
        mock_service.get_admin_cancellation_stats.assert_called_once_with(mock_db)
