"""
SalaryLens AI by CodeSec — Transaction Model
"""
import uuid
from datetime import date
from decimal import Decimal
from typing import Optional
from sqlalchemy import Boolean, Date, ForeignKey, Index, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, GUID, TimestampMixin


class Transaction(Base, TimestampMixin):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    statement_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("statements.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)

    transaction_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    value_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    raw_description: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_description: Mapped[str] = mapped_column(String(500), nullable=False)

    # Use Numeric(14, 2) for exact financial currency values
    credit_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True, default=None)
    debit_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True, default=None)
    balance: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True, default=None)
    currency: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)

    page_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Direction and Details
    transaction_direction: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # CREDIT, DEBIT, AMBIGUOUS
    chqno: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    extraction_method: Mapped[str] = mapped_column(String(20), default="native", nullable=False)  # native, ocr

    # AI & Heuristic candidate flags
    is_salary_candidate: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)
    candidate_employer: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    confidence: Mapped[Optional[Decimal]] = mapped_column(Numeric(4, 3), nullable=True)  # 0.000 to 1.000

    # Validation flags
    is_reversal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    potential_reversal_of_id: Mapped[Optional[uuid.UUID]] = mapped_column(GUID, nullable=True)
    validation_status: Mapped[str] = mapped_column(String(50), default="valid", nullable=False)
    validation_warnings: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Salary Analysis Filtering
    included_in_salary_analysis: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)
    exclusion_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    inclusion_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_transactions_stmt_date", "statement_id", "transaction_date"),
        Index("ix_transactions_org_stmt", "organization_id", "statement_id"),
    )

    # Relationships
    statement = relationship("Statement", back_populates="transactions")
