"""Training service. `_TRAIN_LOCK` caps training at one job at a time
(Implementation_Plan.md §12 guardrail #4). Retrain/train-alternative run
synchronously under the lock (not as a background task) because their
callers need the before/after epsilon in the HTTP response itself."""
import logging
import os
import threading
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

from app.core.config import settings
from app.db.models import Dataset, Model, Subject, Threshold, ThresholdHistory
from app.db.session import SessionLocal
from app.ml_core.evaluation import coerce_binary_label, evaluate_on_test
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


def _fit_and_calibrate(df: pd.DataFrame, algo: str, base_path: str, label_column: Optional[str] = None) -> dict:
    """Shared by every training entry point. Raises ValueError if untrainable."""
    label_series = None
    if label_column and label_column in df.columns:
        try:
            label_series = coerce_binary_label(df[label_column])
        except Exception:
            logger.warning("Column %r is not usable as a binary label, skipping evaluation", label_column)
        df = df.drop(columns=[label_column])

    df = numeric_only(df)
    if df.empty:
        raise ValueError("Dataset contains no numeric columns")

    if label_series is not None:
        label_series = label_series.reindex(df.index)
        train_df, val_df, test_df, _train_lbl, _val_lbl, test_lbl = temporal_split(df, labels=label_series)
    else:
        train_df, val_df, test_df = temporal_split(df)
        test_lbl = None

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
        m = IFModel()
        m.train(X_train)
        model_path = base_path + ".pkl"
        m.save(model_path)
        val_scores = m.score(X_val)

    thr = calibrate_threshold(np.asarray(val_scores), z=3.0)
    evaluation = evaluate_on_test(m, algo, test_df, test_lbl, scaler, thr["epsilon"])

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
        "evaluation": evaluation,
    }


def _load_subject_dataframe(subject: Subject) -> pd.DataFrame:
    """Concatenates all of a Subject's datasets -- retrain uses everything it has."""
    frames = []
    for ds in subject.datasets:
        try:
            frames.append(pd.read_csv(ds.file_path))
        except Exception:
            logger.exception("Could not read dataset %s (%s) for subject %s", ds.id, ds.file_path, subject.id)
    if not frames:
        raise ValueError("Subject has no readable datasets")
    return pd.concat(frames, ignore_index=True)


def _subject_label_column(subject: Subject) -> Optional[str]:
    """First label_column found among the Subject's datasets, if any."""
    for ds in subject.datasets:
        if ds.label_column:
            return ds.label_column
    return None


def _metrics_with_evaluation(fit: dict) -> dict:
    return {**fit["metrics"], "evaluation": fit["evaluation"]}


def _record_threshold_history(db, model_row: Model, thr: dict, source: str, n_rows: Optional[int]) -> None:
    """One row per calibration (training/retrain) or per manual z edit, so
    neither ever silently overwrites what the threshold used to be."""
    db.add(
        ThresholdHistory(
            subject_id=model_row.subject_id,
            model_id=model_row.id,
            mu=thr["mu"],
            sigma=thr["sigma"],
            epsilon=thr["epsilon"],
            z_multiplier=thr["z_multiplier"],
            n_rows=n_rows,
            source=source,
        )
    )


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
        fit = _fit_and_calibrate(df, algo, base_path, dataset.label_column)

        model_row.model_path = fit["model_path"]
        model_row.scaler_path = fit["scaler_path"]
        model_row.trained_at = datetime.utcnow()
        model_row.status = "ready"
        model_row.metrics_json = _metrics_with_evaluation(fit)

        thr = fit["threshold"]
        db.add(Threshold(model_id=model_row.id, mu=thr["mu"], sigma=thr["sigma"], epsilon=thr["epsilon"], z_multiplier=thr["z_multiplier"]))
        _record_threshold_history(db, model_row, thr, source="trained", n_rows=len(df))
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
    with _TRAIN_LOCK:
        _train_impl(dataset_id, user_id)


def _retrain_impl(subject_id: int, user_id: int, forced_algorithm: Optional[str] = None) -> dict:
    os.makedirs(settings.STORAGE_PATH, exist_ok=True)
    db = SessionLocal()
    model_row: Optional[Model] = None
    try:
        subject = db.query(Subject).filter(Subject.id == subject_id).first()
        if subject is None:
            raise ValueError("Subject not found")

        previous_active = db.query(Model).filter_by(subject_id=subject.id, is_active=True).first()
        old_epsilon = previous_active.threshold.epsilon if previous_active and previous_active.threshold else None

        if forced_algorithm:
            # Advanced mode: router deliberately skipped.
            algo, reason, selection_mode = forced_algorithm, "Manually selected by user (Advanced mode)", "manual"
        elif previous_active:
            algo, reason, selection_mode = previous_active.algorithm, previous_active.selection_reason, "auto"
        else:
            df_preview = _load_subject_dataframe(subject)
            from app.ml_core.profiler import profile_dataset

            algo, reason = choose_model(profile_dataset(df_preview))
            selection_mode = "auto"

        model_row = Model(
            user_id=user_id,
            subject_id=subject.id,
            dataset_id=subject.datasets[-1].id,  # most recent dataset, for reference/lineage only
            algorithm=algo,
            selection_reason=reason,
            selection_mode=selection_mode,
            is_active=False,  # flipped on only after training succeeds
            status="training",
        )
        db.add(model_row)
        db.commit()
        db.refresh(model_row)

        df = _load_subject_dataframe(subject)
        base_path = os.path.join(settings.STORAGE_PATH, f"user{user_id}_subj{subject.id}_m{model_row.id}")
        fit = _fit_and_calibrate(df, algo, base_path, _subject_label_column(subject))

        model_row.model_path = fit["model_path"]
        model_row.scaler_path = fit["scaler_path"]
        model_row.trained_at = datetime.utcnow()
        model_row.status = "ready"
        model_row.metrics_json = _metrics_with_evaluation(fit)
        db.commit()

        thr = fit["threshold"]
        db.add(Threshold(model_id=model_row.id, mu=thr["mu"], sigma=thr["sigma"], epsilon=thr["epsilon"], z_multiplier=thr["z_multiplier"]))
        _record_threshold_history(db, model_row, thr, source="retrained", n_rows=len(df))
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


def run_retrain_job(subject_id: int, user_id: int, forced_algorithm: Optional[str] = None) -> dict:
    with _TRAIN_LOCK:
        return _retrain_impl(subject_id, user_id, forced_algorithm)


def run_retrain_job_background(subject_id: int, user_id: int, forced_algorithm: Optional[str] = None) -> None:
    """Fire-and-forget for BackgroundTasks -- never raises (no request left
    to receive the error; failure is already recorded on the Model row)."""
    try:
        with _TRAIN_LOCK:
            _retrain_impl(subject_id, user_id, forced_algorithm)
    except Exception:
        logger.exception("Background retrain failed for subject %s", subject_id)


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
        fit = _fit_and_calibrate(df, algorithm, base_path, _subject_label_column(subject))

        model_row.model_path = fit["model_path"]
        model_row.scaler_path = fit["scaler_path"]
        model_row.trained_at = datetime.utcnow()
        model_row.status = "ready"
        model_row.metrics_json = _metrics_with_evaluation(fit)
        db.commit()

        thr = fit["threshold"]
        db.add(Threshold(model_id=model_row.id, mu=thr["mu"], sigma=thr["sigma"], epsilon=thr["epsilon"], z_multiplier=thr["z_multiplier"]))
        _record_threshold_history(db, model_row, thr, source="trained_alternative", n_rows=len(df))
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
