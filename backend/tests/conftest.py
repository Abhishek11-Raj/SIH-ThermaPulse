"""Pytest configuration — isolated database + app client for the test run.

Environment is set BEFORE importing app modules so settings resolve to the
temporary database and deterministic mock seed.
"""

from __future__ import annotations

import os
import pathlib
import sys
import tempfile

_TEST_DIR = pathlib.Path(tempfile.mkdtemp(prefix="keshav_test_"))
_TEST_DB = _TEST_DIR / "keshav_test.db"

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
os.environ["MOCK_MODE"] = "true"
os.environ["MOCK_SEED"] = "2026"
os.environ["MOCK_SCENARIO"] = "NORMAL_DAY"
os.environ["WEATHER_API_KEY"] = "test-secret-weather-key"
os.environ["AIR_QUALITY_API_KEY"] = "test-secret-aq-key"

_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _prepare_db():
    """Create tables once per session so any db fixture is usable directly."""
    from app.core.database import init_db

    init_db()


@pytest.fixture(scope="session")
def client():
    """FastAPI TestClient; startup bootstraps DB + mock providers."""
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def db():
    from app.core.database import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def registry():
    from app.providers import registry as reg

    return reg