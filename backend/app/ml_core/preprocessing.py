from typing import Optional, Tuple, Union

import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler


def numeric_only(df: pd.DataFrame) -> pd.DataFrame:
    return df.select_dtypes(include=[np.number]).dropna()


def temporal_split(
    df: pd.DataFrame,
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
    labels: Optional[pd.Series] = None,
) -> Union[
    Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame],
    Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.Series, pd.Series, pd.Series],
]:
    """Chronological 70/15/15-style split. `labels`, if given, must share
    `df`'s index and is cut at the exact same row boundaries so features
    and ground-truth labels never drift apart -- when passed, the label
    slices are appended after the dataframe slices instead of changing
    the existing 3-tuple contract, so callers that don't need labels are
    unaffected."""
    n = len(df)
    i = int(n * train_ratio)
    j = int(n * (train_ratio + val_ratio))
    train_df, val_df, test_df = df.iloc[:i].copy(), df.iloc[i:j].copy(), df.iloc[j:].copy()
    if labels is None:
        return train_df, val_df, test_df
    train_lbl, val_lbl, test_lbl = labels.iloc[:i].copy(), labels.iloc[i:j].copy(), labels.iloc[j:].copy()
    return train_df, val_df, test_df, train_lbl, val_lbl, test_lbl


def fit_scaler(X_train: np.ndarray) -> StandardScaler:
    scaler = StandardScaler()
    scaler.fit(X_train)
    return scaler


def apply_scaler(X: np.ndarray, scaler: StandardScaler) -> np.ndarray:
    return scaler.transform(X)


def sliding_windows(X: np.ndarray, window_size: int = 50, stride: int = 10) -> np.ndarray:
    if X.ndim == 1:
        X = X.reshape(-1, 1)
    n = len(X)
    if n < window_size:
        return np.empty((0, window_size, X.shape[1]), dtype=X.dtype)
    windows = [X[i : i + window_size] for i in range(0, n - window_size + 1, stride)]
    return np.array(windows)


def sliding_window_labels(labels: np.ndarray, window_size: int = 50, stride: int = 10) -> np.ndarray:
    """Per-window ground-truth label, aggregated with max() so a window is
    anomalous if any row inside it is -- same (i, window_size, stride)
    indexing as sliding_windows, so window k here lines up with window k
    of sliding_windows(X, ...) on the same underlying array. Conservative
    on purpose: under-detecting is worse than over-detecting a window."""
    y = np.asarray(labels)
    n = len(y)
    if n < window_size:
        return np.empty((0,), dtype=y.dtype)
    return np.array([y[i : i + window_size].max() for i in range(0, n - window_size + 1, stride)])


def save_scaler(scaler: StandardScaler, path: str) -> None:
    joblib.dump(scaler, path)


def load_scaler(path: str) -> StandardScaler:
    return joblib.load(path)
