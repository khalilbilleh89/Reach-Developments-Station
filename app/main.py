"""
Reach Developments Station — Backend Application Entry Point

This is the FastAPI application entry point.
Module routers are registered here as they are implemented.

Architecture: Modular Monolith
See: docs/03-technical/backend-architecture.md
"""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.responses import JSONResponse

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


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Handle application startup and shutdown events."""
    logger.info("Starting %s [env=%s]", settings.APP_NAME, settings.APP_ENV)
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


@app.get("/", tags=["root"])
async def root() -> dict:
    """Lightweight root endpoint for liveness visibility on Render."""
    response: dict = {
        "app": settings.APP_NAME,
        "status": "running",
    }
    if settings.APP_DEBUG:
        response["env"] = settings.APP_ENV
        response["docs"] = "/docs"
    return response


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
