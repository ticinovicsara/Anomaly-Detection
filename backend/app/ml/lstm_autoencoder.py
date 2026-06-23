import math
import numpy as np
from pathlib import Path
from typing import Optional
from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score

from keras.models import Sequential, load_model
from keras.layers import LSTM, Dense, RepeatVector, TimeDistributed
from keras.callbacks import EarlyStopping


def build_model(window_size: int = 50, n_features: int = 1) -> Sequential:
    model = Sequential([
        LSTM(64, input_shape=(window_size, n_features), return_sequences=True),
        LSTM(32, return_sequences=False),
        RepeatVector(window_size),
        LSTM(32, return_sequences=True),
        LSTM(64, return_sequences=True),
        TimeDistributed(Dense(n_features)),
    ])
    model.compile(optimizer="adam", loss="mae")
    return model


def train(
    model: Sequential,
    X_train: np.ndarray,
    X_val: np.ndarray,
    epochs: int = 50,
    batch_size: int = 32,
    save_path: Optional[str] = None,
) -> tuple[Sequential, dict]:
    early_stop = EarlyStopping(monitor="val_loss", patience=5, restore_best_weights=True)

    history = model.fit(
        X_train, X_train,
        validation_data=(X_val, X_val),
        epochs=epochs,
        batch_size=batch_size,
        callbacks=[early_stop],
        verbose=0,
    )

    if save_path:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        model.save(save_path)

    return model, history.history


def get_reconstruction_error(model: Sequential, X: np.ndarray) -> np.ndarray:
    X_pred = model.predict(X, verbose=0)
    return np.mean(np.abs(X - X_pred), axis=(1, 2))


def calibrate_threshold(
    model: Sequential,
    X_val: np.ndarray,
    sigma: int = 3,
) -> tuple[float, float, float]:
    errors = get_reconstruction_error(model, X_val)
    mean = float(np.mean(errors))
    std = float(np.std(errors))
    threshold = mean + sigma * std
    return threshold, mean, std


def predict(
    X: np.ndarray,
    model_path: str,
    threshold: float,
) -> tuple[np.ndarray, np.ndarray]:
    model = load_model(model_path)
    errors = get_reconstruction_error(model, X)
    predictions = (errors > threshold).astype(int)
    return predictions, errors


def evaluate(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    reconstruction_errors: np.ndarray,
) -> dict:
    auc = float(roc_auc_score(y_true, reconstruction_errors)) if len(np.unique(y_true)) > 1 else float("nan")
    return {
        "precision": round(float(precision_score(y_true, y_pred, average="binary", zero_division=0)), 4),
        "recall":    round(float(recall_score(y_true, y_pred, average="binary", zero_division=0)), 4),
        "f1":        round(float(f1_score(y_true, y_pred, average="binary", zero_division=0)), 4),
        "roc_auc":   round(auc, 4) if not math.isnan(auc) else auc,
    }
