"""add pre-retrain data review candidates

Revision ID: 10a442037017
Revises: 9cb333af0762
Create Date: 2026-08-13 00:00:00.000000

Adds the optional, off-by-default pre-retrain data review feature:
Subject.pre_retrain_check_enabled and the data_review_candidates table
(rows a throwaway IsolationForest flagged as worth a human glance before
they get baked into a retrain). Both additive -- existing Subjects default
to the feature disabled, so retrain behavior is unchanged unless a user
explicitly opts in.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '10a442037017'
down_revision: Union[str, None] = '9cb333af0762'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'subjects',
        sa.Column('pre_retrain_check_enabled', sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.create_table(
        'data_review_candidates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('subject_id', sa.Integer(), nullable=False),
        sa.Column('dataset_id', sa.Integer(), nullable=False),
        sa.Column('row_index', sa.Integer(), nullable=False),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('row_preview', sa.JSON(), nullable=True),
        sa.Column('label', sa.String(length=30), nullable=False, server_default='unlabeled'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['dataset_id'], ['datasets.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_data_review_candidates_subject_id'), 'data_review_candidates', ['subject_id'], unique=False
    )
    op.create_index(
        op.f('ix_data_review_candidates_dataset_id'), 'data_review_candidates', ['dataset_id'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_data_review_candidates_dataset_id'), table_name='data_review_candidates')
    op.drop_index(op.f('ix_data_review_candidates_subject_id'), table_name='data_review_candidates')
    op.drop_table('data_review_candidates')

    op.drop_column('subjects', 'pre_retrain_check_enabled')
