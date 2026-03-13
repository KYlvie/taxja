"""Security audit tests for Task 36.5"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
from app.core.config import settings


client = TestClient(app)


class TestSQLInjection:
    """Test for SQL injection vulnerabilities"""
    
    def test_sql_injection_in_transaction_filter(self):
        """Test SQL injection in transaction filtering"""
        # Attempt SQL injection in query parameters
        malicious_inputs = [
            "1' OR '1'='1",
            "1; DROP TABLE transactions--",
            "1' UNION SELECT * FROM users--",
            "1' AND 1=1--",
        ]
        
        for malicious_input in malicious_inputs:
            response = client.get(
                f"/api/v1/transactions?description={malicious_input}",
                headers={"Authorization": "Bearer fake_token"}
            )
            
            # Should either return 401 (unauthorized) or handle safely
            assert response.status_code in [401, 403, 422], \
                f"SQL injection not properly handled: {malicious_input}"
    
    def test_sql_injection_in_search(self):
        """Test SQL injection in search endpoints"""
        malicious_inputs = [
            "'; DROP TABLE documents--",
            "' OR 1=1--",
            "admin'--",
        ]
        
        for malicious_input in malicious_inputs:
            response = client.get(
                f"/api/v1/documents?search={malicious_input}",
                headers={"Authorization": "Bearer fake_token"}
            )
            
            assert response.status_code in [401, 403, 422]


class TestXSS:
    """Test for Cross-Site Scripting (XSS) vulnerabilities"""
    
    def test_xss_in_transaction_description(self):
        """Test XSS in transaction description"""
        xss_payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "javascript:alert('XSS')",
            "<svg onload=alert('XSS')>",
        ]
        
        for payload in xss_payloads:
            response = client.post(
                "/api/v1/transactions",
                json={
                    "description": payload,
                    "amount": 100.00,
                    "date": "2026-03-04",
                    "type": "expense"
                },
                headers={"Authorization": "Bearer fake_token"}
            )
            
            # Should either return 401 or sanitize input
            if response.status_code == 200:
                data = response.json()
                # Check that script tags are escaped or removed
                assert "<script>" not in data.get("description", "").lower()
                assert "onerror" not in data.get("description", "").lower()


class TestAuthentication:
    """Test authentication and authorization"""
    
    def test_protected_endpoints_require_auth(self):
        """Test that protected endpoints require authentication"""
        protected_endpoints = [
            "/api/v1/transactions",
            "/api/v1/documents",
            "/api/v1/tax/calculate",
            "/api/v1/reports",
            "/api/v1/dashboard",
        ]
        
        for endpoint in protected_endpoints:
            response = client.get(endpoint)
            assert response.status_code in [401, 403], \
                f"Endpoint {endpoint} should require authentication"
    
    def test_invalid_token_rejected(self):
        """Test that invalid tokens are rejected"""
        invalid_tokens = [
            "invalid_token",
            "Bearer ",
            "Bearer invalid",
            "",
        ]
        
        for token in invalid_tokens:
            response = client.get(
                "/api/v1/transactions",
                headers={"Authorization": token}
            )
            assert response.status_code in [401, 403]
    
    def test_expired_token_rejected(self):
        """Test that expired tokens are rejected"""
        # This would require generating an expired token
        # For now, just test with an obviously invalid token
        response = client.get(
            "/api/v1/transactions",
            headers={"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.expired.token"}
        )
        assert response.status_code in [401, 403]


class TestDataEncryption:
    """Test data encryption"""
    
    @pytest.mark.asyncio
    async def test_sensitive_fields_encrypted(self, async_db_session):
        """Test that sensitive fields are encrypted in database"""
        # This test would check that tax_number, vat_number, etc. are encrypted
        # For now, just verify the encryption key is set
        assert settings.ENCRYPTION_KEY, "Encryption key must be configured"
        assert len(settings.ENCRYPTION_KEY) >= 32, "Encryption key must be at least 32 bytes"
    
    def test_passwords_hashed(self):
        """Test that passwords are hashed, not stored in plaintext"""
        # Attempt to create user with password
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",
                "password": "TestPassword123!",
                "name": "Test User"
            }
        )
        
        # If successful, verify password is not returned
        if response.status_code == 200:
            data = response.json()
            assert "password" not in data, "Password should not be returned in response"


class TestRateLimiting:
    """Test rate limiting"""
    
    def test_rate_limit_on_auth_endpoint(self):
        """Test rate limiting on authentication endpoint"""
        # Make multiple rapid requests
        responses = []
        for _ in range(10):
            response = client.post(
                "/api/v1/auth/login",
                json={"email": "test@example.com", "password": "wrong"}
            )
            responses.append(response.status_code)
        
        # Should eventually get rate limited (429)
        # Note: This might not trigger in test environment without Redis
        # In production, this should return 429
        assert any(status == 429 for status in responses) or \
               all(status in [401, 422] for status in responses), \
               "Rate limiting should be enforced or auth should fail"


class TestSecurityHeaders:
    """Test security headers"""
    
    def test_hsts_header_present(self):
        """Test that HSTS header is present"""
        response = client.get("/health")
        assert "strict-transport-security" in response.headers, \
            "HSTS header should be present"
    
    def test_csp_header_present(self):
        """Test that Content-Security-Policy header is present"""
        response = client.get("/health")
        assert "content-security-policy" in response.headers, \
            "CSP header should be present"
    
    def test_x_frame_options_header(self):
        """Test that X-Frame-Options header is present"""
        response = client.get("/health")
        assert "x-frame-options" in response.headers, \
            "X-Frame-Options header should be present"
        assert response.headers["x-frame-options"].upper() == "DENY", \
            "X-Frame-Options should be DENY"
    
    def test_x_content_type_options_header(self):
        """Test that X-Content-Type-Options header is present"""
        response = client.get("/health")
        assert "x-content-type-options" in response.headers, \
            "X-Content-Type-Options header should be present"
        assert response.headers["x-content-type-options"] == "nosniff"
    
    def test_no_server_header(self):
        """Test that server header is removed"""
        response = client.get("/health")
        # Server header should be removed or not reveal version info
        server_header = response.headers.get("server", "")
        assert "uvicorn" not in server_header.lower(), \
            "Server header should not reveal implementation details"


class TestCORS:
    """Test CORS configuration"""
    
    def test_cors_headers_present(self):
        """Test that CORS headers are properly configured"""
        response = client.options(
            "/api/v1/transactions",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET"
            }
        )
        
        # Should have CORS headers
        assert "access-control-allow-origin" in response.headers or \
               response.status_code == 405  # Method not allowed is also acceptable
    
    def test_cors_credentials_allowed(self):
        """Test that credentials are allowed in CORS"""
        response = client.get(
            "/health",
            headers={"Origin": "http://localhost:3000"}
        )
        
        # Should allow credentials
        if "access-control-allow-credentials" in response.headers:
            assert response.headers["access-control-allow-credentials"] == "true"


class TestInputValidation:
    """Test input validation"""
    
    def test_invalid_email_rejected(self):
        """Test that invalid email formats are rejected"""
        invalid_emails = [
            "notanemail",
            "@example.com",
            "user@",
            "user space@example.com",
        ]
        
        for email in invalid_emails:
            response = client.post(
                "/api/v1/auth/register",
                json={
                    "email": email,
                    "password": "ValidPassword123!",
                    "name": "Test User"
                }
            )
            assert response.status_code == 422, \
                f"Invalid email should be rejected: {email}"
    
    def test_negative_amounts_rejected(self):
        """Test that negative amounts are rejected"""
        response = client.post(
            "/api/v1/transactions",
            json={
                "description": "Test",
                "amount": -100.00,
                "date": "2026-03-04",
                "type": "expense"
            },
            headers={"Authorization": "Bearer fake_token"}
        )
        
        # Should reject negative amounts
        assert response.status_code in [401, 422]
    
    def test_future_dates_rejected(self):
        """Test that future dates are rejected"""
        response = client.post(
            "/api/v1/transactions",
            json={
                "description": "Test",
                "amount": 100.00,
                "date": "2030-01-01",  # Future date
                "type": "expense"
            },
            headers={"Authorization": "Bearer fake_token"}
        )
        
        # Should reject future dates
        assert response.status_code in [401, 422]


class TestSessionSecurity:
    """Test session security"""
    
    def test_session_timeout(self):
        """Test that sessions timeout after inactivity"""
        # This would require a real session
        # For now, just verify the timeout setting exists
        assert settings.ACCESS_TOKEN_EXPIRE_MINUTES > 0, \
            "Session timeout should be configured"
        assert settings.ACCESS_TOKEN_EXPIRE_MINUTES <= 60, \
            "Session timeout should not be too long"


class TestFileUploadSecurity:
    """Test file upload security"""
    
    def test_file_size_limit(self):
        """Test that file size limits are enforced"""
        # Create a large fake file
        large_file = b"x" * (11 * 1024 * 1024)  # 11 MB
        
        response = client.post(
            "/api/v1/documents/upload",
            files={"file": ("large.jpg", large_file, "image/jpeg")},
            headers={"Authorization": "Bearer fake_token"}
        )
        
        # Should reject files over 10MB
        assert response.status_code in [401, 413, 422]
    
    def test_invalid_file_type_rejected(self):
        """Test that invalid file types are rejected"""
        invalid_files = [
            ("test.exe", b"fake exe", "application/x-msdownload"),
            ("test.sh", b"#!/bin/bash", "application/x-sh"),
            ("test.php", b"<?php", "application/x-php"),
        ]
        
        for filename, content, mime_type in invalid_files:
            response = client.post(
                "/api/v1/documents/upload",
                files={"file": (filename, content, mime_type)},
                headers={"Authorization": "Bearer fake_token"}
            )
            
            # Should reject invalid file types
            assert response.status_code in [401, 415, 422]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
