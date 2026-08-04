"""Training service — runs in a background task so /train returns immediately.

Single global lock (`_TRAIN_LOCK`) prevents two heavy trainings running at once
in the same process — see guardrail #4 in Implementation_Plan.md §12.
"""
import os
import threading
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

from app.core.config import settings
from app.db.models import Dataset, Model, Threshold
from app.db.session import SessionLocal
from app.ml_core.model_router import choose_model
from app.ml_core.models.isolation_forest import IFModel
from app.ml_core.preprocessing import (
    apply_scaler,
    fit_scaler,
    numeric_only,
    save_scaler,
    sliding_windows,
    temporal_split,
)
from app.ml_core.threshold import calibrate_threshold

_TRAIN_LOCK = threading.Lock()


def is_training_slot_free() -> bool:
    return not _TRAIN_LOCK.locked()


def _train_impl(dataset_id: int, user_id: int) -> None:
    os.makedirs(settings.STORAGE_PATH, exist_ok=True)
    db = SessionLocal()

    model_row: Optional[Model] = None
    try:
        dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
        if dataset is None:
            return

        algo, reason = choose_model(dataset.profile_json or {})

        model_row = Model(
            user_id=user_id,
            dataset_id=dataset_id,
            algorithm=algo,
            selection_reason=reason,
            status="training",
        )
        db.add(model_row)
        db.commit()
        db.refresh(model_row)

        df = pd.read_csv(dataset.file_path)
        df = numeric_only(df)
        if df.empty:
            raise ValueError("Dataset contains no numeric columns")

        train_df, val_df, _test_df = temporal_split(df)
        if len(train_df) < 20 or len(val_df) < 5:
            raise ValueError(f"Not enough data (train={len(train_df)}, val={len(val_df)})")

        scaler = fit_scaler(train_df.values)
        X_train = apply_scaler(train_df.values, scaler)
        X_val = apply_scaler(val_df.values, scaler)

        base_path = os.path.join(settings.STORAGE_PATH, f"user{user_id}_ds{dataset_id}_m{model_row.id}")
        scaler_path = base_path + "_scaler.pkl"
        save_scaler(scaler, scaler_path)

        if algo == "LSTM":
            from app.ml_core.models.lstm_autoencoder import LSTMAutoencoder

            W_train = sliding_windows(X_train, window_size=50, stride=10)
            W_val = sliding_windows(X_val, window_size=50, stride=10)
            if len(W_train) < 10 or len(W_val) < 3:
                raise ValueError("Not enough windows for LSTM (need larger dataset)")
            m = LSTMAutoencoder(window_size=50, n_features=X_train.shape[1])
            m.train(W_train, epochs=20, batch_size=64)
            model_path = base_path + ".keras"
            m.save(model_path)
            val_scores = m.score(W_val)
        else:
            m = IFModel(contamination=0.01)
            m.train(X_train)
            model_path = base_path + ".pkl"
            m.save(model_path)
            val_scores = m.score(X_val)

        thr = calibrate_threshold(np.asarray(val_scores), z=3.0)

        model_row.model_path = model_path
        model_row.scaler_path = scaler_path
        model_row.trained_at = datetime.utcnow()
        model_row.status = "ready"
        model_row.metrics_json = {
            "val_score_min": float(np.min(val_scores)),
            "val_score_max": float(np.max(val_scores)),
            "val_score_mean": float(np.mean(val_scores)),
            "n_train_samples": int(len(X_train)),
            "n_val_samples": int(len(X_val)),
        }

        threshold = Threshold(
            model_id=model_row.id,
            mu=thr["mu"],
            sigma=thr["sigma"],
            epsilon=thr["epsilon"],
            z_multiplier=thr["z_multiplier"],
        )
        db.add(threshold)
        db.commit()
    except Exception as exc:  # noqa: BLE001 - want to record any failure
        db.rollback()
        if model_row is not None:
            model_row.status = "failed"
            model_row.metrics_json = {"error": str(exc)[:500]}
            db.commit()
    finally:
        db.close()


def run_training_job(dataset_id: int, user_id: int) -> None:
    """Public entry point. Acquires the lock, runs training, releases the lock."""
    with _TRAIN_LOCK:
        _train_impl(dataset_id, user_id)
