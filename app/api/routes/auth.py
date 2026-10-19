"""
SalaryLens AI by CodeSec — Authentication Routes
"""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user_and_org, get_db_session
from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.models.organization import Organization
from app.models.membership import OrganizationMembership
from app.models.user import User
from app.schemas.auth import TokenResponse, UserLoginRequest, UserProfileResponse, UserRegisterRequest

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register User and Organization Tenant",
    description="Registers a new user, provisions an isolated organization tenant, and returns a signed JWT access token."
)
async def register(
    data: UserRegisterRequest,
    db: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    # Check if user already exists
    existing_user = await db.execute(select(User).where(User.email == data.email.lower()))
    if existing_user.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists.",
        )

    # Create Organization
    org_slug = data.organization_name.lower().replace(" ", "-") + "-" + uuid.uuid4().hex[:6]
    org = Organization(
        name=data.organization_name,
        slug=org_slug,
    )
    db.add(org)
    await db.flush()

    # Create User
    user = User(
        email=data.email.lower(),
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        role=data.role,
        is_active=True,
    )
    db.add(user)
    await db.flush()

    # Create Membership
    membership = OrganizationMembership(
        organization_id=org.id,
        user_id=user.id,
        role=data.role,
    )
    db.add(membership)
    await db.commit()

    # Generate Token
    token = create_access_token(
        subject=str(user.id),
        organization_id=str(org.id),
        role=data.role,
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        user_id=user.id,
        organization_id=org.id,
        role=data.role,
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="User Authentication & Token Issuance",
    description="Validates email and password credentials, returning a signed JWT access token."
)
async def login(
    data: UserLoginRequest,
    db: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    user_q = await db.execute(select(User).where(User.email == data.email.lower()))
    user = user_q.scalar_one_or_none()

    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is inactive.",
        )

    # Get primary membership
    mem_q = await db.execute(
        select(OrganizationMembership).where(OrganizationMembership.user_id == user.id)
    )
    membership = mem_q.scalar_one_or_none()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User has no associated organization membership.",
        )

    token = create_access_token(
        subject=str(user.id),
        organization_id=str(membership.organization_id),
        role=membership.role,
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        user_id=user.id,
        organization_id=membership.organization_id,
        role=membership.role,
    )


@router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="Current User Profile",
    description="Returns profile information for the authenticated user and active organization tenant."
)
async def get_me(
    user_context: tuple[User, uuid.UUID, str] = Depends(get_current_user_and_org),
    db: AsyncSession = Depends(get_db_session),
) -> UserProfileResponse:
    user, org_id, role = user_context

    org_q = await db.execute(select(Organization).where(Organization.id == org_id))
    org = org_q.scalar_one_or_none()

    return UserProfileResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=role,
        is_active=user.is_active,
        organization_id=org_id,
        organization_name=org.name if org else "Default",
    )
