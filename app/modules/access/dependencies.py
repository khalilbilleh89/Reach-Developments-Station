"""FastAPI dependencies for authentication and role enforcement.

One implementation, reused everywhere. Route handlers never read the session
cookie or query roles themselves.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.correlation import get_correlation_id
from app.core.database import get_session
from app.modules.access.models import ROLE_SYSTEM_ADMIN, User
from app.modules.access.service import resolve_session

#: Name of the opaque session cookie. The value is the raw session token, which
#: exists only here and in the browser — never in the database, never in JSON.
SESSION_COOKIE_NAME = "rds_session"

_UNAUTHENTICATED_DETAIL = "Authentication required."
_FORBIDDEN_DETAIL = "You do not have permission to perform this action."
_MUST_CHANGE_PASSWORD_DETAIL = "Password change required before continuing."


@dataclass(frozen=True, slots=True)
class ActorContext:
    """Who is acting, with what roles, through which request.

    Deliberately a small frozen record rather than a context framework. It is
    what an audited operation needs in order to answer "who changed what, when,
    through which request".
    """

    user_id: uuid.UUID
    email: str
    display_name: str
    role_keys: frozenset[str]
    correlation_id: uuid.UUID
    must_change_password: bool

    @property
    def is_system_admin(self) -> bool:
        return ROLE_SYSTEM_ADMIN in self.role_keys

    def has_any_role(self, *keys: str) -> bool:
        return bool(self.role_keys.intersection(keys))


def db_session() -> Iterator[Session]:
    """Yield a request-scoped database session."""
    yield from get_session()


DbSession = Annotated[Session, Depends(db_session)]


def current_user(request: Request, session: DbSession) -> User:
    """Resolve the authenticated user from the session cookie, or fail with 401."""
    raw_token = request.cookies.get(SESSION_COOKIE_NAME, "")
    user = resolve_session(session, raw_token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=_UNAUTHENTICATED_DETAIL
        )
    return user


AuthenticatedUser = Annotated[User, Depends(current_user)]


def current_actor(request: Request, user: AuthenticatedUser) -> ActorContext:
    """The authenticated caller's actor context."""
    return ActorContext(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        role_keys=user.role_keys,
        correlation_id=get_correlation_id(request),
        must_change_password=user.must_change_password,
    )


CurrentActor = Annotated[ActorContext, Depends(current_actor)]


def active_actor(actor: CurrentActor) -> ActorContext:
    """An actor cleared for normal work.

    A user holding an administrator-issued temporary password may read their own
    identity, change their password and log out. Everything else waits until the
    password has been replaced.
    """
    if actor.must_change_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=_MUST_CHANGE_PASSWORD_DETAIL
        )
    return actor


ActiveActor = Annotated[ActorContext, Depends(active_actor)]


def require_roles(*role_keys: str) -> Callable[..., ActorContext]:
    """Build a dependency admitting only callers holding one of ``role_keys``."""

    def dependency(actor: ActiveActor) -> ActorContext:
        if not actor.has_any_role(*role_keys):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_FORBIDDEN_DETAIL)
        return actor

    return dependency


#: The System Administrator gate used by every governance mutation.
require_system_admin = require_roles(ROLE_SYSTEM_ADMIN)

SystemAdmin = Annotated[ActorContext, Depends(require_system_admin)]
