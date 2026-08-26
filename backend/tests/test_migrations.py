import json
import logging
import os
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import JSON, MetaData, Table, create_engine, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models import (
    AiVocabularyGenerationReservation,
    UserWordProgress,
)
from app.schemas import AiFillRequest
from app.services import ai_vocabulary_service, learning_service
from app.services.openai_vocabulary_client import OpenAiVocabularyResult, RawAiVocabulary

BACKEND_ROOT = Path(__file__).resolve().parents[1]
POSTGRES_ADMIN_URL_ENV = "SLOVNIK_TEST_POSTGRES_ADMIN_URL"
LEGACY_WORD_ID = 1001
LEGACY_STRESS_MARKER = "ra-DI-ti"
LEGACY_PROGRESS_ID = 2001
LEGACY_USER_ID = "legacy-learner"
DOMAIN_TABLES = {
    "language_lexical_units",
    "language_senses",
    "language_forms",
    "language_constructions",
    "curriculum_versions",
    "curriculum_nodes",
    "curriculum_prerequisites",
    "practice_runs",
    "activity_instances",
    "learning_events",
    "learner_target_states",
}
LEGACY_METADATA_TABLES = {
    "ai_vocabulary_generation_reservations",
    "ai_vocabulary_generations",
    "quiz_answers",
    "quiz_attempts",
    "user_profiles",
    "user_word_progress",
    "vocabulary_items",
}
DOMAIN_INDEX_DEFINITIONS = {
    "language_senses": {
        "ix_language_senses_lexical_unit": (("lexical_unit_id",), False),
    },
    "language_forms": {
        "ix_language_forms_lexical_unit": (("lexical_unit_id",), False),
    },
    "curriculum_versions": {
        "uq_curriculum_versions_one_active": (("curriculum_code",), True),
    },
    "curriculum_nodes": {
        "ix_curriculum_nodes_target": (("target_key",), False),
    },
    "practice_runs": {
        "ix_practice_runs_learner_status": (("learner_id", "status"), False),
    },
    "activity_instances": {
        "ix_activity_instances_retry": (("retry_of_activity_instance_id",), False),
    },
    "learning_events": {
        "ix_learning_events_learner_time": (("learner_id", "occurred_at"), False),
        "ix_learning_events_learner_target_time": (
            ("learner_id", "target_key", "occurred_at", "id"),
            False,
        ),
    },
    "learner_target_states": {
        "ix_learner_target_states_due": (("learner_id", "memory_due_at"), False),
    },
}
DOMAIN_TARGET_KEY = (
    "v1:sense:abcdef12-1234-5678-9234-567812345678:retrieve_form:written:"
    "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"
)


def build_alembic_config(database_url, monkeypatch):
    monkeypatch.setattr(settings, "database_url", database_url)
    return Config(BACKEND_ROOT / "alembic.ini")


def seed_legacy_vocabulary(engine):
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO vocabulary_items (
                    id,
                    serbian_cyrillic,
                    serbian_latin,
                    russian_translation,
                    cefr_level,
                    theme,
                    stress_marker
                ) VALUES (
                    :id,
                    :serbian_cyrillic,
                    :serbian_latin,
                    :russian_translation,
                    :cefr_level,
                    :theme,
                    :stress_marker
                )
                """
            ),
            {
                "id": LEGACY_WORD_ID,
                "serbian_cyrillic": "радити",
                "serbian_latin": "raditi",
                "russian_translation": "делать",
                "cefr_level": "A1",
                "theme": "work",
                "stress_marker": LEGACY_STRESS_MARKER,
            },
        )


def seed_legacy_progress(engine):
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO user_profiles (
                    user_id,
                    preferred_level,
                    daily_new_word_count,
                    ui_language
                ) VALUES (
                    :user_id,
                    :preferred_level,
                    :daily_new_word_count,
                    :ui_language
                )
                """
            ),
            {
                "user_id": LEGACY_USER_ID,
                "preferred_level": "A1",
                "daily_new_word_count": 5,
                "ui_language": "ru",
            },
        )
        connection.execute(
            text(
                """
                INSERT INTO user_word_progress (
                    id,
                    user_id,
                    word_id,
                    status,
                    correct_count,
                    incorrect_count,
                    is_weak
                ) VALUES (
                    :id,
                    :user_id,
                    :word_id,
                    :status,
                    :correct_count,
                    :incorrect_count,
                    :is_weak
                )
                """
            ),
            {
                "id": LEGACY_PROGRESS_ID,
                "user_id": LEGACY_USER_ID,
                "word_id": LEGACY_WORD_ID,
                "status": "reviewing",
                "correct_count": 3,
                "incorrect_count": 2,
                "is_weak": True,
            },
        )


def read_legacy_stress_marker(engine):
    with engine.connect() as connection:
        return connection.scalar(
            text("SELECT stress_marker FROM vocabulary_items WHERE id = :word_id"),
            {"word_id": LEGACY_WORD_ID},
        )


def read_legacy_progress(engine, *, include_schedule):
    schedule_columns = (
        ", next_review_at, review_interval_days, review_streak"
        if include_schedule
        else ""
    )
    with engine.connect() as connection:
        return connection.execute(
            text(
                f"""
                SELECT status, correct_count, incorrect_count, is_weak
                    {schedule_columns}
                FROM user_word_progress
                WHERE id = :progress_id
                """
            ),
            {"progress_id": LEGACY_PROGRESS_ID},
        ).mappings().one()


def read_seeded_legacy_snapshot(engine):
    with engine.connect() as connection:
        vocabulary = connection.execute(
            text("SELECT * FROM vocabulary_items WHERE id = :row_id"),
            {"row_id": LEGACY_WORD_ID},
        ).mappings().one()
        profile = connection.execute(
            text("SELECT * FROM user_profiles WHERE user_id = :user_id"),
            {"user_id": LEGACY_USER_ID},
        ).mappings().one()
        progress = connection.execute(
            text("SELECT * FROM user_word_progress WHERE id = :row_id"),
            {"row_id": LEGACY_PROGRESS_ID},
        ).mappings().one()
    return {
        "vocabulary": dict(vocabulary),
        "profile": dict(profile),
        "progress": dict(progress),
    }


def assert_domain_schema(engine):
    inspector = inspect(engine)
    assert DOMAIN_TABLES <= set(inspector.get_table_names())
    for table_name, definitions in DOMAIN_INDEX_DEFINITIONS.items():
        indexes = {
            index["name"]: index for index in inspector.get_indexes(table_name)
        }
        for index_name, (columns, unique) in definitions.items():
            assert tuple(indexes[index_name]["column_names"]) == columns
            assert bool(indexes[index_name]["unique"]) is unique
        if table_name == "curriculum_versions":
            dialect_options = indexes[
                "uq_curriculum_versions_one_active"
            ].get("dialect_options", {})
            predicate = str(
                dialect_options[f"{engine.dialect.name}_where"]
            )
            normalized_predicate = (
                predicate.lower()
                .replace("::text", "")
                .replace("(", "")
                .replace(")", "")
                .replace('"', "")
            )
            assert " ".join(normalized_predicate.split()) == "status = 'active'"

    expected_composite_foreign_keys = {
        "curriculum_prerequisites": {
            (
                ("curriculum_version_id", "prerequisite_node_id"),
                "curriculum_nodes",
                ("curriculum_version_id", "id"),
            ),
            (
                ("curriculum_version_id", "dependent_node_id"),
                "curriculum_nodes",
                ("curriculum_version_id", "id"),
            ),
        },
        "activity_instances": {
            (
                ("practice_run_id", "selection_policy_version"),
                "practice_runs",
                ("id", "selection_policy_version"),
            ),
            (
                (
                    "practice_run_id",
                    "retry_of_activity_instance_id",
                    "target_key",
                ),
                "activity_instances",
                ("practice_run_id", "id", "target_key"),
            ),
        },
        "learning_events": {
            (
                ("practice_run_id", "learner_id"),
                "practice_runs",
                ("id", "learner_id"),
            ),
            (
                (
                    "practice_run_id",
                    "activity_instance_id",
                    "target_key",
                    "activity_kind",
                ),
                "activity_instances",
                ("practice_run_id", "id", "target_key", "activity_kind"),
            ),
        },
    }
    for table_name, expected in expected_composite_foreign_keys.items():
        actual = {
            (
                tuple(foreign_key["constrained_columns"]),
                foreign_key["referred_table"],
                tuple(foreign_key["referred_columns"]),
            )
            for foreign_key in inspector.get_foreign_keys(table_name)
        }
        assert expected <= actual

    state_unique_constraints = {
        constraint["name"]: tuple(constraint["column_names"])
        for constraint in inspector.get_unique_constraints("learner_target_states")
    }
    assert state_unique_constraints[
        "uq_learner_target_states_learner_target"
    ] == ("learner_id", "target_key")


def assert_domain_constraints_enforced(engine):
    if engine.dialect.name == "sqlite":
        with engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO curriculum_versions (
                    id, curriculum_code, version_number, status, created_at
                ) VALUES (
                    '10000000-0000-4000-8000-000000000001',
                    'constraint-checks', 1, 'draft', '2026-08-26 00:00:00+00:00'
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO curriculum_versions (
                    id, curriculum_code, version_number, status, created_at
                ) VALUES (
                    '10000000-0000-4000-8000-000000000005',
                    'constraint-checks', 2, 'draft', '2026-08-26 00:00:00+00:00'
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO curriculum_versions (
                    id, curriculum_code, version_number, status,
                    created_at, published_at
                ) VALUES (
                    '10000000-0000-4000-8000-000000000002',
                    'one-active', 1, 'active',
                    '2026-08-26 00:00:00+00:00', '2026-08-26 00:00:00+00:00'
                )
                """
            )
        )

    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO curriculum_versions (
                        id, curriculum_code, version_number, status, created_at
                    ) VALUES (
                        '10000000-0000-4000-8000-000000000003',
                        'bad-lifecycle', 1, 'active', '2026-08-26 00:00:00+00:00'
                    )
                    """
                )
            )

    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO curriculum_versions (
                        id, curriculum_code, version_number, status,
                        created_at, published_at
                    ) VALUES (
                        '10000000-0000-4000-8000-000000000004',
                        'one-active', 2, 'active',
                        '2026-08-26 00:00:00+00:00',
                        '2026-08-26 00:00:00+00:00'
                    )
                    """
                )
            )

    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO curriculum_nodes (
                        id, curriculum_version_id, target_key, target_kind,
                        target_id, capability, modality, condition_payload,
                        priority, outcome_code
                    ) VALUES (
                        '20000000-0000-4000-8000-000000000001',
                        '10000000-0000-4000-8000-000000000001',
                        :target_key, 'sense',
                        'abcdef12-1234-5678-9234-567812345678',
                        'retrieve_form', 'written', '{}', 101, 'A1.bad'
                    )
                    """
                ),
                {"target_key": DOMAIN_TARGET_KEY},
            )

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO practice_runs (
                    id, learner_id, status, selection_policy_version, started_at
                ) VALUES (
                    '30000000-0000-4000-8000-000000000001',
                    :learner_id, 'active', 'policy-v1',
                    '2026-08-26 00:00:00+00:00'
                )
                """
            ),
            {"learner_id": LEGACY_USER_ID},
        )

    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO activity_instances (
                        id, practice_run_id, target_key, learning_intent,
                        activity_kind, operation, sequence_number,
                        attempt_number, spec_payload, selection_policy_version,
                        selection_reason_payload, generator_kind,
                        generator_version, status, selected_at
                    ) VALUES (
                        '40000000-0000-4000-8000-000000000001',
                        '30000000-0000-4000-8000-000000000001',
                        :target_key, 'review', 'exposure', NULL, 1, 1,
                        '{}', 'policy-v2', '[]', 'curated', 'v1', 'pending',
                        '2026-08-26 00:00:00+00:00'
                    )
                    """
                ),
                {"target_key": DOMAIN_TARGET_KEY},
            )


def assert_concurrent_progress_state_creation(engine):
    from sqlalchemy import func
    from sqlalchemy.orm import Session

    from app.domain_models.progress import LearnerTargetStateModel
    from app.repositories.progress import ProgressRepository

    start = threading.Barrier(2)

    class BarrierRepository(ProgressRepository):
        def __init__(self, session):
            super().__init__(session)
            self._first_lookup = True

        def _find_state_row(self, learner_id, target_key):
            row = super()._find_state_row(learner_id, target_key)
            if self._first_lookup:
                self._first_lookup = False
                assert row is None
                start.wait(timeout=10)
            return row

    def ensure(state_id):
        with Session(engine) as session:
            state = BarrierRepository(session).ensure_state(
                learner_id=LEGACY_USER_ID,
                target_key=DOMAIN_TARGET_KEY,
                state_id=state_id,
                updated_at=datetime(2026, 8, 26, tzinfo=timezone.utc),
            )
            session.commit()
            return state.state_id

    state_ids = (
        "50000000-0000-4000-8000-000000000001",
        "50000000-0000-4000-8000-000000000002",
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(ensure, state_id) for state_id in state_ids]
        recovered_ids = [future.result(timeout=30) for future in futures]

    with Session(engine) as session:
        persisted_ids = session.scalars(select(LearnerTargetStateModel.id)).all()
        row_count = session.scalar(
            select(func.count()).select_from(LearnerTargetStateModel)
        )
    assert row_count == 1
    assert recovered_ids == [persisted_ids[0], persisted_ids[0]]


def assert_active_recall_schedule_schema(engine):
    inspector = inspect(engine)
    progress_columns = {
        column["name"]: column
        for column in inspector.get_columns("user_word_progress")
    }
    progress_indexes = {
        index["name"] for index in inspector.get_indexes("user_word_progress")
    }

    assert progress_columns["next_review_at"]["nullable"] is True
    assert progress_columns["review_interval_days"]["nullable"] is False
    assert progress_columns["review_streak"]["nullable"] is False
    for counter_name in ("review_interval_days", "review_streak"):
        default = str(progress_columns[counter_name]["default"]).split("::", 1)[0]
        assert default.strip("'()") == "0"
    assert "ix_user_word_progress_next_review_at" in progress_indexes


def assert_active_recall_schedule_absent(engine):
    inspector = inspect(engine)
    progress_columns = {
        column["name"] for column in inspector.get_columns("user_word_progress")
    }
    progress_indexes = {
        index["name"] for index in inspector.get_indexes("user_word_progress")
    }

    assert {
        "next_review_at",
        "review_interval_days",
        "review_streak",
    }.isdisjoint(progress_columns)
    assert "ix_user_word_progress_next_review_at" not in progress_indexes


def assert_unique_generation_winner_survives(engine):
    generation_table = Table(
        "ai_vocabulary_generations",
        MetaData(),
        autoload_with=engine,
    )
    winner = {
        "source_word": "raditi",
        "normalized_source_word": "raditi",
        "generated_payload": {"serbian_latin": "raditi"},
        "missing_required_fields": [],
        "model": "test-model",
        "prompt_version": "v1",
    }

    with engine.begin() as connection:
        connection.execute(generation_table.insert(), winner)

    with engine.connect() as connection:
        transaction = connection.begin()
        with pytest.raises(IntegrityError):
            connection.execute(
                generation_table.insert(),
                {**winner, "source_word": "Raditi"},
            )
        transaction.rollback()

    with engine.connect() as connection:
        saved_rows = connection.execute(
            select(
                generation_table.c.source_word,
                generation_table.c.normalized_source_word,
                generation_table.c.generated_payload,
            )
        ).all()

    assert saved_rows == [("raditi", "raditi", {"serbian_latin": "raditi"})]


@pytest.fixture()
def migration_database(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'migration.db'}"
    config = build_alembic_config(database_url, monkeypatch)

    command.upgrade(config, "20260702_0001")
    initial_engine = create_engine(database_url)
    seed_legacy_vocabulary(initial_engine)
    seed_legacy_progress(initial_engine)
    initial_engine.dispose()
    command.upgrade(config, "head")

    engine = create_engine(database_url)
    try:
        yield config, engine
    finally:
        engine.dispose()


@pytest.fixture()
def postgresql_migration_database(monkeypatch):
    admin_url_value = os.getenv(POSTGRES_ADMIN_URL_ENV)
    if not admin_url_value:
        pytest.skip(f"{POSTGRES_ADMIN_URL_ENV} is not configured")

    admin_url = make_url(admin_url_value)
    if admin_url.get_backend_name() != "postgresql":
        raise ValueError(f"{POSTGRES_ADMIN_URL_ENV} must use PostgreSQL")

    database_name = f"slovnik_migration_test_{uuid4().hex}"
    test_database_url = admin_url.set(database=database_name)
    if test_database_url == make_url(settings.database_url):
        pytest.fail("Refusing to run migration tests against DATABASE_URL")

    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    database_created = False
    test_engine = None
    try:
        with admin_engine.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{database_name}"'))
        database_created = True

        database_url = test_database_url.render_as_string(hide_password=False)
        config = build_alembic_config(database_url, monkeypatch)
        command.upgrade(config, "20260702_0001")
        initial_engine = create_engine(test_database_url)
        try:
            seed_legacy_vocabulary(initial_engine)
            seed_legacy_progress(initial_engine)
        finally:
            initial_engine.dispose()
        command.upgrade(config, "20260725_0004")
        snapshot_engine = create_engine(test_database_url)
        try:
            legacy_snapshot = read_seeded_legacy_snapshot(snapshot_engine)
        finally:
            snapshot_engine.dispose()
        command.upgrade(config, "head")

        test_engine = create_engine(test_database_url)
        yield config, test_engine, legacy_snapshot
    finally:
        if test_engine is not None:
            test_engine.dispose()
        if database_created:
            with admin_engine.connect() as connection:
                connection.execute(
                    text(
                        """
                        SELECT pg_terminate_backend(pid)
                        FROM pg_stat_activity
                        WHERE datname = :database_name
                          AND pid <> pg_backend_pid()
                        """
                    ),
                    {"database_name": database_name},
                )
                connection.execute(text(f'DROP DATABASE "{database_name}"'))
        admin_engine.dispose()


def advance_postgresql_fixture_without_skip(monkeypatch):
    fixture_generator = postgresql_migration_database.__wrapped__(monkeypatch)
    try:
        return next(fixture_generator)
    except pytest.skip.Exception as error:
        raise AssertionError("A configured PostgreSQL target must not skip") from error


def test_postgresql_migration_target_skips_without_admin_url(monkeypatch):
    monkeypatch.delenv(POSTGRES_ADMIN_URL_ENV, raising=False)
    fixture_generator = postgresql_migration_database.__wrapped__(monkeypatch)

    with pytest.raises(pytest.skip.Exception):
        next(fixture_generator)


def test_domain_metadata_registry_creates_all_sql_01_tables():
    expected_modules = [
        "app.domain_models.catalog",
        "app.domain_models.curriculum",
        "app.domain_models.practice",
        "app.domain_models.progress",
    ]
    script = """
import json
import sys
from app.db import Base, load_model_registry

def snapshot():
    return {
        "modules": sorted(
            name for name in sys.modules
            if name.startswith("app.domain_models.")
        ),
        "tables": sorted(Base.metadata.tables),
    }

before = snapshot()
load_model_registry()
first = snapshot()
load_model_registry()
print(json.dumps({"before": before, "first": first, "second": snapshot()}))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=BACKEND_ROOT,
        env={
            **os.environ,
            "EDITOR_PASSWORD": "test-editor-password",
            "ENVIRONMENT": "test",
            "PYTHONPATH": str(BACKEND_ROOT),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    snapshot = json.loads(result.stdout)
    expected = {
        "modules": expected_modules,
        "tables": sorted(LEGACY_METADATA_TABLES | DOMAIN_TABLES),
    }
    assert snapshot == {
        "before": {"modules": [], "tables": []},
        "first": expected,
        "second": expected,
    }

    from app.db import Base, load_model_registry

    load_model_registry()
    assert set(Base.metadata.tables) == LEGACY_METADATA_TABLES | DOMAIN_TABLES

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    assert DOMAIN_TABLES <= set(inspect(engine).get_table_names())
    Base.metadata.drop_all(engine)
    assert not inspect(engine).get_table_names()
    engine.dispose()


def test_domain_root_context_exports_are_lazy_and_cached():
    script = """
import json
import sys
import app.domain as domain

context_names = ["catalog", "curriculum", "practice", "progress"]

def loaded_contexts():
    return sorted(
        name for name in sys.modules
        if name in {f"app.domain.{context}" for context in context_names}
    )

states = [loaded_contexts()]
cached = []
for context_name in context_names:
    first = getattr(domain, context_name)
    cached.append(first is getattr(domain, context_name))
    states.append(loaded_contexts())

try:
    getattr(domain, "unknown_context")
except AttributeError:
    unknown_rejected = True
else:
    unknown_rejected = False

print(json.dumps({
    "cached": cached,
    "exports": sorted(set(domain.__all__) & set(context_names)),
    "states": states,
    "unknown_rejected": unknown_rejected,
}))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=BACKEND_ROOT,
        env={
            **os.environ,
            "EDITOR_PASSWORD": "test-editor-password",
            "ENVIRONMENT": "test",
            "PYTHONPATH": str(BACKEND_ROOT),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "cached": [True, True, True, True],
        "exports": ["catalog", "curriculum", "practice", "progress"],
        "states": [
            [],
            ["app.domain.catalog"],
            ["app.domain.catalog", "app.domain.curriculum"],
            ["app.domain.catalog", "app.domain.curriculum", "app.domain.practice"],
            [
                "app.domain.catalog",
                "app.domain.curriculum",
                "app.domain.practice",
                "app.domain.progress",
            ],
        ],
        "unknown_rejected": True,
    }


def test_domain_migration_round_trip_preserves_legacy_rows(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'domain-round-trip.db'}"
    config = build_alembic_config(database_url, monkeypatch)
    command.upgrade(config, "20260725_0004")
    engine = create_engine(database_url)
    seed_legacy_vocabulary(engine)
    seed_legacy_progress(engine)
    legacy_tables = set(inspect(engine).get_table_names())
    legacy_snapshot = read_seeded_legacy_snapshot(engine)
    engine.dispose()

    command.upgrade(config, "20260826_0005")
    assert set(inspect(engine).get_table_names()) == legacy_tables | DOMAIN_TABLES
    assert_domain_schema(engine)
    assert_domain_constraints_enforced(engine)
    assert read_seeded_legacy_snapshot(engine) == legacy_snapshot
    engine.dispose()

    command.downgrade(config, "20260725_0004")
    assert set(inspect(engine).get_table_names()) == legacy_tables
    assert read_seeded_legacy_snapshot(engine) == legacy_snapshot
    engine.dispose()


def test_postgresql_migration_target_rejects_invalid_admin_url(monkeypatch):
    monkeypatch.setenv(POSTGRES_ADMIN_URL_ENV, "://")

    with pytest.raises(SQLAlchemyError):
        advance_postgresql_fixture_without_skip(monkeypatch)


def test_postgresql_migration_target_rejects_non_postgresql_url(monkeypatch):
    monkeypatch.setenv(POSTGRES_ADMIN_URL_ENV, "sqlite:///:memory:")

    with pytest.raises(ValueError, match="must use PostgreSQL"):
        advance_postgresql_fixture_without_skip(monkeypatch)


def test_postgresql_migration_target_propagates_engine_errors(monkeypatch):
    monkeypatch.setenv(
        POSTGRES_ADMIN_URL_ENV,
        "postgresql+psycopg://test:test@localhost/postgres",
    )

    def fail_create_engine(*args, **kwargs):
        raise SQLAlchemyError("unreachable")

    monkeypatch.setitem(globals(), "create_engine", fail_create_engine)

    with pytest.raises(SQLAlchemyError, match="unreachable"):
        advance_postgresql_fixture_without_skip(monkeypatch)


def test_postgresql_migration_target_propagates_create_database_errors(monkeypatch):
    monkeypatch.setenv(
        POSTGRES_ADMIN_URL_ENV,
        "postgresql+psycopg://test:test@localhost/postgres",
    )

    class FailingConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def execute(self, statement):
            raise SQLAlchemyError("permission denied")

    class FailingAdminEngine:
        def connect(self):
            return FailingConnection()

        def dispose(self):
            pass

    monkeypatch.setitem(
        globals(),
        "create_engine",
        lambda *args, **kwargs: FailingAdminEngine(),
    )

    with pytest.raises(SQLAlchemyError, match="permission denied"):
        advance_postgresql_fixture_without_skip(monkeypatch)


def test_migrations_do_not_disable_existing_application_loggers(tmp_path, monkeypatch):
    application_logger = logging.getLogger("app.services.openai_vocabulary_client")
    application_logger.disabled = False
    database_url = f"sqlite:///{tmp_path / 'logging.db'}"

    command.upgrade(build_alembic_config(database_url, monkeypatch), "head")

    assert not application_logger.disabled


def test_upgrade_adds_ai_vocabulary_persistence_schema(migration_database):
    _, engine = migration_database
    inspector = inspect(engine)
    table_names = inspector.get_table_names()

    assert "ai_vocabulary_generations" in table_names
    assert "ai_vocabulary_generation_reservations" in table_names

    vocabulary_columns = {
        column["name"]: column for column in inspector.get_columns("vocabulary_items")
    }
    generation_columns = {
        column["name"]
        for column in inspector.get_columns("ai_vocabulary_generations")
    }
    unique_columns = {
        tuple(constraint["column_names"])
        for constraint in inspector.get_unique_constraints("ai_vocabulary_generations")
    }
    unique_indexes = {
        tuple(index["column_names"])
        for index in inspector.get_indexes("ai_vocabulary_generations")
        if index["unique"]
    }
    reservation_columns = {
        column["name"]
        for column in inspector.get_columns(
            "ai_vocabulary_generation_reservations"
        )
    }
    reservation_primary_key = inspector.get_pk_constraint(
        "ai_vocabulary_generation_reservations"
    )

    assert "stress_pattern" in vocabulary_columns
    assert isinstance(vocabulary_columns["stress_pattern"]["type"], JSON)
    assert {
        "id",
        "source_word",
        "normalized_source_word",
        "generated_payload",
        "missing_required_fields",
        "model",
        "prompt_version",
        "created_at",
        "updated_at",
    } == generation_columns
    assert ("normalized_source_word",) in unique_columns | unique_indexes
    assert {
        "normalized_source_word",
        "owner_token",
        "expires_at",
        "created_at",
        "updated_at",
    } == reservation_columns
    assert reservation_primary_key["name"] == (
        "pk_ai_vocabulary_generation_reservations"
    )
    assert reservation_primary_key["constrained_columns"] == [
        "normalized_source_word"
    ]
    assert read_legacy_stress_marker(engine) == LEGACY_STRESS_MARKER
    assert_unique_generation_winner_survives(engine)


def test_upgrade_adds_active_recall_schedule_and_preserves_legacy_progress(
    migration_database,
):
    _, engine = migration_database

    assert_active_recall_schedule_schema(engine)
    assert dict(read_legacy_progress(engine, include_schedule=True)) == {
        "status": "reviewing",
        "correct_count": 3,
        "incorrect_count": 2,
        "is_weak": True,
        "next_review_at": None,
        "review_interval_days": 0,
        "review_streak": 0,
    }


def test_upgrade_from_existing_ai_fill_revision_adds_reservations(
    tmp_path,
    monkeypatch,
):
    database_url = f"sqlite:///{tmp_path / 'upgrade-from-0002.db'}"
    config = build_alembic_config(database_url, monkeypatch)

    command.upgrade(config, "20260724_0002")
    engine = create_engine(database_url)
    try:
        assert (
            "ai_vocabulary_generation_reservations"
            not in inspect(engine).get_table_names()
        )

        engine.dispose()
        command.upgrade(config, "head")

        assert (
            "ai_vocabulary_generation_reservations"
            in inspect(engine).get_table_names()
        )
    finally:
        engine.dispose()


def test_downgrade_removes_active_recall_schedule(migration_database):
    config, engine = migration_database

    engine.dispose()
    command.downgrade(config, "20260725_0003")

    assert_active_recall_schedule_absent(engine)
    assert dict(read_legacy_progress(engine, include_schedule=False)) == {
        "status": "reviewing",
        "correct_count": 3,
        "incorrect_count": 2,
        "is_weak": True,
    }


def test_downgrade_to_initial_schema_preserves_legacy_stress(migration_database):
    config, engine = migration_database

    assert read_legacy_stress_marker(engine) == LEGACY_STRESS_MARKER

    engine.dispose()
    command.downgrade(config, "20260702_0001")

    inspector = inspect(engine)
    vocabulary_columns = {
        column["name"] for column in inspector.get_columns("vocabulary_items")
    }

    assert "vocabulary_items" in inspector.get_table_names()
    assert "stress_marker" in vocabulary_columns
    assert "stress_pattern" not in vocabulary_columns
    assert "ai_vocabulary_generations" not in inspector.get_table_names()
    assert (
        "ai_vocabulary_generation_reservations"
        not in inspector.get_table_names()
    )
    assert read_legacy_stress_marker(engine) == LEGACY_STRESS_MARKER


def test_postgresql_migration_round_trip(postgresql_migration_database):
    config, engine, legacy_snapshot = postgresql_migration_database
    inspector = inspect(engine)
    vocabulary_columns = {
        column["name"]: column for column in inspector.get_columns("vocabulary_items")
    }

    assert_domain_schema(engine)
    assert_domain_constraints_enforced(engine)
    assert_concurrent_progress_state_creation(engine)
    assert isinstance(vocabulary_columns["stress_pattern"]["type"], JSON)
    assert read_legacy_stress_marker(engine) == LEGACY_STRESS_MARKER
    assert_unique_generation_winner_survives(engine)
    assert_active_recall_schedule_schema(engine)
    assert dict(read_legacy_progress(engine, include_schedule=True)) == {
        "status": "reviewing",
        "correct_count": 3,
        "incorrect_count": 2,
        "is_weak": True,
        "next_review_at": None,
        "review_interval_days": 0,
        "review_streak": 0,
    }
    assert read_seeded_legacy_snapshot(engine) == legacy_snapshot

    engine.dispose()
    command.downgrade(config, "20260725_0004")

    assert DOMAIN_TABLES.isdisjoint(inspect(engine).get_table_names())
    assert_active_recall_schedule_schema(engine)
    assert read_seeded_legacy_snapshot(engine) == legacy_snapshot

    engine.dispose()
    command.downgrade(config, "20260725_0003")

    assert_active_recall_schedule_absent(engine)
    assert dict(read_legacy_progress(engine, include_schedule=False)) == {
        "status": "reviewing",
        "correct_count": 3,
        "incorrect_count": 2,
        "is_weak": True,
    }

    engine.dispose()
    command.downgrade(config, "20260702_0001")

    inspector = inspect(engine)
    vocabulary_columns = {
        column["name"] for column in inspector.get_columns("vocabulary_items")
    }
    assert "stress_marker" in vocabulary_columns
    assert "stress_pattern" not in vocabulary_columns
    assert "ai_vocabulary_generations" not in inspector.get_table_names()
    assert (
        "ai_vocabulary_generation_reservations"
        not in inspector.get_table_names()
    )
    assert read_legacy_stress_marker(engine) == LEGACY_STRESS_MARKER


def test_postgresql_expired_reservation_has_one_takeover_and_provider_call(
    postgresql_migration_database,
    monkeypatch,
):
    _, engine, _ = postgresql_migration_database
    SessionFactory = sessionmaker(bind=engine)
    expired_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    with SessionFactory() as session:
        session.add(
            AiVocabularyGenerationReservation(
                normalized_source_word="uciti",
                owner_token="crashed-owner",
                expires_at=expired_at,
            )
        )
        session.commit()

    monkeypatch.setattr(
        ai_vocabulary_service,
        "settings",
        SimpleNamespace(openai_model="test-model", openai_timeout_seconds=0.05),
    )
    monkeypatch.setattr(
        ai_vocabulary_service,
        "RESERVATION_LEASE_GRACE_SECONDS",
        0.05,
    )
    monkeypatch.setattr(ai_vocabulary_service, "RESERVATION_POLL_SECONDS", 0.01)
    provider_entered = threading.Event()
    second_acquisition_failed = threading.Event()
    release_provider = threading.Event()
    provider_lock = threading.Lock()
    provider_call_count = 0
    original_acquire = ai_vocabulary_service._try_acquire_reservation
    first_request_ident = None

    def tracked_acquire(*args, **kwargs):
        acquired = original_acquire(*args, **kwargs)
        if threading.get_ident() != first_request_ident and not acquired:
            second_acquisition_failed.set()
        return acquired

    monkeypatch.setattr(
        ai_vocabulary_service,
        "_try_acquire_reservation",
        tracked_acquire,
    )

    def generate(_):
        nonlocal provider_call_count
        with provider_lock:
            provider_call_count += 1
        provider_entered.set()
        assert release_provider.wait(timeout=3)
        return OpenAiVocabularyResult(
            payload=RawAiVocabulary.model_construct(
                serbian_cyrillic="учити",
                serbian_latin="uciti",
                russian_translation="учить",
                cefr_level="A1",
                theme="education",
            ),
            request_id="postgres-concurrency",
        )

    def fill(*, first_request=False):
        nonlocal first_request_ident
        if first_request:
            first_request_ident = threading.get_ident()
        with SessionFactory() as session:
            return ai_vocabulary_service.fill_vocabulary(
                session,
                AiFillRequest(source_word="uciti"),
                generate=generate,
            )

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(fill, first_request=True)
            assert provider_entered.wait(timeout=3)
            threading.Event().wait(0.12)
            second = executor.submit(fill)
            assert second_acquisition_failed.wait(timeout=3)
            assert provider_call_count == 1
            release_provider.set()
            results = [first.result(timeout=3), second.result(timeout=3)]
    finally:
        release_provider.set()

    assert provider_call_count == 1
    assert {result.source for result in results} == {"openai", "store"}
    with SessionFactory() as session:
        assert session.get(AiVocabularyGenerationReservation, "uciti") is None


def test_postgresql_concurrent_review_grades_accept_exactly_one(
    postgresql_migration_database,
):
    _, engine, _ = postgresql_migration_database
    SessionFactory = sessionmaker(bind=engine)
    with SessionFactory() as session:
        progress = session.get(UserWordProgress, LEGACY_PROGRESS_ID)
        progress.status = "reviewing"
        progress.is_weak = False
        progress.weak_since = None
        progress.next_review_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        session.commit()

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE FUNCTION delay_active_recall_update()
                RETURNS trigger AS $$
                BEGIN
                    PERFORM pg_sleep(0.25);
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TRIGGER delay_active_recall_update
                BEFORE UPDATE OF next_review_at ON user_word_progress
                FOR EACH ROW
                EXECUTE FUNCTION delay_active_recall_update()
                """
            )
        )

    start = threading.Barrier(2)

    def grade():
        with SessionFactory() as session:
            start.wait(timeout=3)
            try:
                learning_service.grade_review(
                    session,
                    LEGACY_USER_ID,
                    LEGACY_WORD_ID,
                    "good",
                )
            except ValueError as error:
                session.rollback()
                return "rejected", str(error)
            return "success", None

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(grade) for _ in range(2)]
        results = [future.result(timeout=5) for future in futures]

    assert sorted(result[0] for result in results) == ["rejected", "success"]
    rejection = next(result for result in results if result[0] == "rejected")
    assert rejection[1] == "Word is not currently due for review"
