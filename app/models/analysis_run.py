"""
SalaryLens AI by CodeSec — Analysis Run Model
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, GUID, TimestampMixin


class AnalysisRun(Base, TimestampMixin):
    """
    Persists the final decision and end-to-end evidence summary of a statement analysis.
    Grounding checks verify that supporting_transaction_ids, supporting_months,
    and employer match validated DB records.
    """
    __tablename__ = "analysis_runs"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    statement_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("statements.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)

    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)  # pending, running, completed, failed
    salary_status: Mapped[str] = mapped_column(
        String(50),
        default="insufficient_evidence",
        nullable=False
    )  # likely_salary, possible_salary, multiple_salary_candidates, insufficient_evidence, conflicting_evidence, analysis_failed

    detected_employer: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    supporting_transaction_ids: Mapped[Optional[list]] = mapped_column(JSON, default=list, nullable=True)
    supporting_months: Mapped[Optional[list]] = mapped_column(JSON, default=list, nullable=True)
    reason_codes: Mapped[Optional[list]] = mapped_column(JSON, default=list, nullable=True)
    explanation: Mapped[str] = mapped_column(Text, default="", nullable=False)
    uncertainties: Mapped[Optional[list]] = mapped_column(JSON, default=list, nullable=True)
    requires_human_review: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Cost and Token Tracking
    total_ai_cost_usd: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("0.0000"), nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    statement = relationship("Statement", back_populates="analysis_runs")
    model_usage_events = relationship("ModelUsageEvent", back_populates="analysis_run", cascade="all, delete-orphan")
