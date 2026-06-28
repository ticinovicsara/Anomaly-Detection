import warnings
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.preprocessing import MinMaxScaler, StandardScaler
from typing import Optional


def normalize(
    df: pd.DataFrame,
    feature_cols: list[str],
    scaler_path: Optional[str] = None,
) -> tuple[pd.DataFrame, MinMaxScaler]:
    df_out = df.copy()

    if scaler_path and Path(scaler_path).exists():
        scaler = joblib.load(scaler_path)
        df_out[feature_cols] = scaler.transform(df_out[feature_cols])
    else:
        scaler = MinMaxScaler()
        df_out[feature_cols] = scaler.fit_transform(df_out[feature_cols])
        if scaler_path:
            Path(scaler_path).parent.mkdir(parents=True, exist_ok=True)
            joblib.dump(scaler, scaler_path)

    return df_out, scaler


def create_windows(
    data: np.ndarray,
    window_size: int = 50,
    step: int = 10,
) -> np.ndarray:
    if data.ndim == 1:
        data = data.reshape(-1, 1)

    windows = []
    for start in range(0, len(data) - window_size + 1, step):
        windows.append(data[start : start + window_size])

    return np.array(windows)


def window_labels(
    labels: np.ndarray,
    window_size: int = 50,
    step: int = 10,
) -> np.ndarray:
    result = []
    for start in range(0, len(labels) - window_size + 1, step):
        result.append(int(labels[start : start + window_size].max()))
    return np.array(result, dtype=int)


def split_by_time(
    df: pd.DataFrame,
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    test_ratio = round(1.0 - train_ratio - val_ratio, 10)
    if test_ratio < 0:
        raise ValueError(
            f"train_ratio + val_ratio = {train_ratio + val_ratio} exceeds 1.0"
        )

    n = len(df)
    train_end = int(n * train_ratio)
    val_end = int(n * (train_ratio + val_ratio))

    return df.iloc[:train_end], df.iloc[train_end:val_end], df.iloc[val_end:]


def load_creditcard(
    raw_path: str,
    amount_scaler_path: Optional[str] = None,
) -> tuple[pd.DataFrame, list[str]]:
    path = Path(raw_path)
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {raw_path}")

    df = pd.read_csv(path)

    required = {"Time", "Amount", "Class"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing expected columns: {missing}")

    df = df.drop(columns=["Time"])

    if amount_scaler_path and Path(amount_scaler_path).exists():
        amount_scaler = joblib.load(amount_scaler_path)
        df[["Amount"]] = amount_scaler.transform(df[["Amount"]])
    else:
        amount_scaler = StandardScaler()
        df[["Amount"]] = amount_scaler.fit_transform(df[["Amount"]])
        if amount_scaler_path:
            Path(amount_scaler_path).parent.mkdir(parents=True, exist_ok=True)
            joblib.dump(amount_scaler, amount_scaler_path)

    feature_cols = [f"V{i}" for i in range(1, 29)] + ["Amount"]

    return df, feature_cols


def load_ecg(
    raw_path: str,
    label_col: str = "label",
) -> tuple[pd.DataFrame, list[str]]:
    path = Path(raw_path)
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {raw_path}")

    df = pd.read_csv(path)

    if label_col not in df.columns:
        warnings.warn(
            f"Label column '{label_col}' not found; inserting all-zero labels. "
            "Pass label_col=None if running inference without ground truth.",
            UserWarning,
            stacklevel=2,
        )
        df[label_col] = 0

    feature_cols = [c for c in df.columns if c != label_col]

    return df, feature_cols


def load_yahoo(
    raw_path: str,
    label_col: str = "is_anomaly",
) -> tuple[pd.DataFrame, list[str]]:
    path = Path(raw_path)
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {raw_path}")

    df = pd.read_csv(path)

    for ts_col in ("timestamps", "timestamp", "Timestamps"):
        if ts_col in df.columns:
            df = df.drop(columns=[ts_col])
            break

    for cp_col in ("changepoint", "is_changepoint"):
        if cp_col in df.columns:
            df = df.drop(columns=[cp_col])

    if label_col not in df.columns:
        warnings.warn(
            f"Label column '{label_col}' not found; inserting all-zero labels.",
            UserWarning,
            stacklevel=2,
        )
        df[label_col] = 0

    feature_cols = [c for c in df.columns if c != label_col]

    return df, feature_cols
