from sqlalchemy.orm import Session

from app.db.models import Model, Subject, User


def ensure_default_subject(user: User, db: Session) -> Subject:
    """Get or create the user's default 'My data' Subject.

    Backstop for callers that don't yet ask the user which Subject data
    belongs to (the plain /upload endpoint, background training) -- keeps
    subject_id populated without forcing every caller through the full
    Subjects flow.
    """
    default = db.query(Subject).filter_by(user_id=user.id, is_default=True).first()
    if not default:
        default = Subject(user_id=user.id, name="My data", is_default=True, source_hint="auto_default")
        db.add(default)
        db.commit()
        db.refresh(default)
    return default


def get_active_model(subject: Subject, db: Session) -> Model | None:
    return db.query(Model).filter_by(subject_id=subject.id, is_active=True).first()


def set_active_model(subject: Subject, model_id: int, db: Session) -> None:
    db.query(Model).filter_by(subject_id=subject.id).update({"is_active": False})
    db.query(Model).filter(Model.id == model_id, Model.subject_id == subject.id).update({"is_active": True})
    db.commit()
