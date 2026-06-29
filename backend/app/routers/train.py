import time
from pathlib import Path
import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, ModelMeta
from app.ml import preprocessing, isolation_forest, lstm_autoencoder

router = APIRouter()

ALLOWED_DATASET_TYPES = {"credit_card", "ecg", "yahoo"}
ALLOWED_MODEL_TYPES = {"isolation_forest", "lstm_autoencoder"}
MODEL_REGISTRY = Path("model_registry")
DATA_DIR = Path("data")
WINDOW_SIZE = 50
WINDOW_STEP = 10


class TrainRequest(BaseModel):
    username: str
    dataset_type: str
    model_type: str
    epochs: int = 50
    batch_size: int = 32
    contamination: float = 0.01


def _label_column(dataset_type: str) -> str:
    if dataset_type == "credit_card":
        return "Class"
    if dataset_type == "yahoo":
        return "is_anomaly"
    return "label"


def _evaluate(y_true, y_pred, scores, model_type: str):
    if y_true is None or len(y_true) == 0 or len(np.unique(y_true)) < 2:
        return {"precision": None, "recall": None, "f1": None, "roc_auc": None}

    if model_type == "isolation_forest":
        return isolation_forest.evaluate(y_true, y_pred)
    return lstm_autoencoder.evaluate(y_true, y_pred, scores)


@router.post("/train")
def train_model(req: TrainRequest, db: Session = Depends(get_db)):
    if req.dataset_type not in ALLOWED_DATASET_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"dataset_type must be one of {sorted(ALLOWED_DATASET_TYPES)}",
        )
    if req.model_type not in ALLOWED_MODEL_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"model_type must be one of {sorted(ALLOWED_MODEL_TYPES)}",
        )

    user = db.query(User).filter(User.username == req.username).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User '{req.username}' not found")

    raw_path = DATA_DIR / req.dataset_type / "raw"
    csv_files = list(raw_path.glob("*.csv"))
    if not csv_files:
        raise HTTPException(
            status_code=404,
            detail=f"No CSV found in {raw_path}. Upload data first.",
        )

    csv_path = str(csv_files[0])

    amount_scaler_path = str(MODEL_REGISTRY / req.dataset_type / f"{user.id}_amount_scaler.pkl")

    if req.dataset_type == "credit_card":
        df, feature_cols = preprocessing.load_creditcard(csv_path, amount_scaler_path=amount_scaler_path)
    elif req.dataset_type == "yahoo":
        df, feature_cols = preprocessing.load_yahoo(csv_path)
    else:
        df, feature_cols = preprocessing.load_ecg(csv_path)

    train_df, val_df, test_df = preprocessing.split_by_time(df)
    label_col = _label_column(req.dataset_type)

    scaler_path = str(MODEL_REGISTRY / req.dataset_type / f"{user.id}_scaler.pkl")
    train_df, _ = preprocessing.normalize(train_df, feature_cols, scaler_path=scaler_path)
    val_df, _ = preprocessing.normalize(val_df, feature_cols, scaler_path=scaler_path)
    test_df, _ = preprocessing.normalize(test_df, feature_cols, scaler_path=scaler_path)

    model_path = str(MODEL_REGISTRY / req.dataset_type / f"{user.id}_{req.model_type}")

    if req.model_type == "isolation_forest":
        X_train = train_df[feature_cols].values
        X_val = val_df[feature_cols].values
        X_test = test_df[feature_cols].values
        model, elapsed = isolation_forest.train(
            X_train,
            contamination=req.contamination,
            save_path=model_path + ".pkl",
        )
        threshold, mean_err, std_err = isolation_forest.calibrate_threshold(model, X_val)
        if len(X_test) == 0:
            test_pred = np.array([], dtype=int)
            test_scores = np.array([], dtype=float)
            y_test = None
        else:
            raw = model.predict(X_test)
            test_pred = np.where(raw == -1, 1, 0)
            test_scores = -model.score_samples(X_test)
            y_test = test_df[label_col].to_numpy() if label_col in test_df.columns else None

    else:
        X_train = preprocessing.create_windows(train_df[feature_cols].values, WINDOW_SIZE, WINDOW_STEP)
        X_val = preprocessing.create_windows(val_df[feature_cols].values, WINDOW_SIZE, WINDOW_STEP)
        X_test = preprocessing.create_windows(test_df[feature_cols].values, WINDOW_SIZE, WINDOW_STEP)
        y_test_raw = test_df[label_col].to_numpy() if label_col in test_df.columns else None

        if len(X_train) == 0 or len(X_val) == 0:
            raise HTTPException(
                status_code=422,
                detail="Not enough data to create windows. Upload a larger dataset.",
            )

        n_features = len(feature_cols)
        model = lstm_autoencoder.build_model(window_size=50, n_features=n_features)
        t0 = time.time()
        model, _ = lstm_autoencoder.train(
            model, X_train, X_val,
            epochs=req.epochs,
            batch_size=req.batch_size,
            save_path=model_path + ".keras",
        )
        elapsed = round(time.time() - t0, 3)
        threshold, mean_err, std_err = lstm_autoencoder.calibrate_threshold(model, X_val)
        if len(X_test) == 0:
            test_pred = np.array([], dtype=int)
            test_scores = np.array([], dtype=float)
            y_test = None
        else:
            test_pred, test_scores = lstm_autoencoder.predict(X_test, model_path + ".keras", threshold)
            y_test = (
                preprocessing.window_labels(y_test_raw, WINDOW_SIZE, WINDOW_STEP)
                if y_test_raw is not None
                else None
            )

    metrics = _evaluate(y_test, test_pred, np.asarray(test_scores), req.model_type)

    existing = (
        db.query(ModelMeta)
        .filter(
            ModelMeta.user_id == user.id,
            ModelMeta.dataset_type == req.dataset_type,
            ModelMeta.model_type == req.model_type,
        )
        .first()
    )
    if existing:
        existing.threshold = threshold
        existing.mean_error = mean_err
        existing.std_error = std_err
        existing.eval_precision = metrics["precision"]
        existing.eval_recall = metrics["recall"]
        existing.eval_f1 = metrics["f1"]
        existing.eval_roc_auc = metrics["roc_auc"]
    else:
        meta = ModelMeta(
            user_id=user.id,
            dataset_type=req.dataset_type,
            model_type=req.model_type,
            threshold=threshold,
            mean_error=mean_err,
            std_error=std_err,
            eval_precision=metrics["precision"],
            eval_recall=metrics["recall"],
            eval_f1=metrics["f1"],
            eval_roc_auc=metrics["roc_auc"],
        )
        db.add(meta)

    db.commit()

    return {
        "username": req.username,
        "dataset_type": req.dataset_type,
        "model_type": req.model_type,
        "threshold": round(threshold, 6),
        "mean_error": round(mean_err, 6),
        "std_error": round(std_err, 6),
        "training_seconds": elapsed,
        "evaluation": metrics,
    }
