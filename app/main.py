"""FastAPI application factory and entrypoint.

Production request routing::

    /api/v1/*  ->  FastAPI JSON API
    /*         ->  static Next.js export (frontend/out)

API routes are registered before the static mount, so the API namespace always
wins.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api import health
from app.core.config import Settings, get_settings
from app.core.database import dispose_engine

logger = logging.getLogger(__name__)

#: Build output of `npm run build` in frontend/ (Next.js `output: "export"`).
FRONTEND_EXPORT_DIR = Path(__file__).resolve().parent.parent / "frontend" / "out"

#: Returned for any unhandled server error. Raw exception strings never reach a client.
_INTERNAL_ERROR_DETAIL = "Internal server error."


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Log the resolved configuration on startup and release the pool on shutdown.

    Startup deliberately does *not* open a database connection: a database
    outage must surface as an unready service, not as a crash loop.
    """
    settings = get_settings()
    logger.info(
        "Starting %s (env=%s, debug=%s, database=%s)",
        settings.APP_NAME,
        settings.APP_ENV,
        settings.APP_DEBUG,
        settings.safe_database_url,
    )
    try:
        yield
    finally:
        dispose_engine()
        logger.info("Stopped %s", settings.APP_NAME)


def _mount_frontend(app: FastAPI) -> None:
    """Serve the static Next.js export at the site root, when it exists.

    ``html=True`` plus the Next.js ``trailingSlash`` export layout resolves
    ``/foo/`` to ``out/foo/index.html`` and unknown paths to ``out/404.html``.
    That is the whole routing story — no custom SPA fallback router.

    A missing export directory is not an error: backend-only development and the
    test suite must work without a frontend build.
    """
    if not FRONTEND_EXPORT_DIR.is_dir():
        logger.warning(
            "Frontend export not found at %s — serving the API only. "
            "Run `npm run build` in frontend/ to produce it.",
            FRONTEND_EXPORT_DIR,
        )
        return

    app.mount("/", StaticFiles(directory=FRONTEND_EXPORT_DIR, html=True), name="frontend")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI application."""
    settings = settings or get_settings()

    app = FastAPI(
        title="Reach Developments Station",
        version=__version__,
        summary="Real estate development tracking and financial control.",
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
        lifespan=lifespan,
    )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        """Return a safe, consistent body for anything that escapes a route handler."""
        logger.exception("Unhandled error while serving %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": _INTERNAL_ERROR_DETAIL},
        )

    # API first, static export second. Order is load-bearing.
    app.include_router(health.router, prefix=settings.API_V1_PREFIX)
    _mount_frontend(app)

    return app


app = create_app()
