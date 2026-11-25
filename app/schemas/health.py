"""
SalaryLens AI by CodeSec — Health Schemas
"""
from datetime import datetime
from typing import Dict
from pydantic import BaseModel, Field


class ConfiguredModels(BaseModel):
    salary_finder: str = Field(..., description="Configured Salary Finder model identifier")
    decision_engine: str = Field(..., description="Configured Jev Decision Engine model identifier")
    embedding: str = Field(..., description="Configured Embedding model identifier")
    ocr_engine: str = Field("hybrid_indra", description="Configured document OCR engine")
    local_llm_provider: str = Field("ollama", description="Configured local LLM inference provider")
    local_llm_model: str = Field("qwen3.5-9b-uncensored:latest", description="Configured local LLM model")
    local_llm_available: bool = Field(False, description="Whether local inference engine is reachable")


class HealthResponse(BaseModel):
    status: str = Field("healthy", description="Overall system health status")
    environment: str = Field(..., description="Application environment")
    demo_mode: bool = Field(..., description="Whether demo mode is active")
    database_connected: bool = Field(..., description="Database connectivity status")
    storage_ready: bool = Field(..., description="Private storage availability status")
    version: str = Field("1.0.0", description="API version")
    timestamp: datetime = Field(..., description="Current server UTC timestamp")
    models: ConfiguredModels = Field(..., description="Configured OpenRouter model identifiers")
