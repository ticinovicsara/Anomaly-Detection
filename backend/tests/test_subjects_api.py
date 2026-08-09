"""API integration tests for the /subjects endpoints (SQLite, no docker).

Shared engine/dependency-override/client fixtures live in conftest.py.
"""
import pytest

from tests.conftest import TestingSession


def _register_and_login(client, email="a@example.com", password="password123"):
    client.post("/auth/register", json={"email": email, "password": password})
    r = client.post("/auth/login", json={"email": email, "password": password})
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers(client):
    return _register_and_login(client)


def test_list_subjects_empty(client, auth_headers):
    r = client.get("/subjects", headers=auth_headers)
    assert r.status_code == 200
    assert r.json() == []


def test_create_subject(client, auth_headers):
    r = client.post("/subjects", headers=auth_headers, json={"name": "Patient 101", "description": "24 y/o male"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "Patient 101"
    assert body["description"] == "24 y/o male"
    assert body["is_default"] is False
    assert body["n_datasets"] == 0
    assert body["n_models"] == 0
    assert body["n_anomalies"] == 0
    assert body["active_epsilon"] is None
    assert body["active_model_id"] is None
    assert body["active_mu"] is None
    assert body["active_sigma"] is None
    assert body["active_z_multiplier"] is None


def test_subject_out_exposes_active_model_threshold_fields(client, auth_headers):
    """Settings needs mu/sigma/z_multiplier per-Subject (not per-model) to
    render a slider without an extra detail fetch per subject."""
    from app.db.models import Dataset, Model, Subject, Threshold, User

    db = TestingSession()
    try:
        user = db.query(User).first()
        subject = Subject(user_id=user.id, name="With model")
        db.add(subject)
        db.commit()
        db.refresh(subject)

        dataset = Dataset(user_id=user.id, subject_id=subject.id, name="d.csv", file_path="/tmp/d.csv", n_rows=10, n_features=1)
        db.add(dataset)
        db.commit()
        db.refresh(dataset)

        model = Model(user_id=user.id, subject_id=subject.id, dataset_id=dataset.id, algorithm="IF", status="ready", is_active=True)
        db.add(model)
        db.commit()
        db.refresh(model)

        db.add(Threshold(model_id=model.id, mu=0.1, sigma=0.02, epsilon=0.16, z_multiplier=3.0))
        db.commit()
        subject_id, model_id = subject.id, model.id
    finally:
        db.close()

    r = client.get(f"/subjects/{subject_id}", headers=auth_headers)
    body = r.json()
    assert body["active_model_id"] == model_id
    assert body["active_mu"] == pytest.approx(0.1)
    assert body["active_sigma"] == pytest.approx(0.02)
    assert body["active_z_multiplier"] == pytest.approx(3.0)


def test_create_subject_duplicate_name_rejected(client, auth_headers):
    client.post("/subjects", headers=auth_headers, json={"name": "Patient 101"})
    r = client.post("/subjects", headers=auth_headers, json={"name": "Patient 101"})
    assert r.status_code == 400


def test_get_subject_detail(client, auth_headers):
    r = client.post("/subjects", headers=auth_headers, json={"name": "Patient 101"})
    subject_id = r.json()["id"]

    r = client.get(f"/subjects/{subject_id}", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == subject_id
    assert body["datasets"] == []
    assert body["models"] == []


def test_update_subject(client, auth_headers):
    r = client.post("/subjects", headers=auth_headers, json={"name": "Patient 101"})
    subject_id = r.json()["id"]

    r = client.patch(f"/subjects/{subject_id}", headers=auth_headers, json={"name": "Patient 101 renamed", "description": "note"})
    assert r.status_code == 200
    assert r.json()["name"] == "Patient 101 renamed"
    assert r.json()["description"] == "note"


def test_update_subject_name_clash_rejected(client, auth_headers):
    client.post("/subjects", headers=auth_headers, json={"name": "A"})
    r = client.post("/subjects", headers=auth_headers, json={"name": "B"})
    b_id = r.json()["id"]

    r = client.patch(f"/subjects/{b_id}", headers=auth_headers, json={"name": "A"})
    assert r.status_code == 400


def test_delete_subject(client, auth_headers):
    r = client.post("/subjects", headers=auth_headers, json={"name": "Patient 101"})
    subject_id = r.json()["id"]

    r = client.delete(f"/subjects/{subject_id}", headers=auth_headers)
    assert r.status_code == 204

    r = client.get(f"/subjects/{subject_id}", headers=auth_headers)
    assert r.status_code == 404


def test_subject_not_found_returns_404(client, auth_headers):
    r = client.get("/subjects/99999", headers=auth_headers)
    assert r.status_code == 404


def test_cannot_access_another_users_subject(client):
    headers_a = _register_and_login(client, "usera@example.com", "password123")
    headers_b = _register_and_login(client, "userb@example.com", "password123")

    r = client.post("/subjects", headers=headers_a, json={"name": "A's subject"})
    subject_id = r.json()["id"]

    # 404, not 403 -- deliberately, matching every other ownership check in
    # this codebase (predict.py, settings.py): confirming a resource ID
    # exists but belongs to someone else is itself an information leak.
    r = client.get(f"/subjects/{subject_id}", headers=headers_b)
    assert r.status_code == 404

    r = client.patch(f"/subjects/{subject_id}", headers=headers_b, json={"name": "hijacked"})
    assert r.status_code == 404

    r = client.delete(f"/subjects/{subject_id}", headers=headers_b)
    assert r.status_code == 404


def test_delete_subject_cascades_datasets_models_and_anomalies(client, auth_headers):
    # Uses the plain /upload endpoint (defaults new data onto the user's
    # default Subject) plus direct ORM inserts for model/prediction/anomaly
    # rows, since full train->predict is exercised end-to-end elsewhere and
    # would make this test slow and LSTM/IF-flaky for no extra coverage here.
    from app.db.models import AnomalyEvent, Dataset, Model, Prediction, Subject, User

    db = TestingSession()
    try:
        user = db.query(User).first()
        subject = Subject(user_id=user.id, name="Cascade test")
        db.add(subject)
        db.commit()
        db.refresh(subject)

        dataset = Dataset(
            user_id=user.id, subject_id=subject.id, name="d.csv", file_path="/tmp/d.csv", n_rows=10, n_features=1
        )
        db.add(dataset)
        db.commit()
        db.refresh(dataset)

        model = Model(user_id=user.id, subject_id=subject.id, dataset_id=dataset.id, algorithm="IF", status="ready")
        db.add(model)
        db.commit()
        db.refresh(model)

        pred = Prediction(model_id=model.id, window_idx=0, score=1.0, is_anomaly=True)
        db.add(pred)
        db.commit()
        db.refresh(pred)

        event = AnomalyEvent(prediction_id=pred.id, user_id=user.id, severity="warning")
        db.add(event)
        db.commit()

        subject_id = subject.id
    finally:
        db.close()

    r = client.delete(f"/subjects/{subject_id}", headers=auth_headers)
    assert r.status_code == 204

    db = TestingSession()
    try:
        assert db.query(Dataset).filter_by(subject_id=subject_id).count() == 0
        assert db.query(Model).filter_by(subject_id=subject_id).count() == 0
        assert db.query(AnomalyEvent).count() == 0, "anomaly events must be gone too (cascades through prediction->model)"
        assert db.query(Prediction).count() == 0
    finally:
        db.close()


def test_anomalies_subject_filter(client, auth_headers):
    """/anomalies?subject_id=... only returns anomalies whose model belongs
    to that subject -- the filter chip on the Anomalies page depends on
    this joining through Prediction -> Model correctly."""
    from app.db.models import AnomalyEvent, Dataset, Model, Prediction, Subject, User

    db = TestingSession()
    try:
        user = db.query(User).first()
        subject_a = Subject(user_id=user.id, name="A")
        subject_b = Subject(user_id=user.id, name="B")
        db.add_all([subject_a, subject_b])
        db.commit()
        db.refresh(subject_a)
        db.refresh(subject_b)

        events = {}
        for subject in (subject_a, subject_b):
            dataset = Dataset(user_id=user.id, subject_id=subject.id, name="d.csv", file_path="/tmp/d.csv", n_rows=10, n_features=1)
            db.add(dataset)
            db.commit()
            db.refresh(dataset)

            model = Model(user_id=user.id, subject_id=subject.id, dataset_id=dataset.id, algorithm="IF", status="ready")
            db.add(model)
            db.commit()
            db.refresh(model)

            pred = Prediction(model_id=model.id, window_idx=0, score=1.0, is_anomaly=True)
            db.add(pred)
            db.commit()
            db.refresh(pred)

            event = AnomalyEvent(prediction_id=pred.id, user_id=user.id, severity="warning")
            db.add(event)
            db.commit()
            db.refresh(event)
            events[subject.id] = event.id

        subject_a_id = subject_a.id
    finally:
        db.close()

    r = client.get("/anomalies", headers=auth_headers, params={"subject_id": subject_a_id})
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body) == 1
    assert body[0]["id"] == events[subject_a_id]
    assert body[0]["subject_id"] == subject_a_id


def test_retrain_requires_data(client, auth_headers):
    r = client.post("/subjects", headers=auth_headers, json={"name": "Empty subject"})
    subject_id = r.json()["id"]

    r = client.post(f"/subjects/{subject_id}/retrain", headers=auth_headers)
    assert r.status_code == 400


def test_train_alternative_requires_data(client, auth_headers):
    r = client.post("/subjects", headers=auth_headers, json={"name": "Empty subject"})
    subject_id = r.json()["id"]

    r = client.post(f"/subjects/{subject_id}/train-alternative", headers=auth_headers, json={"algorithm": "IF"})
    assert r.status_code == 400


def test_train_alternative_rejects_invalid_algorithm(client, auth_headers):
    r = client.post("/subjects", headers=auth_headers, json={"name": "S"})
    subject_id = r.json()["id"]

    r = client.post(f"/subjects/{subject_id}/train-alternative", headers=auth_headers, json={"algorithm": "NOT_REAL"})
    assert r.status_code == 422


def test_activate_model_not_found(client, auth_headers):
    r = client.post("/subjects", headers=auth_headers, json={"name": "S"})
    subject_id = r.json()["id"]

    r = client.post(f"/subjects/{subject_id}/models/99999/activate", headers=auth_headers)
    assert r.status_code == 404
