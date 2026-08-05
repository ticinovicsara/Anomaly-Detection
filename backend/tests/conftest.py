"""Shared pytest fixtures for API-level tests (SQLite, no docker needed).

The engine/dependency-override setup lives here once, not duplicated per
test file: app.dependency_overrides[get_db] mutates the shared FastAPI
`app` singleton, so if multiple test files each set it independently at
module level, whichever file pytest collects *last* silently wins for
every test -- including ones in files collected earlier, which then fail
with "no such table" against an engine they never created tables on.
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.limiter import limiter
from app.db.base import Base
from app.db.session import get_db
from app.main import app

engine = create_engine("sqlite:///./test.db", connect_args={"check_same_thread": False})
TestingSession = sessionmaker(bind=engine)


def _override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture(autouse=True)
def _reset_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    limiter.reset()
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def client():
    return TestClient(app)
