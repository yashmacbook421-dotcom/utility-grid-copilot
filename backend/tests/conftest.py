"""Shared pytest fixtures. Tests run against the same dev Postgres instance
used by the app (no separate test database/migration tooling in this
project) — read-only tests rely on the already-seeded synthetic + real
documents; write-path tests create and clean up their own rows.

    cd backend && pytest tests/ -v
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.main import app


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
