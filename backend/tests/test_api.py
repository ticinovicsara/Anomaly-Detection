"""End-to-end API tests using SQLite in-memory DB (fast, no docker needed)."""
import io
import os

os.environ["DATABASE_URL"] = "sqlite:///./test.db"

import numpy as np
import pandas as pd
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


def override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


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


@pytest.fixture
def token(client):
    client.post("/auth/register", json={"email": "test@x.com", "password": "pass123"})
    r = client.post("/auth/login", json={"email": "test@x.com", "password": "pass123"})
    return r.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_register_login_me(client):
    r = client.post("/auth/register", json={"email": "a@b.com", "password": "abcdef"})
    assert r.status_code == 201
    r = client.post("/auth/login", json={"email": "a@b.com", "password": "abcdef"})
    assert r.status_code == 200
    tok = r.json()["access_token"]
    me = client.get("/auth/me", headers=_auth(tok))
    assert me.json()["email"] == "a@b.com"


def test_login_wrong_password(client):
    client.post("/auth/register", json={"email": "a@b.com", "password": "abcdef"})
    r = client.post("/auth/login", json={"email": "a@b.com", "password": "wrong"})
    assert r.status_code == 401


def test_upload_and_list_datasets(client, token):
    rng = np.random.default_rng(0)
    df = pd.DataFrame(rng.normal(0, 1, (200, 3)), columns=["a", "b", "c"])
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    buf.seek(0)

    r = client.post("/upload", headers=_auth(token), files={"file": ("data.csv", buf, "text/csv")})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["n_rows"] == 200
    assert body["n_features"] == 3
    assert "profile" in body

    r = client.get("/upload", headers=_auth(token))
    assert len(r.json()) == 1


def test_upload_rejects_non_csv(client, token):
    r = client.post("/upload", headers=_auth(token),
                    files={"file": ("data.txt", b"hello", "text/plain")})
    assert r.status_code == 400


def test_unauth_endpoint_requires_token(client):
    r = client.get("/upload")
    assert r.status_code == 422  # missing Authorization header


def test_register_rate_limited_after_5_per_minute(client):
    for i in range(5):
        r = client.post("/auth/register", json={"email": f"rl{i}@x.com", "password": "abcdef"})
        assert r.status_code == 201
    r = client.post("/auth/register", json={"email": "rl6@x.com", "password": "abcdef"})
    assert r.status_code == 429
