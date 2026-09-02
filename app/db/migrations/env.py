"""Alembic runtime environment for MVP 1.0.

The migration runner and the application share one canonical database
configuration: the URL comes from ``app.core.config`` and the engine from
``app.core.database``. ``alembic.ini`` deliberately carries no ``sqlalchemy.url``.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context

from app.core.config import get_settings
from app.core.database import dispose_engine, get_engine
from app.db.base import Base

config = context.config

if config.config_file_name is not None:
    # Keep loggers configured by the host process (uvicorn, pytest) alive.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# Importing the model modules registers them on ``Base.metadata`` so that
# autogenerate and the migration environment see the full schema. Each roadmap
# PR adds its module here.
from app.modules.access import models as access_models  # noqa: E402,F401
from app.modules.audit import models as audit_models  # noqa: E402,F401
from app.modules.collections import models as collections_models  # noqa: E402,F401
from app.modules.inventory import models as inventory_models  # noqa: E402,F401
from app.modules.payment_plans import models as payment_plan_models  # noqa: E402,F401
from app.modules.pricing import models as pricing_models  # noqa: E402,F401
from app.modules.projects import models as projects_models  # noqa: E402,F401
from app.modules.sales import models as sales_models  # noqa: E402,F401
from app.modules.settings import models as settings_models  # noqa: E402,F401
from app.modules.unit_economics import models as unit_economics_models  # noqa: E402,F401

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL to stdout without connecting to a database (``alembic --sql``).

    Offline mode never opens a connection and uses the URL only to select a
    dialect, so no credential is carried in. ``safe_database_url`` is the one
    redaction helper: unlike ``render_as_string(hide_password=True)`` it also
    masks libpq's ``?password=`` query-parameter form.
    """
    settings = get_settings()
    context.configure(
        url=settings.safe_database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live PostgreSQL connection."""
    engine = get_engine()
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
                compare_server_default=True,
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        dispose_engine()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
