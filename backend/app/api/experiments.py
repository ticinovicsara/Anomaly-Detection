from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.db.models import User
from app.db.session import get_db
from app.services.experiments import (
    aggregate_evaluation_metrics,
    run_personalization_experiment,
    run_preset_demo,
)
from app.services.training import is_training_slot_free

router = APIRouter(prefix="/experiments", tags=["experiments"])


class PersonalizationIn(BaseModel):
    subject_ids: list[int] = Field(min_length=2)


class StatisticsOut(BaseModel):
    mean: float
    std: float
    min: float
    max: float
    range_ratio: Optional[float]


class CrossApplicationOut(BaseModel):
    global_epsilon: float
    fp_rate_at_global: dict[str, Optional[float]]
    miss_rate_at_global: dict[str, Optional[float]]


class ExperimentOut(BaseModel):
    subject_ids: list[int]
    epsilons: dict[str, float]
    statistics: StatisticsOut
    cross_application: CrossApplicationOut


class PresetDemoOut(ExperimentOut):
    created_subject_ids: list[int]


class EvaluationSummaryOut(BaseModel):
    subject_ids: list[int]
    excluded_subject_ids: list[int]
    n_labeled_subjects: int
    n_unlabeled_subjects: int
    f1_by_subject: dict[str, float]
    f1_statistics: Optional[StatisticsOut]
    precision_statistics: Optional[StatisticsOut]
    recall_statistics: Optional[StatisticsOut]
    auc_statistics: Optional[StatisticsOut]


@router.post("/personalization", response_model=ExperimentOut)
def personalization(
    body: PersonalizationIn, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    try:
        return run_personalization_experiment(body.subject_ids, db, user.id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


@router.post("/preset-demo", response_model=PresetDemoOut)
def preset_demo(user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not is_training_slot_free():
        raise HTTPException(status.HTTP_409_CONFLICT, "Another training is in progress, try again in a few minutes")
    try:
        return run_preset_demo(db, user.id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


@router.get("/evaluation-summary", response_model=EvaluationSummaryOut)
def evaluation_summary(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Cross-Subject F1/precision/recall/AUC summary -- additive to (never
    a substitute for) each Subject's own number. Silently includes only
    Subjects that have both an active model and a labeled evaluation;
    everyone else is reported in excluded_subject_ids rather than causing
    an error, since most Subjects won't have a label column."""
    return aggregate_evaluation_metrics(db, user.id)
