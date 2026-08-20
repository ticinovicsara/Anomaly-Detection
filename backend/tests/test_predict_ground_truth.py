"""Ground-truth-aware Predict: a live /predict upload that includes a
usable "label" column gets each window tagged tp/fp/fn/tn instead of just
flagged/not-flagged, and a window that's truly anomalous but never
flagged (fn) gets its own AnomalyEvent -- previously invisible anywhere,
since AnomalyEvent only ever existed for flagged windows.
"""
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from app.ml_core.models.isolation_forest import IFModel
from app.ml_core.preprocessing import fit_scaler, save_scaler
from app.services.prediction import persist_predictions, run_prediction
from tests.conftest import TestingSession


def _register_and_login(client, email="a@example.com", password="password123"):
    client.post("/auth/register", json={"email": email, "password": password})
    r = client.post("/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def auth_headers(client):
    return _register_and_login(client)


def _make_subject_with_model(db, user, algorithm="IF"):
    from app.db.models import Dataset, Model, Subject, Threshold

    subject = Subject(user_id=user.id, name=f"Subject {algorithm}")
    db.add(subject)
    db.commit()
    db.refresh(subject)

    dataset = Dataset(user_id=user.id, subject_id=subject.id, name="d.csv", file_path="/tmp/d.csv", n_rows=10, n_features=1)
    db.add(dataset)
    db.commit()
    db.refresh(dataset)

    model = Model(user_id=user.id, subject_id=subject.id, dataset_id=dataset.id, algorithm=algorithm, status="ready", is_active=True)
    db.add(model)
    db.commit()
    db.refresh(model)

    db.add(Threshold(model_id=model.id, mu=0.1, sigma=0.02, epsilon=0.16, z_multiplier=3.0))
    db.commit()
    return subject, model


def test_run_prediction_computes_ground_truth_when_label_column_present(tmp_path):
    rng = np.random.default_rng(0)
    normal = rng.normal(0, 1, size=(200, 1))
    train_df = pd.DataFrame({"signal": normal[:, 0]})
    scaler = fit_scaler(train_df.values)
    scaler_path = str(tmp_path / "scaler.pkl")
    save_scaler(scaler, scaler_path)

    m = IFModel()
    m.train(scaler.transform(train_df.values))
    model_path = str(tmp_path / "model.pkl")
    m.save(model_path)

    model_row = SimpleNamespace(algorithm="IF", scaler_path=scaler_path, model_path=model_path)
    threshold = SimpleNamespace(epsilon=0.0)  # low enough that every point is flagged

    predict_df = pd.DataFrame({"signal": [0.1, 0.2, 0.3], "label": [0, 1, 0]})
    batch_id, results = run_prediction(model_row, threshold, predict_df)

    assert len(results) == 3
    assert [r["actual"] for r in results] == [0, 1, 0]
    assert all(r["batch_id"] == batch_id for r in results)


def test_run_prediction_actual_is_none_without_label_column(tmp_path):
    rng = np.random.default_rng(0)
    train_df = pd.DataFrame({"signal": rng.normal(0, 1, size=200)})
    scaler = fit_scaler(train_df.values)
    scaler_path = str(tmp_path / "scaler.pkl")
    save_scaler(scaler, scaler_path)
    m = IFModel()
    m.train(scaler.transform(train_df.values))
    model_path = str(tmp_path / "model.pkl")
    m.save(model_path)

    model_row = SimpleNamespace(algorithm="IF", scaler_path=scaler_path, model_path=model_path)
    threshold = SimpleNamespace(epsilon=0.0)

    predict_df = pd.DataFrame({"signal": [0.1, 0.2, 0.3]})
    _batch_id, results = run_prediction(model_row, threshold, predict_df)

    assert all(r["actual"] is None for r in results)


def test_persist_predictions_creates_missed_event_for_false_negative(client, auth_headers):
    from app.db.models import AnomalyEvent, Prediction, User

    db = TestingSession()
    try:
        user = db.query(User).first()
        _subject, model = _make_subject_with_model(db, user)
        model_id, user_id = model.id, user.id

        results = [
            {"batch_id": "b1", "window_idx": 0, "score": 0.9, "is_anomaly": True, "actual": 1},   # tp
            {"batch_id": "b1", "window_idx": 1, "score": 0.9, "is_anomaly": True, "actual": 0},   # fp
            {"batch_id": "b1", "window_idx": 2, "score": 0.1, "is_anomaly": False, "actual": 1},  # fn -- the new case
            {"batch_id": "b1", "window_idx": 3, "score": 0.1, "is_anomaly": False, "actual": 0},  # tn -- no event at all
        ]
        anomaly_count = persist_predictions(db, user_id, model_id, results, epsilon=0.16)
        assert anomaly_count == 2  # only the two flagged windows count as "detected"

        preds = db.query(Prediction).filter_by(model_id=model_id).order_by(Prediction.window_idx).all()
        assert [p.actual for p in preds] == [1, 0, 1, 0]

        events = db.query(AnomalyEvent).join(Prediction).filter(Prediction.model_id == model_id).all()
        by_window = {e.prediction.window_idx: e for e in events}

        assert len(events) == 3  # tp, fp, fn each get a row; tn does not
        assert by_window[0].outcome == "tp"
        assert by_window[0].detection_source == "flagged"
        assert by_window[1].outcome == "fp"
        assert by_window[1].detection_source == "flagged"
        assert by_window[2].outcome == "fn"
        assert by_window[2].detection_source == "missed_ground_truth"
        assert by_window[2].severity == "critical"
        assert 3 not in by_window  # the tn window has no AnomalyEvent
    finally:
        db.close()


def test_anomalies_outcome_filter_and_predict_batches_endpoints(client, auth_headers):
    from app.db.models import User

    db = TestingSession()
    try:
        user = db.query(User).first()
        _subject, model = _make_subject_with_model(db, user)
        model_id, user_id = model.id, user.id

        results = [
            {"batch_id": "batchA", "window_idx": 0, "score": 0.9, "is_anomaly": True, "actual": 1},
            {"batch_id": "batchA", "window_idx": 1, "score": 0.9, "is_anomaly": True, "actual": 0},
            {"batch_id": "batchA", "window_idx": 2, "score": 0.1, "is_anomaly": False, "actual": 1},
            {"batch_id": "batchA", "window_idx": 3, "score": 0.1, "is_anomaly": False, "actual": 0},
        ]
        persist_predictions(db, user_id, model_id, results, epsilon=0.16)
    finally:
        db.close()

    r = client.get("/anomalies", params={"outcome": "fn"}, headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["outcome"] == "fn"
    assert body[0]["detection_source"] == "missed_ground_truth"

    r = client.get("/anomalies", params={"outcome": "tp"}, headers=auth_headers)
    assert len(r.json()) == 1
    assert r.json()[0]["outcome"] == "tp"

    r = client.get(f"/predict/{model_id}/batches", headers=auth_headers)
    assert r.status_code == 200
    batches = r.json()
    assert len(batches) == 1
    assert batches[0]["batch_id"] == "batchA"
    assert batches[0]["n_windows"] == 4
    assert batches[0]["confusion"] == {"tp": 1, "fp": 1, "tn": 1, "fn": 1}

    r = client.get(f"/predict/{model_id}/batches/batchA", headers=auth_headers)
    assert r.status_code == 200
    detail = r.json()
    assert len(detail["curve"]) == 4
    assert {p["i"]: (p["actual"], p["predicted"]) for p in detail["curve"]} == {
        0: (1, 1),
        1: (0, 1),
        2: (1, 0),
        3: (0, 0),
    }

    r = client.get(f"/predict/{model_id}/batches/does-not-exist", headers=auth_headers)
    assert r.status_code == 404
