from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.db.models import Model, User
from app.db.session import get_db
from app.ml_core.threshold import recompute_epsilon

router = APIRouter(prefix="/settings", tags=["settings"])


class ThresholdOut(BaseModel):
    model_id: int
    mu: float
    sigma: float
    epsilon: float
    z_multiplier: float
    calibrated_at: str


class RecalibrateIn(BaseModel):
    z_multiplier: float = Field(ge=1.0, le=6.0)


def _get_owned_model(db: Session, model_id: int, user: User) -> Model:
    m = db.query(Model).filter(Model.id == model_id, Model.user_id == user.id).first()
    if not m or not m.threshold:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Model or threshold not found")
    return m


@router.get("/threshold/{model_id}", response_model=ThresholdOut)
def get_threshold(model_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    m = _get_owned_model(db, model_id, user)
    t = m.threshold
    return ThresholdOut(
        model_id=m.id, mu=t.mu, sigma=t.sigma, epsilon=t.epsilon,
        z_multiplier=t.z_multiplier, calibrated_at=t.calibrated_at.isoformat(),
    )


@router.patch("/threshold/{model_id}", response_model=ThresholdOut)
def update_threshold(
    model_id: int,
    body: RecalibrateIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    m = _get_owned_model(db, model_id, user)
    t = m.threshold
    t.z_multiplier = body.z_multiplier
    t.epsilon = recompute_epsilon(t.mu, t.sigma, body.z_multiplier)
    t.calibrated_at = datetime.utcnow()
    db.commit()
    db.refresh(t)
    return ThresholdOut(
        model_id=m.id, mu=t.mu, sigma=t.sigma, epsilon=t.epsilon,
        z_multiplier=t.z_multiplier, calibrated_at=t.calibrated_at.isoformat(),
    )
