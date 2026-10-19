"""
SalaryLens AI by CodeSec — Statement Model
"""
import uuid
from datetime import date, datetime
from typing import Optional
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, GUID, TimestampMixin


class Statement(Base, TimestampMixin):
    __tablename__ = "statements"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    uploaded_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(GUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)  # SHA-256
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_months: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 3 or 6

    # Status: pending, processing, completed, failed, requires_human_review
    status: Mapped[str] = mapped_column(String(50), default="pending", index=True, nullable=False)
    is_scanned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Excel Workbook & Filtering Lifecycle
    workbook_file_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    workbook_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)  # pending, initial, completed, failed
    workbook_generated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    workbook_validation_status: Mapped[Optional[str]] = mapped_column(String(50), default="unverified", nullable=True)

    # Extraction & Filtering Statistics
    total_transactions_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_debit_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_credit_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    included_in_salary_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    excluded_from_salary_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    native_pages_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ocr_pages_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    statement_start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    statement_end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    account_info_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Relationships
    organization = relationship("Organization", back_populates="statements")
    uploaded_by_user = relationship("User", back_populates="uploaded_statements")
    transactions = relationship("Transaction", back_populates="statement", cascade="all, delete-orphan", lazy="selectin")
    candidate_groups = relationship("SalaryCandidateGroup", back_populates="statement", cascade="all, delete-orphan", lazy="selectin")
    analysis_runs = relationship("AnalysisRun", back_populates="statement", cascade="all, delete-orphan", lazy="selectin")
    model_usage_events = relationship("ModelUsageEvent", back_populates="statement", cascade="all, delete-orphan", lazy="selectin")
    human_reviews = relationship("HumanReview", back_populates="statement", cascade="all, delete-orphan", lazy="selectin")
