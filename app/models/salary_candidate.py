"""
SalaryLens AI by CodeSec — Salary Candidate & Group Models
"""
import uuid
from decimal import Decimal
from typing import Optional
from sqlalchemy import Boolean, ForeignKey, Integer, JSON, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, GUID, TimestampMixin


class SalaryCandidateGroup(Base, TimestampMixin):
    """
    Represents an aggregated group of salary credit candidates associated with an employer/pattern.
    All financial metrics are calculated authoritatively by Python using Decimal.
    """
    __tablename__ = "salary_candidate_groups"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    statement_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("statements.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)

    employer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    aliases: Mapped[Optional[list]] = mapped_column(JSON, default=list, nullable=True)

    transaction_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    months_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    missing_months: Mapped[Optional[list]] = mapped_column(JSON, default=list, nullable=True)

    # Authoritative Python Decimal calculations
    average_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    median_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    min_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    max_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    amount_variation_pct: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=Decimal("0.00"), nullable=False)

    recurrence_score: Mapped[Decimal] = mapped_column(Numeric(4, 3), default=Decimal("0.000"), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    statement = relationship("Statement", back_populates="candidate_groups")
    candidates = relationship("SalaryCandidate", back_populates="group", cascade="all, delete-orphan", lazy="selectin")


class SalaryCandidate(Base, TimestampMixin):
    """
    Links a specific transaction into a candidate group with candidate-specific validation info.
    """
    __tablename__ = "salary_candidates"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    group_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("salary_candidate_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    transaction_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)

    month_label: Mapped[str] = mapped_column(String(20), nullable=False)  # e.g. "2026-05"
    day_of_month: Mapped[int] = mapped_column(Integer, nullable=False)

    # Relationships
    group = relationship("SalaryCandidateGroup", back_populates="candidates")
    transaction = relationship("Transaction")
