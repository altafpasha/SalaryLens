"""
SalaryLens AI by CodeSec — Employer Alias Model
"""
import uuid
from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, GUID, TimestampMixin


class EmployerAlias(Base, TimestampMixin):
    """
    Stores recognized canonical employer names and their common statement abbreviations/aliases
    scoped strictly to the organization tenant.
    """
    __tablename__ = "employer_aliases"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)

    canonical_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    alias: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint("organization_id", "alias", name="uq_org_employer_alias"),
        Index("ix_employer_aliases_org_canonical", "organization_id", "canonical_name"),
    )

    # Relationships
    organization = relationship("Organization", back_populates="employer_aliases")
