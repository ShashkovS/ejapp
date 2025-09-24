# backend/tests/conftest.py
# ruff: noqa: E402
from __future__ import annotations

import asyncio
import pathlib
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]  # .../ejapp
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.db import Base
from backend.main import app, engine

DB_FILE = pathlib.Path(__file__).resolve() / 'ejapp_tests.db'


@pytest.fixture(autouse=True)
def _fresh_db_file():
    """
    Ensure file-backed SQLite is clean between pytest runs, not just between tests.
    (Harmless if the DB is elsewhere.)
    """
    try:
        if DB_FILE.exists():
            DB_FILE.unlink()
    except Exception:
        # If it's open, we'll still drop/create tables in the next fixture.
        pass
    yield


@pytest.fixture()
def client():
    """
    Fresh schema for each test, then create a brand-new TestClient bound to the app.
    Doing drop/create BEFORE TestClient avoids races with app startup.
    """

    async def reset():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(reset())

    with TestClient(app) as c:
        yield c
