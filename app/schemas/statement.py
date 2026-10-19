"""
SalaryLens AI by CodeSec — Statement, Transaction, and Review Schemas
"""
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field


class StatementUploadResponse(BaseModel):
    statement_id: uuid.UUID
    filename: str
    file_size_bytes: int
    page_count: int
    duration_months: Optional[int]
    status: str
    is_demo: bool
    created_at: datetime


class StatementStatusResponse(BaseModel):
    statement_id: uuid.UUID
    status: str  # pending, processing, completed, requires_human_review, failed
    is_scanned: bool
    page_count: int
    error_message: Optional[str] = None
    workbook_status: Optional[str] = None
    workbook_generated_at: Optional[datetime] = None
    total_transactions_count: Optional[int] = None
    included_in_salary_count: Optional[int] = None
    excluded_from_salary_count: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class StatementTransactionItem(BaseModel):
    id: uuid.UUID
    transaction_date: date
    value_date: Optional[date] = None
    raw_description: str
    normalized_description: str
    credit_amount: Optional[Decimal] = None
    debit_amount: Optional[Decimal] = None
    balance: Optional[Decimal] = None
    currency: str
    page_number: int
    transaction_direction: Optional[str] = None
    category: Optional[str] = None
    included_in_salary_analysis: Optional[bool] = False
    exclusion_reason: Optional[str] = None
    inclusion_reason: Optional[str] = None
    validation_status: Optional[str] = "valid"
    is_salary_candidate: bool
    candidate_employer: Optional[str] = None
    is_reversal: bool
    is_duplicate: bool


class PaginatedTransactionsResponse(BaseModel):
    statement_id: uuid.UUID
    total_count: int
    page: int
    page_size: int
    transactions: List[StatementTransactionItem]


class CandidateGroupSummary(BaseModel):
    employer_name: str
    aliases: List[str]
    transaction_count: int
    months_count: int
    missing_months: List[str]
    average_amount: Decimal
    median_amount: Decimal
    min_amount: Decimal
    max_amount: Decimal
    amount_variation_pct: Decimal
    recurrence_score: Decimal
    is_primary: bool


class StatementResultsResponse(BaseModel):
    statement_id: uuid.UUID
    status: str  # likely_salary, possible_salary, multiple_salary_candidates, insufficient_evidence, conflicting_evidence, analysis_failed
    detected_employer: Optional[str] = None
    supporting_transaction_ids: List[str] = Field(default_factory=list)
    supporting_months: List[str] = Field(default_factory=list)
    reason_codes: List[str] = Field(default_factory=list)
    explanation: str
    uncertainties: List[str] = Field(default_factory=list)
    requires_human_review: bool
    candidate_groups: List[CandidateGroupSummary] = Field(default_factory=list)
    total_ai_cost_usd: Decimal
    total_tokens: int
    is_demo: bool
    analysis_completed_at: Optional[datetime] = None


class HumanReviewRequest(BaseModel):
    status: str = Field(..., description="approved, rejected, or adjusted")
    confirmed_employer: Optional[str] = Field(None, description="Manually confirmed employer name")
    confirmed_transaction_ids: List[str] = Field(default_factory=list, description="IDs of confirmed salary credits")
    review_notes: Optional[str] = Field(None, description="Reviewer reasoning and audit notes")


class HumanReviewResponse(BaseModel):
    review_id: uuid.UUID
    statement_id: uuid.UUID
    reviewer_user_id: uuid.UUID
    status: str
    confirmed_employer: Optional[str]
    confirmed_transaction_ids: List[str]
    review_notes: Optional[str]
    created_at: datetime
