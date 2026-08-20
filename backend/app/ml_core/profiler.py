"""Data profiler.

Extracts a small set of characteristics from a user-uploaded dataframe
without training anything. Every step is wrapped in try/except and returns
None on failure - real CSVs have missing values, string columns, no time
index, or one row of data, and the profiler must never crash the request.
"""
from typing import Any, Callable, Dict, Optional

import numpy as np
import pandas as pd


def _safe(fn: Callable[[], Any], default: Optional[Any] = None) -> Any:
    try:
        val = fn()
        # NaN / inf leaking out of numpy → JSON serialisation crashes; coerce
        if isinstance(val, float) and (np.isnan(val) or np.isinf(val)):
            return default
        return val
    except Exception:
        return default


def profile_dataset(df: pd.DataFrame) -> Dict[str, Any]:
    numeric = df.select_dtypes(include=[np.number]).dropna()
    if numeric.empty:
        return {"error": "no_numeric_columns", "n_rows": len(df), "n_features": 0}

    profile: Dict[str, Any] = {
        "n_rows": int(len(numeric)),
        "n_features": int(numeric.shape[1]),
        "column_stats": _safe(
            lambda: {
                c: {
                    "mean": float(numeric[c].mean()),
                    "std": float(numeric[c].std()),
                    "min": float(numeric[c].min()),
                    "max": float(numeric[c].max()),
                }
                for c in numeric.columns
            },
            default={},
        ),
    }

    first_col = numeric.iloc[:, 0].values.astype(float)

    def _autocorr_lag1():
        from statsmodels.tsa.stattools import acf
        return float(acf(first_col, nlags=1, fft=True)[1])

    def _adf_pvalue():
        from statsmodels.tsa.stattools import adfuller
        return float(adfuller(first_col, autolag="AIC")[1])

    def _fft_peak():
        from scipy.signal import periodogram
        f, p = periodogram(first_col)
        if len(p) <= 1:
            return None
        idx = int(np.argmax(p[1:])) + 1
        return float(f[idx])

    profile["autocorr_lag1"] = _safe(_autocorr_lag1)
    profile["adf_pvalue"] = _safe(_adf_pvalue)
    profile["fft_peak"] = _safe(_fft_peak)

    return profile
