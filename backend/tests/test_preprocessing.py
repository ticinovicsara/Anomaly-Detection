import numpy as np
import pandas as pd
import pytest
import tempfile
import os
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ml.preprocessing import (
    normalize,
    create_windows,
    window_labels,
    split_by_time,
    load_creditcard,
    load_ecg,
    load_yahoo,
)


class TestNormalize:
    def test_scales_to_0_1(self):
        df = pd.DataFrame({"a": [1.0, 2.0, 3.0], "b": [10.0, 20.0, 30.0]})
        result, _ = normalize(df, ["a", "b"])
        assert result["a"].min() == pytest.approx(0.0)
        assert result["a"].max() == pytest.approx(1.0)
        assert result["b"].min() == pytest.approx(0.0)
        assert result["b"].max() == pytest.approx(1.0)

    def test_does_not_modify_original(self):
        df = pd.DataFrame({"a": [1.0, 2.0, 3.0]})
        original_values = df["a"].tolist()
        normalize(df, ["a"])
        assert df["a"].tolist() == original_values

    def test_untouched_columns_unchanged(self):
        df = pd.DataFrame({"a": [1.0, 2.0, 3.0], "label": [0, 0, 1]})
        result, _ = normalize(df, ["a"])
        assert result["label"].tolist() == [0, 0, 1]

    def test_saves_and_loads_scaler(self):
        df_train = pd.DataFrame({"a": [0.0, 5.0, 10.0]})
        df_pred = pd.DataFrame({"a": [10.0, 20.0]})

        with tempfile.TemporaryDirectory() as tmpdir:
            scaler_path = os.path.join(tmpdir, "scaler.pkl")

            normalize(df_train, ["a"], scaler_path=scaler_path)
            assert Path(scaler_path).exists()

            result, _ = normalize(df_pred, ["a"], scaler_path=scaler_path)
            assert result["a"].iloc[0] == pytest.approx(1.0)
            assert result["a"].iloc[1] == pytest.approx(2.0)

    def test_prediction_uses_training_scale(self):
        df_train = pd.DataFrame({"a": [0.0, 10.0]})
        df_pred = pd.DataFrame({"a": [5.0]})

        with tempfile.TemporaryDirectory() as tmpdir:
            scaler_path = os.path.join(tmpdir, "scaler.pkl")
            normalize(df_train, ["a"], scaler_path=scaler_path)
            result, _ = normalize(df_pred, ["a"], scaler_path=scaler_path)
            assert result["a"].iloc[0] == pytest.approx(0.5)


class TestCreateWindows:
    def test_output_shape_1d(self):
        data = np.arange(100, dtype=float)
        windows = create_windows(data, window_size=10, step=5)
        assert windows.ndim == 3
        assert windows.shape[1] == 10
        assert windows.shape[2] == 1

    def test_output_shape_2d(self):
        data = np.ones((100, 3))
        windows = create_windows(data, window_size=20, step=10)
        assert windows.shape == (9, 20, 3)

    def test_window_count(self):
        data = np.arange(50, dtype=float)
        windows = create_windows(data, window_size=10, step=1)
        assert len(windows) == 41

    def test_first_window_values(self):
        data = np.arange(20, dtype=float).reshape(-1, 1)
        windows = create_windows(data, window_size=5, step=5)
        np.testing.assert_array_equal(windows[0, :, 0], [0, 1, 2, 3, 4])

    def test_second_window_values(self):
        data = np.arange(20, dtype=float).reshape(-1, 1)
        windows = create_windows(data, window_size=5, step=5)
        np.testing.assert_array_equal(windows[1, :, 0], [5, 6, 7, 8, 9])

    def test_data_shorter_than_window_returns_empty(self):
        data = np.arange(5, dtype=float)
        windows = create_windows(data, window_size=10, step=1)
        assert len(windows) == 0


class TestWindowLabels:
    def test_window_labels_follow_max_label(self):
        labels = np.array([0, 0, 1, 0, 0, 1, 0, 0, 0, 0], dtype=int)
        result = window_labels(labels, window_size=5, step=5)
        np.testing.assert_array_equal(result, np.array([1, 1]))

    def test_all_zeros_stays_zero(self):
        labels = np.zeros(20, dtype=int)
        result = window_labels(labels, window_size=5, step=5)
        assert result.sum() == 0

    def test_single_window(self):
        labels = np.array([0, 0, 0, 0, 1], dtype=int)
        result = window_labels(labels, window_size=5, step=5)
        np.testing.assert_array_equal(result, np.array([1]))

    def test_anomaly_at_window_boundary_flags_both(self):
        labels = np.zeros(20, dtype=int)
        labels[4] = 1
        result = window_labels(labels, window_size=5, step=2)
        assert result[0] == 1
        assert result[1] == 1

    def test_output_length_matches_create_windows(self):
        data = np.zeros((100, 3))
        labels = np.zeros(100, dtype=int)
        windows = create_windows(data, window_size=10, step=5)
        win_labels = window_labels(labels, window_size=10, step=5)
        assert len(windows) == len(win_labels)


class TestSplitByTime:
    def test_correct_split_sizes(self):
        df = pd.DataFrame({"x": range(100)})
        train, val, test = split_by_time(df, 0.70, 0.15)
        assert len(train) == 70
        assert len(val) == 15
        assert len(test) == 15

    def test_no_overlap(self):
        df = pd.DataFrame({"x": range(100)})
        train, val, test = split_by_time(df)
        assert len(train) + len(val) + len(test) == 100

    def test_order_preserved(self):
        df = pd.DataFrame({"x": range(100)})
        train, val, test = split_by_time(df)
        assert train["x"].iloc[-1] < val["x"].iloc[0]
        assert val["x"].iloc[-1] < test["x"].iloc[0]

    def test_raises_on_bad_ratios(self):
        df = pd.DataFrame({"x": range(100)})
        with pytest.raises(ValueError):
            split_by_time(df, train_ratio=0.80, val_ratio=0.30)

    def test_custom_ratios(self):
        df = pd.DataFrame({"x": range(200)})
        train, val, test = split_by_time(df, train_ratio=0.60, val_ratio=0.20)
        assert len(train) == 120
        assert len(val) == 40
        assert len(test) == 40


class TestLoadCreditcard:
    def _make_csv(self, tmpdir, rows=200):
        cols = {f"V{i}": np.random.randn(rows) for i in range(1, 29)}
        cols["Time"] = np.arange(rows, dtype=float)
        cols["Amount"] = np.abs(np.random.randn(rows)) * 100
        cols["Class"] = np.zeros(rows, dtype=int)
        df = pd.DataFrame(cols)
        path = os.path.join(tmpdir, "creditcard.csv")
        df.to_csv(path, index=False)
        return path

    def test_drops_time_column(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._make_csv(tmpdir)
            df, _ = load_creditcard(path)
            assert "Time" not in df.columns

    def test_correct_feature_count(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._make_csv(tmpdir)
            _, features = load_creditcard(path)
            assert len(features) == 29

    def test_amount_is_scaled(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._make_csv(tmpdir)
            df, _ = load_creditcard(path)
            assert abs(df["Amount"].mean()) < 0.1

    def test_raises_on_missing_file(self):
        with pytest.raises(FileNotFoundError):
            load_creditcard("/nonexistent/path/creditcard.csv")

    def test_raises_on_missing_columns(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
            path = os.path.join(tmpdir, "bad.csv")
            df.to_csv(path, index=False)
            with pytest.raises(ValueError):
                load_creditcard(path)


class TestLoadEcg:
    def _make_csv(self, tmpdir, with_label=True):
        df = pd.DataFrame({
            "signal_1": np.random.randn(100),
            "signal_2": np.random.randn(100),
        })
        if with_label:
            df["label"] = 0
        path = os.path.join(tmpdir, "ecg.csv")
        df.to_csv(path, index=False)
        return path

    def test_feature_cols_exclude_label(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._make_csv(tmpdir)
            _, features = load_ecg(path)
            assert "label" not in features
            assert "signal_1" in features

    def test_adds_label_col_if_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._make_csv(tmpdir, with_label=False)
            df, _ = load_ecg(path)
            assert "label" in df.columns
            assert df["label"].sum() == 0

    def test_raises_on_missing_file(self):
        with pytest.raises(FileNotFoundError):
            load_ecg("/nonexistent/ecg.csv")

    def test_custom_label_col(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            df = pd.DataFrame({"signal": [1.0, 2.0], "anomaly": [0, 1]})
            path = os.path.join(tmpdir, "ecg.csv")
            df.to_csv(path, index=False)
            _, features = load_ecg(path, label_col="anomaly")
            assert "anomaly" not in features
            assert "signal" in features


class TestLoadCreditcardAmountScaler:
    def _make_csv(self, tmpdir, rows=100, amount_mean=50.0):
        cols = {f"V{i}": np.zeros(rows) for i in range(1, 29)}
        cols["Time"] = np.arange(rows, dtype=float)
        cols["Amount"] = np.full(rows, amount_mean)
        cols["Class"] = np.zeros(rows, dtype=int)
        df = pd.DataFrame(cols)
        path = os.path.join(tmpdir, "cc.csv")
        df.to_csv(path, index=False)
        return path

    def test_amount_scaler_is_saved(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = self._make_csv(tmpdir)
            scaler_path = os.path.join(tmpdir, "amount_scaler.pkl")
            load_creditcard(csv_path, amount_scaler_path=scaler_path)
            assert Path(scaler_path).exists()

    def test_saved_scaler_is_loaded_on_second_call(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_train = self._make_csv(tmpdir, rows=100, amount_mean=50.0)
            scaler_path = os.path.join(tmpdir, "amount_scaler.pkl")
            df_train, _ = load_creditcard(csv_train, amount_scaler_path=scaler_path)
            train_mean = df_train["Amount"].mean()

            csv_pred = self._make_csv(tmpdir, rows=20, amount_mean=50.0)
            df_pred, _ = load_creditcard(csv_pred, amount_scaler_path=scaler_path)

            assert df_pred["Amount"].mean() == pytest.approx(train_mean, abs=1e-6)

    def test_prediction_uses_training_stats_not_own(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_train = self._make_csv(tmpdir, rows=100, amount_mean=0.0)
            scaler_path = os.path.join(tmpdir, "amount_scaler.pkl")
            load_creditcard(csv_train, amount_scaler_path=scaler_path)

            csv_pred = self._make_csv(tmpdir, rows=20, amount_mean=999.0)
            df_pred, _ = load_creditcard(csv_pred, amount_scaler_path=scaler_path)

            assert df_pred["Amount"].mean() > 1.0


class TestLoadYahoo:
    def _make_csv(self, tmpdir, with_label=True, with_timestamp=True, with_changepoint=True):
        n = 50
        data: dict = {"value": np.random.randn(n)}
        if with_timestamp:
            data["timestamps"] = np.arange(n)
        if with_changepoint:
            data["changepoint"] = np.zeros(n, dtype=int)
        if with_label:
            data["is_anomaly"] = np.zeros(n, dtype=int)
        df = pd.DataFrame(data)
        path = os.path.join(tmpdir, "yahoo.csv")
        df.to_csv(path, index=False)
        return path

    def test_feature_cols_exclude_label(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._make_csv(tmpdir)
            _, features = load_yahoo(path)
            assert "is_anomaly" not in features
            assert "value" in features

    def test_timestamp_column_is_dropped(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._make_csv(tmpdir)
            df, _ = load_yahoo(path)
            assert "timestamps" not in df.columns

    def test_changepoint_column_is_dropped(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._make_csv(tmpdir)
            df, _ = load_yahoo(path)
            assert "changepoint" not in df.columns

    def test_missing_label_gets_zero_filled(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._make_csv(tmpdir, with_label=False)
            df, _ = load_yahoo(path)
            assert "is_anomaly" in df.columns
            assert df["is_anomaly"].sum() == 0

    def test_raises_on_missing_file(self):
        with pytest.raises(FileNotFoundError):
            load_yahoo("/nonexistent/yahoo.csv")
