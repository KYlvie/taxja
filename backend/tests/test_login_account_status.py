"""Unit tests for login endpoint account_status checks.

Tests cover:
- Deactivated accounts are rejected with 403 and cooling-off info (Requirement 3, AC 3)
- Deletion-pending accounts are rejected with 403 (Requirement 3, AC 3)
- Active accounts can still log in normally
"""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

from app.core.security import get_password_hash
from app.models.user import User, UserType


@pytest.fixture
def active_user(db):
    """Create an active user for testing."""
    user = User(
        email="active@example.com",
        name="Active User",
        password_hash=get_password_hash("TestPassword123!"),
        user_type=UserType.EMPLOYEE,
        account_status="active",
        email_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def deactivated_user(db):
    """Create a deactivated user with 15 days remaining in cooling-off period."""
    now = datetime.now(timezone.utc)
    user = User(
        email="deactivated@example.com",
        name="Deactivated User",
        password_hash=get_password_hash("TestPassword123!"),
        user_type=UserType.EMPLOYEE,
        account_status="deactivated",
        email_verified=True,
        deactivated_at=now - timedelta(days=15),
        scheduled_deletion_at=now + timedelta(days=15),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def deactivated_user_expired(db):
    """Create a deactivated user whose cooling-off period has passed."""
    now = datetime.now(timezone.utc)
    user = User(
        email="expired@example.com",
        name="Expired User",
        password_hash=get_password_hash("TestPassword123!"),
        user_type=UserType.EMPLOYEE,
        account_status="deactivated",
        email_verified=True,
        deactivated_at=now - timedelta(days=35),
        scheduled_deletion_at=now - timedelta(days=5),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def deletion_pending_user(db):
    """Create a user with deletion_pending status."""
    now = datetime.now(timezone.utc)
    user = User(
        email="pending@example.com",
        name="Pending User",
        password_hash=get_password_hash("TestPassword123!"),
        user_type=UserType.EMPLOYEE,
        account_status="deletion_pending",
        email_verified=True,
        deactivated_at=now - timedelta(days=31),
        scheduled_deletion_at=now - timedelta(days=1),
        deletion_retry_count=1,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


class TestLoginDeactivatedAccount:
    """Test login rejection for deactivated accounts — Requirement 3, AC 3."""

    def test_deactivated_account_returns_403(self, client, deactivated_user):
        """Deactivated user login should return HTTP 403."""
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "deactivated@example.com", "password": "TestPassword123!"},
        )
        assert response.status_code == 403

    def test_deactivated_account_response_body(self, client, deactivated_user):
        """Response should include account_status, cooling_off_days_remaining, and message."""
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "deactivated@example.com", "password": "TestPassword123!"},
        )
        data = response.json()["detail"]
        assert data["account_status"] == "deactivated"
        assert data["detail"] == "Account is deactivated"
        assert isinstance(data["cooling_off_days_remaining"], int)
        assert data["cooling_off_days_remaining"] > 0
        assert "reactivate" in data["message"].lower()

    def test_deactivated_account_cooling_off_days(self, client, deactivated_user):
        """Cooling-off days remaining should reflect scheduled_deletion_at."""
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "deactivated@example.com", "password": "TestPassword123!"},
        )
        days = response.json()["detail"]["cooling_off_days_remaining"]
        # User was deactivated 15 days ago with 30-day period → ~15 days remaining
        assert 13 <= days <= 15

    def test_deactivated_expired_cooling_off_returns_zero(self, client, deactivated_user_expired):
        """When cooling-off period has passed, remaining days should be 0."""
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "expired@example.com", "password": "TestPassword123!"},
        )
        assert response.status_code == 403
        days = response.json()["detail"]["cooling_off_days_remaining"]
        assert days == 0


class TestLoginDeletionPendingAccount:
    """Test login rejection for deletion_pending accounts — Requirement 3, AC 3."""

    def test_deletion_pending_returns_403(self, client, deletion_pending_user):
        """Deletion-pending user login should return HTTP 403."""
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "pending@example.com", "password": "TestPassword123!"},
        )
        assert response.status_code == 403

    def test_deletion_pending_response_body(self, client, deletion_pending_user):
        """Response should include account_status and appropriate message."""
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "pending@example.com", "password": "TestPassword123!"},
        )
        data = response.json()["detail"]
        assert data["account_status"] == "deletion_pending"
        assert data["detail"] == "Account is scheduled for deletion"
        assert "permanent deletion" in data["message"].lower()


class TestLoginActiveAccount:
    """Verify active accounts are unaffected by the new checks."""

    def test_active_account_can_login(self, client, active_user):
        """Active user should still receive an access token."""
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "active@example.com", "password": "TestPassword123!"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_wrong_password_still_returns_401(self, client, active_user):
        """Wrong password should still return 401, not 403."""
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "active@example.com", "password": "WrongPassword!"},
        )
        assert response.status_code == 401
