#!/usr/bin/env python3
"""Downsamples Kaggle's Credit Card Fraud dataset (mlg-ulb/creditcardfraud)
to fit under the app's 50MB upload limit, keeping every fraud row so the
label column stays usable.

Setup:
    Download creditcard.csv manually from
    https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud (requires a
    Kaggle login, no API token needed for a plain browser download).

Usage:
    python scripts/prepare_creditcard_sample.py \
        --input /path/to/creditcard.csv \
        --output creditcard_sample.csv \
        --n-normal 90000
"""
import argparse

import pandas as pd


def run(input_path: str, output_path: str, n_normal: int, seed: int) -> None:
    df = pd.read_csv(input_path)
    if "Class" not in df.columns:
        raise ValueError("Expected a 'Class' column (0=normal, 1=fraud) in the Kaggle Credit Card Fraud dataset")

    fraud = df[df["Class"] == 1]
    normal = df[df["Class"] == 0].sample(n=min(n_normal, (df["Class"] == 0).sum()), random_state=seed)
    out = pd.concat([fraud, normal]).sort_values("Time")
    out.to_csv(output_path, index=False)

    print(f"Wrote {len(out)} rows ({fraud.shape[0]} fraud, {normal.shape[0]} normal) to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", default="creditcard.csv", help="Path to the downloaded creditcard.csv")
    parser.add_argument("--output", default="creditcard_sample.csv", help="Output CSV path, ready for app upload")
    parser.add_argument("--n-normal", type=int, default=90000, help="How many normal (Class=0) rows to keep")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for the normal-row sample")
    args = parser.parse_args()

    run(args.input, args.output, args.n_normal, args.seed)


if __name__ == "__main__":
    main()
