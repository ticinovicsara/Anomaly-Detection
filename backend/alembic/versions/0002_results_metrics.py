"""add evaluation metrics to model_meta

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("model_meta", sa.Column("eval_precision", sa.Float(), nullable=True))
    op.add_column("model_meta", sa.Column("eval_recall", sa.Float(), nullable=True))
    op.add_column("model_meta", sa.Column("eval_f1", sa.Float(), nullable=True))
    op.add_column("model_meta", sa.Column("eval_roc_auc", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("model_meta", "eval_roc_auc")
    op.drop_column("model_meta", "eval_f1")
    op.drop_column("model_meta", "eval_recall")
    op.drop_column("model_meta", "eval_precision")
