from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, ModelMeta

router = APIRouter()


@router.get("/results")
def get_results(
    username: str,
    dataset_type: str,
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User '{username}' not found")

    metas = (
        db.query(ModelMeta)
        .filter(ModelMeta.user_id == user.id, ModelMeta.dataset_type == dataset_type)
        .order_by(ModelMeta.model_type.asc())
        .all()
    )
    if not metas:
        raise HTTPException(status_code=404, detail="No trained models found for this dataset")

    population = {
        row.model_type: row.avg_threshold
        for row in (
            db.query(
                ModelMeta.model_type.label("model_type"),
                func.avg(ModelMeta.threshold).label("avg_threshold"),
            )
            .filter(ModelMeta.dataset_type == dataset_type)
            .group_by(ModelMeta.model_type)
            .all()
        )
    }

    models = []
    for meta in metas:
        avg_threshold = population.get(meta.model_type)
        delta = None if avg_threshold is None else meta.threshold - avg_threshold
        models.append(
            {
                "model_type": meta.model_type,
                "threshold": meta.threshold,
                "avg_threshold": avg_threshold,
                "threshold_delta": delta,
                "metrics": {
                    "precision": meta.eval_precision,
                    "recall": meta.eval_recall,
                    "f1": meta.eval_f1,
                    "roc_auc": meta.eval_roc_auc,
                },
            }
        )

    best_model = None
    best_f1 = -1.0
    for model in models:
        f1 = model["metrics"]["f1"]
        if f1 is not None and f1 > best_f1:
            best_model = model["model_type"]
            best_f1 = f1

    return {
        "username": username,
        "dataset_type": dataset_type,
        "best_model": best_model,
        "models": models,
    }
