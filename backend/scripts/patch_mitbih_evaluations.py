#!/usr/bin/env python3
"""One-off patch for Subjects imported by import_mitbih_subjects.py: fills in
the full evaluation dict (confusion, curve, n_test_samples/positive, epsilon)
on each existing Model row's metrics_json, in place.

Why this exists separately from import_mitbih_subjects.py: that script
deletes and recreates each Subject from scratch, which is more disruptive
than needed for what's really just a metrics_json backfill, and would also
wipe out any Predictions/Anomalies accumulated against those Subjects since
the original import. This script only UPDATEs existing Model rows.

No retraining happens here -- it reloads the already-trained artifacts
(model_path/scaler_path already on the Model row) and re-scores the same
deterministic temporal test split _fit_and_calibrate() used originally.

Usage:
    python scripts/patch_mitbih_evaluations.py [--dry-run]
"""
import argparse
import logging
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db.models import Subject  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.ml_core.evaluation import coerce_binary_label, evaluate_on_test  # noqa: E402
from app.ml_core.preprocessing import load_scaler, numeric_only, temporal_split  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("patch_mitbih_evaluations")

RECORD_ID_RE = re.compile(r"^MIT-BIH (\d+)$")


def _recompute_evaluation(dataset_file_path: str, model_path: str, scaler_path: str, epsilon: float):
    import pandas as pd
    from app.ml_core.models.lstm_autoencoder import LSTMAutoencoder

    df = pd.read_csv(dataset_file_path)
    label_series = coerce_binary_label(df["label"])
    df = numeric_only(df.drop(columns=["label"]))
    label_series = label_series.reindex(df.index)
    _train_df, _val_df, test_df, _train_lbl, _val_lbl, test_lbl = temporal_split(df, labels=label_series)

    model = LSTMAutoencoder(window_size=50, n_features=df.shape[1])
    model.load(model_path)
    scaler = load_scaler(scaler_path)

    return evaluate_on_test(model, "LSTM", test_df, test_lbl, scaler, epsilon)


def run(dry_run: bool) -> None:
    db = SessionLocal()
    subjects = db.query(Subject).filter(Subject.source_hint == "curated:mitbih").order_by(Subject.id).all()
    logger.info("Found %d curated:mitbih Subjects", len(subjects))

    patched, skipped = 0, 0
    for subject in subjects:
        match = RECORD_ID_RE.match(subject.name)
        record_id = match.group(1) if match else subject.name

        model_row = next((m for m in subject.models if m.is_active), None)
        if model_row is None:
            logger.warning("subject %s (%s): no active model, skipping", subject.id, subject.name)
            skipped += 1
            continue
        if not (model_row.model_path and model_row.scaler_path and os.path.isfile(model_row.model_path) and os.path.isfile(model_row.scaler_path)):
            logger.warning("subject %s (%s): missing model/scaler artifact on disk, skipping", subject.id, subject.name)
            skipped += 1
            continue
        if model_row.threshold is None:
            logger.warning("subject %s (%s): no threshold, skipping", subject.id, subject.name)
            skipped += 1
            continue

        dataset = next((d for d in subject.datasets if d.label_column), None)
        if dataset is None or not os.path.isfile(dataset.file_path):
            logger.warning("subject %s (%s): no labeled dataset file on disk, skipping", subject.id, subject.name)
            skipped += 1
            continue

        try:
            evaluation = _recompute_evaluation(
                dataset.file_path, model_row.model_path, model_row.scaler_path, model_row.threshold.epsilon
            )
        except Exception:
            logger.exception("record %s: recompute failed, leaving existing metrics_json untouched", record_id)
            skipped += 1
            continue

        if evaluation is None:
            logger.warning("record %s: evaluate_on_test returned None, leaving existing metrics_json untouched", record_id)
            skipped += 1
            continue

        old = (model_row.metrics_json or {}).get("evaluation") or {}
        logger.info(
            "record %s: f1 %.4f -> %.4f, n_test_samples %s -> %s",
            record_id, old.get("f1") or 0.0, evaluation["f1"], old.get("n_test_samples"), evaluation["n_test_samples"],
        )

        if not dry_run:
            model_row.metrics_json = {**(model_row.metrics_json or {}), "evaluation": evaluation}
            db.add(model_row)
            db.commit()
        patched += 1

    db.close()
    logger.info("%s %d/%d Subjects (%d skipped)", "Would patch" if dry_run else "Patched", patched, len(subjects), skipped)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="Recompute and log but don't write to the DB")
    args = parser.parse_args()
    run(args.dry_run)


if __name__ == "__main__":
    main()
