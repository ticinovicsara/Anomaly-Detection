import time
import math
import joblib
import numpy as np
from pathlib import Path
from sklearn.ensemble import IsolationForest
from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score
from typing import Optional


def train(
    X_train: np.ndarray,
    contamination: float = 0.01,
    random_state: int = 42,
    save_path: Optional[str] = None,
) -> tuple[IsolationForest, float]:
    start = time.time()

    model = IsolationForest(contamination=contamination, random_state=random_state)
    model.fit(X_train)

    elapsed = round(time.time() - start, 3)

    if save_path:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, save_path)

    return model, elapsed


def predict(
    X: np.ndarray,
    model_path: str,
) -> np.ndarray:
    model = joblib.load(model_path)
    raw = model.predict(X)
    return np.where(raw == -1, 1, 0)


def evaluate(
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> dict:
    auc = float(roc_auc_score(y_true, y_pred)) if len(np.unique(y_true)) > 1 else float("nan")
    return {
        "precision": round(float(precision_score(y_true, y_pred, average="binary", zero_division=0)), 4),
        "recall":    round(float(recall_score(y_true, y_pred, average="binary", zero_division=0)), 4),
        "f1":        round(float(f1_score(y_true, y_pred, average="binary", zero_division=0)), 4),
        "roc_auc":   round(auc, 4) if not math.isnan(auc) else auc,
    }


def calibrate_threshold(
    model: IsolationForest,
    X_val: np.ndarray,
    sigma: int = 3,
) -> tuple[float, float, float]:
    scores = -model.score_samples(X_val)
    mean = float(np.mean(scores))
    std = float(np.std(scores))
    threshold = mean + sigma * std
    return threshold, mean, std
