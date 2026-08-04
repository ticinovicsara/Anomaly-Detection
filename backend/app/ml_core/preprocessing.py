from typing import Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler


def numeric_only(df: pd.DataFrame) -> pd.DataFrame:
    return df.select_dtypes(include=[np.number]).dropna()


def temporal_split(
    df: pd.DataFrame, train_ratio: float = 0.7, val_ratio: float = 0.15
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    n = len(df)
    i = int(n * train_ratio)
    j = int(n * (train_ratio + val_ratio))
    return df.iloc[:i].copy(), df.iloc[i:j].copy(), df.iloc[j:].copy()


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


def save_scaler(scaler: StandardScaler, path: str) -> None:
    joblib.dump(scaler, path)


def load_scaler(path: str) -> StandardScaler:
    return joblib.load(path)
