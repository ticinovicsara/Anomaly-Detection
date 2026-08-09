"""Optional supervised evaluation (precision/recall/F1/AUC) on a labeled
test split. Pure, no FastAPI/SQLAlchemy -- same convention as the rest
of ml_core."""
import logging
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score

from app.ml_core.preprocessing import apply_scaler, sliding_window_labels, sliding_windows

logger = logging.getLogger(__name__)

# Curve is downsampled for charting; metrics below always use the full test set.
MAX_CURVE_POINTS = 500


def coerce_binary_label(series: pd.Series) -> pd.Series:
    """Maps a 2-valued column to {0, 1}: minority value = anomaly (works
    regardless of encoding -- 0/1, -1/1, yes/no). Raises if not exactly
    2 distinct values."""
    non_null = series.dropna()
    if non_null.nunique() != 2:
        raise ValueError("label column must have exactly two distinct values")
    anomaly_value = non_null.value_counts().idxmin()
    return series.map(lambda v: np.nan if pd.isna(v) else (1 if v == anomaly_value else 0))


def build_curve(scores: np.ndarray, y_eval: np.ndarray, y_pred: np.ndarray) -> list:
    n = len(scores)
    if n > MAX_CURVE_POINTS:
        idx = np.unique(np.linspace(0, n - 1, MAX_CURVE_POINTS).round().astype(int))
    else:
        idx = np.arange(n)
    return [
        {"i": int(i), "score": float(scores[i]), "actual": int(y_eval[i]), "predicted": int(y_pred[i])}
        for i in idx
    ]


def evaluate_on_test(
    model, algo: str, test_df: pd.DataFrame, test_labels: Optional[pd.Series], scaler, epsilon: float
) -> Optional[dict]:
    """Evaluated at the real operational epsilon, not a tuned cutoff.
    Returns None (never raises) if there's no usable label."""
    if test_labels is None or test_df.empty:
        return None
    try:
        y_test = test_labels.dropna()
        if y_test.empty:
            return None
        aligned_df = test_df.loc[y_test.index]
        y_test = y_test.astype(int)
        if y_test.nunique() < 2:
            return None

        X_test = apply_scaler(aligned_df.values, scaler)
        if algo == "LSTM":
            W_test = sliding_windows(X_test, window_size=50, stride=10)
            if len(W_test) == 0:
                return None
            y_eval = sliding_window_labels(y_test.values, window_size=50, stride=10)
            scores = model.score(W_test)
        else:
            scores = model.score(X_test)
            y_eval = y_test.values

        scores = np.asarray(scores)
        y_pred = (scores > epsilon).astype(int)
        auc = float(roc_auc_score(y_eval, scores)) if len(np.unique(y_eval)) > 1 else None

        return {
            "precision": float(precision_score(y_eval, y_pred, zero_division=0)),
            "recall": float(recall_score(y_eval, y_pred, zero_division=0)),
            "f1": float(f1_score(y_eval, y_pred, zero_division=0)),
            "auc": auc,
            "n_test_samples": int(len(y_eval)),
            "n_test_positive": int(np.sum(y_eval)),
            "epsilon": float(epsilon),
            "confusion": {
                "tp": int(np.sum((y_pred == 1) & (y_eval == 1))),
                "fp": int(np.sum((y_pred == 1) & (y_eval == 0))),
                "tn": int(np.sum((y_pred == 0) & (y_eval == 0))),
                "fn": int(np.sum((y_pred == 0) & (y_eval == 1))),
            },
            "curve": build_curve(scores, y_eval, y_pred),
        }
    except Exception:
        logger.exception("Evaluation on labeled test set failed, continuing without it")
        return None
