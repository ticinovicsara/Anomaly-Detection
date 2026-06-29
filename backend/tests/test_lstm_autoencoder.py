import numpy as np
import pytest
import tempfile
import os
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ml.lstm_autoencoder import (
    build_model,
    train,
    get_reconstruction_error,
    calibrate_threshold,
    predict,
    evaluate,
)


def make_windows(n=100, window_size=10, n_features=2, seed=0):
    rng = np.random.default_rng(seed)
    return rng.normal(size=(n, window_size, n_features)).astype(np.float32)


def make_anomaly_windows(n=20, window_size=10, n_features=2, seed=1):
    rng = np.random.default_rng(seed)
    return (rng.normal(size=(n, window_size, n_features)) + 5.0).astype(np.float32)


class TestBuildModel:
    def test_returns_compiled_model(self):
        model = build_model(window_size=10, n_features=2)
        assert model is not None

    def test_output_shape(self):
        model = build_model(window_size=10, n_features=2)
        X = make_windows(5, 10, 2)
        out = model.predict(X, verbose=0)
        assert out.shape == (5, 10, 2)

    def test_custom_dimensions(self):
        model = build_model(window_size=20, n_features=3)
        X = make_windows(4, 20, 3)
        out = model.predict(X, verbose=0)
        assert out.shape == (4, 20, 3)


class TestTrain:
    def test_returns_model_and_history(self):
        model = build_model(window_size=10, n_features=2)
        X = make_windows(60, 10, 2)
        trained, history = train(model, X[:50], X[50:], epochs=2, batch_size=16)
        assert trained is not None
        assert "loss" in history
        assert "val_loss" in history

    def test_history_has_entries(self):
        model = build_model(window_size=10, n_features=2)
        X = make_windows(60, 10, 2)
        _, history = train(model, X[:50], X[50:], epochs=3, batch_size=16)
        assert len(history["loss"]) >= 1

    def test_saves_model(self):
        model = build_model(window_size=10, n_features=2)
        X = make_windows(60, 10, 2)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "model.keras")
            train(model, X[:50], X[50:], epochs=2, batch_size=16, save_path=path)
            assert Path(path).exists()

    def test_early_stopping_does_not_crash(self):
        model = build_model(window_size=10, n_features=2)
        X = make_windows(60, 10, 2)
        _, history = train(model, X[:50], X[50:], epochs=50, batch_size=16)
        assert len(history["loss"]) <= 50


class TestGetReconstructionError:
    def test_output_shape(self):
        model = build_model(window_size=10, n_features=2)
        X = make_windows(30, 10, 2)
        errors = get_reconstruction_error(model, X)
        assert errors.shape == (30,)

    def test_errors_are_nonnegative(self):
        model = build_model(window_size=10, n_features=2)
        X = make_windows(20, 10, 2)
        errors = get_reconstruction_error(model, X)
        assert (errors >= 0).all()

    def test_trained_model_lower_error_on_normal(self):
        model = build_model(window_size=10, n_features=1)
        X_normal = make_windows(80, 10, 1)
        X_anomaly = make_anomaly_windows(20, 10, 1)

        train(model, X_normal[:60], X_normal[60:], epochs=5, batch_size=16)

        normal_errors = get_reconstruction_error(model, X_normal[60:])
        anomaly_errors = get_reconstruction_error(model, X_anomaly)
        assert normal_errors.mean() < anomaly_errors.mean()


class TestCalibrateThreshold:
    def test_returns_three_floats(self):
        model = build_model(window_size=10, n_features=2)
        X = make_windows(30, 10, 2)
        t, m, s = calibrate_threshold(model, X)
        assert all(isinstance(v, float) for v in (t, m, s))

    def test_threshold_equals_mean_plus_3std(self):
        model = build_model(window_size=10, n_features=2)
        X = make_windows(30, 10, 2)
        t, m, s = calibrate_threshold(model, X, sigma=3)
        assert t == pytest.approx(m + 3 * s, rel=1e-6)

    def test_higher_sigma_gives_higher_threshold(self):
        model = build_model(window_size=10, n_features=2)
        X = make_windows(30, 10, 2)
        t2, _, _ = calibrate_threshold(model, X, sigma=2)
        t3, _, _ = calibrate_threshold(model, X, sigma=3)
        assert t3 > t2


class TestPredict:
    def test_output_shapes(self):
        model = build_model(window_size=10, n_features=2)
        X = make_windows(20, 10, 2)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "model.keras")
            model.save(path)
            preds, errors = predict(X, path, threshold=1.0)
        assert preds.shape == (20,)
        assert errors.shape == (20,)

    def test_predictions_are_binary(self):
        model = build_model(window_size=10, n_features=2)
        X = make_windows(20, 10, 2)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "model.keras")
            model.save(path)
            preds, _ = predict(X, path, threshold=0.5)
        assert set(np.unique(preds)).issubset({0, 1})

    def test_zero_threshold_flags_everything(self):
        model = build_model(window_size=10, n_features=2)
        X = make_windows(10, 10, 2)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "model.keras")
            model.save(path)
            preds, _ = predict(X, path, threshold=0.0)
        assert preds.sum() == len(X)

    def test_huge_threshold_flags_nothing(self):
        model = build_model(window_size=10, n_features=2)
        X = make_windows(10, 10, 2)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "model.keras")
            model.save(path)
            preds, _ = predict(X, path, threshold=999.0)
        assert preds.sum() == 0


class TestEvaluate:
    def test_returns_all_keys(self):
        y_true = np.array([0, 1, 0, 1])
        y_pred = np.array([0, 1, 0, 1])
        errors = np.array([0.1, 0.9, 0.2, 0.8])
        result = evaluate(y_true, y_pred, errors)
        assert set(result.keys()) == {"precision", "recall", "f1", "roc_auc"}

    def test_perfect_predictions(self):
        y_true = np.array([0, 0, 1, 1])
        y_pred = np.array([0, 0, 1, 1])
        errors = np.array([0.1, 0.2, 0.9, 0.8])
        result = evaluate(y_true, y_pred, errors)
        assert result["f1"] == 1.0
        assert result["roc_auc"] == 1.0

    def test_roc_auc_uses_errors_not_preds(self):
        y_true = np.array([0, 0, 1, 1])
        y_pred = np.array([0, 0, 0, 0])
        errors_good = np.array([0.1, 0.1, 0.9, 0.9])
        errors_bad  = np.array([0.5, 0.5, 0.5, 0.5])
        r_good = evaluate(y_true, y_pred, errors_good)
        r_bad  = evaluate(y_true, y_pred, errors_bad)
        assert r_good["roc_auc"] > r_bad["roc_auc"]

    def test_values_rounded_to_4_decimals(self):
        y_true = np.array([0, 1, 0, 1, 0])
        y_pred = np.array([0, 1, 1, 0, 0])
        errors = np.array([0.1, 0.8, 0.6, 0.3, 0.2])
        result = evaluate(y_true, y_pred, errors)
        for v in result.values():
            assert v == round(v, 4)
