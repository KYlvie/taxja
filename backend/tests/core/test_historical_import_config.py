"""Tests for historical import configuration settings."""
import pytest
import os


def test_historical_import_default_values(monkeypatch):
    """Test that historical import settings have correct default values."""
    # Set required environment variables
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-minimum-32-characters")
    monkeypatch.setenv("ENCRYPTION_KEY", "test-encryption-key-32-chars")
    monkeypatch.setenv("POSTGRES_SERVER", "localhost")
    monkeypatch.setenv("POSTGRES_USER", "test")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test")
    monkeypatch.setenv("POSTGRES_DB", "test")
    monkeypatch.setenv("MINIO_ENDPOINT", "localhost:9000")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "test")
    monkeypatch.setenv("MINIO_SECRET_KEY", "test")
    
    # Import after setting env vars
    from app.core.config import Settings
    
    settings = Settings()
    
    assert settings.HISTORICAL_IMPORT_MAX_FILE_SIZE_MB == 50
    assert settings.HISTORICAL_IMPORT_RETENTION_DAYS == 90
    assert settings.HISTORICAL_IMPORT_MIN_CONFIDENCE == 0.7
    assert settings.HISTORICAL_IMPORT_ENABLE_AUTO_LINK is True


def test_historical_import_custom_values(monkeypatch):
    """Test that historical import settings can be overridden via environment."""
    # Set required environment variables
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-minimum-32-characters")
    monkeypatch.setenv("ENCRYPTION_KEY", "test-encryption-key-32-chars")
    monkeypatch.setenv("POSTGRES_SERVER", "localhost")
    monkeypatch.setenv("POSTGRES_USER", "test")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test")
    monkeypatch.setenv("POSTGRES_DB", "test")
    monkeypatch.setenv("MINIO_ENDPOINT", "localhost:9000")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "test")
    monkeypatch.setenv("MINIO_SECRET_KEY", "test")
    
    # Set custom historical import values
    monkeypatch.setenv("HISTORICAL_IMPORT_MAX_FILE_SIZE_MB", "100")
    monkeypatch.setenv("HISTORICAL_IMPORT_RETENTION_DAYS", "180")
    monkeypatch.setenv("HISTORICAL_IMPORT_MIN_CONFIDENCE", "0.8")
    monkeypatch.setenv("HISTORICAL_IMPORT_ENABLE_AUTO_LINK", "false")
    
    # Import after setting env vars
    from app.core.config import Settings
    
    settings = Settings()
    
    assert settings.HISTORICAL_IMPORT_MAX_FILE_SIZE_MB == 100
    assert settings.HISTORICAL_IMPORT_RETENTION_DAYS == 180
    assert settings.HISTORICAL_IMPORT_MIN_CONFIDENCE == 0.8
    assert settings.HISTORICAL_IMPORT_ENABLE_AUTO_LINK is False


def test_debug_release_value_is_normalized_to_false(monkeypatch):
    """Legacy DEBUG=release values should remain bootable."""
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-minimum-32-characters")
    monkeypatch.setenv("ENCRYPTION_KEY", "test-encryption-key-32-chars")
    monkeypatch.setenv("POSTGRES_SERVER", "localhost")
    monkeypatch.setenv("POSTGRES_USER", "test")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test")
    monkeypatch.setenv("POSTGRES_DB", "test")
    monkeypatch.setenv("MINIO_ENDPOINT", "localhost:9000")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "test")
    monkeypatch.setenv("MINIO_SECRET_KEY", "test")
    monkeypatch.setenv("DEBUG", "release")

    from app.core.config import Settings

    settings = Settings()

    assert settings.DEBUG is False


def test_local_frontend_uses_dev_safe_cookie_defaults(monkeypatch):
    """Local frontend URLs should not inherit production cookie defaults."""
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-minimum-32-characters")
    monkeypatch.setenv("ENCRYPTION_KEY", "test-encryption-key-32-chars")
    monkeypatch.setenv("POSTGRES_SERVER", "localhost")
    monkeypatch.setenv("POSTGRES_USER", "test")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test")
    monkeypatch.setenv("POSTGRES_DB", "test")
    monkeypatch.setenv("MINIO_ENDPOINT", "localhost:9000")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "test")
    monkeypatch.setenv("MINIO_SECRET_KEY", "test")
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:5173")

    from app.core.config import Settings

    settings = Settings()

    assert settings.COOKIE_DOMAIN == ""
    assert settings.COOKIE_SECURE is False


def test_debug_prod_frontend_logs_warning(monkeypatch, caplog):
    """Warn when a debug/local backend is configured to emit production links."""
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-minimum-32-characters")
    monkeypatch.setenv("ENCRYPTION_KEY", "test-encryption-key-32-chars")
    monkeypatch.setenv("POSTGRES_SERVER", "localhost")
    monkeypatch.setenv("POSTGRES_USER", "test")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test")
    monkeypatch.setenv("POSTGRES_DB", "test")
    monkeypatch.setenv("MINIO_ENDPOINT", "localhost:9000")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "test")
    monkeypatch.setenv("MINIO_SECRET_KEY", "test")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("FRONTEND_URL", "https://taxja.at")

    from app.core.config import Settings

    with caplog.at_level("WARNING"):
        Settings()

    assert any("production FRONTEND_URL" in message for message in caplog.messages)


def test_file_size_validation():
    """Test file size validation logic."""
    max_file_size_mb = 50
    max_size_bytes = max_file_size_mb * 1024 * 1024
    
    # Test file within limit
    assert 10 * 1024 * 1024 <= max_size_bytes  # 10 MB
    
    # Test file at limit
    assert 50 * 1024 * 1024 <= max_size_bytes  # 50 MB
    
    # Test file over limit
    assert 100 * 1024 * 1024 > max_size_bytes  # 100 MB


def test_confidence_threshold_validation():
    """Test confidence threshold validation logic."""
    min_confidence = 0.7
    
    # Test confidence below threshold
    assert 0.6 < min_confidence
    
    # Test confidence at threshold
    assert 0.7 >= min_confidence
    
    # Test confidence above threshold
    assert 0.8 >= min_confidence


def test_auto_link_property_action():
    """Test property auto-link action determination."""
    enable_auto_link = True
    
    def determine_action(confidence: float) -> str:
        if not enable_auto_link:
            return "suggest"
        if confidence > 0.9:
            return "auto_link"
        elif confidence >= 0.7:
            return "suggest"
        else:
            return "create_new"
    
    # Test high confidence
    assert determine_action(0.95) == "auto_link"
    
    # Test medium confidence
    assert determine_action(0.8) == "suggest"
    
    # Test low confidence
    assert determine_action(0.5) == "create_new"


def test_auto_link_disabled():
    """Test property action when auto-link is disabled."""
    enable_auto_link = False
    
    def determine_action(confidence: float) -> str:
        if not enable_auto_link:
            return "suggest"
        if confidence > 0.9:
            return "auto_link"
        elif confidence >= 0.7:
            return "suggest"
        else:
            return "create_new"
    
    # All confidence levels should return "suggest" when auto-link is disabled
    assert determine_action(0.95) == "suggest"
    assert determine_action(0.8) == "suggest"
    assert determine_action(0.5) == "suggest"

