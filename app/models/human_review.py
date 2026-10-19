"""
SalaryLens AI by CodeSec — Human Review Model
"""
import uuid
from typing import Optional
from sqlalchemy import ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, GUID, TimestampMixin


class HumanReview(Base, TimestampMixin):
    """
    Captures human reviewer oversight, manual overrides, adjustments,
    and confirmations for bank statements requiring manual intervention.
    """
    __tablename__ = "human_reviews"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    statement_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("statements.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    reviewer_user_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)

    status: Mapped[str] = mapped_column(String(50), nullable=False)  # approved, rejected, adjusted
    confirmed_employer: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    confirmed_transaction_ids: Mapped[Optional[list]] = mapped_column(JSON, default=list, nullable=True)
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    statement = relationship("Statement", back_populates="human_reviews")
    reviewer = relationship("User", back_populates="reviews")
