from typing import List

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.db.models import Model, Prediction, User
from app.db.session import get_db
from app.services.prediction import persist_predictions, run_prediction

router = APIRouter(prefix="/predict", tags=["predict"])


class PredictCurvePointOut(BaseModel):
    i: int
    score: float
    actual: int
    predicted: int


class PredictConfusionOut(BaseModel):
    tp: int
    fp: int
    tn: int
    fn: int


class PredictBatchSummaryOut(BaseModel):
    batch_id: str
    model_id: int
    created_at: str
    n_windows: int
    confusion: PredictConfusionOut


class PredictBatchDetailOut(PredictBatchSummaryOut):
    curve: List[PredictCurvePointOut]


def _owned_model(db: Session, model_id: int, user: User) -> Model:
    m = db.query(Model).filter(Model.id == model_id, Model.user_id == user.id).first()
    if not m:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Model not found")
    return m


def _confusion_from_predictions(preds: List[Prediction]) -> PredictConfusionOut:
    tp = sum(1 for p in preds if p.actual == 1 and p.is_anomaly)
    fp = sum(1 for p in preds if p.actual == 0 and p.is_anomaly)
    fn = sum(1 for p in preds if p.actual == 1 and not p.is_anomaly)
    tn = sum(1 for p in preds if p.actual == 0 and not p.is_anomaly)
    return PredictConfusionOut(tp=tp, fp=fp, tn=tn, fn=fn)


@router.post("/{model_id}")
def predict(
    model_id: int,
    file: UploadFile = File(...),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only .csv files are accepted")

    model_row = db.query(Model).filter(Model.id == model_id, Model.user_id == user.id).first()
    if not model_row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Model not found")
    if model_row.status != "ready":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Model is not ready (status={model_row.status})")
    threshold = model_row.threshold
    if not threshold:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Model has no calibrated threshold")

    head = file.file.read(8192)
    file.file.seek(0)
    if b"\x00" in head:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "File does not look like a text CSV")

    try:
        df = pd.read_csv(file.file)
    except Exception as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Cannot parse CSV: {exc}")

    try:
        batch_id, results = run_prediction(model_row, threshold, df)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))

    anomaly_count = persist_predictions(db, user.id, model_row.id, results, threshold.epsilon)
    has_labels = any(r["actual"] is not None for r in results)

    return {
        "batch_id": batch_id,
        "model_id": model_row.id,
        "algorithm": model_row.algorithm,
        "threshold": threshold.epsilon,
        "total_windows": len(results),
        "anomaly_count": anomaly_count,
        "anomaly_rate": (anomaly_count / len(results)) if results else 0.0,
        "has_labels": has_labels,
        "results": results,
    }


@router.get("/{model_id}/batches", response_model=List[PredictBatchSummaryOut])
def list_labeled_batches(model_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Every Predict run against this model that included a usable ground-truth
    label -- ordinary unlabeled predictions never show up here."""
    model_row = _owned_model(db, model_id, user)
    rows = (
        db.query(Prediction)
        .filter(Prediction.model_id == model_row.id, Prediction.actual.isnot(None))
        .order_by(Prediction.created_at.asc())
        .all()
    )
    by_batch: dict = {}
    for p in rows:
        by_batch.setdefault(p.batch_id, []).append(p)

    summaries = [
        PredictBatchSummaryOut(
            batch_id=batch_id,
            model_id=model_row.id,
            created_at=preds[0].created_at.isoformat(),
            n_windows=len(preds),
            confusion=_confusion_from_predictions(preds),
        )
        for batch_id, preds in by_batch.items()
    ]
    summaries.sort(key=lambda s: s.created_at, reverse=True)
    return summaries


@router.get("/{model_id}/batches/{batch_id}", response_model=PredictBatchDetailOut)
def get_labeled_batch(
    model_id: int, batch_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    model_row = _owned_model(db, model_id, user)
    preds = (
        db.query(Prediction)
        .filter(Prediction.model_id == model_row.id, Prediction.batch_id == batch_id, Prediction.actual.isnot(None))
        .order_by(Prediction.window_idx.asc())
        .all()
    )
    if not preds:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Labeled batch not found")
    return PredictBatchDetailOut(
        batch_id=batch_id,
        model_id=model_row.id,
        created_at=preds[0].created_at.isoformat(),
        n_windows=len(preds),
        confusion=_confusion_from_predictions(preds),
        curve=[
            PredictCurvePointOut(i=p.window_idx, score=p.score, actual=p.actual, predicted=int(p.is_anomaly))
            for p in preds
        ],
    )
