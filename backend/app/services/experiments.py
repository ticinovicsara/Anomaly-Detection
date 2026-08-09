"""Personalization Experiment -- the empirical proof behind thesis ch. 7.4:
train the same pipeline independently per Subject, calibrate each threshold
from that Subject's own data only, then show the epsilon spread and what a
single global threshold would have cost in false positives / missed
anomalies. Nothing here is dataset-specific; it operates on whatever
Subjects the caller already has.
"""
import logging
import os
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Dataset, Model, Subject, Threshold
from app.services.prediction import run_prediction
from app.services.subjects import get_active_model
from app.services.training import _TRAIN_LOCK, _fit_and_calibrate, _load_subject_dataframe

logger = logging.getLogger(__name__)

_DEMO_N_SUBJECTS = 10
_DEMO_N_ROWS = 1500


def _subject_scores(subject: Subject, model: Model) -> list[float]:
    """Re-score a Subject's own data against its own active model, so the
    cross-application comparison doesn't depend on the user having run a
    separate /predict call first."""
    df = _load_subject_dataframe(subject)
    _batch_id, results = run_prediction(model, model.threshold, df)
    return [r["score"] for r in results]


def run_personalization_experiment(subject_ids: list[int], db: Session, user_id: int) -> dict:
    subjects = (
        db.query(Subject)
        .filter(Subject.id.in_(subject_ids), Subject.user_id == user_id)
        .all()
    )
    if len(subjects) < 2:
        raise ValueError("Select at least 2 subjects to run this experiment")

    epsilons: dict[str, float] = {}
    active_by_subject: dict[int, Model] = {}
    for s in subjects:
        m = get_active_model(s, db)
        if not m or m.status != "ready" or not m.threshold:
            raise ValueError(f"Subject '{s.name}' has no trained, active model yet")
        epsilons[s.name] = m.threshold.epsilon
        active_by_subject[s.id] = m

    eps_values = list(epsilons.values())
    mean_eps = float(np.mean(eps_values))
    min_eps = float(min(eps_values))
    max_eps = float(max(eps_values))

    fp_rate: dict[str, Optional[float]] = {}
    miss_rate: dict[str, Optional[float]] = {}
    for s in subjects:
        model = active_by_subject[s.id]
        try:
            scores = _subject_scores(s, model)
        except Exception:
            logger.exception("Could not re-score subject %s for the experiment", s.id)
            scores = []
        if not scores:
            fp_rate[s.name] = None
            miss_rate[s.name] = None
            continue
        personal_eps = epsilons[s.name]
        n = len(scores)
        personalized_flags = [sc > personal_eps for sc in scores]
        global_flags = [sc > mean_eps for sc in scores]
        fp_rate[s.name] = sum(1 for pf, gf in zip(personalized_flags, global_flags) if not pf and gf) / n
        miss_rate[s.name] = sum(1 for pf, gf in zip(personalized_flags, global_flags) if pf and not gf) / n

    return {
        "subject_ids": [s.id for s in subjects],
        "epsilons": epsilons,
        "statistics": {
            "mean": mean_eps,
            "std": float(np.std(eps_values)),
            "min": min_eps,
            "max": max_eps,
            "range_ratio": (max_eps / min_eps) if min_eps > 0 else None,
        },
        "cross_application": {
            "global_epsilon": mean_eps,
            "fp_rate_at_global": fp_rate,
            "miss_rate_at_global": miss_rate,
        },
    }


def _synthetic_dataframe(noise_std: float, n_rows: int, seed: int) -> pd.DataFrame:
    """A periodic two-channel signal with a per-subject noise level -- stands
    in for 'the same structural process, different individual variability'
    (what MIT-BIH patients look like structurally) without shipping a
    specific external dataset. Same periodicity everywhere so the router
    consistently picks the same algorithm and the demo isolates epsilon,
    the exact thing the experiment measures, as the only variable."""
    rng = np.random.default_rng(seed)
    t = np.arange(n_rows)
    base = np.sin(2 * np.pi * t / 50) + 0.3 * np.sin(2 * np.pi * t / 17)
    signal_a = base + rng.normal(0, noise_std, n_rows)
    signal_b = np.roll(base, 3) + rng.normal(0, noise_std * 0.6, n_rows)
    return pd.DataFrame({"signal_a": signal_a, "signal_b": signal_b})


def run_preset_demo(
    db: Session,
    user_id: int,
    n_subjects: int = _DEMO_N_SUBJECTS,
    n_rows: int = _DEMO_N_ROWS,
) -> dict:
    """Create `n_subjects` synthetic Subjects spanning a wide range of noise
    levels, train each independently (same algorithm, same hyperparameters,
    only the data differs), then run the personalization experiment across
    them. For users who don't have real Subjects yet and want to see the
    ch. 7.4 argument immediately."""
    os.makedirs(settings.STORAGE_PATH, exist_ok=True)
    demo_dir = os.path.join(settings.STORAGE_PATH, "demo")
    os.makedirs(demo_dir, exist_ok=True)

    noise_levels = np.logspace(np.log10(0.02), np.log10(0.5), n_subjects)
    created_subject_ids: list[int] = []
    trained_subject_ids: list[int] = []

    with _TRAIN_LOCK:
        for i, noise_std in enumerate(noise_levels, start=1):
            name = f"Demo subject {i:02d}"
            existing = db.query(Subject).filter_by(user_id=user_id, name=name).first()
            if existing:
                db.delete(existing)
                db.commit()

            subject = Subject(
                user_id=user_id,
                name=name,
                description=(
                    f"Synthetic demo data (noise std={noise_std:.3f}), generated for the "
                    "personalization experiment preset."
                ),
                source_hint="preset_demo",
            )
            db.add(subject)
            db.commit()
            db.refresh(subject)

            df = _synthetic_dataframe(noise_std, n_rows, seed=1000 + i)
            file_path = os.path.join(demo_dir, f"user{user_id}_demo_subj{subject.id}.csv")
            df.to_csv(file_path, index=False)

            dataset = Dataset(
                user_id=user_id,
                subject_id=subject.id,
                name=name,
                detected_type="synthetic_demo",
                file_path=file_path,
                n_rows=len(df),
                n_features=df.shape[1],
            )
            db.add(dataset)
            db.commit()
            db.refresh(dataset)

            model_row = Model(
                user_id=user_id,
                subject_id=subject.id,
                dataset_id=dataset.id,
                algorithm="LSTM",
                selection_reason=(
                    "Fixed to LSTM Autoencoder for every synthetic subject in this demo, so the "
                    "algorithm is held constant and epsilon is the only variable that changes -- "
                    "mirrors the ch. 7.4 methodology."
                ),
                selection_mode="auto",
                status="training",
            )
            db.add(model_row)
            db.commit()
            db.refresh(model_row)

            try:
                base_path = os.path.join(demo_dir, f"user{user_id}_demo_subj{subject.id}_m{model_row.id}")
                fit = _fit_and_calibrate(df, "LSTM", base_path)

                model_row.model_path = fit["model_path"]
                model_row.scaler_path = fit["scaler_path"]
                model_row.trained_at = datetime.utcnow()
                model_row.status = "ready"
                model_row.metrics_json = fit["metrics"]
                db.commit()

                thr = fit["threshold"]
                db.add(
                    Threshold(
                        model_id=model_row.id,
                        mu=thr["mu"],
                        sigma=thr["sigma"],
                        epsilon=thr["epsilon"],
                        z_multiplier=thr["z_multiplier"],
                    )
                )
                db.commit()
                trained_subject_ids.append(subject.id)
            except Exception as exc:
                logger.exception("Preset demo training failed for synthetic subject %s", subject.id)
                db.rollback()
                model_row.status = "failed"
                model_row.metrics_json = {"error": str(exc)[:500]}
                db.commit()

            created_subject_ids.append(subject.id)

    if len(trained_subject_ids) < 2:
        raise ValueError("Preset demo training failed for too many synthetic subjects to run the experiment")

    result = run_personalization_experiment(trained_subject_ids, db, user_id)
    result["created_subject_ids"] = created_subject_ids
    return result
