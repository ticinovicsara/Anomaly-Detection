"""Tests for the optional, off-by-default pre-retrain data review feature:
app/services/data_review.py's find_candidate_anomalies (pure, no DB) and
the /subjects/{id}/retrain gate + /data-review endpoints (API level)."""
import io
import math

import numpy as np
import pandas as pd
import pytest

from app.db.models import DataReviewCandidate
from app.services.data_review import find_candidate_anomalies
from tests.conftest import TestingSession


# ---------------------------------------------------------------------------
# find_candidate_anomalies -- pure function, no DB
# ---------------------------------------------------------------------------


def test_find_candidate_anomalies_flags_injected_outliers():
    rng = np.random.default_rng(0)
    values = rng.normal(0, 1, 300)
    outlier_idx = [20, 120, 250]
    for i in outlier_idx:
        values[i] = 100.0
    df = pd.DataFrame({"value": values})

    candidates = find_candidate_anomalies(df, max_candidates=100, top_fraction=0.03)
    flagged = {c["row_index"] for c in candidates}
    assert set(outlier_idx).issubset(flagged)
    assert len(candidates) <= math.ceil(0.03 * 300)


def test_find_candidate_anomalies_respects_max_candidates_cap():
    rng = np.random.default_rng(1)
    values = rng.normal(0, 1, 10_000)
    df = pd.DataFrame({"value": values})

    candidates = find_candidate_anomalies(df, max_candidates=50, top_fraction=0.5)
    # top_fraction alone would ask for 5000 rows -- max_candidates must win.
    assert len(candidates) == 50


def test_find_candidate_anomalies_too_few_rows_returns_empty():
    df = pd.DataFrame({"value": np.arange(5, dtype=float)})
    assert find_candidate_anomalies(df) == []


def test_find_candidate_anomalies_no_numeric_columns_returns_empty():
    df = pd.DataFrame({"text": ["a", "b", "c"] * 10})
    assert find_candidate_anomalies(df) == []


def test_find_candidate_anomalies_candidates_sorted_most_suspicious_first():
    rng = np.random.default_rng(2)
    values = rng.normal(0, 1, 200)
    values[15] = 200.0  # far more extreme than anything else
    df = pd.DataFrame({"value": values})

    candidates = find_candidate_anomalies(df, max_candidates=10, top_fraction=0.05)
    assert candidates[0]["row_index"] == 15


# ---------------------------------------------------------------------------
# API level: /subjects/{id}/retrain gate + /data-review endpoints
# ---------------------------------------------------------------------------


@pytest.fixture
def auth_headers(client):
    client.post("/auth/register", json={"email": "review@example.com", "password": "password123"})
    r = client.post("/auth/login", json={"email": "review@example.com", "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _outlier_csv_bytes(n=200, outlier_indices=(10, 90, 150)):
    """Mostly normal, with a handful of far-outlier rows an unsupervised
    IF scan should easily surface among its top candidates."""
    rng = np.random.default_rng(5)
    values = rng.normal(0, 1, n)
    for i in outlier_indices:
        values[i] = 50.0
    df = pd.DataFrame({"value": values})
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return buf


def _upload_and_commit(client, auth_headers, subject_name="Review subject"):
    r = client.post(
        "/upload/analyze", headers=auth_headers, files={"file": ("data.csv", _outlier_csv_bytes(), "text/csv")}
    )
    temp_id = r.json()["temp_id"]
    r = client.post(
        "/upload/commit",
        headers=auth_headers,
        json={
            "temp_id": temp_id,
            "target": "new",
            "subject_name": subject_name,
            "split": {"mode": "none"},
            "algorithm": "IF",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["subject_ids"][0]


def test_retrain_unchanged_by_default_even_with_outliers_present(client, auth_headers):
    """Regression check: the toggle defaults to off, so retrain must
    behave exactly as it did before this feature existed -- no scan runs,
    no candidates get created, nothing blocks."""
    subject_id = _upload_and_commit(client, auth_headers)

    r = client.post(f"/subjects/{subject_id}/retrain", headers=auth_headers)
    assert r.status_code == 200, r.text

    db = TestingSession()
    try:
        assert db.query(DataReviewCandidate).filter_by(subject_id=subject_id).count() == 0
    finally:
        db.close()


def test_retrain_blocked_when_toggle_on_and_candidates_unreviewed(client, auth_headers):
    subject_id = _upload_and_commit(client, auth_headers)
    r = client.patch(f"/subjects/{subject_id}", headers=auth_headers, json={"pre_retrain_check_enabled": True})
    assert r.status_code == 200 and r.json()["pre_retrain_check_enabled"] is True

    r = client.post(f"/subjects/{subject_id}/retrain", headers=auth_headers)
    assert r.status_code == 422, r.text
    body = r.json()["detail"]
    assert body["pending_candidates"], "expected at least one flagged candidate on an outlier-laden dataset"

    db = TestingSession()
    try:
        stored = db.query(DataReviewCandidate).filter_by(subject_id=subject_id).all()
        assert len(stored) == len(body["pending_candidates"])
        assert all(c.label == "unlabeled" for c in stored)
    finally:
        db.close()


def test_retrain_proceeds_after_candidates_reviewed(client, auth_headers):
    subject_id = _upload_and_commit(client, auth_headers)
    client.patch(f"/subjects/{subject_id}", headers=auth_headers, json={"pre_retrain_check_enabled": True})

    r = client.post(f"/subjects/{subject_id}/retrain", headers=auth_headers)
    assert r.status_code == 422
    pending = r.json()["detail"]["pending_candidates"]
    assert pending

    for c in pending:
        r = client.patch(
            f"/subjects/{subject_id}/data-review/candidates/{c['id']}",
            headers=auth_headers,
            json={"label": "false_positive"},
        )
        assert r.status_code == 200, r.text

    r = client.post(f"/subjects/{subject_id}/retrain", headers=auth_headers)
    assert r.status_code == 200, r.text


def test_retrain_force_bypasses_block_without_reviewing(client, auth_headers):
    subject_id = _upload_and_commit(client, auth_headers)
    client.patch(f"/subjects/{subject_id}", headers=auth_headers, json={"pre_retrain_check_enabled": True})

    r = client.post(f"/subjects/{subject_id}/retrain", headers=auth_headers)
    assert r.status_code == 422

    r = client.post(f"/subjects/{subject_id}/retrain", headers=auth_headers, params={"force": "true"})
    assert r.status_code == 200, r.text


def test_precheck_endpoint_is_idempotent(client, auth_headers):
    subject_id = _upload_and_commit(client, auth_headers)

    r1 = client.post(f"/subjects/{subject_id}/data-review/precheck", headers=auth_headers)
    r2 = client.post(f"/subjects/{subject_id}/data-review/precheck", headers=auth_headers)
    assert r1.status_code == 200 and r2.status_code == 200
    assert [c["id"] for c in r1.json()] == [c["id"] for c in r2.json()]

    db = TestingSession()
    try:
        assert db.query(DataReviewCandidate).filter_by(subject_id=subject_id).count() == len(r1.json())
    finally:
        db.close()


def test_data_review_candidates_ownership_isolated(client, auth_headers):
    subject_id = _upload_and_commit(client, auth_headers)
    client.post(f"/subjects/{subject_id}/data-review/precheck", headers=auth_headers)

    client.post("/auth/register", json={"email": "other_review@example.com", "password": "password123"})
    r = client.post("/auth/login", json={"email": "other_review@example.com", "password": "password123"})
    other_headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    r = client.get(f"/subjects/{subject_id}/data-review/candidates", headers=other_headers)
    assert r.status_code == 404
