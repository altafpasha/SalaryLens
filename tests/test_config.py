"""
Unit tests for configuration and security validation
"""
import pytest
from app.core.config import Settings


def test_default_settings():
    s = Settings(
        SECRET_KEY="test_secret_key_12345_at_least_32_characters",
        AUTH_SECRET_KEY="test_auth_secret_key_12345_at_least_32_characters",
    )
    assert s.APP_NAME == "SalaryLens AI by CodeSec"
    assert s.API_V1_STR == "/api/v1"
    assert s.MAX_UPLOAD_SIZE_MB == 50
    assert s.MAX_DOCUMENT_PAGES == 120


def test_cors_origins_parsing():
    s = Settings(
        CORS_ORIGINS=["http://localhost:3000", "http://example.com"]
    )
    assert "http://localhost:3000" in s.CORS_ORIGINS
    assert "http://example.com" in s.CORS_ORIGINS


def test_production_config_validation_fails_on_default_secret():
    s = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="change_this_to_something",
        AUTH_SECRET_KEY="change_this_too",
    )
    with pytest.raises(ValueError, match="Insecure default SECRET_KEY"):
        s.validate_production_configuration()


def test_production_config_validation_fails_when_demo_false_without_api_key():
    s = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="valid_random_secure_key_12345678901234567890",
        AUTH_SECRET_KEY="another_valid_random_key_12345678901234567890",
        DEMO_MODE=False,
        OPENROUTER_API_KEY=None,
    )
    with pytest.raises(ValueError, match="OPENROUTER_API_KEY is required"):
        s.validate_production_configuration()
