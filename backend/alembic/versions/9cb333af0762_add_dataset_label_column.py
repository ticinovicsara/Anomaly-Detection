"""add dataset label_column

Revision ID: 9cb333af0762
Revises: 7c44300660ea
Create Date: 2026-08-13 00:00:00.000000

Adds an optional label_column to datasets: the name of a column the user
marked at upload time as holding a 0/1 ground-truth anomaly label. Nullable
and additive only -- existing datasets simply have no label column, and
behave exactly as before (train/val used, test split unused for anything
beyond existing today).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9cb333af0762'
down_revision: Union[str, None] = '7c44300660ea'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('datasets', sa.Column('label_column', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('datasets', 'label_column')
