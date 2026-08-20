import logging
import uuid
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

from app.db.models import AnomalyEvent, Model, Prediction, Threshold
from app.ml_core.evaluation import coerce_binary_label
from app.ml_core.models.isolation_forest import IFModel
from app.ml_core.preprocessing import apply_scaler, load_scaler, numeric_only, sliding_window_labels, sliding_windows

logger = logging.getLogger(__name__)

# Auto-detected ground-truth column for a live Predict upload -- unlike
# training (where label_column is chosen per-Dataset at upload time), an
# ad-hoc predict CSV has no such metadata, so a literal column named
# "label" is the convention (matches the sample files this app hands out).
PREDICT_LABEL_COLUMN = "label"


def run_prediction(model_row: Model, threshold: Threshold, df: pd.DataFrame) -> Tuple[str, List[dict]]:
    label_series: Optional[pd.Series] = None
    if PREDICT_LABEL_COLUMN in df.columns:
        try:
            label_series = coerce_binary_label(df[PREDICT_LABEL_COLUMN])
        except Exception:
            logger.warning("'%s' column present but not usable as a binary ground-truth label, ignoring", PREDICT_LABEL_COLUMN)
        df = df.drop(columns=[PREDICT_LABEL_COLUMN])

    df = numeric_only(df)
    if df.empty:
        raise ValueError("No numeric columns in input")

    scaler = load_scaler(model_row.scaler_path)
    X = apply_scaler(df.values, scaler)

    if model_row.algorithm == "LSTM":
        from app.ml_core.models.lstm_autoencoder import LSTMAutoencoder

        m = LSTMAutoencoder(window_size=50, n_features=X.shape[1])
        m.load(model_row.model_path)
        W = sliding_windows(X, window_size=50, stride=10)
        if len(W) == 0:
            raise ValueError("Input is shorter than the model window size (50)")
        scores = m.score(W)
        actuals = (
            sliding_window_labels(label_series.values, window_size=50, stride=10) if label_series is not None else None
        )
    else:
        m = IFModel()
        m.load(model_row.model_path)
        scores = m.score(X)
        actuals = label_series.values if label_series is not None else None

    batch_id = uuid.uuid4().hex[:16]
    results = []
    for i, s in enumerate(scores):
        is_anom = bool(s > threshold.epsilon)
        actual = int(actuals[i]) if actuals is not None and i < len(actuals) else None
        results.append(
            {"batch_id": batch_id, "window_idx": i, "score": float(s), "is_anomaly": is_anom, "actual": actual}
        )
    return batch_id, results


def persist_predictions(db, user_id: int, model_id: int, results: List[dict], epsilon: float) -> int:
    """Save predictions + emit AnomalyEvents. Returns the flagged count (unchanged
    meaning -- callers show this as "anomalies detected"). When ground truth
    (r["actual"]) is known, a flagged window also gets tagged tp/fp, and a
    truly-anomalous window the system never flagged (fn) gets its own
    AnomalyEvent too -- previously silent, since only flagged windows had a
    row at all."""
    anomaly_count = 0
    for r in results:
        pred = Prediction(
            model_id=model_id,
            batch_id=r["batch_id"],
            window_idx=r["window_idx"],
            score=r["score"],
            is_anomaly=r["is_anomaly"],
            actual=r.get("actual"),
        )
        db.add(pred)
        db.flush()  # need pred.id
        actual = r.get("actual")

        if r["is_anomaly"]:
            anomaly_count += 1
            outcome = None if actual is None else ("tp" if actual == 1 else "fp")
            db.add(
                AnomalyEvent(
                    prediction_id=pred.id,
                    user_id=user_id,
                    severity=_severity_from(r["score"], epsilon),
                    outcome=outcome,
                    detection_source="flagged",
                )
            )
        elif actual == 1:
            # Truly anomalous per ground truth, but the score never crossed
            # epsilon -- always the worst-case outcome regardless of how far
            # below threshold the score was, hence "critical" unconditionally.
            db.add(
                AnomalyEvent(
                    prediction_id=pred.id,
                    user_id=user_id,
                    severity="critical",
                    outcome="fn",
                    detection_source="missed_ground_truth",
                )
            )
    db.commit()
    return anomaly_count


def _severity_from(score: float, epsilon: float) -> str:
    """Severity relative to the personalized threshold (score/epsilon ratio),
    per Implementation_Plan.md sec 5.3 -- not an absolute score cutoff, since
    each model's score scale differs (IF log-density vs LSTM MAE)."""
    if epsilon <= 0:
        return "warning"
    ratio = score / epsilon
    if ratio > 2.0:
        return "critical"
    if ratio > 1.3:
        return "warning"
    return "info"
