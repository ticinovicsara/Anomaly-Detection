"""Tests for evaluation on the held-out test split (F1/precision/recall/
AU-ROC) -- app/services/training.py's _fit_and_calibrate, exercised
directly (pure function, no DB) with tmp_path for on-disk artifacts."""
import numpy as np
import pandas as pd
import pytest

from app.services.training import _fit_and_calibrate


def _separable_labeled_df(n_normal=850, n_test=150, seed=0):
    """Train/val portions are entirely normal (as production data would
    be); the test portion alternates normal rows with rows shifted far
    away, so the trained model should separate them cleanly at the
    calibrated threshold."""
    rng = np.random.default_rng(seed)
    normal = rng.normal(0, 1, n_normal)
    test_values = np.empty(n_test)
    test_labels = np.zeros(n_test, dtype=int)
    for i in range(n_test):
        if i % 2 == 0:
            test_values[i] = rng.normal(20, 1)
            test_labels[i] = 1
        else:
            test_values[i] = rng.normal(0, 1)
    values = np.concatenate([normal, test_values])
    labels = np.concatenate([np.zeros(n_normal, dtype=int), test_labels])
    return pd.DataFrame({"value": values, "label": labels})


def test_if_evaluation_on_separable_labeled_data_is_near_perfect(tmp_path):
    df = _separable_labeled_df()
    fit = _fit_and_calibrate(df, "IF", str(tmp_path / "m"), label_column="label")
    ev = fit["evaluation"]
    assert ev is not None
    assert ev["f1"] > 0.9
    assert ev["auc"] is not None and ev["auc"] > 0.9
    assert ev["n_test_positive"] == 75


def test_evaluation_confusion_matrix_matches_precision_recall(tmp_path):
    df = _separable_labeled_df()
    fit = _fit_and_calibrate(df, "IF", str(tmp_path / "m"), label_column="label")
    ev = fit["evaluation"]
    conf = ev["confusion"]
    assert conf["tp"] + conf["fp"] + conf["tn"] + conf["fn"] == ev["n_test_samples"]
    assert conf["tp"] + conf["fn"] == ev["n_test_positive"]
    recomputed_precision = conf["tp"] / (conf["tp"] + conf["fp"]) if (conf["tp"] + conf["fp"]) else 0.0
    recomputed_recall = conf["tp"] / (conf["tp"] + conf["fn"]) if (conf["tp"] + conf["fn"]) else 0.0
    assert recomputed_precision == pytest.approx(ev["precision"])
    assert recomputed_recall == pytest.approx(ev["recall"])
    assert ev["epsilon"] is not None


def test_evaluation_curve_has_one_point_per_test_sample_when_under_cap(tmp_path):
    df = _separable_labeled_df()
    fit = _fit_and_calibrate(df, "IF", str(tmp_path / "m"), label_column="label")
    ev = fit["evaluation"]
    assert len(ev["curve"]) == ev["n_test_samples"]
    first = ev["curve"][0]
    assert set(first.keys()) == {"i", "score", "actual", "predicted"}


def test_evaluation_curve_is_capped_and_downsampled_for_large_test_sets(tmp_path):
    df = _separable_labeled_df(n_normal=8500, n_test=1500)
    fit = _fit_and_calibrate(df, "IF", str(tmp_path / "m"), label_column="label")
    ev = fit["evaluation"]
    assert ev["n_test_samples"] == 1500
    assert len(ev["curve"]) <= 500


def test_evaluation_is_none_without_label_column(tmp_path):
    df = _separable_labeled_df()
    fit = _fit_and_calibrate(df, "IF", str(tmp_path / "m"), label_column=None)
    assert fit["evaluation"] is None


def test_evaluation_is_none_for_unknown_label_column(tmp_path):
    df = pd.DataFrame({"value": np.random.default_rng(1).normal(0, 1, 200)})
    fit = _fit_and_calibrate(df, "IF", str(tmp_path / "m"), label_column="does_not_exist")
    assert fit["evaluation"] is None


def test_evaluation_is_none_for_non_binary_label_column(tmp_path):
    rng = np.random.default_rng(2)
    df = pd.DataFrame({"value": rng.normal(0, 1, 200), "category": [i % 3 for i in range(200)]})
    fit = _fit_and_calibrate(df, "IF", str(tmp_path / "m"), label_column="category")
    assert fit["evaluation"] is None


def test_lstm_evaluation_separates_injected_anomalous_block(tmp_path):
    """840 train / 180 val / 180 test, all normal N(0,1) except the last
    60 test rows which are shifted far away -- windows overlapping that
    block should score much higher than the calibrated epsilon."""
    rng = np.random.default_rng(3)
    n_train, n_val, n_test = 840, 180, 180
    train = rng.normal(0, 1, n_train)
    val = rng.normal(0, 1, n_val)
    test = rng.normal(0, 1, n_test)
    test[-60:] = rng.normal(15, 1, 60)
    labels = np.zeros(n_train + n_val + n_test, dtype=int)
    labels[-60:] = 1
    df = pd.DataFrame({"value": np.concatenate([train, val, test]), "label": labels})

    fit = _fit_and_calibrate(df, "LSTM", str(tmp_path / "m"), label_column="label")
    ev = fit["evaluation"]
    assert ev is not None
    assert ev["n_test_positive"] > 0
    assert ev["auc"] is not None and ev["auc"] > 0.7
