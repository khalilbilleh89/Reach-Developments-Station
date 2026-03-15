"""
Reach Developments Station — Backend Application Entry Point

This is the FastAPI application entry point.
Module routers are registered here as they are implemented.

Architecture: Modular Monolith
See: docs/03-technical/backend-architecture.md
"""

import os
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from app.core.bootstrap import seed_admin_user
from app.core.config import settings
from app.core.database import SessionLocal, check_db_connection
from app.core.logging import logger
from app.modules.auth.api import router as auth_router
from app.modules.buildings.api import router as buildings_router
from app.modules.collections.api import router as collections_router
from app.modules.feasibility.api import router as feasibility_router
from app.modules.finance.api import router as finance_router
from app.modules.floors.api import router as floors_router
from app.modules.land.api import router as land_router
from app.modules.payment_plans.api import router as payment_plans_router
from app.modules.phases.api import router as phases_router
from app.modules.projects.api import router as projects_router
from app.modules.pricing.api import router as pricing_router
from app.modules.sales.api import router as sales_router
from app.modules.registration.api import router as registration_router
from app.modules.sales_exceptions.api import router as sales_exceptions_router
from app.modules.units.api import router as units_router
from app.modules.commission.api import router as commission_router
from app.modules.cashflow.api import router as cashflow_router

# Path to the pre-rendered HTML files produced by `next build`.
# Next.js (App Router) writes one .html file per static route to this directory.
# Relative to the working directory uvicorn is started from (repo root).
_FRONTEND_HTML_DIR = Path("frontend/.next/server/app")

# Path to the compiled JS/CSS chunks served at /_next/static/*.
_FRONTEND_STATIC_DIR = Path("frontend/.next/static")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Handle application startup and shutdown events."""
    logger.info("Starting %s [env=%s]", settings.APP_NAME, settings.APP_ENV)
    _is_test_env = (settings.APP_ENV or "").lower() == "test"
    _has_credentials = bool(settings.ADMIN_EMAIL and settings.ADMIN_PASSWORD)
    if not _is_test_env and _has_credentials:
        try:
            with SessionLocal() as db:
                seed_admin_user(db)
        except Exception:
            logger.exception("Bootstrap: admin seed failed — application startup continues.")
    yield


app = FastAPI(
    title=settings.APP_NAME,
    description="Real Estate Development Operating System",
    version="0.1.0",
    debug=settings.APP_DEBUG,
    lifespan=lifespan,
)

# Asset hierarchy routers
_API_PREFIX = settings.API_V1_PREFIX
app.include_router(auth_router, prefix=_API_PREFIX)
app.include_router(projects_router, prefix=_API_PREFIX)
app.include_router(phases_router, prefix=_API_PREFIX)
app.include_router(buildings_router, prefix=_API_PREFIX)
app.include_router(floors_router, prefix=_API_PREFIX)
app.include_router(units_router, prefix=_API_PREFIX)
app.include_router(land_router, prefix=_API_PREFIX)
app.include_router(feasibility_router, prefix=_API_PREFIX)
app.include_router(pricing_router, prefix=_API_PREFIX)
app.include_router(sales_router, prefix=_API_PREFIX)
app.include_router(payment_plans_router, prefix=_API_PREFIX)
app.include_router(collections_router, prefix=_API_PREFIX)
app.include_router(finance_router, prefix=_API_PREFIX)
app.include_router(registration_router, prefix=_API_PREFIX)
app.include_router(sales_exceptions_router, prefix=_API_PREFIX)
app.include_router(commission_router, prefix=_API_PREFIX)
app.include_router(cashflow_router, prefix=_API_PREFIX)

# Mount Next.js compiled static chunks (/_next/static/*) when the build exists.
# These are the JS/CSS assets referenced by the pre-rendered HTML pages.
if _FRONTEND_STATIC_DIR.is_dir():
    app.mount(
        "/_next/static",
        StaticFiles(directory=str(_FRONTEND_STATIC_DIR)),
        name="nextjs-static",
    )


@app.get("/health", tags=["health"])
async def health_check() -> JSONResponse:
    """Application health check endpoint."""
    return JSONResponse({"status": "ok", "service": "reach-developments-station"})


@app.get("/health/db", tags=["health"])
async def health_db() -> JSONResponse:
    """Database connectivity health check endpoint."""
    reachable = check_db_connection()
    if reachable:
        return JSONResponse({"status": "ok", "database": "reachable"})
    return JSONResponse(
        {"status": "error", "database": "unreachable"},
        status_code=503,
    )


def _safe_resolve(base: Path, rel: str) -> Path | None:
    """Resolve a path relative to base and verify it stays within base.

    Returns the resolved Path if safe, or None if the result would escape base
    (path traversal guard).
    """
    try:
        resolved = (base / rel).resolve()
        base_resolved = base.resolve()
        if str(resolved).startswith(str(base_resolved) + os.sep) or resolved == base_resolved:
            return resolved
    except (ValueError, OSError):
        pass
    return None


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_frontend(full_path: str) -> Response:
    """Serve the built Next.js frontend UI for all browser routes.

    Route resolution order (all candidates are inside frontend/.next/server/app/):
      1. Exact HTML file:   /login        → login.html
      2. Index fallback:    /login/       → login/index.html  (rare)
      3. Parent segment:    /sales/123    → sales.html  (dynamic route SPA fallback)
      4. Root index.html:   catch-all SPA fallback

    When the frontend build is absent (development, CI, test environments)
    a lightweight JSON status payload is returned to preserve backward
    compatibility with existing health monitors that poll GET /.

    API routes (/api/v1/*, /docs, /health*) are registered before this
    catch-all and are matched first by FastAPI's router.
    """
    if _FRONTEND_HTML_DIR.is_dir():
        resolved_html_dir = _FRONTEND_HTML_DIR.resolve()

        if full_path:
            # 1. Exact HTML file: /login → login.html
            exact = _safe_resolve(resolved_html_dir, full_path + ".html")
            if exact and exact.is_file():
                return FileResponse(str(exact))

            # 2. Subdirectory index: /login/ → login/index.html
            index = _safe_resolve(resolved_html_dir, full_path + "/index.html")
            if index and index.is_file():
                return FileResponse(str(index))

            # 3. Parent segment fallback for dynamic routes:
            #    /sales/123 → try sales.html (SPA loads and client-routes to /sales/123)
            parent = Path(full_path).parent
            if str(parent) not in {".", ""}:
                parent_html = _safe_resolve(resolved_html_dir, str(parent) + ".html")
                if parent_html and parent_html.is_file():
                    return FileResponse(str(parent_html))

        # 4. Root index.html — ultimate SPA fallback
        root_index = resolved_html_dir / "index.html"
        if root_index.is_file():
            return FileResponse(str(root_index))

    # Frontend build not present — return lightweight status payload.
    # Preserves backward compatibility in development and test environments.
    response_body: dict = {"app": settings.APP_NAME, "status": "running"}
    if settings.APP_DEBUG:
        response_body["env"] = settings.APP_ENV
        response_body["docs"] = "/docs"
    return JSONResponse(response_body)
