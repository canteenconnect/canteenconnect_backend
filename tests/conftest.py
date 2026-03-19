"""Test fixtures for the FastAPI backend."""

# ruff: noqa: E402

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

TEST_DB_PATH = Path("./test_fastapi_backend.db")
TEST_DATABASE_URL = f"sqlite:///{TEST_DB_PATH}"

os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["AUTO_CREATE_SCHEMA"] = "false"
os.environ["CORS_ORIGINS"] = "http://testserver"

from app.core.database import get_db
from app.main import app
from app.models import Base
from app.services.auth import ensure_roles

engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture()
def client() -> TestClient:
    """Create a fresh app client backed by a temporary SQLite database."""

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestingSessionLocal() as db:
        ensure_roles(db)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if TEST_DB_PATH.exists():
        try:
            TEST_DB_PATH.unlink()
        except PermissionError:
            pass


@pytest.fixture()
def db_session_factory():
    """Expose the test session factory for service-level setup in tests."""

    return TestingSessionLocal
