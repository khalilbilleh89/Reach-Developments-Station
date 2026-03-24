"""
Reach Developments Station — Backend Application Entry Point

This is the FastAPI application entry point.
Module routers are registered here as they are implemented.

Architecture: Modular Monolith
See: docs/03-technical/backend-architecture.md
"""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from app.api.health import router as health_router
from app.core.bootstrap import seed_admin_user
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.error_handlers import register_error_handlers
from app.core.logging import logger
from app.core.middleware.request_logging import RequestLoggingMiddleware
from app.modules.auth.api import router as auth_router
from app.modules.buildings.api import router as buildings_router
from app.modules.collections.api import router as collections_router
from app.modules.feasibility.api import router as feasibility_router
from app.modules.finance.api import router as finance_router
from app.modules.finance.revenue_router import router as finance_revenue_router
from app.modules.floors.api import router as floors_router
from app.modules.land.api import router as land_router
from app.modules.payment_plans.api import router as payment_plans_router
from app.modules.phases.api import router as phases_router
from app.modules.projects.api import router as projects_router
from app.modules.pricing.api import router as pricing_router
from app.modules.sales.api import router as sales_router
from app.modules.registry.api import router as registry_router, legacy_router as registration_legacy_router
from app.modules.sales_exceptions.api import router as sales_exceptions_router
from app.modules.units.api import router as units_router
from app.modules.commission.api import router as commission_router
from app.modules.cashflow.api import router as cashflow_router
from app.modules.reservations.api import router as reservations_router
from app.modules.receivables.api import router as receivables_router
from app.modules.construction.api import router as construction_router
from app.modules.settings.api import router as settings_router
from app.modules.scenario.api import router as scenario_router
from app.modules.concept_design.api import router as concept_design_router

# Path to the static export produced by `next build` with `output: "export"`.
# Next.js writes self-contained HTML files and assets to this directory.
# Relative to the working directory uvicorn is started from (repo root).
_FRONTEND_HTML_DIR = Path("frontend/out")

# Path to the compiled JS/CSS chunks served at /_next/static/*.
_FRONTEND_STATIC_DIR = Path("frontend/out/_next/static")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Handle application startup and shutdown events."""
    logger.info("Starting %s [env=%s]", settings.APP_NAME, settings.APP_ENV)

    # Log frontend build availability so operators can confirm static serving state.
    if _FRONTEND_HTML_DIR.is_dir():
        logger.info("Startup: frontend build found at '%s'.", _FRONTEND_HTML_DIR)
    else:
        logger.info(
            "Startup: frontend build not found at '%s' — JSON status fallback active.",
            _FRONTEND_HTML_DIR,
        )

    _is_test_env = (settings.APP_ENV or "").lower() == "test"
    _has_credentials = bool(settings.ADMIN_EMAIL and settings.ADMIN_PASSWORD)

    if _is_test_env:
        logger.debug("Bootstrap: skipped (test environment).")
    elif not _has_credentials:
        logger.info(
            "Bootstrap: ADMIN_EMAIL / ADMIN_PASSWORD not configured — admin seed skipped."
        )
    else:
        try:
            with SessionLocal() as db:
                seed_admin_user(db)
        except Exception:
            logger.exception("Bootstrap: admin seed failed — application startup continues.")

    logger.info("Startup complete: %s is ready.", settings.APP_NAME)
    yield
    logger.info("Shutdown: %s stopping.", settings.APP_NAME)


app = FastAPI(
    title=settings.APP_NAME,
    description="Real Estate Development Operating System",
    version="0.1.0",
    debug=settings.APP_DEBUG,
    lifespan=lifespan,
)

register_error_handlers(app)
app.add_middleware(RequestLoggingMiddleware)

# Health and diagnostics endpoints (no authentication required)
app.include_router(health_router)

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
# Revenue Recognition Engine router — registered after finance_router so that
# the static /finance/revenue/overview path takes priority over /{scenario_id}.
app.include_router(finance_revenue_router, prefix=_API_PREFIX)
app.include_router(registry_router, prefix=_API_PREFIX)
app.include_router(registration_legacy_router, prefix=_API_PREFIX)  # temporary compat alias, see registry/api.py
app.include_router(sales_exceptions_router, prefix=_API_PREFIX)
app.include_router(commission_router, prefix=_API_PREFIX)
app.include_router(cashflow_router, prefix=_API_PREFIX)
app.include_router(reservations_router, prefix=_API_PREFIX)
app.include_router(receivables_router, prefix=_API_PREFIX)
app.include_router(construction_router, prefix=_API_PREFIX)
app.include_router(settings_router, prefix=_API_PREFIX)
app.include_router(scenario_router, prefix=_API_PREFIX)
app.include_router(concept_design_router, prefix=_API_PREFIX)

# Mount Next.js compiled static chunks (/_next/static/*) when the build exists.
# These are the JS/CSS assets referenced by the pre-rendered HTML pages.
if _FRONTEND_STATIC_DIR.is_dir():
    app.mount(
        "/_next/static",
        StaticFiles(directory=str(_FRONTEND_STATIC_DIR)),
        name="nextjs-static",
    )

def _safe_resolve(base: Path, rel: str) -> Path | None:
    """Resolve a path relative to base and verify it stays within base.

    Returns the resolved Path if safe, or None if the result would escape base
    (path traversal guard).
    """
    try:
        resolved = (base / rel).resolve()
        base_resolved = base.resolve()
        if resolved == base_resolved or resolved.is_relative_to(base_resolved):
            return resolved
    except (ValueError, OSError):
        pass
    return None


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_frontend(full_path: str) -> Response:
    """Serve the built Next.js frontend UI for all browser routes.

    Paths that carry a file extension (e.g. /favicon.ico, /robots.txt,
    /manifest.json) are treated as static asset requests:
      - Serve the exact file from the frontend build output if it exists.
      - Return 404 if the file is not found.
    They are never sent through the HTML SPA fallback chain.

    Extensionless paths (app routes) follow the HTML resolution chain:
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

        if full_path and "." in full_path.rsplit("/", 1)[-1]:
            # Static asset request (has a file extension): serve the exact file
            # or return 404.  Never fall through to the HTML/SPA chain.
            asset = _safe_resolve(resolved_html_dir, full_path)
            if asset and asset.is_file():
                return FileResponse(str(asset))
            return JSONResponse({"detail": "Not Found"}, status_code=404)

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
