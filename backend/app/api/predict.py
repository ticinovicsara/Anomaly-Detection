import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.db.models import Model, User
from app.db.session import get_db
from app.services.prediction import persist_predictions, run_prediction

router = APIRouter(prefix="/predict", tags=["predict"])


@router.post("/{model_id}")
async def predict(
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

    try:
        df = pd.read_csv(file.file)
    except Exception as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Cannot parse CSV: {exc}")

    try:
        batch_id, results = run_prediction(model_row, threshold, df)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))

    anomaly_count = persist_predictions(db, user.id, model_row.id, results)

    return {
        "batch_id": batch_id,
        "model_id": model_row.id,
        "algorithm": model_row.algorithm,
        "threshold": threshold.epsilon,
        "total_windows": len(results),
        "anomaly_count": anomaly_count,
        "anomaly_rate": (anomaly_count / len(results)) if results else 0.0,
        "results": results,
    }
