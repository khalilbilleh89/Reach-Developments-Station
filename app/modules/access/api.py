"""Authentication and user-administration routes.

Handlers validate, authorise and orchestrate. Domain logic and transaction
boundaries live in :mod:`app.modules.access.service`.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, Request, Response, status

from app.core.config import get_settings
from app.modules.access import service
from app.modules.access.dependencies import (
    SESSION_COOKIE_NAME,
    ActiveActor,
    AuthenticatedUser,
    CurrentActor,
    DbSession,
    SystemAdmin,
)
from app.modules.access.models import User
from app.modules.access.schemas import (
    ChangePasswordRequest,
    CurrentUser,
    LoginRequest,
    PasswordResetRequest,
    RoleRead,
    UserCreateRequest,
    UserPage,
    UserRead,
    UserUpdateRequest,
)

auth_router = APIRouter(prefix="/auth", tags=["authentication"])
admin_router = APIRouter(prefix="/admin", tags=["administration"])

#: One message for every credential failure. Distinguishing "no such user" from
#: "wrong password" would turn the login form into an account enumerator.
_INVALID_CREDENTIALS = "Invalid email or password."


def _set_session_cookie(response: Response, raw_token: str) -> None:
    """Attach the opaque session cookie.

    ``Secure`` is conditional purely so that local http development works; every
    other flag is unconditional. ``SameSite=Strict`` is the primary CSRF
    defence — the browser will not attach this cookie to a cross-site request
    at all.
    """
    settings = get_settings()
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=raw_token,
        max_age=settings.SESSION_TTL_MINUTES * 60,
        httponly=True,
        secure=settings.is_production,
        samesite="strict",
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")


def _to_current_user(user: User) -> CurrentUser:
    return CurrentUser(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        is_active=user.is_active,
        must_change_password=user.must_change_password,
        roles=[
            RoleRead(key=role.key, label=role.label)
            for role in sorted(user.roles, key=lambda r: r.label)
        ],
    )


def _to_user_read(user: User) -> UserRead:
    return UserRead(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        is_active=user.is_active,
        must_change_password=user.must_change_password,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        role_keys=sorted(user.role_keys),
    )


# --------------------------------------------------------------------------- #
# Authentication
# --------------------------------------------------------------------------- #


@auth_router.post("/login", response_model=CurrentUser, summary="Open a session")
def login(
    payload: LoginRequest,
    response: Response,
    session: DbSession,
) -> CurrentUser:
    """Authenticate and set the session cookie."""
    result = service.login(session, email=payload.email, password=payload.password)
    if result is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_INVALID_CREDENTIALS)
    user, raw_token = result
    _set_session_cookie(response, raw_token)
    return _to_current_user(user)


@auth_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="End the session")
def logout(
    request: Request,
    response: Response,
    session: DbSession,
) -> Response:
    """Revoke the current session and clear the cookie. Safe to call twice."""
    service.logout(session, request.cookies.get(SESSION_COOKIE_NAME, ""))
    _clear_session_cookie(response)
    return Response(status_code=status.HTTP_204_NO_CONTENT, headers=dict(response.headers))


@auth_router.get("/me", response_model=CurrentUser, summary="The authenticated caller")
def read_me(user: AuthenticatedUser) -> CurrentUser:
    """Available even while a password change is outstanding."""
    return _to_current_user(user)


@auth_router.post(
    "/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Replace the caller's password",
)
def change_password(
    payload: ChangePasswordRequest,
    response: Response,
    actor: CurrentActor,
    user: AuthenticatedUser,
    session: DbSession,
) -> Response:
    """Change the caller's own password, then force a fresh login.

    Every session is revoked, including this one: a password change must not
    leave an old session usable.
    """
    service.change_own_password(
        session,
        user=user,
        current_password=payload.current_password,
        new_password=payload.new_password,
        correlation_id=actor.correlation_id,
    )
    _clear_session_cookie(response)
    return Response(status_code=status.HTTP_204_NO_CONTENT, headers=dict(response.headers))


# --------------------------------------------------------------------------- #
# User administration
# --------------------------------------------------------------------------- #


@admin_router.get("/roles", response_model=list[RoleRead], summary="Fixed role catalogue")
def list_roles(
    session: DbSession,
    _actor: ActiveActor,
) -> list[RoleRead]:
    """Read-only. Roles are seeded by migration and are not editable."""
    return [RoleRead(key=role.key, label=role.label) for role in service.list_roles(session)]


@admin_router.get("/users", response_model=UserPage, summary="List users")
def list_users(
    session: DbSession,
    _actor: SystemAdmin,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    is_active: bool | None = Query(default=None),
    search: str | None = Query(default=None, max_length=200),
) -> UserPage:
    users, total = service.list_users(
        session, limit=limit, offset=offset, is_active=is_active, search=search
    )
    return UserPage(
        items=[_to_user_read(user) for user in users], total=total, limit=limit, offset=offset
    )


@admin_router.post(
    "/users",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a user",
)
def create_user(
    payload: UserCreateRequest,
    session: DbSession,
    actor: SystemAdmin,
) -> UserRead:
    """The new user must replace the supplied temporary password at first login."""
    user = service.create_user(
        session,
        email=payload.email,
        display_name=payload.display_name,
        password=payload.initial_password,
        role_keys=payload.role_keys,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
    )
    return _to_user_read(user)


@admin_router.get("/users/{user_id}", response_model=UserRead, summary="Read a user")
def read_user(
    user_id: uuid.UUID,
    session: DbSession,
    _actor: SystemAdmin,
) -> UserRead:
    return _to_user_read(service.get_user(session, user_id))


@admin_router.patch("/users/{user_id}", response_model=UserRead, summary="Update a user")
def update_user(
    user_id: uuid.UUID,
    payload: UserUpdateRequest,
    session: DbSession,
    actor: SystemAdmin,
) -> UserRead:
    """There is no delete endpoint. Users are deactivated, never removed."""
    user = service.update_user(
        session,
        user_id=user_id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        display_name=payload.display_name,
        is_active=payload.is_active,
        role_keys=payload.role_keys,
        reason=payload.reason,
    )
    return _to_user_read(user)


@admin_router.post(
    "/users/{user_id}/reset-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Issue a temporary password",
)
def reset_password(
    user_id: uuid.UUID,
    payload: PasswordResetRequest,
    session: DbSession,
    actor: SystemAdmin,
) -> Response:
    """Sets a temporary password and revokes the user's sessions immediately."""
    service.reset_password(
        session,
        user_id=user_id,
        new_password=payload.new_password,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
