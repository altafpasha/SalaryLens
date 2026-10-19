"""
SalaryLens AI by CodeSec — Model Usage and Cost Event Model
"""
import uuid
from decimal import Decimal
from typing import Optional
from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, GUID, TimestampMixin


class ModelUsageEvent(Base, TimestampMixin):
    """
    Records every individual OpenRouter model interaction with exact token counts,
    provider-reported costs, fallback estimated costs, latencies, and stage identifiers.
    """
    __tablename__ = "model_usage_events"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    statement_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("statements.id", ondelete="CASCADE"), nullable=False, index=True)
    analysis_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(GUID, ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=True, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)

    model_name: Mapped[str] = mapped_column(String(150), nullable=False)
    stage: Mapped[str] = mapped_column(String(50), nullable=False)  # extraction, decision, embedding

    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cached_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    provider_cost_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6), nullable=True)
    estimated_cost_usd: Mapped[Decimal] = mapped_column(Numeric(8, 6), default=Decimal("0.000000"), nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    statement = relationship("Statement", back_populates="model_usage_events")
    analysis_run = relationship("AnalysisRun", back_populates="model_usage_events")
