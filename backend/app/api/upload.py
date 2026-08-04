import os
import uuid

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.config import settings
from app.db.models import Dataset, UploadLog, User
from app.db.session import get_db
from app.ml_core.profiler import profile_dataset

router = APIRouter(prefix="/upload", tags=["upload"])

MAX_CSV_BYTES = 50 * 1024 * 1024  # 50 MB


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_csv(
    file: UploadFile = File(...),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only .csv files are accepted")

    contents = await file.read()
    size = len(contents)
    if size == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty file")
    if size > MAX_CSV_BYTES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"File too large (max {MAX_CSV_BYTES // 1024 // 1024} MB)")
    if b"\x00" in contents[:8192]:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "File does not look like a text CSV")

    os.makedirs(settings.STORAGE_PATH, exist_ok=True)
    original_name = os.path.basename(file.filename).replace("/", "_").replace("\\", "_")
    safe_name = f"user{user.id}_{uuid.uuid4().hex[:8]}_{original_name}"
    disk_path = os.path.join(settings.STORAGE_PATH, safe_name)
    with open(disk_path, "wb") as f:
        f.write(contents)

    try:
        df = pd.read_csv(disk_path)
    except Exception as exc:
        db.add(UploadLog(user_id=user.id, filename=file.filename, size_bytes=size,
                         status="rejected", reason=f"parse_error: {exc}"[:255]))
        db.commit()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Could not parse CSV: {exc}")

    profile = profile_dataset(df)

    dataset = Dataset(
        user_id=user.id,
        name=file.filename,
        file_path=disk_path,
        profile_json=profile,
        n_rows=int(len(df)),
        n_features=int(df.shape[1]),
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)

    db.add(UploadLog(user_id=user.id, dataset_id=dataset.id, filename=file.filename,
                     size_bytes=size, status="ok"))
    db.commit()

    return {
        "dataset_id": dataset.id,
        "name": dataset.name,
        "n_rows": dataset.n_rows,
        "n_features": dataset.n_features,
        "profile": profile,
    }


@router.get("")
def list_datasets(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(Dataset).filter(Dataset.user_id == user.id).order_by(Dataset.uploaded_at.desc()).all()
    return [
        {
            "id": d.id,
            "name": d.name,
            "n_rows": d.n_rows,
            "n_features": d.n_features,
            "uploaded_at": d.uploaded_at.isoformat(),
        }
        for d in rows
    ]
