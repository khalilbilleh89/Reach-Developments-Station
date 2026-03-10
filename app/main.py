"""
Reach Developments Station — Backend Application Entry Point

This is the FastAPI application entry point.
Module routers are registered here as they are implemented.

Architecture: Modular Monolith
See: docs/03-technical/backend-architecture.md
"""

from fastapi import FastAPI

app = FastAPI(
    title="Reach Developments Station",
    description="Real Estate Development Operating System",
    version="0.1.0",
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "reach-developments-station"}
