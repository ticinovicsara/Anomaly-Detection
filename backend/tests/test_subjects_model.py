"""ORM-level tests for the Subject entity (SQLite in-memory, no docker needed).

Covers CRUD, the (user_id, name) uniqueness constraint, and cascade delete
down to Dataset/Model. API-level tests for the /subjects endpoints land in
Phase 2 alongside the endpoints themselves.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import Dataset, Model, Subject, User

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
TestingSession = sessionmaker(bind=engine)


@pytest.fixture(autouse=True)
def _reset_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def db():
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


def _make_user(db, email="test@example.com") -> User:
    user = User(email=email, password_hash="x")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_create_subject(db):
    user = _make_user(db)
    subject = Subject(user_id=user.id, name="Patient 101", description="24 y/o male")
    db.add(subject)
    db.commit()
    db.refresh(subject)

    assert subject.id is not None
    assert subject.is_default is False
    assert subject.created_at is not None


def test_read_update_subject(db):
    user = _make_user(db)
    subject = Subject(user_id=user.id, name="Patient 101")
    db.add(subject)
    db.commit()
    db.refresh(subject)

    subject.name = "Patient 101 (renamed)"
    subject.description = "updated"
    db.commit()

    fetched = db.query(Subject).filter(Subject.id == subject.id).first()
    assert fetched.name == "Patient 101 (renamed)"
    assert fetched.description == "updated"


def test_delete_subject(db):
    user = _make_user(db)
    subject = Subject(user_id=user.id, name="Patient 101")
    db.add(subject)
    db.commit()
    db.refresh(subject)

    db.delete(subject)
    db.commit()

    assert db.query(Subject).count() == 0


def test_unique_name_per_user(db):
    user = _make_user(db)
    db.add(Subject(user_id=user.id, name="Patient 101"))
    db.commit()

    db.add(Subject(user_id=user.id, name="Patient 101"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_same_name_allowed_across_different_users(db):
    user1 = _make_user(db, "a@example.com")
    user2 = _make_user(db, "b@example.com")

    db.add(Subject(user_id=user1.id, name="My data"))
    db.add(Subject(user_id=user2.id, name="My data"))
    db.commit()  # must not raise -- uniqueness is scoped per user, not global

    assert db.query(Subject).count() == 2


def test_cascade_delete_removes_datasets_and_models(db):
    user = _make_user(db)
    subject = Subject(user_id=user.id, name="Patient 101")
    db.add(subject)
    db.commit()
    db.refresh(subject)

    dataset = Dataset(
        user_id=user.id,
        subject_id=subject.id,
        name="ecg.csv",
        file_path="/tmp/ecg.csv",
        n_rows=100,
        n_features=1,
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)

    model = Model(
        user_id=user.id,
        subject_id=subject.id,
        dataset_id=dataset.id,
        algorithm="LSTM",
        status="ready",
    )
    db.add(model)
    db.commit()

    assert db.query(Dataset).count() == 1
    assert db.query(Model).count() == 1

    db.delete(subject)
    db.commit()

    assert db.query(Dataset).count() == 0, "deleting a Subject must cascade-delete its datasets"
    assert db.query(Model).count() == 0, "deleting a Subject must cascade-delete its models"


def test_model_defaults(db):
    user = _make_user(db)
    subject = Subject(user_id=user.id, name="Patient 101")
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

    assert model.selection_mode == "auto"
    assert model.is_active is True


def test_ensure_default_subject_is_idempotent(db):
    from app.services.subjects import ensure_default_subject

    user = _make_user(db)
    first = ensure_default_subject(user, db)
    second = ensure_default_subject(user, db)

    assert first.id == second.id
    assert db.query(Subject).filter_by(user_id=user.id, is_default=True).count() == 1
