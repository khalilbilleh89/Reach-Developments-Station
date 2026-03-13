"""
Shared pytest fixtures for database-backed tests.

Uses an in-memory SQLite database for fast, isolated testing.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.dependencies import get_db
from app.db.base import Base

# Import all models so SQLAlchemy registers them with Base.metadata
import app.modules.projects.models  # noqa: F401
import app.modules.phases.models  # noqa: F401
import app.modules.buildings.models  # noqa: F401
import app.modules.floors.models  # noqa: F401
import app.modules.units.models  # noqa: F401
import app.modules.land.models  # noqa: F401
import app.modules.feasibility.models  # noqa: F401
import app.modules.pricing.models  # noqa: F401
import app.modules.sales.models  # noqa: F401
import app.modules.payment_plans.models  # noqa: F401
import app.modules.collections.models  # noqa: F401

from app.main import app

SQLITE_URL = "sqlite://"

engine = create_engine(
    SQLITE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Create tables, yield a test session, then drop all tables."""
    Base.metadata.create_all(bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """TestClient that injects the in-memory test database session."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
