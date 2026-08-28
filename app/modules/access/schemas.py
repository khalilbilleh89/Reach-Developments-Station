"""Public request and response contracts for identity and access.

No schema here exposes ``password_hash`` or any session token.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.access.security import MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH


class RoleRead(BaseModel):
    """One entry of the fixed role catalogue."""

    model_config = ConfigDict(from_attributes=True)

    key: str
    label: str


class UserRead(BaseModel):
    """A user as returned to administrators."""

    id: uuid.UUID
    email: str
    display_name: str
    is_active: bool
    must_change_password: bool
    last_login_at: datetime | None
    created_at: datetime
    role_keys: list[str]


class UserPage(BaseModel):
    """One bounded page of users."""

    items: list[UserRead]
    total: int
    limit: int
    offset: int


class CurrentUser(BaseModel):
    """The authenticated caller's own view of themselves."""

    id: uuid.UUID
    email: str
    display_name: str
    is_active: bool
    must_change_password: bool
    roles: list[RoleRead]


class LoginRequest(BaseModel):
    email: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)


class ChangePasswordRequest(BaseModel):
    """Current password is optional only while a temporary password is in force."""

    current_password: str | None = Field(default=None, max_length=MAX_PASSWORD_LENGTH)
    new_password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)


class UserCreateRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    display_name: str = Field(min_length=1, max_length=200)
    #: Temporary password. The user must replace it at first login.
    initial_password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)
    role_keys: list[str] = Field(default_factory=list, max_length=20)


class UserUpdateRequest(BaseModel):
    """Only intentionally mutable fields. Email identity is not changed here."""

    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    is_active: bool | None = None
    role_keys: list[str] | None = Field(default=None, max_length=20)
    reason: str | None = Field(default=None, max_length=500)


class PasswordResetRequest(BaseModel):
    new_password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)
