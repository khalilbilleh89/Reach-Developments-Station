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
from app.modules.auth.security import get_current_user_payload

# Import all models so SQLAlchemy registers them with Base.metadata
import app.modules.projects.models  # noqa: F401  (also registers ProjectAttributeDefinition/Option)
import app.modules.phases.models  # noqa: F401
import app.modules.buildings.models  # noqa: F401
import app.modules.floors.models  # noqa: F401
import app.modules.units.models  # noqa: F401  (also registers UnitDynamicAttributeValue)
import app.modules.land.models  # noqa: F401
import app.modules.feasibility.models  # noqa: F401
import app.modules.pricing.models  # noqa: F401
import app.modules.pricing_attributes.models  # noqa: F401
import app.modules.sales.models  # noqa: F401
import app.modules.payment_plans.models  # noqa: F401
import app.modules.collections.models  # noqa: F401
import app.modules.auth.models  # noqa: F401
import app.modules.registry.models  # noqa: F401
import app.modules.sales_exceptions.models  # noqa: F401
import app.modules.commission.models  # noqa: F401
import app.modules.cashflow.models  # noqa: F401
import app.modules.reservations.models  # noqa: F401
import app.modules.receivables.models  # noqa: F401
import app.modules.construction.models  # noqa: F401
import app.modules.finance.models  # noqa: F401
import app.modules.scenario.models  # noqa: F401
import app.modules.concept_design.models  # noqa: F401
import app.modules.construction_costs.models  # noqa: F401
import app.modules.tender_comparison.models  # noqa: F401
import app.modules.strategy_approval.models  # noqa: F401

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
    """TestClient that injects the in-memory test database session and a mock authenticated user."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    def override_get_current_user_payload():
        return {"sub": "test-user", "roles": ["admin"]}

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user_payload] = override_get_current_user_payload
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def unauth_client(db_session):
    """TestClient without authentication, for testing 401/403 rejection."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
