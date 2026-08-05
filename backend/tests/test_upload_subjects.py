"""API integration tests for the two-step /upload/analyze + /upload/commit
flow (SQLite, no docker). Shared fixtures from conftest.py."""
import io

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def auth_headers(client):
    client.post("/auth/register", json={"email": "u@example.com", "password": "password123"})
    r = client.post("/auth/login", json={"email": "u@example.com", "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _csv_bytes(n=100, with_id=False):
    rng = np.random.default_rng(0)
    df = pd.DataFrame({"value": rng.normal(0, 1, n)})
    if with_id:
        df["patient_id"] = [f"p{i % 4}" for i in range(n)]
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return buf


def test_analyze_returns_temp_id_and_profile(client, auth_headers):
    r = client.post("/upload/analyze", headers=auth_headers, files={"file": ("data.csv", _csv_bytes(), "text/csv")})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["temp_id"]
    assert body["n_rows"] == 100
    assert "profile" in body
    assert "split_options" in body


def test_analyze_rejects_non_csv(client, auth_headers):
    r = client.post("/upload/analyze", headers=auth_headers, files={"file": ("data.txt", b"hello", "text/plain")})
    assert r.status_code == 400


def test_commit_no_split_new_subject(client, auth_headers):
    r = client.post("/upload/analyze", headers=auth_headers, files={"file": ("data.csv", _csv_bytes(), "text/csv")})
    temp_id = r.json()["temp_id"]

    r = client.post(
        "/upload/commit",
        headers=auth_headers,
        json={
            "temp_id": temp_id,
            "target": "new",
            "subject_name": "Patient 101",
            "split": {"mode": "none"},
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert len(body["subject_ids"]) == 1
    assert len(body["dataset_ids"]) == 1
    assert body["training_queued"] is True

    r = client.get(f"/subjects/{body['subject_ids'][0]}", headers=auth_headers)
    assert r.json()["name"] == "Patient 101"
    assert r.json()["n_datasets"] == 1


def test_commit_no_split_existing_subject(client, auth_headers):
    r = client.post("/subjects", headers=auth_headers, json={"name": "Existing subject"})
    subject_id = r.json()["id"]

    r = client.post("/upload/analyze", headers=auth_headers, files={"file": ("data.csv", _csv_bytes(), "text/csv")})
    temp_id = r.json()["temp_id"]

    r = client.post(
        "/upload/commit",
        headers=auth_headers,
        json={"temp_id": temp_id, "target": "existing", "subject_id": subject_id, "split": {"mode": "none"}},
    )
    assert r.status_code == 201, r.text
    assert r.json()["subject_ids"] == [subject_id]

    r = client.get(f"/subjects/{subject_id}", headers=auth_headers)
    assert r.json()["n_datasets"] == 1


def test_commit_split_by_column_creates_multiple_subjects(client, auth_headers):
    r = client.post(
        "/upload/analyze", headers=auth_headers, files={"file": ("data.csv", _csv_bytes(with_id=True), "text/csv")}
    )
    temp_id = r.json()["temp_id"]
    ids = {c["column"] for c in r.json()["split_options"]["candidate_id_columns"]}
    assert "patient_id" in ids

    r = client.post(
        "/upload/commit",
        headers=auth_headers,
        json={
            "temp_id": temp_id,
            "target": "new",
            "subject_name": "Batch",
            "split": {"mode": "by_column", "column": "patient_id"},
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert len(body["subject_ids"]) == 4  # p0..p3
    assert len(body["dataset_ids"]) == 4


def test_commit_split_disallows_existing_target(client, auth_headers):
    r = client.post("/subjects", headers=auth_headers, json={"name": "Existing"})
    subject_id = r.json()["id"]

    r = client.post(
        "/upload/analyze", headers=auth_headers, files={"file": ("data.csv", _csv_bytes(with_id=True), "text/csv")}
    )
    temp_id = r.json()["temp_id"]

    r = client.post(
        "/upload/commit",
        headers=auth_headers,
        json={
            "temp_id": temp_id,
            "target": "existing",
            "subject_id": subject_id,
            "split": {"mode": "by_column", "column": "patient_id"},
        },
    )
    assert r.status_code == 400


def test_commit_unknown_temp_id_rejected(client, auth_headers):
    r = client.post(
        "/upload/commit",
        headers=auth_headers,
        json={"temp_id": "does-not-exist", "target": "new", "subject_name": "X", "split": {"mode": "none"}},
    )
    assert r.status_code == 400


def test_commit_new_without_name_rejected(client, auth_headers):
    r = client.post("/upload/analyze", headers=auth_headers, files={"file": ("data.csv", _csv_bytes(), "text/csv")})
    temp_id = r.json()["temp_id"]

    r = client.post(
        "/upload/commit",
        headers=auth_headers,
        json={"temp_id": temp_id, "target": "new", "split": {"mode": "none"}},
    )
    assert r.status_code == 400


def test_commit_cannot_use_another_users_temp_id(client, auth_headers):
    r = client.post("/upload/analyze", headers=auth_headers, files={"file": ("data.csv", _csv_bytes(), "text/csv")})
    temp_id = r.json()["temp_id"]

    client.post("/auth/register", json={"email": "other@example.com", "password": "password123"})
    r2 = client.post("/auth/login", json={"email": "other@example.com", "password": "password123"})
    other_headers = {"Authorization": f"Bearer {r2.json()['access_token']}"}

    r = client.post(
        "/upload/commit",
        headers=other_headers,
        json={"temp_id": temp_id, "target": "new", "subject_name": "X", "split": {"mode": "none"}},
    )
    assert r.status_code == 404


def test_original_upload_endpoint_still_works_unsplit(client, auth_headers):
    """Backward compat: the plain POST /upload endpoint is untouched by
    Phase 3 -- always lands on the user's default Subject, no splitting."""
    r = client.post("/upload", headers=auth_headers, files={"file": ("data.csv", _csv_bytes(), "text/csv")})
    assert r.status_code == 201, r.text

    r = client.get("/subjects", headers=auth_headers)
    subjects = r.json()
    assert len(subjects) == 1
    assert subjects[0]["is_default"] is True
    assert subjects[0]["n_datasets"] == 1
