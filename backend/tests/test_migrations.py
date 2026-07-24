import json
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from app.config import settings

BACKEND_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def migration_database(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'migration.db'}"
    monkeypatch.setattr(settings, "database_url", database_url)
    config = Config(BACKEND_ROOT / "alembic.ini")

    command.upgrade(config, "20260702_0001")
    command.upgrade(config, "head")

    engine = create_engine(database_url)
    try:
        yield config, engine
    finally:
        engine.dispose()


def test_upgrade_adds_ai_vocabulary_persistence_schema(migration_database):
    _, engine = migration_database
    inspector = inspect(engine)

    vocabulary_columns = {
        column["name"] for column in inspector.get_columns("vocabulary_items")
    }
    generation_columns = {
        column["name"] for column in inspector.get_columns("ai_vocabulary_generations")
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
    assert "ai_vocabulary_generations" in inspector.get_table_names()
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

    insert_generation = text(
        """
        INSERT INTO ai_vocabulary_generations (
            source_word,
            normalized_source_word,
            generated_payload,
            missing_required_fields,
            model,
            prompt_version
        ) VALUES (
            :source_word,
            :normalized_source_word,
            :generated_payload,
            :missing_required_fields,
            :model,
            :prompt_version
        )
        """
    )
    values = {
        "source_word": "raditi",
        "normalized_source_word": "raditi",
        "generated_payload": json.dumps({"serbian_latin": "raditi"}),
        "missing_required_fields": json.dumps([]),
        "model": "test-model",
        "prompt_version": "v1",
    }

    with engine.begin() as connection:
        connection.execute(insert_generation, values)
        with pytest.raises(IntegrityError):
            connection.execute(insert_generation, {**values, "source_word": "Raditi"})


def test_downgrade_to_initial_schema_preserves_legacy_stress(migration_database):
    config, engine = migration_database

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
