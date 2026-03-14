"""
auth.repository

Database access layer for authentication entities.

No cross-domain data access — operates only on users, roles, and user_roles tables.
"""

from sqlalchemy.orm import Session

from app.modules.auth.models import Role, User, UserRole


class AuthRepository:
    """Database operations for authentication entities."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # User operations
    # ------------------------------------------------------------------

    def get_user_by_email(self, email: str) -> User | None:
        """Return a User matching the given email, or None."""
        return self.db.query(User).filter(User.email == email).first()

    def get_user_by_id(self, user_id: str) -> User | None:
        """Return a User matching the given id, or None."""
        return self.db.query(User).filter(User.id == user_id).first()

    def create_user(self, email: str, password_hash: str) -> User:
        """Persist a new User and return it."""
        user = User(email=email, password_hash=password_hash)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    # ------------------------------------------------------------------
    # Role operations
    # ------------------------------------------------------------------

    def get_role_by_name(self, name: str) -> Role | None:
        """Return a Role by name, or None."""
        return self.db.query(Role).filter(Role.name == name).first()

    def create_role(self, name: str, description: str = "") -> Role:
        """Persist a new Role and return it."""
        role = Role(name=name, description=description)
        self.db.add(role)
        self.db.commit()
        self.db.refresh(role)
        return role

    # ------------------------------------------------------------------
    # UserRole operations
    # ------------------------------------------------------------------

    def get_user_roles(self, user_id: str) -> list[Role]:
        """Return the list of roles assigned to a user."""
        user_roles = (
            self.db.query(UserRole).filter(UserRole.user_id == user_id).all()
        )
        return [ur.role for ur in user_roles]

    def assign_role(self, user_id: str, role_id: str) -> UserRole:
        """Assign a role to a user if not already assigned."""
        existing = (
            self.db.query(UserRole)
            .filter(UserRole.user_id == user_id, UserRole.role_id == role_id)
            .first()
        )
        if existing:
            return existing
        user_role = UserRole(user_id=user_id, role_id=role_id)
        self.db.add(user_role)
        self.db.commit()
        self.db.refresh(user_role)
        return user_role
