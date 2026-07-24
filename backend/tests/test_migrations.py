import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import JSON, MetaData, Table, create_engine, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.config import settings

BACKEND_ROOT = Path(__file__).resolve().parents[1]
POSTGRES_ADMIN_URL_ENV = "SLOVNIK_TEST_POSTGRES_ADMIN_URL"
LEGACY_WORD_ID = 1001
LEGACY_STRESS_MARKER = "ra-DI-ti"


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


def read_legacy_stress_marker(engine):
    with engine.connect() as connection:
        return connection.scalar(
            text("SELECT stress_marker FROM vocabulary_items WHERE id = :word_id"),
            {"word_id": LEGACY_WORD_ID},
        )


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
        finally:
            initial_engine.dispose()
        command.upgrade(config, "head")

        test_engine = create_engine(test_database_url)
        yield config, test_engine
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


def test_upgrade_adds_ai_vocabulary_persistence_schema(migration_database):
    _, engine = migration_database
    inspector = inspect(engine)
    table_names = inspector.get_table_names()

    assert "ai_vocabulary_generations" in table_names

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
    assert read_legacy_stress_marker(engine) == LEGACY_STRESS_MARKER
    assert_unique_generation_winner_survives(engine)


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
    assert read_legacy_stress_marker(engine) == LEGACY_STRESS_MARKER


def test_postgresql_migration_round_trip(postgresql_migration_database):
    config, engine = postgresql_migration_database
    inspector = inspect(engine)
    vocabulary_columns = {
        column["name"]: column for column in inspector.get_columns("vocabulary_items")
    }

    assert isinstance(vocabulary_columns["stress_pattern"]["type"], JSON)
    assert read_legacy_stress_marker(engine) == LEGACY_STRESS_MARKER
    assert_unique_generation_winner_survives(engine)

    engine.dispose()
    command.downgrade(config, "20260702_0001")

    inspector = inspect(engine)
    vocabulary_columns = {
        column["name"] for column in inspector.get_columns("vocabulary_items")
    }
    assert "stress_marker" in vocabulary_columns
    assert "stress_pattern" not in vocabulary_columns
    assert "ai_vocabulary_generations" not in inspector.get_table_names()
    assert read_legacy_stress_marker(engine) == LEGACY_STRESS_MARKER
