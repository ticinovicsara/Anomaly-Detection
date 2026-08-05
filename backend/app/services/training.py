"""Training service — runs in a background task so /train returns immediately.

Single global lock (`_TRAIN_LOCK`) prevents two heavy trainings running at once
in the same process — see guardrail #4 in Implementation_Plan.md §12.

Subject-aware entry points (run_retrain_job / run_train_alternative_job) run
synchronously under the same lock instead of as a background task: their
callers (the /subjects/{id}/retrain and /subjects/{id}/train-alternative
endpoints) need the computed before/after epsilon back in the HTTP response
itself, not a "started" placeholder.
"""
import logging
import os
import threading
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

from app.core.config import settings
from app.db.models import Dataset, Model, Subject, Threshold
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

logger = logging.getLogger(__name__)

_TRAIN_LOCK = threading.Lock()


def is_training_slot_free() -> bool:
    return not _TRAIN_LOCK.locked()


def _fit_and_calibrate(df: pd.DataFrame, algo: str, base_path: str) -> dict:
    """Core fit + calibrate step shared by every training entry point.
    Returns a dict of everything the caller needs to populate a Model row,
    or raises ValueError on data that isn't trainable."""
    df = numeric_only(df)
    if df.empty:
        raise ValueError("Dataset contains no numeric columns")

    train_df, val_df, _test_df = temporal_split(df)
    if len(train_df) < 20 or len(val_df) < 5:
        raise ValueError(f"Not enough data (train={len(train_df)}, val={len(val_df)})")

    scaler = fit_scaler(train_df.values)
    X_train = apply_scaler(train_df.values, scaler)
    X_val = apply_scaler(val_df.values, scaler)

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

    return {
        "model_path": model_path,
        "scaler_path": scaler_path,
        "metrics": {
            "val_score_min": float(np.min(val_scores)),
            "val_score_max": float(np.max(val_scores)),
            "val_score_mean": float(np.mean(val_scores)),
            "n_train_samples": int(len(X_train)),
            "n_val_samples": int(len(X_val)),
        },
        "threshold": thr,
    }


def _load_subject_dataframe(subject: Subject) -> pd.DataFrame:
    """Concatenate every one of a Subject's uploaded datasets into one
    dataframe -- "multi-dataset per Subject" from the design spec (a Subject
    can get more data later; retrain trains on everything it has)."""
    frames = []
    for ds in subject.datasets:
        try:
            frames.append(pd.read_csv(ds.file_path))
        except Exception:
            logger.exception("Could not read dataset %s (%s) for subject %s", ds.id, ds.file_path, subject.id)
    if not frames:
        raise ValueError("Subject has no readable datasets")
    return pd.concat(frames, ignore_index=True)


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
            subject_id=dataset.subject_id,
            dataset_id=dataset_id,
            algorithm=algo,
            selection_reason=reason,
            status="training",
        )
        db.add(model_row)
        db.commit()
        db.refresh(model_row)

        df = pd.read_csv(dataset.file_path)
        base_path = os.path.join(settings.STORAGE_PATH, f"user{user_id}_ds{dataset_id}_m{model_row.id}")
        fit = _fit_and_calibrate(df, algo, base_path)

        model_row.model_path = fit["model_path"]
        model_row.scaler_path = fit["scaler_path"]
        model_row.trained_at = datetime.utcnow()
        model_row.status = "ready"
        model_row.metrics_json = fit["metrics"]

        thr = fit["threshold"]
        db.add(Threshold(model_id=model_row.id, mu=thr["mu"], sigma=thr["sigma"], epsilon=thr["epsilon"], z_multiplier=thr["z_multiplier"]))
        db.commit()
    except Exception as exc:  # noqa: BLE001 - want to record any failure
        logger.exception("Training failed for dataset %s, user %s", dataset_id, user_id)
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


def _retrain_impl(subject_id: int, user_id: int) -> dict:
    os.makedirs(settings.STORAGE_PATH, exist_ok=True)
    db = SessionLocal()
    model_row: Optional[Model] = None
    try:
        subject = db.query(Subject).filter(Subject.id == subject_id).first()
        if subject is None:
            raise ValueError("Subject not found")

        previous_active = db.query(Model).filter_by(subject_id=subject.id, is_active=True).first()
        old_epsilon = previous_active.threshold.epsilon if previous_active and previous_active.threshold else None
        # Reuse the previous active model's algorithm ("same algorithm, latest
        # data"); if the Subject has never been trained, fall back to the router.
        if previous_active:
            algo, reason = previous_active.algorithm, previous_active.selection_reason
        else:
            df_preview = _load_subject_dataframe(subject)
            from app.ml_core.profiler import profile_dataset

            algo, reason = choose_model(profile_dataset(df_preview))

        model_row = Model(
            user_id=user_id,
            subject_id=subject.id,
            dataset_id=subject.datasets[-1].id,  # most recent dataset, for reference/lineage only
            algorithm=algo,
            selection_reason=reason,
            selection_mode="auto",
            is_active=False,  # flipped on only after training succeeds
            status="training",
        )
        db.add(model_row)
        db.commit()
        db.refresh(model_row)

        df = _load_subject_dataframe(subject)
        base_path = os.path.join(settings.STORAGE_PATH, f"user{user_id}_subj{subject.id}_m{model_row.id}")
        fit = _fit_and_calibrate(df, algo, base_path)

        model_row.model_path = fit["model_path"]
        model_row.scaler_path = fit["scaler_path"]
        model_row.trained_at = datetime.utcnow()
        model_row.status = "ready"
        model_row.metrics_json = fit["metrics"]
        db.commit()

        thr = fit["threshold"]
        db.add(Threshold(model_id=model_row.id, mu=thr["mu"], sigma=thr["sigma"], epsilon=thr["epsilon"], z_multiplier=thr["z_multiplier"]))
        db.commit()

        db.query(Model).filter_by(subject_id=subject.id).update({"is_active": False})
        db.query(Model).filter(Model.id == model_row.id).update({"is_active": True})
        db.commit()

        new_epsilon = thr["epsilon"]
        delta_pct = ((new_epsilon - old_epsilon) / old_epsilon * 100) if old_epsilon else None
        return {
            "model_id": model_row.id,
            "old_epsilon": old_epsilon,
            "new_epsilon": new_epsilon,
            "delta_pct": delta_pct,
        }
    except Exception as exc:
        logger.exception("Retrain failed for subject %s, user %s", subject_id, user_id)
        db.rollback()
        if model_row is not None:
            model_row.status = "failed"
            model_row.metrics_json = {"error": str(exc)[:500]}
            db.commit()
        raise ValueError(str(exc)) from exc
    finally:
        db.close()


def run_retrain_job(subject_id: int, user_id: int) -> dict:
    with _TRAIN_LOCK:
        return _retrain_impl(subject_id, user_id)


def _train_alternative_impl(subject_id: int, user_id: int, algorithm: str) -> dict:
    os.makedirs(settings.STORAGE_PATH, exist_ok=True)
    db = SessionLocal()
    model_row: Optional[Model] = None
    try:
        subject = db.query(Subject).filter(Subject.id == subject_id).first()
        if subject is None:
            raise ValueError("Subject not found")

        model_row = Model(
            user_id=user_id,
            subject_id=subject.id,
            dataset_id=subject.datasets[-1].id,
            algorithm=algorithm,
            selection_reason=f"Manually selected ({algorithm}) as an alternative for comparison",
            selection_mode="manual",
            is_active=False,  # advanced-mode alternative: never auto-replaces the active model
            status="training",
        )
        db.add(model_row)
        db.commit()
        db.refresh(model_row)

        df = _load_subject_dataframe(subject)
        base_path = os.path.join(settings.STORAGE_PATH, f"user{user_id}_subj{subject.id}_alt_m{model_row.id}")
        fit = _fit_and_calibrate(df, algorithm, base_path)

        model_row.model_path = fit["model_path"]
        model_row.scaler_path = fit["scaler_path"]
        model_row.trained_at = datetime.utcnow()
        model_row.status = "ready"
        model_row.metrics_json = fit["metrics"]
        db.commit()

        thr = fit["threshold"]
        db.add(Threshold(model_id=model_row.id, mu=thr["mu"], sigma=thr["sigma"], epsilon=thr["epsilon"], z_multiplier=thr["z_multiplier"]))
        db.commit()

        return {"model_id": model_row.id, "algorithm": algorithm, "epsilon": thr["epsilon"]}
    except Exception as exc:
        logger.exception("Train-alternative failed for subject %s, user %s", subject_id, user_id)
        db.rollback()
        if model_row is not None:
            model_row.status = "failed"
            model_row.metrics_json = {"error": str(exc)[:500]}
            db.commit()
        raise ValueError(str(exc)) from exc
    finally:
        db.close()


def run_train_alternative_job(subject_id: int, user_id: int, algorithm: str) -> dict:
    with _TRAIN_LOCK:
        return _train_alternative_impl(subject_id, user_id, algorithm)
