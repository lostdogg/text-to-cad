"""FastAPI application entry point."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.collaborate import router as collaborate_router
from .api.export import router as export_router
from .api.generate import router as generate_router
from .api.system import router as system_router
from .config import settings
from .metadata import APP_VERSION

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("Text-to-CAD backend starting in %s mode...", settings.MODE)
    os.makedirs(os.path.abspath(settings.EXPORT_DIR), exist_ok=True)
    logger.info("Export directory: %s", os.path.abspath(settings.EXPORT_DIR))
    yield
    logger.info("Text-to-CAD backend shutting down.")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Text-to-CAD API",
        description=(
            "AI-powered text-to-CAD system with multi-agent architecture, "
            "CSG operations, manufacturing optimization, and real-time collaboration."
        ),
        version=APP_VERSION,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ------------------------------------------------------------------ #
    # CORS                                                                 #
    # ------------------------------------------------------------------ #
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ------------------------------------------------------------------ #
    # Routers                                                              #
    # ------------------------------------------------------------------ #
    app.include_router(generate_router, prefix="/api")
    app.include_router(collaborate_router, prefix="/api")
    app.include_router(export_router, prefix="/api")
    app.include_router(system_router, prefix="/api")

    # ------------------------------------------------------------------ #
    # Health & root                                                        #
    # ------------------------------------------------------------------ #

    @app.get("/", include_in_schema=False)
    async def root() -> Dict[str, str]:
        return {"message": "Text-to-CAD API", "docs": "/docs"}

    @app.get("/api/health", tags=["system"])
    async def health() -> Dict[str, Any]:
        return {
            "status": "ok",
            "mode": settings.MODE,
            "version": APP_VERSION,
            "openai_enabled": bool(settings.OPENAI_API_KEY),
        }

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.MODE == "local",
        workers=1,
    )
