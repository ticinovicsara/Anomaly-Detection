"""add prediction ground truth tracking

Revision ID: 2166e5001758
Revises: fe6e07ade488
Create Date: 2026-08-20 00:00:00.000000

Adds Prediction.actual (ground truth for a window, only set when a live
Predict upload had a usable "label" column) and AnomalyEvent.outcome /
detection_source, so a labeled Predict run can show which flagged windows
were correct (tp) vs false positives (fp), and -- new -- surface windows
that were truly anomalous but never flagged at all (fn / "missed"), which
previously had no row anywhere since AnomalyEvent only ever existed for
flagged windows. Purely additive; ordinary unlabeled predict uploads are
unaffected (both new columns stay null, detection_source defaults to
"flagged" matching today's only behavior).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2166e5001758'
down_revision: Union[str, None] = 'fe6e07ade488'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('predictions', sa.Column('actual', sa.Integer(), nullable=True))
    op.add_column('anomaly_events', sa.Column('outcome', sa.String(length=10), nullable=True))
    op.add_column(
        'anomaly_events',
        sa.Column('detection_source', sa.String(length=30), nullable=False, server_default='flagged'),
    )


def downgrade() -> None:
    op.drop_column('anomaly_events', 'detection_source')
    op.drop_column('anomaly_events', 'outcome')
    op.drop_column('predictions', 'actual')
