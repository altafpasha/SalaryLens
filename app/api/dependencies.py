"""
SalaryLens AI by CodeSec — FastAPI Route Dependencies
"""
import uuid
from typing import AsyncGenerator, Optional
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.models.organization import Organization
from app.models.membership import OrganizationMembership

security_scheme = HTTPBearer(auto_error=False)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provides an isolated async session per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_current_user_and_org(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_scheme),
    db: AsyncSession = Depends(get_db_session),
) -> tuple[User, uuid.UUID, str]:
    """
    Validates JWT token, loads the current authenticated user,
    and returns (user, organization_id, role).
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(credentials.credentials)
    user_id_str = payload.get("sub")
    org_id_str = payload.get("org_id")
    role = payload.get("role", "agent")

    if not user_id_str or not org_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_uuid = uuid.UUID(user_id_str)
        org_uuid = uuid.UUID(org_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token identity identifiers",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify user exists in database
    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify organization membership
    mem_result = await db.execute(
        select(OrganizationMembership).where(
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.organization_id == org_uuid
        )
    )
    membership = mem_result.scalar_one_or_none()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not have access to this organization tenant",
        )

    return user, org_uuid, membership.role


def require_role(required_role: str):
    """
    Dependency factory to enforce role-based access control.
    Role hierarchy: admin > reviewer > agent
    """
    role_weights = {"agent": 1, "reviewer": 2, "admin": 3}

    async def role_checker(
        user_context: tuple[User, uuid.UUID, str] = Depends(get_current_user_and_org)
    ) -> tuple[User, uuid.UUID, str]:
        user, org_id, current_role = user_context
        current_weight = role_weights.get(current_role, 0)
        required_weight = role_weights.get(required_role, 0)

        if current_weight < required_weight:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation requires '{required_role}' privileges (current: '{current_role}')",
            )
        return user_context

    return role_checker
