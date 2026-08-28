"""Canonical PostgreSQL engine and session infrastructure.

There is exactly one engine per process and exactly one place that builds it. No
other module may call :func:`sqlalchemy.create_engine`.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

logger = logging.getLogger(__name__)

#: Recycle pooled connections before managed PostgreSQL services drop them.
_POOL_RECYCLE_SECONDS = 1800

#: Bound on a single connection attempt. libpq defaults to waiting forever, so a
#: PostgreSQL that accepts TCP but never completes the startup handshake (an
#: overloaded server, a wedged pooler, a stateful firewall) would block the
#: calling thread indefinitely. Readiness probes run in the shared threadpool
#: that also serves liveness, so an unbounded probe eventually takes liveness
#: down with it and Render kills a process that is otherwise healthy.
#: libpq treats values below 2 as 2.
_CONNECT_TIMEOUT_SECONDS = 5

#: Bound on waiting for a pooled connection, for the same reason.
_POOL_TIMEOUT_SECONDS = 5


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Return the process-wide SQLAlchemy engine.

    Created lazily so that importing the application never requires a reachable
    database — the backend must stay importable and testable without one.
    """
    settings = get_settings()
    logger.info("Creating database engine for %s", settings.safe_database_url)
    return create_engine(
        settings.sqlalchemy_database_url,
        pool_pre_ping=True,
        pool_recycle=_POOL_RECYCLE_SECONDS,
        pool_timeout=_POOL_TIMEOUT_SECONDS,
        connect_args={"connect_timeout": _CONNECT_TIMEOUT_SECONDS},
    )


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    """Return the process-wide session factory.

    Sessions do not autoflush and do not autocommit: transaction boundaries are
    always written explicitly by the calling service.
    """
    return sessionmaker(
        bind=get_engine(),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a database session and always closing it.

    The session is *not* committed here. Services commit or roll back explicitly.
    """
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def check_database_connection() -> None:
    """Execute a minimal ``SELECT 1`` against PostgreSQL.

    Returns normally when the database is reachable.

    Raises:
        sqlalchemy.exc.SQLAlchemyError: if a connection cannot be obtained or the
            probe statement fails.
    """
    with get_engine().connect() as connection:
        connection.execute(text("SELECT 1"))


def dispose_engine() -> None:
    """Close pooled connections and drop the cached engine.

    Called on application shutdown and by tests that re-point configuration.
    Safe to call when no engine has been created.
    """
    if get_engine.cache_info().currsize:
        get_engine().dispose()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
