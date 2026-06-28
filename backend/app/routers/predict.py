import uuid
import joblib
import numpy as np
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, ModelMeta
from app.ml import preprocessing, isolation_forest, lstm_autoencoder

router = APIRouter()

ALLOWED_DATASET_TYPES = {"credit_card", "ecg", "yahoo"}
ALLOWED_MODEL_TYPES = {"isolation_forest", "lstm_autoencoder"}
MODEL_REGISTRY = Path("model_registry")
DATA_DIR = Path("data")


@router.post("/predict")
async def predict_anomalies(
    file: UploadFile = File(...),
    username: str = "default",
    dataset_type: str = "credit_card",
    model_type: str = "isolation_forest",
    db: Session = Depends(get_db),
):
    if dataset_type not in ALLOWED_DATASET_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"dataset_type must be one of {sorted(ALLOWED_DATASET_TYPES)}",
        )
    if model_type not in ALLOWED_MODEL_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"model_type must be one of {sorted(ALLOWED_MODEL_TYPES)}",
        )

    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User '{username}' not found")

    meta = (
        db.query(ModelMeta)
        .filter(
            ModelMeta.user_id == user.id,
            ModelMeta.dataset_type == dataset_type,
            ModelMeta.model_type == model_type,
        )
        .first()
    )
    if not meta:
        raise HTTPException(
            status_code=404,
            detail=f"No trained {model_type} model found for user '{username}'. Train first.",
        )

    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are accepted")

    contents = await file.read()
    tmp_dir = DATA_DIR / dataset_type
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / f"tmp_{user.id}_{uuid.uuid4().hex}.csv"
    tmp_path.write_bytes(contents)

    amount_scaler_path = str(MODEL_REGISTRY / dataset_type / f"{user.id}_amount_scaler.pkl")

    try:
        if dataset_type == "credit_card":
            df, feature_cols = preprocessing.load_creditcard(
                str(tmp_path), amount_scaler_path=amount_scaler_path
            )
        elif dataset_type == "yahoo":
            df, feature_cols = preprocessing.load_yahoo(str(tmp_path))
        else:
            df, feature_cols = preprocessing.load_ecg(str(tmp_path))
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    finally:
        tmp_path.unlink(missing_ok=True)

    scaler_path = str(MODEL_REGISTRY / dataset_type / f"{user.id}_scaler.pkl")
    if not Path(scaler_path).exists():
        raise HTTPException(
            status_code=404,
            detail="Scaler not found. Retrain the model to regenerate it.",
        )

    df, _ = preprocessing.normalize(df, feature_cols, scaler_path=scaler_path)
    model_path = str(MODEL_REGISTRY / dataset_type / f"{user.id}_{model_type}")

    if model_type == "isolation_forest":
        X = df[feature_cols].values
        iforest_model = joblib.load(model_path + ".pkl")
        raw = iforest_model.predict(X)
        predictions = np.where(raw == -1, 1, 0)
        scores = (-iforest_model.score_samples(X)).tolist()
    else:
        X = preprocessing.create_windows(df[feature_cols].values)
        if len(X) == 0:
            raise HTTPException(status_code=422, detail="Not enough data to create windows.")
        predictions, errors = lstm_autoencoder.predict(X, model_path + ".keras", meta.threshold)
        scores = errors.tolist()

    anomaly_indices = [int(i) for i, p in enumerate(predictions) if p == 1]

    return {
        "username": username,
        "dataset_type": dataset_type,
        "model_type": model_type,
        "threshold": meta.threshold,
        "total_windows": len(predictions),
        "anomaly_count": int(predictions.sum()),
        "anomaly_rate": round(float(predictions.mean()), 4),
        "anomaly_indices": anomaly_indices,
        "scores": scores,
    }
