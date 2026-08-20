"""add threshold history

Revision ID: fe6e07ade488
Revises: 10a442037017
Create Date: 2026-08-20 00:00:00.000000

Adds an append-only threshold_history table so a z-multiplier edit
(settings.py::update_threshold currently overwrites the Threshold row in
place) or a retrain on new data (which does create a new Model+Threshold,
but wasn't surfaced as one unified per-Subject timeline) can both be
compared against what came before, instead of the user having to write
the old epsilon down somewhere themselves. Purely additive -- existing
Subjects/Models/Thresholds are unaffected until a new calibration or z
edit happens.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fe6e07ade488'
down_revision: Union[str, None] = '10a442037017'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'threshold_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('subject_id', sa.Integer(), nullable=False),
        sa.Column('model_id', sa.Integer(), nullable=False),
        sa.Column('mu', sa.Float(), nullable=False),
        sa.Column('sigma', sa.Float(), nullable=False),
        sa.Column('epsilon', sa.Float(), nullable=False),
        sa.Column('z_multiplier', sa.Float(), nullable=False),
        sa.Column('n_rows', sa.Integer(), nullable=True),
        sa.Column('source', sa.String(length=30), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['model_id'], ['models.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_threshold_history_subject_id'), 'threshold_history', ['subject_id'], unique=False
    )
    op.create_index(
        op.f('ix_threshold_history_model_id'), 'threshold_history', ['model_id'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_threshold_history_model_id'), table_name='threshold_history')
    op.drop_index(op.f('ix_threshold_history_subject_id'), table_name='threshold_history')
    op.drop_table('threshold_history')
