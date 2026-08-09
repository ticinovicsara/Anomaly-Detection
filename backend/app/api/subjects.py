from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from app.api.deps import current_user
from app.db.models import AnomalyEvent, Dataset, Model, Prediction, Subject, User
from app.db.session import get_db
from app.services.subjects import get_active_model, set_active_model
from app.services.training import is_training_slot_free, run_retrain_job, run_train_alternative_job

router = APIRouter(prefix="/subjects", tags=["subjects"])


class SubjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)


class SubjectUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)


class ThresholdOut(BaseModel):
    mu: float
    sigma: float
    epsilon: float
    z_multiplier: float


class SubjectOut(BaseModel):
    id: int
    name: str
    description: Optional[str]
    source_hint: Optional[str]
    is_default: bool
    created_at: str
    n_datasets: int
    n_models: int
    n_anomalies: int
    active_epsilon: Optional[float]
    active_algorithm: Optional[str]
    active_model_id: Optional[int]
    active_mu: Optional[float]
    active_sigma: Optional[float]
    active_z_multiplier: Optional[float]


class DatasetOut(BaseModel):
    id: int
    name: str
    n_rows: Optional[int]
    n_features: Optional[int]
    uploaded_at: str


class ModelOut(BaseModel):
    id: int
    algorithm: str
    selection_reason: Optional[str]
    selection_mode: str
    status: str
    is_active: bool
    trained_at: Optional[str]
    threshold: Optional[ThresholdOut]


class SubjectDetailOut(SubjectOut):
    datasets: list[DatasetOut]
    models: list[ModelOut]


class TrainAlternativeIn(BaseModel):
    algorithm: str = Field(pattern="^(IF|LSTM)$")


class RetrainOut(BaseModel):
    model_id: int
    old_epsilon: Optional[float]
    new_epsilon: float
    delta_pct: Optional[float]


class TrainAlternativeOut(BaseModel):
    model_id: int
    algorithm: str
    epsilon: float


def _owned_subject(db: Session, subject_id: int, user: User) -> Subject:
    subject = db.query(Subject).filter(Subject.id == subject_id, Subject.user_id == user.id).first()
    if not subject:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Subject not found")
    return subject


def _anomaly_count(db: Session, subject_id: int) -> int:
    return (
        db.query(AnomalyEvent)
        .join(Prediction, AnomalyEvent.prediction_id == Prediction.id)
        .join(Model, Prediction.model_id == Model.id)
        .filter(Model.subject_id == subject_id)
        .count()
    )


def _model_out(m: Model) -> ModelOut:
    return ModelOut(
        id=m.id,
        algorithm=m.algorithm,
        selection_reason=m.selection_reason,
        selection_mode=m.selection_mode,
        status=m.status,
        is_active=m.is_active,
        trained_at=m.trained_at.isoformat() if m.trained_at else None,
        threshold=ThresholdOut(
            mu=m.threshold.mu, sigma=m.threshold.sigma, epsilon=m.threshold.epsilon, z_multiplier=m.threshold.z_multiplier
        )
        if m.threshold
        else None,
    )


def _subject_out(db: Session, subject: Subject) -> SubjectOut:
    active = get_active_model(subject, db)
    return SubjectOut(
        id=subject.id,
        name=subject.name,
        description=subject.description,
        source_hint=subject.source_hint,
        is_default=subject.is_default,
        created_at=subject.created_at.isoformat(),
        n_datasets=len(subject.datasets),
        n_models=len(subject.models),
        n_anomalies=_anomaly_count(db, subject.id),
        active_epsilon=active.threshold.epsilon if active and active.threshold else None,
        active_algorithm=active.algorithm if active else None,
        active_model_id=active.id if active else None,
        active_mu=active.threshold.mu if active and active.threshold else None,
        active_sigma=active.threshold.sigma if active and active.threshold else None,
        active_z_multiplier=active.threshold.z_multiplier if active and active.threshold else None,
    )


@router.get("", response_model=list[SubjectOut])
def list_subjects(user: User = Depends(current_user), db: Session = Depends(get_db)):
    subjects = db.query(Subject).filter(Subject.user_id == user.id).order_by(Subject.created_at.desc()).all()
    return [_subject_out(db, s) for s in subjects]


@router.post("", response_model=SubjectOut, status_code=status.HTTP_201_CREATED)
def create_subject(body: SubjectCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if db.query(Subject).filter(Subject.user_id == user.id, Subject.name == body.name).first():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You already have a subject with this name")
    subject = Subject(user_id=user.id, name=body.name, description=body.description, source_hint="upload")
    db.add(subject)
    db.commit()
    db.refresh(subject)
    return _subject_out(db, subject)


@router.get("/{subject_id}", response_model=SubjectDetailOut)
def get_subject(subject_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    subject = _owned_subject(db, subject_id, user)
    base = _subject_out(db, subject)
    datasets = db.query(Dataset).filter(Dataset.subject_id == subject.id).order_by(Dataset.uploaded_at.desc()).all()
    models = (
        db.query(Model)
        .options(joinedload(Model.threshold))
        .filter(Model.subject_id == subject.id)
        .order_by(Model.created_at.desc())
        .all()
    )
    return SubjectDetailOut(
        **base.model_dump(),
        datasets=[
            DatasetOut(id=d.id, name=d.name, n_rows=d.n_rows, n_features=d.n_features, uploaded_at=d.uploaded_at.isoformat())
            for d in datasets
        ],
        models=[_model_out(m) for m in models],
    )


@router.patch("/{subject_id}", response_model=SubjectOut)
def update_subject(
    subject_id: int, body: SubjectUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    subject = _owned_subject(db, subject_id, user)
    if body.name is not None and body.name != subject.name:
        clash = (
            db.query(Subject)
            .filter(Subject.user_id == user.id, Subject.name == body.name, Subject.id != subject.id)
            .first()
        )
        if clash:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "You already have a subject with this name")
        subject.name = body.name
    if body.description is not None:
        subject.description = body.description
    db.commit()
    db.refresh(subject)
    return _subject_out(db, subject)


@router.delete("/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_subject(subject_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    subject = _owned_subject(db, subject_id, user)
    db.delete(subject)
    db.commit()
    return None


@router.post("/{subject_id}/retrain", response_model=RetrainOut)
def retrain_subject(subject_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    subject = _owned_subject(db, subject_id, user)
    if not subject.datasets:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Subject has no data to train on")
    if not is_training_slot_free():
        raise HTTPException(status.HTTP_409_CONFLICT, "Another training is in progress, try again in a few minutes")
    try:
        result = run_retrain_job(subject.id, user.id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    return RetrainOut(**result)


@router.post("/{subject_id}/train-alternative", response_model=TrainAlternativeOut)
def train_alternative(
    subject_id: int, body: TrainAlternativeIn, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    subject = _owned_subject(db, subject_id, user)
    if not subject.datasets:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Subject has no data to train on")
    if not is_training_slot_free():
        raise HTTPException(status.HTTP_409_CONFLICT, "Another training is in progress, try again in a few minutes")
    try:
        result = run_train_alternative_job(subject.id, user.id, body.algorithm)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    return TrainAlternativeOut(**result)


@router.post("/{subject_id}/models/{model_id}/activate", response_model=ModelOut)
def activate_model(
    subject_id: int, model_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    subject = _owned_subject(db, subject_id, user)
    model = db.query(Model).filter(Model.id == model_id, Model.subject_id == subject.id).first()
    if not model:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Model not found on this subject")
    if model.status != "ready":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only a ready model can be activated")
    set_active_model(subject, model.id, db)
    db.refresh(model)
    return _model_out(model)
