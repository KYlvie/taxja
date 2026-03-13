"""Integration tests for authentication flow

Tests complete authentication workflows including:
- User registration (Requirement 11.1, 11.2)
- Login with 2FA (Requirement 17.3, 17.4, 17.5)
- Token refresh (Requirement 17.3)
- Session management (Requirement 17.4)
"""
import pytest
from fastapi.testclient import TestClient
import pyotp
from datetime import datetime, timedelta


class TestUserRegistration:
    """Integration tests for user registration flow"""
    
    def test_complete_registration_flow(self, client):
        """Test complete user registration workflow"""
        # Step 1: Register new user
        registration_data = {
            "email": "newuser@example.com",
            "password": "SecurePassword123!",
            "full_name": "Test User",
            "user_type": "employee"
        }
        
        response = client.post("/api/v1/auth/register", json=registration_data)
        assert response.status_code == 201
        
        data = response.json()
        assert "id" in data
        assert data["email"] == registration_data["email"]
        assert data["full_name"] == registration_data["full_name"]
        assert "password" not in data  # Password should not be returned
        
        user_id = data["id"]
        
        # Step 2: Verify user can login with credentials
        login_data = {
            "username": registration_data["email"],
            "password": registration_data["password"]
        }
        
        response = client.post("/api/v1/auth/login", data=login_data)
        assert response.status_code == 200
        
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
    
    def test_registration_with_duplicate_email(self, client):
        """Test registration fails with duplicate email"""
        # Register first user
        registration_data = {
            "email": "duplicate@example.com",
            "password": "Password123!",
            "full_name": "First User",
            "user_type": "employee"
        }
        
        response = client.post("/api/v1/auth/register", json=registration_data)
        assert response.status_code == 201
        
        # Try to register second user with same email
        registration_data["full_name"] = "Second User"
        response = client.post("/api/v1/auth/register", json=registration_data)
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()
    
    def test_registration_with_invalid_email(self, client):
        """Test registration fails with invalid email format"""
        registration_data = {
            "email": "invalid-email",
            "password": "Password123!",
            "full_name": "Test User",
            "user_type": "employee"
        }
        
        response = client.post("/api/v1/auth/register", json=registration_data)
        assert response.status_code == 422  # Validation error
    
    def test_registration_with_weak_password(self, client):
        """Test registration fails with weak password"""
        registration_data = {
            "email": "user@example.com",
            "password": "weak",
            "full_name": "Test User",
            "user_type": "employee"
        }
        
        response = client.post("/api/v1/auth/register", json=registration_data)
        assert response.status_code == 400
        assert "password" in response.json()["detail"].lower()
    
    def test_registration_with_all_user_types(self, client):
        """Test registration works for all user types"""
        user_types = ["employee", "self_employed", "landlord", "small_business"]
        
        for i, user_type in enumerate(user_types):
            registration_data = {
                "email": f"user{i}@example.com",
                "password": "Password123!",
                "full_name": f"User {i}",
                "user_type": user_type
            }
            
            response = client.post("/api/v1/auth/register", json=registration_data)
            assert response.status_code == 201
            assert response.json()["user_type"] == user_type


class TestLoginFlow:
    """Integration tests for login flow"""
    
    def test_login_without_2fa(self, client, test_user):
        """Test login flow for user without 2FA enabled"""
        login_data = {
            "username": test_user["email"],
            "password": "TestPassword123!"
        }
        
        response = client.post("/api/v1/auth/login", data=login_data)
        assert response.status_code == 200
        
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["two_factor_required"] is False
    
    def test_login_with_wrong_password(self, client, test_user):
        """Test login fails with incorrect password"""
        login_data = {
            "username": test_user["email"],
            "password": "WrongPassword123!"
        }
        
        response = client.post("/api/v1/auth/login", data=login_data)
        assert response.status_code == 401
        assert "incorrect" in response.json()["detail"].lower()
    
    def test_login_with_nonexistent_user(self, client):
        """Test login fails with non-existent user"""
        login_data = {
            "username": "nonexistent@example.com",
            "password": "Password123!"
        }
        
        response = client.post("/api/v1/auth/login", data=login_data)
        assert response.status_code == 401
    
    def test_login_returns_user_info(self, client, test_user):
        """Test login response includes user information"""
        login_data = {
            "username": test_user["email"],
            "password": "TestPassword123!"
        }
        
        response = client.post("/api/v1/auth/login", data=login_data)
        assert response.status_code == 200
        
        data = response.json()
        assert "user" in data
        assert data["user"]["email"] == test_user["email"]
        assert data["user"]["full_name"] == test_user["full_name"]
        assert "password" not in data["user"]


class TestTwoFactorAuthFlow:
    """Integration tests for 2FA setup and login flow"""
    
    def test_complete_2fa_setup_flow(self, client, authenticated_client):
        """Test complete 2FA setup workflow"""
        # Step 1: Request 2FA setup
        response = authenticated_client.post("/api/v1/auth/2fa/setup")
        assert response.status_code == 200
        
        data = response.json()
        assert "secret" in data
        assert "qr_code_uri" in data
        assert "backup_codes" in data
        assert len(data["backup_codes"]) == 10
        
        secret = data["secret"]
        
        # Step 2: Verify 2FA with generated code
        totp = pyotp.TOTP(secret)
        verification_code = totp.now()
        
        verify_data = {
            "token": verification_code
        }
        
        response = authenticated_client.post("/api/v1/auth/2fa/verify", json=verify_data)
        assert response.status_code == 200
        assert response.json()["two_factor_enabled"] is True
    
    def test_2fa_setup_requires_authentication(self, client):
        """Test 2FA setup requires authenticated user"""
        response = client.post("/api/v1/auth/2fa/setup")
        assert response.status_code == 401
    
    def test_2fa_verification_with_invalid_code(self, client, authenticated_client):
        """Test 2FA verification fails with invalid code"""
        # Setup 2FA
        response = authenticated_client.post("/api/v1/auth/2fa/setup")
        assert response.status_code == 200
        
        # Try to verify with invalid code
        verify_data = {
            "token": "000000"
        }
        
        response = authenticated_client.post("/api/v1/auth/2fa/verify", json=verify_data)
        assert response.status_code == 400
        assert "invalid" in response.json()["detail"].lower()
    
    def test_login_with_2fa_enabled(self, client, test_user_with_2fa):
        """Test login flow for user with 2FA enabled"""
        # Step 1: Initial login with password
        login_data = {
            "username": test_user_with_2fa["email"],
            "password": "TestPassword123!"
        }
        
        response = client.post("/api/v1/auth/login", data=login_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["two_factor_required"] is True
        assert "temp_token" in data
        assert "access_token" not in data  # Full token not issued yet
        
        temp_token = data["temp_token"]
        
        # Step 2: Complete login with 2FA code
        totp = pyotp.TOTP(test_user_with_2fa["two_factor_secret"])
        two_factor_code = totp.now()
        
        verify_data = {
            "temp_token": temp_token,
            "token": two_factor_code
        }
        
        response = client.post("/api/v1/auth/2fa/login", json=verify_data)
        assert response.status_code == 200
        
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
    
    def test_2fa_login_with_invalid_code(self, client, test_user_with_2fa):
        """Test 2FA login fails with invalid code"""
        # Initial login
        login_data = {
            "username": test_user_with_2fa["email"],
            "password": "TestPassword123!"
        }
        
        response = client.post("/api/v1/auth/login", data=login_data)
        temp_token = response.json()["temp_token"]
        
        # Try with invalid 2FA code
        verify_data = {
            "temp_token": temp_token,
            "token": "000000"
        }
        
        response = client.post("/api/v1/auth/2fa/login", json=verify_data)
        assert response.status_code == 401
    
    def test_2fa_login_with_backup_code(self, client, test_user_with_2fa):
        """Test 2FA login works with backup code"""
        # Initial login
        login_data = {
            "username": test_user_with_2fa["email"],
            "password": "TestPassword123!"
        }
        
        response = client.post("/api/v1/auth/login", data=login_data)
        temp_token = response.json()["temp_token"]
        
        # Use backup code
        backup_code = test_user_with_2fa["backup_codes"][0]
        
        verify_data = {
            "temp_token": temp_token,
            "token": backup_code,
            "is_backup_code": True
        }
        
        response = client.post("/api/v1/auth/2fa/login", json=verify_data)
        assert response.status_code == 200
        assert "access_token" in response.json()
    
    def test_backup_code_can_only_be_used_once(self, client, test_user_with_2fa):
        """Test backup code becomes invalid after use"""
        backup_code = test_user_with_2fa["backup_codes"][0]
        
        # Use backup code first time
        login_data = {
            "username": test_user_with_2fa["email"],
            "password": "TestPassword123!"
        }
        response = client.post("/api/v1/auth/login", data=login_data)
        temp_token = response.json()["temp_token"]
        
        verify_data = {
            "temp_token": temp_token,
            "token": backup_code,
            "is_backup_code": True
        }
        response = client.post("/api/v1/auth/2fa/login", json=verify_data)
        assert response.status_code == 200
        
        # Try to use same backup code again
        response = client.post("/api/v1/auth/login", data=login_data)
        temp_token = response.json()["temp_token"]
        
        verify_data["temp_token"] = temp_token
        response = client.post("/api/v1/auth/2fa/login", json=verify_data)
        assert response.status_code == 401
    
    def test_disable_2fa(self, client, authenticated_client_with_2fa):
        """Test disabling 2FA"""
        response = authenticated_client_with_2fa.post("/api/v1/auth/2fa/disable")
        assert response.status_code == 200
        assert response.json()["two_factor_enabled"] is False


class TestTokenRefresh:
    """Integration tests for token refresh flow"""
    
    def test_refresh_access_token(self, client, test_user):
        """Test refreshing access token with refresh token"""
        # Login to get tokens
        login_data = {
            "username": test_user["email"],
            "password": "TestPassword123!"
        }
        
        response = client.post("/api/v1/auth/login", data=login_data)
        assert response.status_code == 200
        
        tokens = response.json()
        refresh_token = tokens["refresh_token"]
        
        # Refresh the access token
        refresh_data = {
            "refresh_token": refresh_token
        }
        
        response = client.post("/api/v1/auth/refresh", json=refresh_data)
        assert response.status_code == 200
        
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        
        # New access token should be different
        assert data["access_token"] != tokens["access_token"]
    
    def test_refresh_with_invalid_token(self, client):
        """Test refresh fails with invalid refresh token"""
        refresh_data = {
            "refresh_token": "invalid_token_here"
        }
        
        response = client.post("/api/v1/auth/refresh", json=refresh_data)
        assert response.status_code == 401
    
    def test_refresh_with_expired_token(self, client, test_user):
        """Test refresh fails with expired refresh token"""
        # This would require creating an expired token
        # Implementation depends on how tokens are generated
        pass
    
    def test_access_protected_endpoint_with_refreshed_token(self, client, test_user):
        """Test that refreshed token works for protected endpoints"""
        # Login
        login_data = {
            "username": test_user["email"],
            "password": "TestPassword123!"
        }
        response = client.post("/api/v1/auth/login", data=login_data)
        refresh_token = response.json()["refresh_token"]
        
        # Refresh token
        refresh_data = {"refresh_token": refresh_token}
        response = client.post("/api/v1/auth/refresh", json=refresh_data)
        new_access_token = response.json()["access_token"]
        
        # Use new token to access protected endpoint
        headers = {"Authorization": f"Bearer {new_access_token}"}
        response = client.get("/api/v1/users/me", headers=headers)
        assert response.status_code == 200
        assert response.json()["email"] == test_user["email"]


class TestSessionManagement:
    """Integration tests for session management"""
    
    def test_logout_invalidates_token(self, client, authenticated_client):
        """Test logout invalidates the access token"""
        # Access protected endpoint (should work)
        response = authenticated_client.get("/api/v1/users/me")
        assert response.status_code == 200
        
        # Logout
        response = authenticated_client.post("/api/v1/auth/logout")
        assert response.status_code == 200
        
        # Try to access protected endpoint again (should fail)
        response = authenticated_client.get("/api/v1/users/me")
        assert response.status_code == 401
    
    def test_session_timeout(self, client, test_user):
        """Test session expires after timeout period"""
        # This would require time manipulation or waiting
        # Implementation depends on session timeout configuration
        pass
    
    def test_concurrent_sessions(self, client, test_user):
        """Test user can have multiple active sessions"""
        login_data = {
            "username": test_user["email"],
            "password": "TestPassword123!"
        }
        
        # Create first session
        response1 = client.post("/api/v1/auth/login", data=login_data)
        assert response1.status_code == 200
        token1 = response1.json()["access_token"]
        
        # Create second session
        response2 = client.post("/api/v1/auth/login", data=login_data)
        assert response2.status_code == 200
        token2 = response2.json()["access_token"]
        
        # Both tokens should work
        headers1 = {"Authorization": f"Bearer {token1}"}
        headers2 = {"Authorization": f"Bearer {token2}"}
        
        response = client.get("/api/v1/users/me", headers=headers1)
        assert response.status_code == 200
        
        response = client.get("/api/v1/users/me", headers=headers2)
        assert response.status_code == 200
    
    def test_access_protected_endpoint_without_token(self, client):
        """Test accessing protected endpoint without token fails"""
        response = client.get("/api/v1/users/me")
        assert response.status_code == 401
    
    def test_access_protected_endpoint_with_invalid_token(self, client):
        """Test accessing protected endpoint with invalid token fails"""
        headers = {"Authorization": "Bearer invalid_token_here"}
        response = client.get("/api/v1/users/me", headers=headers)
        assert response.status_code == 401


class TestPasswordReset:
    """Integration tests for password reset flow"""
    
    def test_request_password_reset(self, client, test_user):
        """Test requesting password reset"""
        reset_data = {
            "email": test_user["email"]
        }
        
        response = client.post("/api/v1/auth/password-reset/request", json=reset_data)
        assert response.status_code == 200
        assert "message" in response.json()
    
    def test_password_reset_with_token(self, client, test_user, password_reset_token):
        """Test resetting password with valid token"""
        new_password = "NewSecurePassword123!"
        
        reset_data = {
            "token": password_reset_token,
            "new_password": new_password
        }
        
        response = client.post("/api/v1/auth/password-reset/confirm", json=reset_data)
        assert response.status_code == 200
        
        # Verify can login with new password
        login_data = {
            "username": test_user["email"],
            "password": new_password
        }
        
        response = client.post("/api/v1/auth/login", data=login_data)
        assert response.status_code == 200
    
    def test_password_reset_with_invalid_token(self, client):
        """Test password reset fails with invalid token"""
        reset_data = {
            "token": "invalid_token",
            "new_password": "NewPassword123!"
        }
        
        response = client.post("/api/v1/auth/password-reset/confirm", json=reset_data)
        assert response.status_code == 400
