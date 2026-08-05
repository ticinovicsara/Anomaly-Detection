"""Tests for the pure ML modules — no DB, no FastAPI."""
import numpy as np
import pandas as pd

from app.ml_core.model_router import choose_model
from app.ml_core.models.isolation_forest import IFModel
from app.ml_core.preprocessing import sliding_windows, temporal_split
from app.ml_core.profiler import profile_dataset
from app.ml_core.threshold import calibrate_threshold, recompute_epsilon


def test_if_detects_synthetic_anomalies():
    rng = np.random.default_rng(0)
    X_normal = rng.normal(0, 1, (500, 5))
    X_anom = rng.normal(8, 1, (10, 5))
    X = np.vstack([X_normal, X_anom])

    m = IFModel(contamination=0.02)
    m.train(X)
    scores = m.score(X)

    assert scores[-10:].mean() > scores[:500].mean()


def test_temporal_split_ratios():
    df = pd.DataFrame({"a": range(1000)})
    tr, va, te = temporal_split(df, 0.7, 0.15)
    assert len(tr) == 700 and len(va) == 150 and len(te) == 150
    # order preserved
    assert tr["a"].iloc[-1] == 699
    assert va["a"].iloc[0] == 700


def test_sliding_windows_shape():
    X = np.arange(200).reshape(-1, 1)
    W = sliding_windows(X, window_size=50, stride=10)
    assert W.shape == ((200 - 50) // 10 + 1, 50, 1)


def test_threshold_calibration():
    scores = np.array([0.1, 0.2, 0.15, 0.18, 0.22])
    t = calibrate_threshold(scores, z=3.0)
    assert t["epsilon"] > t["mu"]
    assert abs(recompute_epsilon(t["mu"], t["sigma"], 3.0) - t["epsilon"]) < 1e-9


def test_profiler_handles_string_columns():
    df = pd.DataFrame({"num": np.arange(100.0), "text": ["a"] * 100})
    p = profile_dataset(df)
    assert p["n_features"] == 1


def test_profiler_handles_empty_numeric():
    df = pd.DataFrame({"text": ["a", "b", "c"]})
    p = profile_dataset(df)
    assert "error" in p


def test_router_small_dataset_picks_IF():
    algo, reason = choose_model({"n_rows": 100, "n_features": 3})
    assert algo == "IF"
    assert "Small" in reason


def test_router_high_dim_low_autocorr_picks_IF():
    algo, _ = choose_model({"n_rows": 10000, "n_features": 28, "autocorr_lag1": 0.05})
    assert algo == "IF"


def test_router_high_autocorr_picks_LSTM():
    algo, _ = choose_model({"n_rows": 10000, "n_features": 1, "autocorr_lag1": 0.9})
    assert algo == "LSTM"
