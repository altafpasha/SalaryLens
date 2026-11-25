"""
SalaryLens AI by CodeSec — Application Configuration
"""
from typing import List, Optional
import os
from pathlib import Path
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Application
    APP_NAME: str = "SalaryLens AI by CodeSec"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    API_V1_STR: str = "/api/v1"
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Demo Mode
    DEMO_MODE: bool = True

    # Security & JWT Authentication
    SECRET_KEY: str = Field(default="change_this_to_a_very_secure_random_secret_key_at_least_32_chars")
    AUTH_SECRET_KEY: str = Field(default="change_this_to_another_very_secure_random_key_for_jwt_tokens")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    ALGORITHM: str = "HS256"

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://localhost:8001",
        "http://localhost:8080",
    ]

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./salarylens_dev.db"
    DATABASE_SYNC_URL: str = "sqlite:///./salarylens_dev.db"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_ECHO: bool = False

    # Redis & Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    CELERY_TASK_ALWAYS_EAGER: bool = True

    # Private Storage
    STORAGE_ROOT: str = "./storage"
    STORAGE_BASE_DIR: str = "./storage"
    UPLOAD_DIR: str = "./storage/uploads"
    RENDER_DIR: str = "./storage/renders"

    # Constraints & Limits
    MAX_UPLOAD_SIZE_MB: int = 50
    MAX_DOCUMENT_PAGES: int = 120
    MAX_TRANSACTIONS_PER_STATEMENT: int = 5000
    ALLOWED_MIME_TYPES: List[str] = ["application/pdf"]

    # OpenRouter AI Integration
    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_APP_NAME: str = "SalaryLens AI by CodeSec"
    OPENROUTER_SITE_URL: str = "http://localhost:8000"

    # Model Configuration
    SALARY_FINDER_MODEL: str = "google/gemma-4-31b-it:free"
    DECISION_MODEL: str = "google/gemma-4-31b-it:free"
    EMBEDDING_MODEL: str = "text-embedding-3-small"

    # Local LLM & Inference Runtime Configuration
    LOCAL_LLM_PROVIDER: str = "ollama"  # "ollama" | "openrouter" | "auto"
    LOCAL_LLM_BASE_URL: str = "http://localhost:11434"
    LOCAL_LLM_MODEL: str = "qwen3.5-9b-uncensored:latest"
    LOCAL_LLM_TIMEOUT_SECONDS: float = 90.0

    # OCR Engine Configuration
    OCR_ENGINE: str = "hybrid_indra"  # "hybrid_indra" | "indra" | "native"
    INDRA_DPI: float = 200.0
    INDRA_THREADS: int = 4

    # AI Cost Limits & Timeouts
    MAX_AI_COST_USD_PER_STATEMENT: float = 1.50
    OPENROUTER_REQUEST_TIMEOUT_SECONDS: float = 60.0
    OPENROUTER_MAX_RETRIES: int = 3
    OPENROUTER_RETRY_BACKOFF_FACTOR: float = 1.5

    # Deterministic Pre-Filtering & Optimization
    SALARY_PREFILTER_MIN_AMOUNT_INR: float = 1500.00
    SALARY_PREFILTER_MIN_AMOUNT_USD: float = 25.00
    AI_EVALUATION_CACHE_ENABLED: bool = True
    STATEMENT_PROCESSING_VERSION: str = "v2.0_optimized"

    # Retention Policies
    DOCUMENT_RETENTION_DAYS: int = 90
    RESULT_RETENTION_DAYS: int = 365
    AUDIT_LOG_RETENTION_DAYS: int = 730

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    REDACT_SENSITIVE_LOGS: bool = True

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, v):
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes", "on", "t")
        return bool(v)

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v):
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                import json
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    def validate_production_configuration(self) -> None:
        """Enforces security checks at startup."""
        if self.ENVIRONMENT == "production":
            if self.SECRET_KEY.startswith("change_this"):
                raise ValueError("Insecure default SECRET_KEY detected in production environment!")
            if self.AUTH_SECRET_KEY.startswith("change_this"):
                raise ValueError("Insecure default AUTH_SECRET_KEY detected in production environment!")
            if not self.DEMO_MODE and not self.OPENROUTER_API_KEY:
                raise ValueError("OPENROUTER_API_KEY is required in production when DEMO_MODE is false!")

    def ensure_directories(self) -> None:
        """Ensure necessary storage directories exist."""
        Path(self.STORAGE_ROOT).mkdir(parents=True, exist_ok=True)
        Path(self.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
        Path(self.RENDER_DIR).mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_directories()
