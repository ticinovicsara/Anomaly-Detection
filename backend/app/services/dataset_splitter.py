"""Analyzes an uploaded CSV for viable ways to split it into multiple
Subjects (by an identifier column, or by time period). Dataset-agnostic by
design -- this looks only at column dtypes/cardinality, never at column
names or domain knowledge, so it works identically on MIT-BIH, Credit Card
Fraud, or a CSV nobody involved in this project has ever seen.

Every heuristic is wrapped so a single bad column can never crash the
request -- real user CSVs have mixed types, huge cardinality, garbage
values, all of it.
"""
import warnings
from typing import Literal

import pandas as pd
import pandas.api.types as ptypes


def analyze_split_options(df: pd.DataFrame) -> dict:
    """Look at a dataframe and return which split strategies are viable.
    Never crashes -- always returns something, even for a single-row or
    all-numeric-junk CSV."""
    result: dict = {
        "n_rows": len(df),
        "candidate_id_columns": [],
        "candidate_time_columns": [],
    }

    for col in df.columns:
        # ID candidates: string or integer dtype with a "reasonable" number
        # of distinct values -- enough to be worth splitting on, not so many
        # that every row would become its own Subject. Uses is_string_dtype
        # rather than `dtype == object`: pandas 2.x/3.x can back plain text
        # columns with a dedicated "str" dtype instead of legacy "object",
        # and `== object` silently stops matching them.
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

        # Time candidates: the column parses as a datetime for at least a
        # sample of its values. Restricted to string/object columns --
        # pd.to_datetime happily reinterprets any bare float or int as a
        # nanosecond-since-epoch timestamp and "succeeds", which would
        # flag every numeric measurement column as a time candidate.
        try:
            if not (ptypes.is_string_dtype(df[col].dtype) or ptypes.is_object_dtype(df[col].dtype)):
                continue
            sample = df[col].dropna().iloc[:100]
            if sample.empty:
                continue
            with warnings.catch_warnings():
                # dateutil's per-element fallback (triggered when trying
                # non-date text like a "p0"/"p1" id column) is noisy but
                # harmless here -- the whole block is already wrapped in
                # try/except and any parse failure is treated as "not a
                # time column", which is exactly what we want.
                warnings.simplefilter("ignore", UserWarning)
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
    """Return {group_key: df_slice}. Group key is stringified so it can be
    used directly as a Subject name. The split column itself is dropped
    from each slice -- it's now redundant (every row in a slice shares it)."""
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
