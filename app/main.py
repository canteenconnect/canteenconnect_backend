"""FastAPI application entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import api_router
from app.core.config import get_settings
from app.services.bootstrap import initialize_application

OPENAPI_TAGS = [
    {"name": "token", "description": "OAuth2 password-flow token issuance for Swagger UI and API clients."},
    {"name": "auth", "description": "Public authentication and profile bootstrap endpoints."},
    {"name": "menu", "description": "Outlet menu browsing and admin-managed menu operations."},
    {"name": "orders", "description": "Student ordering and operational order status workflows."},
    {"name": "payments", "description": "Payment registration against created orders."},
    {"name": "admin", "description": "Administrative user, outlet, and reporting operations protected by RBAC."},
]


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Initialize the application once the process starts."""

    initialize_application()
    yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        description="Production-ready FastAPI backend for the Canteen Management SaaS.",
        openapi_tags=OPENAPI_TAGS,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/", summary="Service metadata")
    def root() -> dict[str, Any]:
        """Return a lightweight root payload for uptime checks."""

        return {
            "message": "Canteen Management SaaS API",
            "status": "ok",
            "docs": "/docs",
            "health": "/health",
        }

    @app.get("/health", summary="Health check")
    def health() -> dict[str, str]:
        """Return a health response for load balancers and uptime monitors."""

        return {"status": "ok"}

    app.include_router(api_router)
    return app


app = create_app()

