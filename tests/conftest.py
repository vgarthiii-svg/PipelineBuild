"""
Shared pytest fixtures. Each test gets an isolated SQLite DB so runs never
touch data/pipeline.db. We override the FastAPI dependency that hands out
DB sessions so the whole app uses our test DB.
"""

import os
import sys
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure the project root is importable
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from app.database import Base, get_db  # noqa: E402
from app import models  # noqa: E402,F401 - register models
from app.main import app  # noqa: E402


@pytest.fixture
def test_db():
    """One fresh SQLite file per test."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Seed the criteria library so tests that toggle criteria find library entries
    from app.seed import _seed_criteria_library
    db = TestingSessionLocal()
    try:
        _seed_criteria_library(db)
        db.commit()
    finally:
        db.close()

    def _override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    yield TestingSessionLocal
    app.dependency_overrides.clear()
    try:
        os.remove(path)
    except OSError:
        pass


@pytest.fixture
def client(test_db):
    """TestClient that routes through the fresh test DB."""
    return TestClient(app)


@pytest.fixture
def sample_client(test_db):
    """A minimal client row, no criteria. Returns dict with id."""
    from app.models import Client
    db = test_db()
    try:
        c = Client(name="Acme Insurance", description="Regional P&C carrier.", active=True)
        db.add(c)
        db.commit()
        db.refresh(c)
        return {"id": c.id, "name": c.name}
    finally:
        db.close()


@pytest.fixture
def sample_prospect(test_db):
    """A minimal prospect row. Returns dict with id."""
    from app.models import Prospect
    db = test_db()
    try:
        p = Prospect(name="Vendor Co", description="Tech vendor", type="Technology")
        db.add(p)
        db.commit()
        db.refresh(p)
        return {"id": p.id, "name": p.name}
    finally:
        db.close()
