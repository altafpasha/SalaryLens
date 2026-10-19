"""
SalaryLens AI by CodeSec — Retention Job Model
"""
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, GUID, TimestampMixin


class RetentionJob(Base, TimestampMixin):
    """
    Tracks execution and outcomes of document and data retention cleanup policies.
    """
    __tablename__ = "retention_jobs"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)

    status: Mapped[str] = mapped_column(String(50), default="running", nullable=False)  # running, completed, failed
    deleted_statements_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    deleted_files_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
