"""Application bootstrap utilities for schema initialization and seed data."""

from __future__ import annotations

from sqlalchemy import inspect

from app.core.config import get_settings
from app.core.database import Base, SessionLocal, engine
from app.models import RefreshToken, RevokedToken
from app.services.auth import ensure_roles, seed_initial_admin

REQUIRED_TABLES = {
    "roles",
    "users",
    "outlets",
    "menu_items",
    "orders",
    "order_items",
    "payments",
    "refresh_tokens",
    "revoked_tokens",
}
AUTH_SUPPORT_TABLES = [RefreshToken.__table__, RevokedToken.__table__]


def initialize_application() -> None:
    """Initialize schema-dependent seed data during application startup."""

    settings = get_settings()

    if settings.auto_create_schema:
        Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    if not {"refresh_tokens", "revoked_tokens"}.issubset(existing_tables):
        Base.metadata.create_all(bind=engine, tables=AUTH_SUPPORT_TABLES)
        inspector = inspect(engine)
        existing_tables = set(inspector.get_table_names())

    if not REQUIRED_TABLES.issubset(existing_tables):
        return

    with SessionLocal() as db:
        ensure_roles(db)
        seed_initial_admin(db, settings)

