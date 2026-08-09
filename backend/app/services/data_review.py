"""Pre-retrain data review: optional, off-by-default. Scans a Subject's
newest data with a throwaway IF before it's baked into a retrain, so
obvious anomalies don't get taught to the model as "normal"."""
import logging
import math
from typing import Optional

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.db.models import DataReviewCandidate, Dataset, Subject
from app.ml_core.models.isolation_forest import IFModel
from app.ml_core.preprocessing import numeric_only

logger = logging.getLogger(__name__)

_MIN_ROWS = 20  # too few rows for a throwaway IF fit to mean anything


def find_candidate_anomalies(
    df: pd.DataFrame, max_candidates: int = 100, top_fraction: float = 0.03
) -> list[dict]:
    """Top-scoring rows from a throwaway IF fit, most-suspicious first.
    Never raises -- returns [] on bad/small data."""
    try:
        num_df = numeric_only(df)
        n = len(num_df)
        if n < _MIN_ROWS:
            return []

        m = IFModel(contamination=min(0.1, max(0.01, top_fraction)))
        m.train(num_df.values)
        scores = np.asarray(m.score(num_df.values))

        n_candidates = min(max_candidates, max(1, math.ceil(top_fraction * n)))
        order = np.argsort(scores)[::-1][:n_candidates]

        return [
            {
                "row_index": int(num_df.index[pos]),
                "score": float(scores[pos]),
                "row_preview": {str(col): float(num_df.iloc[pos][col]) for col in num_df.columns},
            }
            for pos in order
        ]
    except Exception:
        logger.exception("Candidate-anomaly scan failed, returning no candidates")
        return []


def ensure_review_candidates(db: Session, subject: Subject, dataset: Dataset) -> list[DataReviewCandidate]:
    """Idempotent -- reuses existing candidates instead of re-scanning."""
    existing = db.query(DataReviewCandidate).filter_by(dataset_id=dataset.id).all()
    if existing:
        return existing

    try:
        df = pd.read_csv(dataset.file_path)
    except Exception:
        logger.exception("Could not read dataset %s for pre-retrain review", dataset.id)
        return []

    candidates = find_candidate_anomalies(df)
    rows = [
        DataReviewCandidate(
            subject_id=subject.id,
            dataset_id=dataset.id,
            row_index=c["row_index"],
            score=c["score"],
            row_preview=c["row_preview"],
        )
        for c in candidates
    ]
    if rows:
        db.add_all(rows)
        db.commit()
        for r in rows:
            db.refresh(r)
    return rows
