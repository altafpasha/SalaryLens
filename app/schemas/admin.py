"""
SalaryLens AI by CodeSec — Admin and Dashboard Schemas
"""
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class ModelInfoItem(BaseModel):
    model_id: str
    role: str  # salary_finder, decision_engine, embedding
    input_price_per_1m: Decimal
    output_price_per_1m: Decimal
    supports_vision: bool


class AdminModelsResponse(BaseModel):
    models: List[ModelInfoItem]
    max_budget_per_statement_usd: Decimal
    demo_mode_enabled: bool


class AdminUsageMetrics(BaseModel):
    total_model_calls: int
    total_tokens_consumed: int
    total_cost_usd: Decimal
    total_simulated_calls: int
    average_latency_ms: float
    usage_by_stage: Dict[str, int]
    usage_by_model: Dict[str, int]


class DashboardSummaryResponse(BaseModel):
    total_statements_processed: int
    likely_salary_count: int
    possible_salary_count: int
    multiple_candidates_count: int
    insufficient_evidence_count: int
    requires_human_review_count: int
    pending_reviews_count: int
    average_monthly_salary_usd: Decimal
    total_ai_spend_usd: Decimal
