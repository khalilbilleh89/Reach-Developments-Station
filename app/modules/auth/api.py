"""
auth.api

REST API router for authentication.

Endpoints:
    POST /auth/register  — create account, return JWT
    POST /auth/login     — verify credentials, return JWT
    GET  /auth/me        — return the authenticated user's profile
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.auth.schemas import TokenResponse, UserCreate, UserLogin, UserResponse
from app.modules.auth.security import get_current_user_payload
from app.modules.auth.service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def _get_service(db: Session = Depends(get_db)) -> AuthService:
    return AuthService(db)


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(
    data: UserCreate,
    service: Annotated[AuthService, Depends(_get_service)],
) -> TokenResponse:
    """Register a new user account and return a JWT access token."""
    return service.register(data)


@router.post("/login", response_model=TokenResponse)
def login(
    data: UserLogin,
    service: Annotated[AuthService, Depends(_get_service)],
) -> TokenResponse:
    """Authenticate with email + password and return a JWT access token."""
    return service.login(data)


@router.get("/me", response_model=UserResponse)
def me(
    payload: Annotated[dict, Depends(get_current_user_payload)],
    service: Annotated[AuthService, Depends(_get_service)],
) -> UserResponse:
    """Return the profile of the currently authenticated user."""
    user_id: str = payload["sub"]
    return service.get_current_user(user_id)
