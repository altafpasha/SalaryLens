"""
Unit tests for structured logging and sensitive data redaction filter
"""
from app.core.logging import SensitiveDataFilter


def test_redact_bearer_token():
    filter_instance = SensitiveDataFilter()
    msg = "Sending request with header Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.tokencontent"
    redacted = filter_instance.redact(msg)
    assert "[REDACTED_TOKEN]" in redacted
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in redacted


def test_redact_api_key():
    filter_instance = SensitiveDataFilter()
    msg = "Configured OpenRouter key: sk-or-v1-abcdef1234567890abcdef1234567890"
    redacted = filter_instance.redact(msg)
    assert "[REDACTED_API_KEY]" in redacted
    assert "sk-or-v1-abcdef" not in redacted


def test_redact_credit_card():
    filter_instance = SensitiveDataFilter()
    msg = "Transaction card: 4111 2222 3333 4444 approved"
    redacted = filter_instance.redact(msg)
    assert "[REDACTED_CARD]" in redacted
    assert "4111 2222 3333 4444" not in redacted


def test_redact_account_number():
    filter_instance = SensitiveDataFilter()
    msg = "Customer account_number: 1234567890123"
    redacted = filter_instance.redact(msg)
    assert "[REDACTED_ACCOUNT]" in redacted
    assert "1234567890123" not in redacted
