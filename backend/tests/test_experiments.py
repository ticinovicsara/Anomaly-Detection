"""Tests for the /experiments endpoints (SQLite, no docker).

Most tests insert Subject/Model/Threshold rows directly via the ORM (same
pattern as test_subjects_api.py) to stay fast -- the statistics/validation
logic doesn't need a real trained model. One end-to-end test exercises
run_preset_demo with a small real LSTM training run to make sure the
scoring path (loading the saved model + scaler, re-predicting) actually
works against real files.
"""
import pytest

from app.db.models import Model, Subject, Threshold, User
from app.services.experiments import run_preset_demo
from tests.conftest import TestingSession


@pytest.fixture
def auth_headers(client):
    client.post("/auth/register", json={"email": "exp@example.com", "password": "password123"})
    r = client.post("/auth/login", json={"email": "exp@example.com", "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _make_trained_subject(user_id: int, name: str, epsilon: float) -> int:
    db = TestingSession()
    try:
        subject = Subject(user_id=user_id, name=name)
        db.add(subject)
        db.commit()
        db.refresh(subject)

        model = Model(
            user_id=user_id, subject_id=subject.id, dataset_id=None, algorithm="IF", status="ready", is_active=True
        )
        # dataset_id is NOT NULL in the schema; give it a real (if unused) row.
        from app.db.models import Dataset

        dataset = Dataset(
            user_id=user_id, subject_id=subject.id, name="d.csv", file_path="/tmp/nonexistent.csv", n_rows=10, n_features=1
        )
        db.add(dataset)
        db.commit()
        db.refresh(dataset)
        model.dataset_id = dataset.id
        db.add(model)
        db.commit()
        db.refresh(model)

        db.add(Threshold(model_id=model.id, mu=0.1, sigma=0.01, epsilon=epsilon, z_multiplier=3.0))
        db.commit()

        return subject.id
    finally:
        db.close()


def test_personalization_requires_two_subjects(client, auth_headers):
    db = TestingSession()
    user = db.query(User).filter_by(email="exp@example.com").first()
    db.close()
    sid = _make_trained_subject(user.id, "Only one", 0.05)

    r = client.post("/experiments/personalization", headers=auth_headers, json={"subject_ids": [sid]})
    assert r.status_code == 422  # Field(min_length=2) rejects at the schema level


def test_personalization_rejects_untrained_subject(client, auth_headers):
    r = client.post("/subjects", headers=auth_headers, json={"name": "Untrained"})
    untrained_id = r.json()["id"]

    db = TestingSession()
    user = db.query(User).filter_by(email="exp@example.com").first()
    db.close()
    trained_id = _make_trained_subject(user.id, "Trained", 0.05)

    r = client.post(
        "/experiments/personalization", headers=auth_headers, json={"subject_ids": [untrained_id, trained_id]}
    )
    assert r.status_code == 400


def test_personalization_computes_statistics(client, auth_headers):
    db = TestingSession()
    user = db.query(User).filter_by(email="exp@example.com").first()
    db.close()

    a = _make_trained_subject(user.id, "Low threshold", 0.02)
    b = _make_trained_subject(user.id, "High threshold", 0.08)

    r = client.post("/experiments/personalization", headers=auth_headers, json={"subject_ids": [a, b]})
    assert r.status_code == 200, r.text
    body = r.json()

    assert set(body["epsilons"].keys()) == {"Low threshold", "High threshold"}
    assert body["statistics"]["min"] == pytest.approx(0.02)
    assert body["statistics"]["max"] == pytest.approx(0.08)
    assert body["statistics"]["range_ratio"] == pytest.approx(4.0)
    assert body["cross_application"]["global_epsilon"] == pytest.approx(0.05)
    # The stub datasets point at a file that doesn't exist, so re-scoring
    # fails gracefully -- rates come back null rather than a 500.
    assert body["cross_application"]["fp_rate_at_global"]["Low threshold"] is None


def test_personalization_ownership_isolated(client, auth_headers):
    db = TestingSession()
    user = db.query(User).filter_by(email="exp@example.com").first()
    db.close()
    mine_a = _make_trained_subject(user.id, "Mine A", 0.02)
    mine_b = _make_trained_subject(user.id, "Mine B", 0.04)

    client.post("/auth/register", json={"email": "other@example.com", "password": "password123"})
    other = TestingSession().query(User).filter_by(email="other@example.com").first()
    theirs = _make_trained_subject(other.id, "Theirs", 0.9)

    r = client.post(
        "/experiments/personalization", headers=auth_headers, json={"subject_ids": [mine_a, mine_b, theirs]}
    )
    assert r.status_code == 200, r.text
    # Only the caller's own subjects are included -- someone else's ID is
    # silently dropped, not leaked into the comparison or an error.
    assert set(r.json()["epsilons"].keys()) == {"Mine A", "Mine B"}


def test_preset_demo_endpoint_requires_free_training_slot(client, auth_headers, monkeypatch):
    import app.api.experiments as experiments_api

    monkeypatch.setattr(experiments_api, "is_training_slot_free", lambda: False)
    r = client.post("/experiments/preset-demo", headers=auth_headers)
    assert r.status_code == 409


def test_run_preset_demo_end_to_end():
    """Small real training run (LSTM, 3 synthetic subjects) to exercise the
    full fit->calibrate->rescore path against real files on disk."""
    from app.core.security import hash_password

    db = TestingSession()
    try:
        user = User(email="demo@example.com", password_hash=hash_password("password123"))
        db.add(user)
        db.commit()
        db.refresh(user)
        user_id = user.id
    finally:
        db.close()

    db = TestingSession()
    try:
        result = run_preset_demo(db, user_id, n_subjects=3, n_rows=700)
    finally:
        db.close()

    assert len(result["created_subject_ids"]) == 3
    assert len(result["epsilons"]) == 3
    assert result["statistics"]["min"] <= result["statistics"]["max"]
    assert result["cross_application"]["global_epsilon"] > 0
