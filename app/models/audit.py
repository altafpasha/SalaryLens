"""
SalaryLens AI by CodeSec — Audit Event Model
"""
import uuid
from typing import Optional
from sqlalchemy import ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, GUID, TimestampMixin


class AuditEvent(Base, TimestampMixin):
    """
    Immutable audit logging records for security, data governance,
    and compliance monitoring.
    """
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(GUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(100), nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    details_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Relationships
    organization = relationship("Organization", back_populates="audit_events")
