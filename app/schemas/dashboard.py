"""
SalaryLens AI by CodeSec — Dashboard Schemas
"""
from decimal import Decimal
from pydantic import BaseModel


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
