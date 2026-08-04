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


class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    name = Column(String(255), nullable=False)
    detected_type = Column(String(50))
    profile_json = Column(JSON, default=dict)
    file_path = Column(String(500), nullable=False)
    n_rows = Column(Integer)
    n_features = Column(Integer)
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="datasets")
    models = relationship("Model", back_populates="dataset", cascade="all, delete-orphan")


class Model(Base):
    __tablename__ = "models"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    dataset_id = Column(Integer, ForeignKey("datasets.id", ondelete="CASCADE"), index=True, nullable=False)
    algorithm = Column(String(50), nullable=False)  # IF | LSTM
    selection_reason = Column(Text)
    status = Column(String(20), default="pending", nullable=False)  # pending|training|ready|failed
    model_path = Column(String(500))
    scaler_path = Column(String(500))
    metrics_json = Column(JSON, default=dict)
    drift_status = Column(String(20), default="ok")  # ok | drift_suspected
    trained_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="models")
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
    event_id = Column(Integer, ForeignKey("anomaly_events.id", ondelete="SET NULL"))
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


class UploadLog(Base):
    __tablename__ = "upload_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    dataset_id = Column(Integer, ForeignKey("datasets.id", ondelete="SET NULL"))
    filename = Column(String(255))
    size_bytes = Column(Integer)
    status = Column(String(20))  # ok | rejected
    reason = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
