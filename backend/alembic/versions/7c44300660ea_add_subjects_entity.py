"""add subjects entity

Revision ID: 7c44300660ea
Revises: 6fa0fc2c862a
Create Date: 2026-08-05 15:54:40.826203

Introduces the Subject entity (the thing personalization is calibrated
for -- a patient, a card, a service -- separate from User). Existing
datasets and models are backfilled onto a per-user default "My data"
Subject so nothing already in the database is orphaned.

Sequenced deliberately to be safe against non-empty tables: the new
subject_id columns are added NULLABLE first, backfilled via raw SQL,
then tightened to NOT NULL -- a straight NOT NULL column add would
fail outright against any existing row.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c44300660ea'
down_revision: Union[str, None] = '6fa0fc2c862a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. New subjects table
    op.create_table(
        'subjects',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('source_hint', sa.String(length=255), nullable=True),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'name', name='uq_subjects_user_name'),
    )
    op.create_index(op.f('ix_subjects_user_id'), 'subjects', ['user_id'], unique=False)

    # 2. subject_id columns added NULLABLE first (backfilled below, then tightened)
    op.add_column('datasets', sa.Column('subject_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_datasets_subject_id', 'datasets', 'subjects', ['subject_id'], ['id'], ondelete='CASCADE'
    )
    op.create_index(op.f('ix_datasets_subject_id'), 'datasets', ['subject_id'], unique=False)

    op.add_column('models', sa.Column('subject_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_models_subject_id', 'models', 'subjects', ['subject_id'], ['id'], ondelete='CASCADE'
    )
    op.create_index(op.f('ix_models_subject_id'), 'models', ['subject_id'], unique=False)

    # 3. New Model columns -- safe to add directly as NOT NULL, server_default
    #    backfills existing rows in the same statement.
    op.add_column(
        'models',
        sa.Column('selection_mode', sa.String(length=20), nullable=False, server_default='auto'),
    )
    op.add_column(
        'models',
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    # 4. Data migration: one default "My data" Subject per existing user,
    #    then link every existing dataset/model row to its owner's default.
    op.execute(
        """
        INSERT INTO subjects (user_id, name, description, source_hint, is_default, created_at)
        SELECT id, 'My data', NULL, 'legacy_migration', true, NOW()
        FROM users
        WHERE NOT EXISTS (
            SELECT 1 FROM subjects WHERE subjects.user_id = users.id AND subjects.is_default = true
        )
        """
    )
    op.execute(
        """
        UPDATE datasets
        SET subject_id = subjects.id
        FROM subjects
        WHERE datasets.subject_id IS NULL
          AND subjects.user_id = datasets.user_id
          AND subjects.is_default = true
        """
    )
    op.execute(
        """
        UPDATE models
        SET subject_id = subjects.id
        FROM subjects
        WHERE models.subject_id IS NULL
          AND subjects.user_id = models.user_id
          AND subjects.is_default = true
        """
    )

    # 5. Now safe to tighten -- every row has been backfilled.
    op.alter_column('datasets', 'subject_id', nullable=False)
    op.alter_column('models', 'subject_id', nullable=False)


def downgrade() -> None:
    op.alter_column('models', 'subject_id', nullable=True)
    op.alter_column('datasets', 'subject_id', nullable=True)

    op.drop_column('models', 'is_active')
    op.drop_column('models', 'selection_mode')

    op.drop_index(op.f('ix_models_subject_id'), table_name='models')
    op.drop_constraint('fk_models_subject_id', 'models', type_='foreignkey')
    op.drop_column('models', 'subject_id')

    op.drop_index(op.f('ix_datasets_subject_id'), table_name='datasets')
    op.drop_constraint('fk_datasets_subject_id', 'datasets', type_='foreignkey')
    op.drop_column('datasets', 'subject_id')

    op.drop_index(op.f('ix_subjects_user_id'), table_name='subjects')
    op.drop_table('subjects')
