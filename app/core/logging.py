"""
SalaryLens AI by CodeSec — Structured Logging with Sensitive Data Redaction
"""
import re
import json
import logging
import sys
from typing import Any, Dict


class SensitiveDataFilter(logging.Filter):
    """
    Filters and redacts sensitive information such as:
    - Bank account numbers
    - Credit card numbers
    - Bearer tokens and API keys
    - Passwords and secrets
    """
    REDACTION_PATTERNS = [
        # Bearer tokens
        (re.compile(r"Bearer\s+([a-zA-Z0-9_\-\.]{15,})", re.IGNORECASE), "Bearer [REDACTED_TOKEN]"),
        # OpenRouter or OpenAI API Keys
        (re.compile(r"sk-(or-v1-)?[a-zA-Z0-9]{20,}", re.IGNORECASE), "[REDACTED_API_KEY]"),
        # Credit Card Numbers (13 to 19 digits)
        (re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b"), "[REDACTED_CARD]"),
        # Account numbers (9 to 18 consecutive digits)
        (re.compile(r"(account(?:_no|_number)?\s*[:=]\s*)['\"]?(\d{8,18})['\"]?", re.IGNORECASE), r"\1[REDACTED_ACCOUNT]"),
        # Passwords in JSON/key-value pairs
        (re.compile(r"('password'|\"password\")\s*:\s*['\"][^'\"]+['\"]", re.IGNORECASE), r'\1: "[REDACTED_PASSWORD]"'),
        (re.compile(r"(password=)[^\s&]+", re.IGNORECASE), r"\1[REDACTED]"),
    ]

    def redact(self, text: str) -> str:
        for pattern, replacement in self.REDACTION_PATTERNS:
            text = pattern.sub(replacement, text)
        return text

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self.redact(record.msg)
        if record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(self.redact(str(arg)) if isinstance(arg, str) else arg for arg in record.args)
            elif isinstance(record.args, dict):
                record.args = {k: self.redact(str(v)) if isinstance(v, str) else v for k, v in record.args.items()}
        return True


class JSONFormatter(logging.Formatter):
    """Formatter to output logs in structured JSON format."""
    def format(self, record: logging.LogRecord) -> str:
        log_record: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "statement_id"):
            log_record["statement_id"] = record.statement_id
        if hasattr(record, "tenant_id"):
            log_record["tenant_id"] = record.tenant_id
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_record)


def setup_logging(log_level: str = "INFO", log_format: str = "json") -> None:
    """Configures application-wide logging."""
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Remove existing handlers
    for handler in list(logger.handlers):
        logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(SensitiveDataFilter())

    if log_format.lower() == "json":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        )

    logger.addHandler(handler)

    # Silence noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
