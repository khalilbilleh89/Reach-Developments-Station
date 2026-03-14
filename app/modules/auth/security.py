"""
auth.security

Low-level security utilities: password hashing and JWT encode/decode.
FastAPI dependencies for extracting and verifying the current user are also here.
"""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

_bearer = HTTPBearer(auto_error=True)


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------


def hash_password(plain: str) -> str:
    """Return the bcrypt hash of *plain*."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Return True when *plain* matches *hashed*."""
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------


def create_access_token(payload: dict) -> str:
    """Return a signed JWT containing *payload* plus an expiry claim."""
    data = payload.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    data["exp"] = expire
    return jwt.encode(data, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and verify *token*; raise HTTPException on failure."""
    try:
        return jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------


def get_current_user_payload(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    """Dependency: decode the Bearer token and return the raw payload dict."""
    return decode_access_token(credentials.credentials)


def require_roles(*required: str):
    """Return a dependency that enforces at least one of the given roles."""

    def _check(payload: dict = Depends(get_current_user_payload)) -> dict:
        user_roles: list[str] = payload.get("roles", [])
        if not any(r in user_roles for r in required):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return payload

    return _check
