from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from app.api.deps import current_user
from app.db.models import AnomalyEvent, Prediction, User
from app.db.session import get_db

router = APIRouter(prefix="/anomalies", tags=["anomalies"])


class AnomalyOut(BaseModel):
    id: int
    prediction_id: int
    model_id: int
    window_idx: int
    score: float
    severity: str
    label: str
    note: Optional[str] = None
    created_at: str


class LabelIn(BaseModel):
    label: str = Field(pattern="^(confirmed|false_positive|resolved|unlabeled)$")
    note: Optional[str] = Field(default=None, max_length=500)


@router.get("", response_model=list[AnomalyOut])
def list_anomalies(
    model_id: Optional[int] = Query(None),
    label: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    q = (
        db.query(AnomalyEvent)
        .options(joinedload(AnomalyEvent.prediction))
        .filter(AnomalyEvent.user_id == user.id)
    )
    if label:
        q = q.filter(AnomalyEvent.label == label)
    if model_id is not None:
        q = q.join(Prediction).filter(Prediction.model_id == model_id)
    q = q.order_by(AnomalyEvent.created_at.desc()).limit(limit)

    return [
        AnomalyOut(
            id=e.id,
            prediction_id=e.prediction_id,
            model_id=e.prediction.model_id,
            window_idx=e.prediction.window_idx,
            score=e.prediction.score,
            severity=e.severity,
            label=e.label,
            note=e.note,
            created_at=e.created_at.isoformat(),
        )
        for e in q.all()
    ]


@router.patch("/{event_id}", response_model=AnomalyOut)
def label_anomaly(
    event_id: int,
    body: LabelIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    event = (
        db.query(AnomalyEvent)
        .options(joinedload(AnomalyEvent.prediction))
        .filter(AnomalyEvent.id == event_id, AnomalyEvent.user_id == user.id)
        .first()
    )
    if not event:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Anomaly event not found")
    event.label = body.label
    if body.note is not None:
        event.note = body.note
    db.commit()
    db.refresh(event)

    return AnomalyOut(
        id=event.id,
        prediction_id=event.prediction_id,
        model_id=event.prediction.model_id,
        window_idx=event.prediction.window_idx,
        score=event.prediction.score,
        severity=event.severity,
        label=event.label,
        note=event.note,
        created_at=event.created_at.isoformat(),
    )
