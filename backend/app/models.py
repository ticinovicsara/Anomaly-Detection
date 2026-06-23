from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    uploads: Mapped[list["UploadLog"]] = relationship("UploadLog", back_populates="user")
    model_metas: Mapped[list["ModelMeta"]] = relationship("ModelMeta", back_populates="user")


class UploadLog(Base):
    __tablename__ = "upload_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String(256), nullable=False)
    dataset_type: Mapped[str] = mapped_column(String(32), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="uploads")


class ModelMeta(Base):
    __tablename__ = "model_meta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    dataset_type: Mapped[str] = mapped_column(String(32), nullable=False)
    model_type: Mapped[str] = mapped_column(String(32), nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    mean_error: Mapped[float] = mapped_column(Float, nullable=False)
    std_error: Mapped[float] = mapped_column(Float, nullable=False)
    eval_precision: Mapped[float | None] = mapped_column(Float, nullable=True)
    eval_recall: Mapped[float | None] = mapped_column(Float, nullable=True)
    eval_f1: Mapped[float | None] = mapped_column(Float, nullable=True)
    eval_roc_auc: Mapped[float | None] = mapped_column(Float, nullable=True)
    trained_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="model_metas")
