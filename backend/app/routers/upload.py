from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, UploadLog
from app.ml.preprocessing import load_creditcard, load_ecg, load_yahoo

router = APIRouter()

ALLOWED_DATASET_TYPES = {"credit_card", "ecg", "yahoo"}
DATA_DIR = Path("data")


def _get_or_create_user(db: Session, username: str) -> User:
    user = db.query(User).filter(User.username == username).first()
    if not user:
        try:
            user = User(username=username)
            db.add(user)
            db.flush()
        except IntegrityError:
            db.rollback()
            user = db.query(User).filter(User.username == username).first()
    return user


@router.post("/upload")
async def upload_csv(
    file: UploadFile = File(...),
    username: str = "default",
    dataset_type: str = "credit_card",
    db: Session = Depends(get_db),
):
    if dataset_type not in ALLOWED_DATASET_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"dataset_type must be one of {sorted(ALLOWED_DATASET_TYPES)}",
        )

    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are accepted")

    contents = await file.read()
    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    safe_filename = Path(file.filename).name
    save_dir = DATA_DIR / dataset_type / "raw"
    save_dir.mkdir(parents=True, exist_ok=True)
    save_path = save_dir / safe_filename
    save_path.write_bytes(contents)

    try:
        if dataset_type == "credit_card":
            df, _ = load_creditcard(str(save_path))
        elif dataset_type == "yahoo":
            df, _ = load_yahoo(str(save_path))
        else:
            df, _ = load_ecg(str(save_path))
    except (ValueError, KeyError) as exc:
        save_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=str(exc))

    user = _get_or_create_user(db, username)

    log = UploadLog(
        user_id=user.id,
        filename=safe_filename,
        dataset_type=dataset_type,
        row_count=len(df),
    )
    db.add(log)
    db.commit()

    return {
        "upload_id": log.id,
        "user_id": user.id,
        "filename": safe_filename,
        "dataset_type": dataset_type,
        "row_count": len(df),
        "saved_to": str(save_path),
    }
