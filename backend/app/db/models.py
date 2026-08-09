from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    notification_prefs = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    datasets = relationship("Dataset", back_populates="user", cascade="all, delete-orphan")
    models = relationship("Model", back_populates="user", cascade="all, delete-orphan")
    subjects = relationship("Subject", back_populates="user", cascade="all, delete-orphan")


class Subject(Base):
    """Entity personalization is calibrated for (patient/card/service) -- separate from User."""

    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    source_hint = Column(String(255), nullable=True)  # upload | curated:<slug> | kaggle:<ref> | split_from:<id> | auto_default
    is_default = Column(Boolean, default=False, nullable=False)
    pre_retrain_check_enabled = Column(Boolean, default=False, nullable=False)  # off by default, see services/data_review.py
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="subjects")
    datasets = relationship("Dataset", back_populates="subject", cascade="all, delete-orphan")
    models = relationship("Model", back_populates="subject", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_subjects_user_name"),)


class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), index=True, nullable=False)
    name = Column(String(255), nullable=False)
    detected_type = Column(String(50))
    profile_json = Column(JSON, default=dict)
    file_path = Column(String(500), nullable=False)
    n_rows = Column(Integer)
    n_features = Column(Integer)
    label_column = Column(String(255), nullable=True)  # optional ground-truth anomaly column, see ml_core/evaluation.py
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="datasets")
    subject = relationship("Subject", back_populates="datasets")
    models = relationship("Model", back_populates="dataset", cascade="all, delete-orphan")


class Model(Base):
    __tablename__ = "models"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), index=True, nullable=False)
    dataset_id = Column(Integer, ForeignKey("datasets.id", ondelete="CASCADE"), index=True, nullable=False)
    algorithm = Column(String(50), nullable=False)  # IF | LSTM
    selection_reason = Column(Text)
    selection_mode = Column(String(20), default="auto", nullable=False)  # auto | manual
    is_active = Column(Boolean, default=True, nullable=False)  # the Subject's primary model
    status = Column(String(20), default="pending", nullable=False)  # pending|training|ready|failed
    model_path = Column(String(500))
    scaler_path = Column(String(500))
    metrics_json = Column(JSON, default=dict)
    drift_status = Column(String(20), default="ok")  # ok | drift_suspected
    trained_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="models")
    subject = relationship("Subject", back_populates="models")
    dataset = relationship("Dataset", back_populates="models")
    threshold = relationship("Threshold", back_populates="model", uselist=False, cascade="all, delete-orphan")
    predictions = relationship("Prediction", back_populates="model", cascade="all, delete-orphan")


class Threshold(Base):
    __tablename__ = "thresholds"

    id = Column(Integer, primary_key=True)
    model_id = Column(Integer, ForeignKey("models.id", ondelete="CASCADE"), unique=True, nullable=False)
    mu = Column(Float, nullable=False)
    sigma = Column(Float, nullable=False)
    epsilon = Column(Float, nullable=False)
    z_multiplier = Column(Float, default=3.0, nullable=False)
    calibrated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    model = relationship("Model", back_populates="threshold")


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True)
    model_id = Column(Integer, ForeignKey("models.id", ondelete="CASCADE"), index=True, nullable=False)
    batch_id = Column(String(64), index=True)
    window_idx = Column(Integer, nullable=False)
    score = Column(Float, nullable=False)
    is_anomaly = Column(Boolean, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    model = relationship("Model", back_populates="predictions")
    event = relationship("AnomalyEvent", back_populates="prediction", uselist=False, cascade="all, delete-orphan")


class AnomalyEvent(Base):
    __tablename__ = "anomaly_events"

    id = Column(Integer, primary_key=True)
    prediction_id = Column(Integer, ForeignKey("predictions.id", ondelete="CASCADE"), unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    severity = Column(String(20), default="warning")  # info | warning | critical
    label = Column(String(30), default="unlabeled")  # unlabeled | confirmed | false_positive | resolved
    note = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    resolved_at = Column(DateTime)

    prediction = relationship("Prediction", back_populates="event")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    event_id = Column(Integer, ForeignKey("anomaly_events.id", ondelete="SET NULL"), index=True)
    channel = Column(String(20), nullable=False)  # email | push | inapp
    status = Column(String(20), default="pending")  # pending | sent | failed
    sent_at = Column(DateTime)
    payload = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    period = Column(String(20), nullable=False)  # week | month
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    file_path = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class DataReviewCandidate(Base):
    """Pre-retrain review candidate (see services/data_review.py) -- not AnomalyEvent
    since it comes from data with no trained Model yet."""

    __tablename__ = "data_review_candidates"

    id = Column(Integer, primary_key=True)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), index=True, nullable=False)
    dataset_id = Column(Integer, ForeignKey("datasets.id", ondelete="CASCADE"), index=True, nullable=False)
    row_index = Column(Integer, nullable=False)
    score = Column(Float, nullable=False)
    row_preview = Column(JSON, default=dict)
    label = Column(String(30), default="unlabeled", nullable=False)  # unlabeled | confirmed | false_positive
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    subject = relationship("Subject")
    dataset = relationship("Dataset")


class UploadLog(Base):
    __tablename__ = "upload_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), index=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id", ondelete="SET NULL"), index=True)
    filename = Column(String(255))
    size_bytes = Column(Integer)
    status = Column(String(20))  # ok | rejected
    reason = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
