from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.api.deps import current_user
from app.db.models import Dataset, Model, User
from app.db.session import get_db
from app.ml_core.model_router import choose_model
from app.services.training import is_training_slot_free, run_training_job

router = APIRouter(prefix="/train", tags=["train"])


@router.post("/{dataset_id}", status_code=status.HTTP_202_ACCEPTED)
def train(
    dataset_id: int,
    background_tasks: BackgroundTasks,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id, Dataset.user_id == user.id).first()
    if not dataset:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dataset not found")

    if not is_training_slot_free():
        raise HTTPException(status.HTTP_409_CONFLICT, "Another training is in progress, try again in a few minutes")

    # Preview the router's decision so the user sees WHY without waiting for training
    algo, reason = choose_model(dataset.profile_json or {})

    background_tasks.add_task(run_training_job, dataset.id, user.id)
    return {"status": "training_started", "algorithm_chosen": algo, "reason": reason}


@router.get("/models", tags=["models"])
def list_models(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(Model)
        .options(joinedload(Model.threshold))
        .filter(Model.user_id == user.id)
        .order_by(Model.created_at.desc())
        .all()
    )
    out = []
    for m in rows:
        thr = m.threshold
        out.append({
            "id": m.id,
            "dataset_id": m.dataset_id,
            "subject_id": m.subject_id,
            "algorithm": m.algorithm,
            "status": m.status,
            "selection_reason": m.selection_reason,
            "selection_mode": m.selection_mode,
            "is_active": m.is_active,
            "trained_at": m.trained_at.isoformat() if m.trained_at else None,
            "drift_status": m.drift_status,
            "metrics": m.metrics_json,
            "threshold": {
                "mu": thr.mu, "sigma": thr.sigma, "epsilon": thr.epsilon, "z_multiplier": thr.z_multiplier,
            } if thr else None,
        })
    return out
