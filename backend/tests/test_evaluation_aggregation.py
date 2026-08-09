"""Tests for cross-Subject evaluation aggregation (app/services/experiments.py
aggregate_evaluation_metrics + GET /experiments/evaluation-summary) and for
correct per-Subject attribution -- one Subject's evaluation must never leak
into or blend with another's, even when both belong to the same User.
"""
import io

import numpy as np
import pandas as pd
import pytest

from app.db.models import Dataset, Model, Subject, Threshold, User
from tests.conftest import TestingSession


@pytest.fixture
def auth_headers(client):
    client.post("/auth/register", json={"email": "agg@example.com", "password": "password123"})
    r = client.post("/auth/login", json={"email": "agg@example.com", "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _make_subject_with_evaluation(user_id: int, name: str, f1: float, precision: float, recall: float, auc) -> int:
    """DB-only stub (same pattern as test_experiments.py's
    _make_trained_subject) -- fast path for exercising the aggregation
    math itself without paying for a real training run."""
    db = TestingSession()
    try:
        subject = Subject(user_id=user_id, name=name)
        db.add(subject)
        db.commit()
        db.refresh(subject)

        dataset = Dataset(
            user_id=user_id, subject_id=subject.id, name="d.csv", file_path="/tmp/nonexistent.csv",
            n_rows=10, n_features=1,
        )
        db.add(dataset)
        db.commit()
        db.refresh(dataset)

        model = Model(
            user_id=user_id, subject_id=subject.id, dataset_id=dataset.id, algorithm="IF",
            status="ready", is_active=True,
            metrics_json={
                "evaluation": {
                    "precision": precision, "recall": recall, "f1": f1, "auc": auc,
                    "n_test_samples": 100, "n_test_positive": 10,
                }
            },
        )
        db.add(model)
        db.commit()
        db.refresh(model)

        db.add(Threshold(model_id=model.id, mu=0.1, sigma=0.01, epsilon=0.13, z_multiplier=3.0))
        db.commit()
        return subject.id
    finally:
        db.close()


def _make_untrained_subject(user_id: int, name: str) -> int:
    db = TestingSession()
    try:
        subject = Subject(user_id=user_id, name=name)
        db.add(subject)
        db.commit()
        db.refresh(subject)
        return subject.id
    finally:
        db.close()


def test_evaluation_summary_aggregates_known_f1_values(client, auth_headers):
    db = TestingSession()
    user = db.query(User).filter_by(email="agg@example.com").first()
    db.close()

    _make_subject_with_evaluation(user.id, "S1", f1=0.6, precision=0.6, recall=0.6, auc=0.7)
    _make_subject_with_evaluation(user.id, "S2", f1=0.8, precision=0.8, recall=0.8, auc=0.85)
    _make_subject_with_evaluation(user.id, "S3", f1=1.0, precision=1.0, recall=1.0, auc=1.0)

    r = client.get("/experiments/evaluation-summary", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["n_labeled_subjects"] == 3
    assert body["n_unlabeled_subjects"] == 0
    assert set(body["f1_by_subject"].keys()) == {"S1", "S2", "S3"}
    assert body["f1_statistics"]["mean"] == pytest.approx(0.8)
    assert body["f1_statistics"]["min"] == pytest.approx(0.6)
    assert body["f1_statistics"]["max"] == pytest.approx(1.0)
    assert body["auc_statistics"]["mean"] == pytest.approx((0.7 + 0.85 + 1.0) / 3)


def test_evaluation_summary_excludes_untrained_and_unlabeled_subjects(client, auth_headers):
    db = TestingSession()
    user = db.query(User).filter_by(email="agg@example.com").first()
    db.close()

    labeled_id = _make_subject_with_evaluation(user.id, "Labeled", f1=0.75, precision=0.7, recall=0.8, auc=0.9)
    untrained_id = _make_untrained_subject(user.id, "Untrained")

    r = client.get("/experiments/evaluation-summary", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["n_labeled_subjects"] == 1
    assert body["n_unlabeled_subjects"] == 1
    assert body["subject_ids"] == [labeled_id]
    assert body["excluded_subject_ids"] == [untrained_id]
    assert body["f1_statistics"]["mean"] == pytest.approx(0.75)


def test_evaluation_summary_with_no_labeled_subjects_returns_none_stats(client, auth_headers):
    db = TestingSession()
    user = db.query(User).filter_by(email="agg@example.com").first()
    db.close()
    _make_untrained_subject(user.id, "Untrained only")

    r = client.get("/experiments/evaluation-summary", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["n_labeled_subjects"] == 0
    assert body["f1_statistics"] is None
    assert body["auc_statistics"] is None


def test_evaluation_summary_ownership_isolated(client, auth_headers):
    db = TestingSession()
    user = db.query(User).filter_by(email="agg@example.com").first()
    db.close()
    _make_subject_with_evaluation(user.id, "Mine", f1=0.5, precision=0.5, recall=0.5, auc=0.6)

    client.post("/auth/register", json={"email": "other_agg@example.com", "password": "password123"})
    other = TestingSession().query(User).filter_by(email="other_agg@example.com").first()
    _make_subject_with_evaluation(other.id, "Theirs", f1=0.99, precision=0.99, recall=0.99, auc=0.99)

    r = client.get("/experiments/evaluation-summary", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body["f1_by_subject"].keys()) == {"Mine"}
    assert body["f1_statistics"]["mean"] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Per-Subject attribution: two real, independently-trained Subjects with
# deliberately different label distributions must end up with different,
# non-blended evaluation numbers -- not averaged, not overwritten, not
# cross-contaminated in the DB.
# ---------------------------------------------------------------------------


def _clean_labeled_csv_bytes(n_normal=595, n_test=105, seed=11):
    """Anomalies shifted far away (+20) -- should be almost perfectly
    separable, i.e. a high F1."""
    rng = np.random.default_rng(seed)
    normal = rng.normal(0, 1, n_normal)
    test_values = np.empty(n_test)
    test_labels = np.zeros(n_test, dtype=int)
    for i in range(n_test):
        if i % 2 == 0:
            test_values[i] = rng.normal(20, 1)
            test_labels[i] = 1
        else:
            test_values[i] = rng.normal(0, 1)
    df = pd.DataFrame(
        {
            "value": np.concatenate([normal, test_values]),
            "is_anomaly": np.concatenate([np.zeros(n_normal, dtype=int), test_labels]),
        }
    )
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return buf


def _noisy_labeled_csv_bytes(n_normal=595, n_test=105, seed=12):
    """Anomalies barely shifted (+0.3) and buried in the same noise as
    normal rows -- should be much harder to separate, i.e. a low F1."""
    rng = np.random.default_rng(seed)
    normal = rng.normal(0, 1, n_normal)
    test_values = np.empty(n_test)
    test_labels = np.zeros(n_test, dtype=int)
    for i in range(n_test):
        if i % 2 == 0:
            test_values[i] = rng.normal(0.3, 1)
            test_labels[i] = 1
        else:
            test_values[i] = rng.normal(0, 1)
    df = pd.DataFrame(
        {
            "value": np.concatenate([normal, test_values]),
            "is_anomaly": np.concatenate([np.zeros(n_normal, dtype=int), test_labels]),
        }
    )
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return buf


def _upload_and_commit(client, auth_headers, csv_bytes, subject_name):
    r = client.post("/upload/analyze", headers=auth_headers, files={"file": ("data.csv", csv_bytes, "text/csv")})
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
            "label_column": "is_anomaly",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["subject_ids"][0]


def test_two_subjects_get_independent_non_blended_evaluations(client, auth_headers):
    clean_id = _upload_and_commit(client, auth_headers, _clean_labeled_csv_bytes(), "Clean subject")
    noisy_id = _upload_and_commit(client, auth_headers, _noisy_labeled_csv_bytes(), "Noisy subject")

    r_clean = client.get(f"/subjects/{clean_id}", headers=auth_headers)
    r_noisy = client.get(f"/subjects/{noisy_id}", headers=auth_headers)
    assert r_clean.status_code == 200 and r_noisy.status_code == 200

    ev_clean = r_clean.json()["models"][0]["evaluation"]
    ev_noisy = r_noisy.json()["models"][0]["evaluation"]
    assert ev_clean is not None and ev_noisy is not None

    # The two Subjects' data is different enough that their F1s must differ
    # -- if they came out identical (or one leaked into the other) this
    # would be the bug this test exists to catch.
    assert ev_clean["f1"] != pytest.approx(ev_noisy["f1"])
    assert ev_clean["f1"] > ev_noisy["f1"]

    # Direct DB check -- not just the API response shape -- that each
    # Model row's metrics_json only ever held its own Subject's numbers.
    db = TestingSession()
    try:
        model_clean = db.query(Model).filter_by(subject_id=clean_id).first()
        model_noisy = db.query(Model).filter_by(subject_id=noisy_id).first()
        assert model_clean.metrics_json["evaluation"]["f1"] == pytest.approx(ev_clean["f1"])
        assert model_noisy.metrics_json["evaluation"]["f1"] == pytest.approx(ev_noisy["f1"])
        assert model_clean.metrics_json["evaluation"]["f1"] != model_noisy.metrics_json["evaluation"]["f1"]
    finally:
        db.close()

    # And the aggregation endpoint reports both, independently, by name.
    r = client.get("/experiments/evaluation-summary", headers=auth_headers)
    body = r.json()
    assert body["f1_by_subject"]["Clean subject"] == pytest.approx(ev_clean["f1"])
    assert body["f1_by_subject"]["Noisy subject"] == pytest.approx(ev_noisy["f1"])
