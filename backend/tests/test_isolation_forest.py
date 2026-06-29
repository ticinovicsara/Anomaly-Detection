import numpy as np
import pytest
import tempfile
import os
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ml.isolation_forest import train, predict, evaluate, calibrate_threshold


def make_normal(n=200, seed=0):
    rng = np.random.default_rng(seed)
    return rng.normal(loc=0.0, scale=1.0, size=(n, 4))


def make_anomalies(n=20, seed=1):
    rng = np.random.default_rng(seed)
    return rng.normal(loc=10.0, scale=0.5, size=(n, 4))


class TestTrain:
    def test_returns_model_and_time(self):
        X = make_normal()
        model, elapsed = train(X)
        assert model is not None
        assert elapsed >= 0.0

    def test_saves_model_to_disk(self):
        X = make_normal()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "iforest.pkl")
            train(X, save_path=path)
            assert Path(path).exists()

    def test_creates_parent_dirs(self):
        X = make_normal()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "subdir", "model.pkl")
            train(X, save_path=path)
            assert Path(path).exists()

    def test_contamination_respected(self):
        X = make_normal()
        model, _ = train(X, contamination=0.1)
        preds = model.predict(X)
        anomaly_rate = (preds == -1).mean()
        assert abs(anomaly_rate - 0.1) < 0.05


class TestPredict:
    def test_output_is_binary(self):
        X_train = make_normal()
        X_test = np.vstack([make_normal(50), make_anomalies(10)])

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "model.pkl")
            train(X_train, save_path=path)
            preds = predict(X_test, path)

        assert set(np.unique(preds)).issubset({0, 1})

    def test_anomalies_flagged(self):
        X_train = make_normal(300)
        X_anomaly = make_anomalies(50)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "model.pkl")
            train(X_train, contamination=0.05, save_path=path)
            preds = predict(X_anomaly, path)

        assert preds.mean() > 0.5

    def test_output_shape(self):
        X_train = make_normal()
        X_test = make_normal(30)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "model.pkl")
            train(X_train, save_path=path)
            preds = predict(X_test, path)

        assert preds.shape == (30,)


class TestEvaluate:
    def test_returns_all_keys(self):
        y_true = np.array([0, 0, 1, 1, 0, 1])
        y_pred = np.array([0, 0, 1, 1, 0, 0])
        result = evaluate(y_true, y_pred)
        assert set(result.keys()) == {"precision", "recall", "f1", "roc_auc"}

    def test_perfect_predictions(self):
        y_true = np.array([0, 0, 1, 1])
        y_pred = np.array([0, 0, 1, 1])
        result = evaluate(y_true, y_pred)
        assert result["precision"] == 1.0
        assert result["recall"] == 1.0
        assert result["f1"] == 1.0
        assert result["roc_auc"] == 1.0

    def test_values_rounded_to_4_decimals(self):
        y_true = np.array([0, 1, 0, 1, 0, 1])
        y_pred = np.array([0, 1, 1, 0, 0, 1])
        result = evaluate(y_true, y_pred)
        for v in result.values():
            assert v == round(v, 4)

    def test_all_wrong_no_crash(self):
        y_true = np.array([1, 1, 1])
        y_pred = np.array([0, 0, 0])
        result = evaluate(y_true, y_pred)
        assert result["precision"] == 0.0
        assert result["recall"] == 0.0


class TestCalibrateThreshold:
    def test_returns_three_values(self):
        X = make_normal()
        model, _ = train(X)
        threshold, mean, std = calibrate_threshold(model, X)
        assert isinstance(threshold, float)
        assert isinstance(mean, float)
        assert isinstance(std, float)

    def test_threshold_equals_mean_plus_3std(self):
        X = make_normal()
        model, _ = train(X)
        threshold, mean, std = calibrate_threshold(model, X, sigma=3)
        assert threshold == pytest.approx(mean + 3 * std, rel=1e-6)

    def test_custom_sigma(self):
        X = make_normal()
        model, _ = train(X)
        t2, m, s = calibrate_threshold(model, X, sigma=2)
        t3, _, _ = calibrate_threshold(model, X, sigma=3)
        assert t3 > t2

    def test_anomalies_score_above_threshold(self):
        X_train = make_normal(500)
        X_val = make_normal(100)
        X_anomaly = make_anomalies(50)

        model, _ = train(X_train, contamination=0.01)
        threshold, _, _ = calibrate_threshold(model, X_val)

        anomaly_scores = -model.score_samples(X_anomaly)
        assert (anomaly_scores > threshold).mean() > 0.8
