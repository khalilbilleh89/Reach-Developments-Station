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

from app.core.config import settings
from app.core.database import check_db_connection
from app.core.logging import logger


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Handle application startup and shutdown events."""
    logger.info("Starting %s [env=%s]", settings.APP_NAME, settings.APP_ENV)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    description="Real Estate Development Operating System",
    version="0.1.0",
    debug=settings.APP_DEBUG,
    lifespan=lifespan,
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
