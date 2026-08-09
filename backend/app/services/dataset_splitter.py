"""Analyzes an uploaded CSV for viable Subject splits (by ID column or
time period). Looks only at dtype/cardinality, never column names --
dataset-agnostic by design. Every heuristic is wrapped in try/except;
a bad column must never crash the request."""
import warnings
from typing import Literal

import pandas as pd
import pandas.api.types as ptypes


def analyze_split_options(df: pd.DataFrame) -> dict:
    """Never crashes -- always returns something, even for junk input."""
    result: dict = {
        "n_rows": len(df),
        "candidate_id_columns": [],
        "candidate_time_columns": [],
        "candidate_label_columns": [],
    }

    for col in df.columns:
        # is_string_dtype not `dtype == object`: pandas 2.x/3.x may back text
        # columns with a "str" dtype that `== object` silently misses.
        try:
            dtype = df[col].dtype
            if ptypes.is_string_dtype(dtype) or ptypes.is_integer_dtype(dtype):
                uniq = df[col].nunique(dropna=True)
                if 2 <= uniq <= min(1000, max(2, len(df) // 5)):
                    result["candidate_id_columns"].append(
                        {
                            "column": str(col),
                            "n_unique": int(uniq),
                            "example_values": [str(v) for v in df[col].dropna().unique()[:5]],
                        }
                    )
        except Exception:
            pass

        # Label candidates: any column with exactly 2 distinct values.
        try:
            uniq_vals = df[col].dropna().unique()
            if len(uniq_vals) == 2:
                counts = df[col].value_counts()
                minority_ratio = float(counts.min() / counts.sum())
                result["candidate_label_columns"].append(
                    {
                        "column": str(col),
                        "example_values": [str(v) for v in uniq_vals[:2]],
                        "minority_ratio": minority_ratio,
                    }
                )
        except Exception:
            pass

        # Restricted to string/object dtype: pd.to_datetime otherwise
        # reinterprets any float/int as a nanosecond timestamp and "succeeds".
        try:
            if not (ptypes.is_string_dtype(df[col].dtype) or ptypes.is_object_dtype(df[col].dtype)):
                continue
            sample = df[col].dropna().iloc[:100]
            if sample.empty:
                continue
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)  # dateutil noise on non-date text
                parsed = pd.to_datetime(sample, errors="raise")
            result["candidate_time_columns"].append(
                {
                    "column": str(col),
                    "sample_range": [str(parsed.min()), str(parsed.max())],
                }
            )
        except Exception:
            pass

    return result


def split_by_column(df: pd.DataFrame, column: str) -> dict[str, pd.DataFrame]:
    """{group_key: df_slice}; key is stringified (used as Subject name),
    split column dropped from each slice."""
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found")
    return {str(k): g.drop(columns=[column]).reset_index(drop=True) for k, g in df.groupby(column)}


_FREQ_MAP = {"hourly": "h", "daily": "D", "weekly": "W", "monthly": "M"}


def split_by_time(
    df: pd.DataFrame, column: str, period: Literal["hourly", "daily", "weekly", "monthly"]
) -> dict[str, pd.DataFrame]:
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found")
    if period not in _FREQ_MAP:
        raise ValueError(f"Unknown period '{period}', expected one of {list(_FREQ_MAP)}")

    df = df.copy()
    df[column] = pd.to_datetime(df[column])
    groups = df.groupby(df[column].dt.to_period(_FREQ_MAP[period]))
    return {str(k): g.drop(columns=[column]).reset_index(drop=True) for k, g in groups}
