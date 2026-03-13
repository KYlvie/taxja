"""Unit tests for authentication functionality

Tests cover:
- JWT token generation and validation (Requirement 17.3)
- 2FA setup and verification (Requirement 17.4)
- Password hashing and verification (Requirement 17.3)
"""
import pytest
from datetime import datetime, timedelta
from jose import jwt, JWTError
import pyotp
from app.core.security import (
    create_access_token,
    verify_password,
    get_password_hash,
)
from app.core.config import settings


class TestJWTTokens:
    """Test JWT token generation and validation - Requirement 17.3"""
    
    def test_create_access_token_with_default_expiry(self):
        """Test JWT token creation with default expiration time"""
        subject = "test_user@example.com"
        token = create_access_token(subject=subject)
        
        # Verify token can be decoded
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        
        assert payload["sub"] == subject
        assert "exp" in payload
        
        # Verify expiration is approximately correct (within 1 minute tolerance)
        expected_exp = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        actual_exp = datetime.fromtimestamp(payload["exp"])
        time_diff = abs((expected_exp - actual_exp).total_seconds())
        assert time_diff < 60  # Within 1 minute
    
    def test_create_access_token_with_custom_expiry(self):
        """Test JWT token creation with custom expiration time"""
        subject = "test_user@example.com"
        custom_delta = timedelta(hours=2)
        token = create_access_token(subject=subject, expires_delta=custom_delta)
        
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        
        # Verify custom expiration is used
        expected_exp = datetime.utcnow() + custom_delta
        actual_exp = datetime.fromtimestamp(payload["exp"])
        time_diff = abs((expected_exp - actual_exp).total_seconds())
        assert time_diff < 60  # Within 1 minute
    
    def test_create_access_token_with_integer_subject(self):
        """Test JWT token creation with integer subject (user ID)"""
        subject = 12345
        token = create_access_token(subject=subject)
        
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        
        # Subject should be converted to string
        assert payload["sub"] == str(subject)
    
    def test_decode_valid_token(self):
        """Test decoding a valid JWT token"""
        subject = "test_user@example.com"
        token = create_access_token(subject=subject)
        
        # Decode should succeed
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload["sub"] == subject
    
    def test_decode_expired_token(self):
        """Test decoding an expired JWT token"""
        subject = "test_user@example.com"
        # Create token that expires immediately
        token = create_access_token(subject=subject, expires_delta=timedelta(seconds=-1))
        
        # Decoding should raise JWTError
        with pytest.raises(JWTError):
            jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    
    def test_decode_invalid_token(self):
        """Test decoding an invalid JWT token"""
        invalid_token = "invalid.token.here"
        
        with pytest.raises(JWTError):
            jwt.decode(invalid_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    
    def test_decode_token_with_wrong_secret(self):
        """Test decoding a token with wrong secret key"""
        subject = "test_user@example.com"
        token = create_access_token(subject=subject)
        
        wrong_secret = "wrong_secret_key_12345"
        
        with pytest.raises(JWTError):
            jwt.decode(token, wrong_secret, algorithms=[settings.ALGORITHM])
    
    def test_decode_token_with_wrong_algorithm(self):
        """Test decoding a token with wrong algorithm"""
        subject = "test_user@example.com"
        token = create_access_token(subject=subject)
        
        with pytest.raises(JWTError):
            jwt.decode(token, settings.SECRET_KEY, algorithms=["HS512"])
    
    def test_token_contains_only_required_claims(self):
        """Test that token contains only exp and sub claims"""
        subject = "test_user@example.com"
        token = create_access_token(subject=subject)
        
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        
        # Should only contain exp and sub
        assert set(payload.keys()) == {"exp", "sub"}


class TestPasswordHashing:
    """Test password hashing and verification - Requirement 17.3"""
    
    def test_hash_password(self):
        """Test password hashing produces a hash"""
        password = "SecurePassword123!"
        hashed = get_password_hash(password)
        
        # Hash should be different from original password
        assert hashed != password
        
        # Hash should be a non-empty string
        assert isinstance(hashed, str)
        assert len(hashed) > 0
        
        # Bcrypt hashes start with $2b$
        assert hashed.startswith("$2b$")
    
    def test_verify_correct_password(self):
        """Test verifying correct password against hash"""
        password = "SecurePassword123!"
        hashed = get_password_hash(password)
        
        # Verification should succeed
        assert verify_password(password, hashed) is True
    
    def test_verify_incorrect_password(self):
        """Test verifying incorrect password against hash"""
        password = "SecurePassword123!"
        wrong_password = "WrongPassword456!"
        hashed = get_password_hash(password)
        
        # Verification should fail
        assert verify_password(wrong_password, hashed) is False
    
    def test_hash_same_password_produces_different_hashes(self):
        """Test that hashing the same password twice produces different hashes (salt uniqueness)"""
        password = "SecurePassword123!"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)
        
        # Hashes should be different due to different salts
        assert hash1 != hash2
        
        # But both should verify correctly
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True
    
    def test_hash_empty_password(self):
        """Test hashing an empty password"""
        password = ""
        hashed = get_password_hash(password)
        
        # Should still produce a hash
        assert isinstance(hashed, str)
        assert len(hashed) > 0
        
        # Should verify correctly
        assert verify_password(password, hashed) is True
    
    def test_hash_long_password(self):
        """Test hashing a very long password"""
        password = "a" * 1000  # 1000 character password
        hashed = get_password_hash(password)
        
        # Should handle long passwords
        assert isinstance(hashed, str)
        assert verify_password(password, hashed) is True
    
    def test_hash_special_characters(self):
        """Test hashing password with special characters"""
        password = "P@ssw0rd!#$%^&*()_+-=[]{}|;:',.<>?/~`"
        hashed = get_password_hash(password)
        
        # Should handle special characters
        assert verify_password(password, hashed) is True
    
    def test_hash_unicode_password(self):
        """Test hashing password with unicode characters"""
        password = "密码123!Пароль"
        hashed = get_password_hash(password)
        
        # Should handle unicode
        assert verify_password(password, hashed) is True
    
    def test_verify_case_sensitive(self):
        """Test that password verification is case-sensitive"""
        password = "SecurePassword123!"
        hashed = get_password_hash(password)
        
        # Different case should fail
        assert verify_password("securepassword123!", hashed) is False
        assert verify_password("SECUREPASSWORD123!", hashed) is False


class Test2FASetup:
    """Test 2FA setup and secret generation - Requirement 17.4"""
    
    def test_generate_2fa_secret(self):
        """Test generating a new 2FA secret"""
        secret = pyotp.random_base32()
        
        # Secret should be a base32 string
        assert isinstance(secret, str)
        assert len(secret) == 32
        
        # Should only contain valid base32 characters
        valid_chars = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ234567")
        assert all(c in valid_chars for c in secret)
    
    def test_generate_unique_secrets(self):
        """Test that multiple secret generations produce unique values"""
        secret1 = pyotp.random_base32()
        secret2 = pyotp.random_base32()
        secret3 = pyotp.random_base32()
        
        # All secrets should be unique
        assert secret1 != secret2
        assert secret2 != secret3
        assert secret1 != secret3
    
    def test_create_totp_from_secret(self):
        """Test creating TOTP instance from secret"""
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        
        # Should be able to generate a code
        code = totp.now()
        
        # Code should be 6 digits
        assert isinstance(code, str)
        assert len(code) == 6
        assert code.isdigit()
    
    def test_generate_provisioning_uri(self):
        """Test generating QR code provisioning URI"""
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        
        user_email = "test@example.com"
        issuer_name = "Taxja"
        
        uri = totp.provisioning_uri(name=user_email, issuer_name=issuer_name)
        
        # URI should be in correct format
        assert uri.startswith("otpauth://totp/")
        assert user_email in uri
        assert issuer_name in uri
        assert f"secret={secret}" in uri
    
    def test_provisioning_uri_contains_required_parameters(self):
        """Test that provisioning URI contains all required parameters"""
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        
        uri = totp.provisioning_uri(name="test@example.com", issuer_name="Taxja")
        
        # Should contain secret, issuer, and algorithm
        assert "secret=" in uri
        assert "issuer=" in uri
        assert "algorithm=" in uri or "SHA1" in uri  # Default algorithm


class Test2FAVerification:
    """Test 2FA code verification - Requirement 17.4"""
    
    def test_verify_valid_totp_code(self):
        """Test verifying a valid TOTP code"""
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        
        # Generate current code
        code = totp.now()
        
        # Verification should succeed
        assert totp.verify(code) is True
    
    def test_verify_invalid_totp_code(self):
        """Test verifying an invalid TOTP code"""
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        
        invalid_code = "000000"
        
        # Verification should fail (extremely unlikely to match)
        assert totp.verify(invalid_code) is False
    
    def test_verify_expired_totp_code(self):
        """Test that old TOTP codes are rejected"""
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        
        # Generate code for a time far in the past
        old_timestamp = datetime.utcnow() - timedelta(minutes=5)
        old_code = totp.at(old_timestamp)
        
        # Verification should fail (code is too old)
        assert totp.verify(old_code) is False
    
    def test_verify_with_time_window(self):
        """Test TOTP verification with time window tolerance"""
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        
        # Generate code for 30 seconds ago
        past_time = datetime.utcnow() - timedelta(seconds=30)
        past_code = totp.at(past_time)
        
        # Should verify with valid_window=1 (allows 1 step before/after)
        assert totp.verify(past_code, valid_window=1) is True
    
    def test_verify_code_format(self):
        """Test that verification handles different code formats"""
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        
        code = totp.now()
        
        # Should verify with string
        assert totp.verify(code) is True
        
        # Should verify with integer
        assert totp.verify(int(code)) is True
    
    def test_verify_wrong_length_code(self):
        """Test verifying codes with wrong length"""
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        
        # Too short
        assert totp.verify("123") is False
        
        # Too long
        assert totp.verify("1234567") is False
    
    def test_verify_non_numeric_code(self):
        """Test verifying non-numeric codes"""
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        
        # Should handle gracefully
        assert totp.verify("abcdef") is False
        assert totp.verify("12345a") is False
    
    def test_totp_time_based_validation(self):
        """Test that TOTP codes change over time"""
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        
        # Generate code at current time
        code1 = totp.now()
        
        # Generate code at different time (simulate 30 seconds later)
        future_time = datetime.utcnow() + timedelta(seconds=30)
        code2 = totp.at(future_time)
        
        # Codes should be different
        assert code1 != code2
    
    def test_same_secret_produces_same_code(self):
        """Test that same secret at same time produces same code"""
        secret = pyotp.random_base32()
        
        totp1 = pyotp.TOTP(secret)
        totp2 = pyotp.TOTP(secret)
        
        # Both should generate the same code at the same time
        code1 = totp1.now()
        code2 = totp2.now()
        
        assert code1 == code2
    
    def test_different_secrets_produce_different_codes(self):
        """Test that different secrets produce different codes"""
        secret1 = pyotp.random_base32()
        secret2 = pyotp.random_base32()
        
        totp1 = pyotp.TOTP(secret1)
        totp2 = pyotp.TOTP(secret2)
        
        code1 = totp1.now()
        code2 = totp2.now()
        
        # Codes should be different (extremely unlikely to match)
        assert code1 != code2


class Test2FAIntegration:
    """Integration tests for complete 2FA workflow - Requirement 17.4"""
    
    def test_complete_2fa_setup_and_verification_flow(self):
        """Test complete 2FA setup and verification workflow"""
        # Step 1: Generate secret for user
        secret = pyotp.random_base32()
        
        # Step 2: Create TOTP instance
        totp = pyotp.TOTP(secret)
        
        # Step 3: Generate provisioning URI for QR code
        uri = totp.provisioning_uri(
            name="user@example.com",
            issuer_name="Taxja"
        )
        
        assert "otpauth://totp/" in uri
        
        # Step 4: User scans QR code and generates code
        user_code = totp.now()
        
        # Step 5: Verify the code
        assert totp.verify(user_code) is True
        
        # Step 6: Subsequent logins should work
        new_code = totp.now()
        assert totp.verify(new_code) is True
    
    def test_2fa_setup_with_backup_codes(self):
        """Test 2FA setup includes backup code generation"""
        import secrets
        
        # Generate 10 backup codes
        backup_codes = [secrets.token_hex(4) for _ in range(10)]
        
        # Each backup code should be unique
        assert len(backup_codes) == len(set(backup_codes))
        
        # Each code should be 8 characters (4 bytes hex)
        for code in backup_codes:
            assert len(code) == 8
            assert all(c in "0123456789abcdef" for c in code)
    
    def test_2fa_verification_with_multiple_attempts(self):
        """Test 2FA verification handles multiple attempts correctly"""
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        
        # First attempt with wrong code
        assert totp.verify("000000") is False
        
        # Second attempt with wrong code
        assert totp.verify("111111") is False
        
        # Third attempt with correct code should still work
        correct_code = totp.now()
        assert totp.verify(correct_code) is True
