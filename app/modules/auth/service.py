"""
auth.service

Authentication business logic: registration, login, token issuance, role lookup.
"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.auth.models import Role, User
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import RoleResponse, TokenResponse, UserCreate, UserLogin, UserResponse
from app.modules.auth.security import create_access_token, hash_password, verify_password


class AuthService:
    """Handles registration, login, token generation, and role queries."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = AuthRepository(db)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, data: UserCreate) -> TokenResponse:
        """Create a new user account and return a JWT token."""
        if self.repo.get_user_by_email(data.email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )
        password_hash = hash_password(data.password)
        user = self.repo.create_user(email=data.email, password_hash=password_hash)
        token = create_access_token({"sub": user.id, "roles": []})
        return TokenResponse(access_token=token)

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------

    def login(self, data: UserLogin) -> TokenResponse:
        """Verify credentials and return a JWT token."""
        user = self.repo.get_user_by_email(data.email)
        if user is None or not verify_password(data.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is disabled",
            )
        roles = self._role_names(user)
        token = create_access_token({"sub": user.id, "roles": roles})
        return TokenResponse(access_token=token)

    # ------------------------------------------------------------------
    # Current user
    # ------------------------------------------------------------------

    def get_current_user(self, user_id: str) -> UserResponse:
        """Return the user record for *user_id*."""
        user = self.repo.get_user_by_id(user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        role_objs = self.repo.get_user_roles(user.id)
        return self._build_response(user, role_objs)

    # ------------------------------------------------------------------
    # Role assignment (internal / future admin use)
    # ------------------------------------------------------------------

    def assign_role(self, user_id: str, role_name: str) -> None:
        """Assign an existing role to a user, creating the role if needed."""
        role = self.repo.get_role_by_name(role_name)
        if role is None:
            role = self.repo.create_role(name=role_name)
        self.repo.assign_role(user_id=user_id, role_id=role.id)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _role_names(self, user: User) -> list[str]:
        return [ur.role.name for ur in user.user_roles]

    @staticmethod
    def _build_response(user: User, roles: list[Role]) -> UserResponse:
        return UserResponse(
            id=user.id,
            email=user.email,
            is_active=user.is_active,
            created_at=user.created_at,
            roles=[RoleResponse(id=r.id, name=r.name, description=r.description) for r in roles],
        )
