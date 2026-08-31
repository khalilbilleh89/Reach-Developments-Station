"""FastAPI application factory and entrypoint.

Production request routing::

    /api/v1/*  ->  FastAPI JSON API
    /*         ->  static Next.js export (frontend/out)

API routes are registered before the static mount, so the API namespace always
wins.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api import health
from app.core.config import get_settings
from app.core.correlation import correlation_middleware
from app.core.database import dispose_engine
from app.core.errors import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ServiceError,
    ValidationError,
)
from app.modules.access.api import admin_router, auth_router
from app.modules.access.dependencies import SESSION_COOKIE_NAME
from app.modules.audit.api import router as audit_router
from app.modules.inventory.api import router as inventory_router
from app.modules.payment_plans.api import router as payment_plans_router
from app.modules.pricing.api import router as pricing_router
from app.modules.projects.api import router as projects_router
from app.modules.sales.api import router as sales_router
from app.modules.settings.api import router as settings_router

logger = logging.getLogger(__name__)

#: Build output of `npm run build` in frontend/ (Next.js `output: "export"`).
FRONTEND_EXPORT_DIR = Path(__file__).resolve().parent.parent / "frontend" / "out"

#: HTTP methods the API namespace guard answers on.
_GUARDED_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]

#: Returned for any unhandled server error. Raw exception strings never reach a client.
_INTERNAL_ERROR_DETAIL = "Internal server error."

#: Service errors map to exactly one status each, in one place, so that no
#: route handler has to translate them itself.
_SERVICE_ERROR_STATUS: dict[type[ServiceError], int] = {
    AuthenticationError: status.HTTP_401_UNAUTHORIZED,
    PermissionDeniedError: status.HTTP_403_FORBIDDEN,
    NotFoundError: status.HTTP_404_NOT_FOUND,
    ConflictError: status.HTTP_409_CONFLICT,
    ValidationError: status.HTTP_422_UNPROCESSABLE_CONTENT,
}

#: Methods that can change state and therefore need origin protection.
_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

_CROSS_ORIGIN_DETAIL = "Cross-origin request rejected."


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


async def enforce_same_origin(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Reject cookie-authenticated cross-origin state changes.

    ``SameSite=Strict`` already stops a browser attaching the session cookie to
    a cross-site request, so this is defence in depth against a browser or proxy
    that fails to honour it.

    Only a *present and mismatched* ``Origin`` is rejected. A cross-site form or
    fetch always sends one, so the real attack is covered; a missing header
    means a non-browser client, which cannot be induced to replay a cookie it
    was never given.
    """
    origin = request.headers.get("origin")
    if (
        request.method in _UNSAFE_METHODS
        and origin is not None
        and SESSION_COOKIE_NAME in request.cookies
    ):
        expected = f"{request.url.scheme}://{request.url.netloc}"
        if origin.rstrip("/") != expected:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": _CROSS_ORIGIN_DETAIL},
            )
    return await call_next(request)


def _reserve_api_namespace(app: FastAPI, prefix: str) -> None:
    """Keep every path under the API prefix on the JSON error contract.

    ``StaticFiles(html=True)`` answers *any* unmatched path with the frontend's
    404 page, so without this a mistyped endpoint would hand an API client seven
    kilobytes of HTML instead of ``{"detail": ...}``. Registering routers before
    the static mount only protects routes that exist; this reserves the rest of
    the namespace.

    Two patterns are required. ``{prefix}/{path:path}`` does not match the prefix
    root, so a bare ``/api/v1`` would otherwise fall through to the static mount
    and answer with HTML.

    Must be registered after every API router and before the static mount.
    """

    @app.api_route(prefix, methods=_GUARDED_METHODS, include_in_schema=False)
    async def api_root_not_found() -> None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found.")

    @app.api_route(
        f"{prefix}/{{unmatched_path:path}}",
        methods=_GUARDED_METHODS,
        include_in_schema=False,
    )
    async def api_not_found(unmatched_path: str) -> None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found.")


def create_app() -> FastAPI:
    """Build the FastAPI application from the canonical settings.

    Deliberately takes no settings argument. Accepting one would imply the whole
    app could be built against an injected configuration, but the lifespan and
    the database layer read ``get_settings()`` directly, so only the OpenAPI URL
    and the router prefix would ever follow it. Tests re-point configuration
    through the environment and clear the settings cache instead.
    """
    settings = get_settings()

    # The schema enumerates every administrative endpoint and payload shape.
    # That was harmless when only health probes existed; it is not now that
    # authentication and governance administration do. Withheld entirely in
    # production rather than hidden behind an authenticated Swagger UI.
    expose_docs = settings.expose_api_docs
    app = FastAPI(
        title="Reach Developments Station",
        version=__version__,
        summary="Real estate development tracking and financial control.",
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json" if expose_docs else None,
        docs_url="/docs" if expose_docs else None,
        redoc_url="/redoc" if expose_docs else None,
        lifespan=lifespan,
    )

    # Registered outermost-first: correlation wraps everything so that even a
    # rejected request carries an identifier.
    app.middleware("http")(enforce_same_origin)
    app.middleware("http")(correlation_middleware)

    @app.exception_handler(ServiceError)
    async def handle_service_error(request: Request, exc: ServiceError) -> JSONResponse:
        """Translate a domain error into its status code and safe body."""
        status_code = _SERVICE_ERROR_STATUS.get(type(exc), status.HTTP_400_BAD_REQUEST)
        return JSONResponse(status_code=status_code, content={"detail": exc.detail})

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        """Return a safe, consistent body for anything that escapes a route handler."""
        logger.exception("Unhandled error while serving %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": _INTERNAL_ERROR_DETAIL},
        )

    # Order is load-bearing: real API routes, then the namespace guard that
    # claims whatever is left under /api/v1, then the static export.
    for router in (
        health.router,
        auth_router,
        admin_router,
        settings_router,
        projects_router,
        inventory_router,
        pricing_router,
        sales_router,
        payment_plans_router,
        audit_router,
    ):
        app.include_router(router, prefix=settings.API_V1_PREFIX)
    _reserve_api_namespace(app, settings.API_V1_PREFIX)
    _mount_frontend(app)

    return app


app = create_app()
