"""Integration tests for the current authentication contracts."""

from datetime import datetime, timedelta
from unittest.mock import patch

from app.core.security import get_password_hash
from app.models.user import User


class TestUserRegistration:
    """Registration + verification flow as currently implemented."""

    @patch("app.api.v1.endpoints.auth.send_verification_email")
    @patch("app.api.v1.endpoints.auth.generate_verification_token", return_value="verify-token")
    def test_complete_registration_flow(
        self,
        mock_generate_token,
        mock_send_email,
        client,
        db,
    ):
        registration_data = {
            "email": "newuser@example.com",
            "password": "SecurePassword123!",
            "name": "Test User",
            "user_type": "employee",
        }

        response = client.post("/api/v1/auth/register", json=registration_data)
        assert response.status_code == 201
        assert response.json() == {
            "message": "verification_email_sent",
            "email": "newuser@example.com",
        }

        user = db.query(User).filter(User.email == "newuser@example.com").first()
        assert user is not None
        assert user.name == "Test User"
        assert user.email_verified is False
        assert user.email_verification_token == "verify-token"
        mock_generate_token.assert_called_once()
        mock_send_email.assert_called_once()

    @patch("app.api.v1.endpoints.auth.send_verification_email")
    @patch("app.api.v1.endpoints.auth.generate_verification_token", return_value="verify-token")
    def test_registration_with_duplicate_email(
        self,
        _mock_generate_token,
        _mock_send_email,
        client,
    ):
        payload = {
            "email": "duplicate@example.com",
            "password": "Password123!",
            "name": "First User",
            "user_type": "employee",
        }

        first = client.post("/api/v1/auth/register", json=payload)
        second = client.post("/api/v1/auth/register", json=payload)

        assert first.status_code == 201
        assert second.status_code == 400
        assert "already registered" in second.json()["detail"].lower()

    def test_registration_with_invalid_email(self, client):
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "invalid-email",
                "password": "Password123!",
                "name": "Test User",
                "user_type": "employee",
            },
        )
        assert response.status_code == 422


class TestEmailVerificationAndLogin:
    """Verified/unverified login behavior."""

    def test_login_blocks_unverified_user(self, client, db):
        db.add(
            User(
                email="pending@example.com",
                name="Pending User",
                password_hash=get_password_hash("Password123!"),
                user_type="employee",
                email_verified=False,
            )
        )
        db.commit()

        response = client.post(
            "/api/v1/auth/login",
            json={"email": "pending@example.com", "password": "Password123!"},
        )

        assert response.status_code == 403
        detail = response.json()["detail"]
        assert detail["detail"] == "email_not_verified"
        assert detail["email"] == "pending@example.com"

    def test_verify_email_marks_user_verified_and_returns_token(self, client, db):
        db.add(
            User(
                email="verifyme@example.com",
                name="Verify Me",
                password_hash=get_password_hash("Password123!"),
                user_type="employee",
                email_verified=False,
                email_verification_token="verify-token",
            )
        )
        db.commit()

        with patch("app.api.v1.endpoints.auth.TrialService.activate_trial"):
            response = client.post("/api/v1/auth/verify-email?token=verify-token")

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "email_verified"
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == "verifyme@example.com"
        assert data["user"]["name"] == "Verify Me"

        user = db.query(User).filter(User.email == "verifyme@example.com").first()
        assert user.email_verified is True
        assert user.email_verification_token is None

    def test_login_verified_user_returns_access_token_and_user_info(
        self,
        client,
        test_user,
    ):
        response = client.post(
            "/api/v1/auth/login",
            json={"email": test_user["email"], "password": test_user["password"]},
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == test_user["email"]
        assert data["user"]["name"] == test_user["full_name"]
        assert "password" not in data["user"]

    def test_login_with_wrong_password(self, client, test_user):
        response = client.post(
            "/api/v1/auth/login",
            json={"email": test_user["email"], "password": "WrongPassword123!"},
        )
        assert response.status_code == 401
        assert "incorrect" in response.json()["detail"].lower()

    def test_access_profile_with_login_token(self, client, test_user):
        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": test_user["email"], "password": test_user["password"]},
        )
        token = login_response.json()["access_token"]

        response = client.get(
            "/api/v1/users/profile",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        profile = response.json()
        assert profile["email"] == test_user["email"]
        assert profile["name"] == test_user["full_name"]
        assert "tax_profile_completeness" in profile


class TestPasswordResetFlow:
    """Current forgot/reset password endpoints."""

    @patch("app.api.v1.endpoints.auth.send_password_reset_email")
    def test_forgot_password_returns_success_for_existing_email(
        self,
        mock_send_email,
        client,
        test_user,
        db,
    ):
        response = client.post(
            "/api/v1/auth/forgot-password",
            json={"email": test_user["email"]},
        )

        assert response.status_code == 200
        assert response.json()["message"] == "password_reset_email_sent"
        mock_send_email.assert_called_once()

        user = db.query(User).filter(User.email == test_user["email"]).first()
        assert user.password_reset_token is not None
        assert user.password_reset_sent_at is not None

    def test_forgot_password_returns_success_for_missing_email(self, client):
        response = client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "missing@example.com"},
        )
        assert response.status_code == 200
        assert response.json()["message"] == "password_reset_email_sent"

    def test_reset_password_with_valid_token(self, client, test_user, db):
        user = db.query(User).filter(User.email == test_user["email"]).first()
        user.password_reset_token = "reset-token"
        user.password_reset_sent_at = datetime.utcnow()
        db.commit()

        response = client.post(
            "/api/v1/auth/reset-password",
            json={"token": "reset-token", "password": "NewSecurePassword123!"},
        )
        assert response.status_code == 200
        assert response.json()["message"] == "password_reset_success"

        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": test_user["email"], "password": "NewSecurePassword123!"},
        )
        assert login_response.status_code == 200

    def test_reset_password_with_invalid_token(self, client):
        response = client.post(
            "/api/v1/auth/reset-password",
            json={"token": "invalid-token", "password": "NewSecurePassword123!"},
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "invalid_or_expired_token"

    def test_reset_password_with_expired_token(self, client, test_user, db):
        user = db.query(User).filter(User.email == test_user["email"]).first()
        user.password_reset_token = "expired-token"
        user.password_reset_sent_at = datetime.utcnow() - timedelta(hours=2)
        db.commit()

        response = client.post(
            "/api/v1/auth/reset-password",
            json={"token": "expired-token", "password": "NewSecurePassword123!"},
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "token_expired"


class TestPlaceholderAuthEndpoints:
    """Current placeholder endpoints should stay stable until real implementations land."""

    def test_logout_returns_success_message(self, client):
        response = client.post("/api/v1/auth/logout")
        assert response.status_code == 200
        assert response.json()["message"] == "Successfully logged out"

    def test_refresh_returns_placeholder_message(self, client):
        response = client.post("/api/v1/auth/refresh")
        assert response.status_code == 200
        assert response.json()["message"] == "Token refresh not implemented yet"

    def test_2fa_setup_returns_placeholder_payload(self, client):
        response = client.post("/api/v1/auth/2fa/setup")
        assert response.status_code == 200
        assert response.json() == {"qr_code": "", "secret": ""}

    def test_2fa_verify_returns_placeholder_payload(self, client):
        response = client.post("/api/v1/auth/2fa/verify")
        assert response.status_code == 200
        assert response.json() == {"success": True}
