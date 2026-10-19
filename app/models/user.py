"""
SalaryLens AI by CodeSec — User Model
"""
import uuid
from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, GUID, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="agent", nullable=False)  # agent, reviewer, admin
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    memberships = relationship("OrganizationMembership", back_populates="user", cascade="all, delete-orphan")
    uploaded_statements = relationship("Statement", back_populates="uploaded_by_user")
    reviews = relationship("HumanReview", back_populates="reviewer")
