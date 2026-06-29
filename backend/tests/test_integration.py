import numpy as np
import pandas as pd
import pytest
import tempfile
import os
from pathlib import Path

from app.ml import preprocessing, isolation_forest, lstm_autoencoder


def _make_ecg_csv(tmpdir, rows=500, n_signals=3, anomaly_rate=0.05):
    rng = np.random.default_rng(42)
    data = {f"signal_{i}": rng.standard_normal(rows) for i in range(n_signals)}
    labels = (rng.random(rows) < anomaly_rate).astype(int)
    data["label"] = labels
    df = pd.DataFrame(data)
    path = os.path.join(tmpdir, "ecg.csv")
    df.to_csv(path, index=False)
    return path


class TestIsolationForestPipeline:
    def test_full_pipeline_produces_valid_predictions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = _make_ecg_csv(tmpdir)
            df, feature_cols = preprocessing.load_ecg(csv_path)
            train_df, val_df, test_df = preprocessing.split_by_time(df)

            scaler_path = os.path.join(tmpdir, "scaler.pkl")
            train_df, _ = preprocessing.normalize(train_df, feature_cols, scaler_path=scaler_path)
            val_df, _ = preprocessing.normalize(val_df, feature_cols, scaler_path=scaler_path)
            test_df, _ = preprocessing.normalize(test_df, feature_cols, scaler_path=scaler_path)

            X_train = train_df[feature_cols].values
            X_val = val_df[feature_cols].values
            X_test = test_df[feature_cols].values

            model_path = os.path.join(tmpdir, "iforest.pkl")
            model, elapsed = isolation_forest.train(X_train, contamination=0.05, save_path=model_path)
            assert Path(model_path).exists()
            assert elapsed > 0

            threshold, mean_err, std_err = isolation_forest.calibrate_threshold(model, X_val)
            assert threshold > mean_err

            raw = model.predict(X_test)
            predictions = np.where(raw == -1, 1, 0)
            scores = -model.score_samples(X_test)

            assert predictions.shape == (len(X_test),)
            assert scores.shape == (len(X_test),)
            assert set(np.unique(predictions)).issubset({0, 1})

    def test_evaluate_returns_expected_keys(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = _make_ecg_csv(tmpdir, rows=300)
            df, feature_cols = preprocessing.load_ecg(csv_path)
            train_df, val_df, test_df = preprocessing.split_by_time(df)

            scaler_path = os.path.join(tmpdir, "scaler.pkl")
            train_df, _ = preprocessing.normalize(train_df, feature_cols, scaler_path=scaler_path)
            val_df, _ = preprocessing.normalize(val_df, feature_cols, scaler_path=scaler_path)
            test_df, _ = preprocessing.normalize(test_df, feature_cols, scaler_path=scaler_path)

            model, _ = isolation_forest.train(train_df[feature_cols].values, contamination=0.05)
            isolation_forest.calibrate_threshold(model, val_df[feature_cols].values)

            X_test = test_df[feature_cols].values
            raw = model.predict(X_test)
            y_pred = np.where(raw == -1, 1, 0)
            y_true = test_df["label"].to_numpy()

            metrics = isolation_forest.evaluate(y_true, y_pred)
            assert set(metrics.keys()) == {"precision", "recall", "f1", "roc_auc"}


class TestLSTMAutoencoderPipeline:
    def test_full_pipeline_produces_valid_predictions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = _make_ecg_csv(tmpdir, rows=400, n_signals=2)
            df, feature_cols = preprocessing.load_ecg(csv_path)
            train_df, val_df, test_df = preprocessing.split_by_time(df)

            scaler_path = os.path.join(tmpdir, "scaler.pkl")
            train_df, _ = preprocessing.normalize(train_df, feature_cols, scaler_path=scaler_path)
            val_df, _ = preprocessing.normalize(val_df, feature_cols, scaler_path=scaler_path)
            test_df, _ = preprocessing.normalize(test_df, feature_cols, scaler_path=scaler_path)

            WINDOW_SIZE = 10
            STEP = 5

            X_train = preprocessing.create_windows(train_df[feature_cols].values, WINDOW_SIZE, STEP)
            X_val = preprocessing.create_windows(val_df[feature_cols].values, WINDOW_SIZE, STEP)
            X_test = preprocessing.create_windows(test_df[feature_cols].values, WINDOW_SIZE, STEP)

            assert len(X_train) > 0
            assert X_train.shape[1] == WINDOW_SIZE
            assert X_train.shape[2] == len(feature_cols)

            model_path = os.path.join(tmpdir, "lstm.keras")
            model = lstm_autoencoder.build_model(window_size=WINDOW_SIZE, n_features=len(feature_cols))
            model, history = lstm_autoencoder.train(
                model, X_train, X_val, epochs=2, batch_size=16, save_path=model_path
            )
            assert Path(model_path).exists()
            assert "loss" in history

            threshold, mean_err, std_err = lstm_autoencoder.calibrate_threshold(model, X_val)
            assert threshold == pytest.approx(mean_err + 3 * std_err, rel=1e-5)

            predictions, errors = lstm_autoencoder.predict(X_test, model_path, threshold)
            assert predictions.shape == (len(X_test),)
            assert errors.shape == (len(X_test),)
            assert set(np.unique(predictions)).issubset({0, 1})

    def test_window_labels_aligns_with_windows(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = _make_ecg_csv(tmpdir, rows=300, n_signals=2)
            df, feature_cols = preprocessing.load_ecg(csv_path)
            _, _, test_df = preprocessing.split_by_time(df)

            WINDOW_SIZE = 10
            STEP = 5

            scaler_path = os.path.join(tmpdir, "scaler.pkl")
            preprocessing.normalize(df, feature_cols, scaler_path=scaler_path)
            test_df, _ = preprocessing.normalize(test_df, feature_cols, scaler_path=scaler_path)

            X_test = preprocessing.create_windows(test_df[feature_cols].values, WINDOW_SIZE, STEP)
            y_test = preprocessing.window_labels(test_df["label"].to_numpy(), WINDOW_SIZE, STEP)

            assert len(X_test) == len(y_test)
