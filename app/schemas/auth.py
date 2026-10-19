"""
SalaryLens AI by CodeSec — Authentication Pydantic Schemas
"""
import uuid
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class UserRegisterRequest(BaseModel):
    email: EmailStr = Field(..., description="User corporate email address")
    password: str = Field(..., min_length=8, description="Secure user password")
    full_name: str = Field(..., description="User full name")
    organization_name: str = Field(..., description="Organization or financial institution name")
    role: str = Field("agent", description="User role: agent, reviewer, or admin")


class UserLoginRequest(BaseModel):
    email: EmailStr = Field(..., description="Registered email address")
    password: str = Field(..., description="Password")


class TokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT Bearer access token")
    token_type: str = Field("bearer", description="Token type")
    expires_in_minutes: int = Field(..., description="Token lifespan in minutes")
    user_id: uuid.UUID = Field(..., description="User UUID")
    organization_id: uuid.UUID = Field(..., description="Organization UUID")
    role: str = Field(..., description="User role")


class UserProfileResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    organization_id: uuid.UUID
    organization_name: str
