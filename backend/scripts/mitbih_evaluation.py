#!/usr/bin/env python3
"""Ch. 7.4 experiment: personalization proof on the MIT-BIH Arrhythmia Database (48 records).

Standalone research script, not imported by the app. Calls the same
_fit_and_calibrate() the production training service uses, on labeled
records built from MIT-BIH's beat annotations (AAMI EC57 convention:
N-class symbols = normal, everything else = anomalous).

Setup:
    pip install wfdb
    # download separately (size + license): https://physionet.org/content/mitdb/1.0.0/

Usage:
    python scripts/mitbih_evaluation.py \
        --data-dir /path/to/mit-bih-arrhythmia-database-1.0.0 \
        --out results/mitbih_evaluation.csv
"""
import argparse
import csv
import logging
import os
import sys
from typing import List, Optional

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.services.training import _fit_and_calibrate  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("mitbih_evaluation")

# AAMI EC57 "N" (normal-class) beat symbols in MIT-BIH's annotation
# alphabet -- everything else (V, A, F, /, f, ...) counts as anomalous
# for this experiment.
AAMI_NORMAL_SYMBOLS = {"N", "L", "R", "e", "j"}

# The standard 48-record MIT-BIH Arrhythmia Database set.
MIT_BIH_RECORDS = [
    "100", "101", "102", "103", "104", "105", "106", "107", "108", "109",
    "111", "112", "113", "114", "115", "116", "117", "118", "119", "121",
    "122", "123", "124", "200", "201", "202", "203", "205", "207", "208",
    "209", "210", "212", "213", "214", "215", "217", "219", "220", "221",
    "222", "223", "228", "230", "231", "232", "233", "234",
]


def _load_labeled_record(data_dir: str, record_id: str) -> pd.DataFrame:
    import wfdb  # imported lazily -- only this script needs it, not the app

    record = wfdb.rdrecord(os.path.join(data_dir, record_id))
    ann = wfdb.rdann(os.path.join(data_dir, record_id), "atr")

    signal = record.p_signal[:, 0]
    label = np.zeros(len(signal), dtype=int)
    for sample, symbol in zip(ann.sample, ann.symbol):
        if symbol not in AAMI_NORMAL_SYMBOLS and 0 <= sample < len(signal):
            label[sample] = 1

    return pd.DataFrame({"signal": signal, "label": label})


FIELDNAMES = [
    "record", "epsilon", "mu", "sigma", "precision", "recall", "f1", "auc",
    "n_test_samples", "n_test_positive",
]


def _already_done(out_csv: str) -> set:
    """Record IDs already written to out_csv from a previous, interrupted run."""
    if not os.path.isfile(out_csv):
        return set()
    with open(out_csv, newline="") as f:
        return {row["record"] for row in csv.DictReader(f)}


def run(data_dir: str, out_csv: str, algorithm: str, records: List[str]) -> None:
    out_dir = os.path.dirname(out_csv) or "."
    os.makedirs(out_dir, exist_ok=True)
    artifacts_dir = os.path.join(out_dir, "_mitbih_artifacts")
    os.makedirs(artifacts_dir, exist_ok=True)

    done = _already_done(out_csv)
    todo = [r for r in records if r not in done]
    if done:
        logger.info("Resuming: %d/%d records already done, %d left", len(done), len(records), len(todo))

    file_exists = os.path.isfile(out_csv)
    # Line-buffered (buffering=1) + a flush after every row -- so a killed
    # process (shutdown, sleep, crash) only loses the in-flight record, and
    # rerunning the same command picks up from `_already_done` instead of
    # starting the whole 48-record, multi-day run over from scratch.
    with open(out_csv, "a", newline="", buffering=1) as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if not file_exists:
            writer.writeheader()
            f.flush()

        for record_id in todo:
            try:
                df = _load_labeled_record(data_dir, record_id)
            except Exception:
                logger.exception("Could not load record %s, skipping", record_id)
                continue

            base_path = os.path.join(artifacts_dir, f"record_{record_id}")
            try:
                fit = _fit_and_calibrate(df, algorithm, base_path, label_column="label")
            except Exception:
                logger.exception("Training failed for record %s, skipping", record_id)
                continue

            thr = fit["threshold"]
            ev = fit["evaluation"] or {}
            row = {
                "record": record_id,
                "epsilon": thr["epsilon"],
                "mu": thr["mu"],
                "sigma": thr["sigma"],
                "precision": ev.get("precision"),
                "recall": ev.get("recall"),
                "f1": ev.get("f1"),
                "auc": ev.get("auc"),
                "n_test_samples": ev.get("n_test_samples"),
                "n_test_positive": ev.get("n_test_positive"),
            }
            writer.writerow(row)
            f.flush()
            logger.info(
                "record %s: epsilon=%.4f f1=%s auc=%s",
                record_id, thr["epsilon"], ev.get("f1"), ev.get("auc"),
            )

    with open(out_csv, newline="") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        logger.error("No records were successfully evaluated")
        return

    epsilons = np.array([float(r["epsilon"]) for r in rows])
    f1s = np.array([float(r["f1"]) for r in rows if r["f1"] not in (None, "", "None")])
    logger.info("Wrote %d/%d records to %s", len(rows), len(records), out_csv)
    logger.info(
        "epsilon: min=%.4f max=%.4f mean=%.4f std=%.4f range_ratio=%s",
        epsilons.min(), epsilons.max(), epsilons.mean(), epsilons.std(),
        f"{epsilons.max() / epsilons.min():.2f}x" if epsilons.min() > 0 else "n/a",
    )
    if len(f1s):
        logger.info("F1 across records with usable labels: mean=%.3f std=%.3f", f1s.mean(), f1s.std())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", required=True, help="Directory containing MIT-BIH .dat/.hea/.atr files")
    parser.add_argument("--out", default="results/mitbih_evaluation.csv", help="Output CSV path")
    parser.add_argument(
        "--algorithm", default="LSTM", choices=["IF", "LSTM"],
        help="Fixed algorithm for every record, so epsilon is the only variable across the 48 patients (ch. 7.4)",
    )
    parser.add_argument(
        "--records", nargs="*", default=None,
        help="Subset of record IDs to run, e.g. --records 100 101 102 (default: all 48)",
    )
    args = parser.parse_args()

    run(args.data_dir, args.out, args.algorithm, args.records or MIT_BIH_RECORDS)


if __name__ == "__main__":
    main()
