"""Tests for the dataset splitter -- pure pandas, no DB, no FastAPI."""
import numpy as np
import pandas as pd
import pytest

from app.services.dataset_splitter import analyze_split_options, split_by_column, split_by_time


def test_analyze_detects_id_column():
    df = pd.DataFrame(
        {
            "patient_id": [f"p{i % 5}" for i in range(100)],
            "value": np.random.normal(0, 1, 100),
        }
    )
    result = analyze_split_options(df)
    cols = {c["column"] for c in result["candidate_id_columns"]}
    assert "patient_id" in cols
    assert "value" not in cols  # continuous numeric, not a plausible identifier


def test_analyze_detects_time_column():
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=50, freq="D").astype(str),
            "value": np.random.normal(0, 1, 50),
        }
    )
    result = analyze_split_options(df)
    cols = {c["column"] for c in result["candidate_time_columns"]}
    assert "timestamp" in cols


def test_analyze_only_numeric_columns_no_candidates():
    df = pd.DataFrame({"a": np.random.normal(0, 1, 200), "b": np.random.normal(0, 1, 200)})
    result = analyze_split_options(df)
    assert result["candidate_id_columns"] == []
    assert result["candidate_time_columns"] == []
    assert result["n_rows"] == 200


def test_analyze_handles_empty_dataframe():
    df = pd.DataFrame()
    result = analyze_split_options(df)
    assert result["n_rows"] == 0
    assert result["candidate_id_columns"] == []


def test_analyze_handles_single_row():
    df = pd.DataFrame({"a": [1], "b": ["x"]})
    result = analyze_split_options(df)
    assert result["n_rows"] == 1
    # id-candidate range requires >= 2 unique values -- a single row can
    # never satisfy that, regardless of column content.
    assert result["candidate_id_columns"] == []


def test_analyze_never_crashes_on_garbage_mixed_types():
    df = pd.DataFrame({"weird": [1, "two", None, [1, 2], {"a": 1}]})
    result = analyze_split_options(df)  # must not raise
    assert result["n_rows"] == 5


def test_analyze_ignores_id_column_with_too_high_cardinality():
    # every row unique -> not a plausible grouping column
    df = pd.DataFrame({"row_uuid": [f"id-{i}" for i in range(100)], "value": range(100)})
    result = analyze_split_options(df)
    cols = {c["column"] for c in result["candidate_id_columns"]}
    assert "row_uuid" not in cols


def test_split_by_column():
    df = pd.DataFrame({"patient_id": ["a", "a", "b", "b", "b"], "value": [1, 2, 3, 4, 5]})
    groups = split_by_column(df, "patient_id")
    assert set(groups.keys()) == {"a", "b"}
    assert len(groups["a"]) == 2
    assert len(groups["b"]) == 3
    assert "patient_id" not in groups["a"].columns  # split column dropped from slices


def test_split_by_column_unknown_column_raises():
    df = pd.DataFrame({"a": [1, 2, 3]})
    with pytest.raises(ValueError):
        split_by_column(df, "does_not_exist")


def test_split_by_time_daily():
    df = pd.DataFrame(
        {
            "ts": pd.date_range("2026-01-01", periods=48, freq="h").astype(str),
            "value": range(48),
        }
    )
    groups = split_by_time(df, "ts", "daily")
    assert len(groups) == 2  # 48 hourly rows = 2 calendar days
    assert sum(len(g) for g in groups.values()) == 48


def test_split_by_time_invalid_period_raises():
    df = pd.DataFrame({"ts": pd.date_range("2026-01-01", periods=5).astype(str)})
    with pytest.raises(ValueError):
        split_by_time(df, "ts", "biweekly")
