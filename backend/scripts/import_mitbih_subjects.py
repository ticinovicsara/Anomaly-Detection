#!/usr/bin/env python3
"""Ch. 7.4 follow-up: import the 48 already-trained MIT-BIH models
(scripts/mitbih_evaluation.py) into the app DB as real Subjects, so
services/experiments.py::run_personalization_experiment() can compute the
cross-application FP/miss table -- the one number still missing from ch. 7.4.

No retraining happens here. Every record was already fit by
_fit_and_calibrate() when mitbih_evaluation.py ran, which means the trained
model + scaler already exist on disk under results/_mitbih_artifacts/. This
script only writes the DB rows (Subject/Dataset/Model/Threshold) that point
at those existing files, then re-uses them.

Standalone research script, not imported by the app.

Usage:
    python scripts/import_mitbih_subjects.py \
        --data-dir ../../_datasets/mitdb \
        --results-csv results/mitbih_evaluation.csv \
        --user-email user@gmail.com
"""
import argparse
import csv
import logging
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db.models import Dataset, Model, Subject, Threshold, User  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.services.experiments import run_personalization_experiment  # noqa: E402
from scripts.mitbih_evaluation import _load_labeled_record  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("import_mitbih_subjects")


def _read_results(results_csv: str) -> dict:
    with open(results_csv, newline="") as f:
        return {row["record"]: row for row in csv.DictReader(f)}


def run(data_dir: str, results_csv: str, artifacts_dir: str, datasets_dir: str, user_email: str) -> None:
    rows = _read_results(results_csv)
    os.makedirs(datasets_dir, exist_ok=True)

    db = SessionLocal()
    user = db.query(User).filter_by(email=user_email).first()
    if not user:
        raise ValueError(f"User {user_email!r} not found -- create the account first")

    subject_ids = []
    for record_id, row in rows.items():
        model_path = os.path.abspath(os.path.join(artifacts_dir, f"record_{record_id}.keras"))
        scaler_path = os.path.abspath(os.path.join(artifacts_dir, f"record_{record_id}_scaler.pkl"))
        if not (os.path.isfile(model_path) and os.path.isfile(scaler_path)):
            logger.warning("record %s: missing trained artifacts, skipping", record_id)
            continue
        if row["mu"] in (None, "", "None") or row["epsilon"] in (None, "", "None"):
            logger.warning("record %s: no threshold in results CSV, skipping", record_id)
            continue

        name = f"MIT-BIH {record_id}"
        existing = db.query(Subject).filter_by(user_id=user.id, name=name).first()
        if existing:
            db.delete(existing)
            db.commit()

        subject = Subject(
            user_id=user.id,
            name=name,
            description=(
                "MIT-BIH Arrhythmia Database record, imported for the ch. 7.4 "
                "cross-application FP/miss experiment. Model was already trained by "
                "scripts/mitbih_evaluation.py -- this row only re-registers the "
                "existing artifact, no retraining."
            ),
            source_hint="curated:mitbih",
        )
        db.add(subject)
        db.commit()
        db.refresh(subject)

        df = _load_labeled_record(data_dir, record_id)
        file_path = os.path.abspath(os.path.join(datasets_dir, f"record_{record_id}.csv"))
        df.to_csv(file_path, index=False)

        dataset = Dataset(
            user_id=user.id,
            subject_id=subject.id,
            name=name,
            detected_type="mitbih_ecg",
            file_path=file_path,
            n_rows=len(df),
            n_features=1,  # only `signal`; `label` is excluded via label_column below
            label_column="label",
        )
        db.add(dataset)
        db.commit()
        db.refresh(dataset)

        model_row = Model(
            user_id=user.id,
            subject_id=subject.id,
            dataset_id=dataset.id,
            algorithm="LSTM",
            selection_reason=(
                "Fixed to LSTM Autoencoder for every MIT-BIH record (ch. 7.4 methodology) "
                "so epsilon is the only variable across patients -- router intentionally "
                "bypassed for this controlled experiment."
            ),
            selection_mode="manual",
            is_active=True,
            status="ready",
            model_path=model_path,
            scaler_path=scaler_path,
            trained_at=datetime.utcnow(),
            metrics_json={
                "evaluation": {
                    "precision": float(row["precision"]) if row["precision"] not in (None, "", "None") else None,
                    "recall": float(row["recall"]) if row["recall"] not in (None, "", "None") else None,
                    "f1": float(row["f1"]) if row["f1"] not in (None, "", "None") else None,
                    "auc": float(row["auc"]) if row["auc"] not in (None, "", "None") else None,
                }
            },
        )
        db.add(model_row)
        db.commit()
        db.refresh(model_row)

        db.add(
            Threshold(
                model_id=model_row.id,
                mu=float(row["mu"]),
                sigma=float(row["sigma"]),
                epsilon=float(row["epsilon"]),
                z_multiplier=3.0,
            )
        )
        db.commit()

        subject_ids.append(subject.id)
        logger.info("record %s -> subject %s imported", record_id, subject.id)

    logger.info("Imported %d/%d records as real Subjects", len(subject_ids), len(rows))

    if len(subject_ids) < 2:
        logger.error("Fewer than 2 subjects imported, cannot run the experiment")
        db.close()
        return

    result = run_personalization_experiment(subject_ids, db, user.id)
    db.close()

    stats = result["statistics"]
    logger.info(
        "epsilon: min=%.4f max=%.4f mean=%.4f std=%.4f range_ratio=%s",
        stats["min"], stats["max"], stats["mean"], stats["std"],
        f"{stats['range_ratio']:.2f}x" if stats["range_ratio"] else "n/a",
    )
    fp = result["cross_application"]["fp_rate_at_global"]
    miss = result["cross_application"]["miss_rate_at_global"]
    fp_vals = [v for v in fp.values() if v is not None]
    miss_vals = [v for v in miss.values() if v is not None]
    if fp_vals:
        logger.info("FP rate at global epsilon: mean=%.3f max=%.3f (n=%d)", sum(fp_vals) / len(fp_vals), max(fp_vals), len(fp_vals))
    if miss_vals:
        logger.info("Miss rate at global epsilon: mean=%.3f max=%.3f (n=%d)", sum(miss_vals) / len(miss_vals), max(miss_vals), len(miss_vals))

    import json
    out_path = os.path.join(os.path.dirname(results_csv) or ".", "mitbih_personalization_experiment.json")
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    logger.info("Full result written to %s", out_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", required=True, help="Directory containing MIT-BIH .dat/.hea/.atr files")
    parser.add_argument("--results-csv", default="results/mitbih_evaluation.csv")
    parser.add_argument("--artifacts-dir", default="results/_mitbih_artifacts")
    parser.add_argument("--datasets-dir", default="results/_mitbih_datasets")
    parser.add_argument("--user-email", default="user@gmail.com")
    args = parser.parse_args()

    run(args.data_dir, args.results_csv, args.artifacts_dir, args.datasets_dir, args.user_email)


if __name__ == "__main__":
    main()
