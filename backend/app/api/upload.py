import json
import logging
import os
import time
import uuid
from typing import Optional

import pandas as pd
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.config import settings
from app.core.limiter import limiter
from app.db.models import Dataset, Subject, UploadLog, User
from app.db.session import get_db
from app.ml_core.profiler import profile_dataset
from app.services.dataset_splitter import analyze_split_options, split_by_column, split_by_time
from app.services.subjects import ensure_default_subject
from app.services.training import run_retrain_job_background

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["upload"])

MAX_CSV_BYTES = 50 * 1024 * 1024  # 50 MB
TMP_DIR = os.path.join(settings.STORAGE_PATH, "tmp")
TMP_EXPIRY_SECONDS = 3600  # 1 hour


@router.post("", status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
def upload_csv(
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only .csv files are accepted")

    contents = file.file.read()
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
        logger.exception("Failed to parse uploaded CSV for user %s (%s)", user.id, file.filename)
        db.add(UploadLog(user_id=user.id, filename=file.filename, size_bytes=size,
                         status="rejected", reason=f"parse_error: {exc}"[:255]))
        db.commit()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Could not parse CSV: {exc}")

    profile = profile_dataset(df)
    subject = ensure_default_subject(user, db)

    dataset = Dataset(
        user_id=user.id,
        subject_id=subject.id,
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


# ---------------------------------------------------------------------------
# Two-step Subject-aware upload flow: analyze (profile + split options,
# staged to a short-lived temp file) then commit (create Subject(s), persist
# the dataset(s), queue training). The plain POST /upload above is kept
# as-is for programmatic/backward-compat use -- it always lands on the
# user's default Subject with no splitting.
# ---------------------------------------------------------------------------


def _cleanup_expired_tmp() -> None:
    if not os.path.isdir(TMP_DIR):
        return
    now = time.time()
    for fname in os.listdir(TMP_DIR):
        fpath = os.path.join(TMP_DIR, fname)
        try:
            if now - os.path.getmtime(fpath) > TMP_EXPIRY_SECONDS:
                os.remove(fpath)
        except OSError:
            pass


def _tmp_csv_path(temp_id: str) -> str:
    return os.path.join(TMP_DIR, f"{temp_id}.csv")


def _tmp_meta_path(temp_id: str) -> str:
    return os.path.join(TMP_DIR, f"{temp_id}.meta.json")


@router.post("/analyze", status_code=status.HTTP_200_OK)
@limiter.limit("10/minute")
def analyze_upload(request: Request, file: UploadFile = File(...), user: User = Depends(current_user)):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only .csv files are accepted")

    contents = file.file.read()
    size = len(contents)
    if size == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty file")
    if size > MAX_CSV_BYTES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"File too large (max {MAX_CSV_BYTES // 1024 // 1024} MB)")
    if b"\x00" in contents[:8192]:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "File does not look like a text CSV")

    _cleanup_expired_tmp()
    os.makedirs(TMP_DIR, exist_ok=True)
    temp_id = uuid.uuid4().hex
    tmp_path = _tmp_csv_path(temp_id)
    with open(tmp_path, "wb") as f:
        f.write(contents)

    try:
        df = pd.read_csv(tmp_path)
    except Exception as exc:
        os.remove(tmp_path)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Could not parse CSV: {exc}")

    original_name = os.path.basename(file.filename).replace("/", "_").replace("\\", "_")
    with open(_tmp_meta_path(temp_id), "w") as f:
        json.dump({"user_id": user.id, "original_filename": original_name}, f)

    profile = profile_dataset(df)
    split_options = analyze_split_options(df)

    return {
        "temp_id": temp_id,
        "n_rows": int(len(df)),
        "n_features": int(df.shape[1]),
        "columns": [str(c) for c in df.columns],
        "split_options": split_options,
        "profile": profile,
    }


class SplitConfig(BaseModel):
    mode: str = Field(pattern="^(none|by_column|by_time)$")
    column: Optional[str] = None
    period: Optional[str] = Field(default=None, pattern="^(hourly|daily|weekly|monthly)$")


class CommitIn(BaseModel):
    temp_id: str
    target: str = Field(pattern="^(new|existing)$")
    subject_name: Optional[str] = Field(default=None, max_length=255)
    subject_description: Optional[str] = Field(default=None, max_length=2000)
    subject_id: Optional[int] = None
    split: SplitConfig
    # Advanced-mode only: overrides the router for the first training run
    # on each Subject this commit creates. Left null for the default
    # (router-decides) path.
    algorithm: Optional[str] = Field(default=None, pattern="^(IF|LSTM)$")


@router.post("/commit", status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
def commit_upload(
    request: Request,
    body: CommitIn,
    background_tasks: BackgroundTasks,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    tmp_path = _tmp_csv_path(body.temp_id)
    meta_path = _tmp_meta_path(body.temp_id)
    if not os.path.isfile(tmp_path) or not os.path.isfile(meta_path):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Upload session expired or not found, please upload the file again")
    if time.time() - os.path.getmtime(tmp_path) > TMP_EXPIRY_SECONDS:
        os.remove(tmp_path)
        os.remove(meta_path)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Upload session expired, please upload the file again")

    with open(meta_path) as f:
        meta = json.load(f)
    if meta.get("user_id") != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Upload session not found")
    original_filename = meta.get("original_filename", "data.csv")

    if body.split.mode != "none" and body.target == "existing":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Splitting always creates new subjects")
    if body.target == "new" and not body.subject_name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "subject_name is required when creating a new subject")
    if body.target == "existing" and not body.subject_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "subject_id is required when adding to an existing subject")

    try:
        df = pd.read_csv(tmp_path)
    except Exception as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Could not parse CSV: {exc}")

    # (subject, dataframe, dataset_display_name) for every Subject this
    # commit will touch -- exactly 1 unless split.mode created several.
    targets: list[tuple[Subject, pd.DataFrame, str]] = []

    if body.split.mode == "none":
        if body.target == "existing":
            subject = db.query(Subject).filter(Subject.id == body.subject_id, Subject.user_id == user.id).first()
            if not subject:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Subject not found")
        else:
            subject = Subject(user_id=user.id, name=body.subject_name, description=body.subject_description, source_hint="upload")
            db.add(subject)
            db.commit()
            db.refresh(subject)
        targets.append((subject, df, original_filename))
    else:
        if not body.split.column:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "split.column is required for this split mode")
        try:
            if body.split.mode == "by_column":
                groups = split_by_column(df, body.split.column)
            else:
                if not body.split.period:
                    raise HTTPException(status.HTTP_400_BAD_REQUEST, "split.period is required for split by time")
                groups = split_by_time(df, body.split.column, body.split.period)
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))

        if not groups:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Split produced no groups")

        base_name = body.subject_name or original_filename
        for group_key, group_df in groups.items():
            name = f"{base_name} - {group_key}"
            suffix = 2
            while db.query(Subject).filter(Subject.user_id == user.id, Subject.name == name).first():
                name = f"{base_name} - {group_key} ({suffix})"
                suffix += 1
            subject = Subject(
                user_id=user.id, name=name, description=body.subject_description, source_hint="split_from:upload"
            )
            db.add(subject)
            db.commit()
            db.refresh(subject)
            targets.append((subject, group_df, f"{original_filename} ({group_key})"))

    os.makedirs(settings.STORAGE_PATH, exist_ok=True)
    subject_ids: list[int] = []
    dataset_ids: list[int] = []

    for subject, group_df, dataset_name in targets:
        safe_name = f"user{user.id}_{uuid.uuid4().hex[:8]}_{dataset_name}".replace("/", "_").replace("\\", "_")
        disk_path = os.path.join(settings.STORAGE_PATH, safe_name)
        group_df.to_csv(disk_path, index=False)

        profile = profile_dataset(group_df)
        dataset = Dataset(
            user_id=user.id,
            subject_id=subject.id,
            name=dataset_name,
            file_path=disk_path,
            profile_json=profile,
            n_rows=int(len(group_df)),
            n_features=int(group_df.shape[1]),
        )
        db.add(dataset)
        db.commit()
        db.refresh(dataset)

        db.add(UploadLog(user_id=user.id, dataset_id=dataset.id, filename=dataset_name, size_bytes=os.path.getsize(disk_path), status="ok"))
        db.commit()

        subject_ids.append(subject.id)
        dataset_ids.append(dataset.id)
        background_tasks.add_task(run_retrain_job_background, subject.id, user.id, body.algorithm)

    os.remove(tmp_path)
    os.remove(meta_path)

    return {
        "subject_ids": subject_ids,
        "dataset_ids": dataset_ids,
        "training_queued": True,
    }
