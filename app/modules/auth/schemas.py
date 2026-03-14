"""
auth.schemas

Pydantic request / response models for authentication.
"""

from datetime import datetime

from pydantic import BaseModel, EmailStr, field_validator


class UserCreate(BaseModel):
    """Payload for registering a new user."""

    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class UserLogin(BaseModel):
    """Payload for authenticating an existing user."""

    email: EmailStr
    password: str


class RoleResponse(BaseModel):
    """Serialized role."""

    id: str
    name: str
    description: str

    model_config = {"from_attributes": True}


class UserResponse(BaseModel):
    """Serialized user (password excluded)."""

    id: str
    email: str
    is_active: bool
    created_at: datetime
    roles: list[RoleResponse] = []

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """JWT token issued on successful login or registration."""

    access_token: str
    token_type: str = "bearer"
