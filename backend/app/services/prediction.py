import uuid
from typing import List, Tuple

import numpy as np
import pandas as pd

from app.db.models import AnomalyEvent, Model, Prediction, Threshold
from app.ml_core.models.isolation_forest import IFModel
from app.ml_core.preprocessing import apply_scaler, load_scaler, numeric_only, sliding_windows


def run_prediction(model_row: Model, threshold: Threshold, df: pd.DataFrame) -> Tuple[str, List[dict]]:
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
    else:
        m = IFModel()
        m.load(model_row.model_path)
        scores = m.score(X)

    batch_id = uuid.uuid4().hex[:16]
    results = []
    for i, s in enumerate(scores):
        is_anom = bool(s > threshold.epsilon)
        results.append({"batch_id": batch_id, "window_idx": i, "score": float(s), "is_anomaly": is_anom})
    return batch_id, results


def persist_predictions(db, user_id: int, model_id: int, results: List[dict]) -> int:
    """Save predictions + emit AnomalyEvents for scores above threshold. Returns anomaly count."""
    anomaly_count = 0
    for r in results:
        pred = Prediction(
            model_id=model_id,
            batch_id=r["batch_id"],
            window_idx=r["window_idx"],
            score=r["score"],
            is_anomaly=r["is_anomaly"],
        )
        db.add(pred)
        db.flush()  # need pred.id
        if r["is_anomaly"]:
            anomaly_count += 1
            db.add(
                AnomalyEvent(
                    prediction_id=pred.id,
                    user_id=user_id,
                    severity=_severity_from(r["score"]),
                )
            )
    db.commit()
    return anomaly_count


def _severity_from(score: float) -> str:
    if score > 1.0:
        return "critical"
    if score > 0.5:
        return "warning"
    return "info"
