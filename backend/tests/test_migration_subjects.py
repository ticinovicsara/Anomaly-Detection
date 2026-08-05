"""Integration test for the actual Alembic migration (7c44300660ea), not a
simulation of it -- needs real Postgres since the migration's data backfill
is raw Postgres-dialect SQL (UPDATE ... FROM ...) that SQLite can't run.

Runs alembic as a subprocess with DATABASE_URL pointed at a disposable
throwaway database (created and dropped around the test), so it never
touches the real dev DB. Skipped automatically if Postgres isn't reachable,
so the rest of the suite stays docker-free.
"""
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine, text

BACKEND_DIR = Path(__file__).resolve().parent.parent
BASE_ADMIN_URL = "postgresql://anomaly:anomaly_dev@localhost:5433/postgres"
TEST_DB_NAME = f"anomaly_db_migtest_{uuid.uuid4().hex[:8]}"
TEST_DB_URL = f"postgresql://anomaly:anomaly_dev@localhost:5433/{TEST_DB_NAME}"

PRE_SUBJECTS_REVISION = "6fa0fc2c862a"


def _postgres_available() -> bool:
    try:
        engine = create_engine(BASE_ADMIN_URL, connect_args={"connect_timeout": 2})
        with engine.connect():
            return True
    except Exception:
        return False
    finally:
        engine.dispose() if "engine" in dir() else None


pytestmark = pytest.mark.skipif(
    not _postgres_available(), reason="Postgres not reachable on localhost:5433 (docker-compose up)"
)


def _run_alembic(*args: str) -> None:
    env = {**os.environ, "DATABASE_URL": TEST_DB_URL}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=str(BACKEND_DIR),
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"alembic {args} failed:\nstdout={result.stdout}\nstderr={result.stderr}"


@pytest.fixture
def migtest_db():
    admin_engine = create_engine(BASE_ADMIN_URL, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{TEST_DB_NAME}"'))
    admin_engine.dispose()
    try:
        yield TEST_DB_URL
    finally:
        admin_engine = create_engine(BASE_ADMIN_URL, isolation_level="AUTOCOMMIT")
        with admin_engine.connect() as conn:
            conn.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :name AND pid <> pg_backend_pid()"
                ),
                {"name": TEST_DB_NAME},
            )
            conn.execute(text(f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}"'))
        admin_engine.dispose()


def test_migration_backfills_default_subject_and_links_existing_rows(migtest_db):
    # 1. Bring the throwaway DB up to just before the subjects migration.
    _run_alembic("upgrade", PRE_SUBJECTS_REVISION)

    # 2. Seed pre-migration data directly (old schema: no subject_id yet).
    engine = create_engine(migtest_db)
    with engine.begin() as conn:
        user_id = conn.execute(
            text(
                "INSERT INTO users (email, password_hash, created_at) "
                "VALUES ('migtest@example.com', 'x', NOW()) RETURNING id"
            )
        ).scalar_one()
        dataset_id = conn.execute(
            text(
                "INSERT INTO datasets (user_id, name, file_path, n_rows, n_features, uploaded_at) "
                "VALUES (:uid, 'seed.csv', '/tmp/seed.csv', 100, 1, NOW()) RETURNING id"
            ),
            {"uid": user_id},
        ).scalar_one()
        model_id = conn.execute(
            text(
                "INSERT INTO models (user_id, dataset_id, algorithm, status, created_at) "
                "VALUES (:uid, :did, 'IF', 'ready', NOW()) RETURNING id"
            ),
            {"uid": user_id, "did": dataset_id},
        ).scalar_one()

    # 3. Run the actual migration under test.
    _run_alembic("upgrade", "head")

    # 4. Verify the backfill.
    with engine.connect() as conn:
        subjects = conn.execute(
            text("SELECT id, name, is_default, source_hint FROM subjects WHERE user_id = :uid"),
            {"uid": user_id},
        ).fetchall()
        assert len(subjects) == 1, "expected exactly one default Subject created for the user"
        subject_id, name, is_default, source_hint = subjects[0]
        assert name == "My data"
        assert is_default is True
        assert source_hint == "legacy_migration"

        dataset_subject = conn.execute(
            text("SELECT subject_id FROM datasets WHERE id = :id"), {"id": dataset_id}
        ).scalar_one()
        assert dataset_subject == subject_id, "existing dataset must be linked to the default Subject"

        model_subject = conn.execute(
            text("SELECT subject_id FROM models WHERE id = :id"), {"id": model_id}
        ).scalar_one()
        assert model_subject == subject_id, "existing model must be linked to the default Subject"

        # NOT NULL must actually be enforced post-backfill.
        inspector = sa.inspect(engine)
        cols = {c["name"]: c for c in inspector.get_columns("datasets")}
        assert cols["subject_id"]["nullable"] is False

    engine.dispose()

    # 5. Downgrade must cleanly remove what it added.
    _run_alembic("downgrade", PRE_SUBJECTS_REVISION)
    engine = create_engine(migtest_db)
    with engine.connect() as conn:
        inspector = sa.inspect(engine)
        assert "subjects" not in inspector.get_table_names()
        assert "subject_id" not in {c["name"] for c in inspector.get_columns("datasets")}
        assert "subject_id" not in {c["name"] for c in inspector.get_columns("models")}
    engine.dispose()
