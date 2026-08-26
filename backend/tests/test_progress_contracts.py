import json
import os
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest


TARGET_KEY = (
    "v1:sense:abcdef12-1234-5678-9234-567812345678:retrieve_form:written:"
    "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"
)


@pytest.fixture()
def progress_session(db_session):
    from app.domain_models.progress import LearnerTargetStateModel

    LearnerTargetStateModel.__table__.create(
        bind=db_session.get_bind(),
        checkfirst=True,
    )
    return db_session


@pytest.fixture()
def postgresql_progress_database():
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    admin_url_value = os.getenv("SLOVNIK_TEST_POSTGRES_ADMIN_URL")
    if not admin_url_value:
        pytest.skip("SLOVNIK_TEST_POSTGRES_ADMIN_URL is not configured")
    admin_url = make_url(admin_url_value)
    if admin_url.get_backend_name() != "postgresql":
        raise ValueError("SLOVNIK_TEST_POSTGRES_ADMIN_URL must use PostgreSQL")

    database_name = f"slovnik_progress_test_{uuid4().hex}"
    test_database_url = admin_url.set(database=database_name)
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    database_created = False
    test_engine = None
    try:
        with admin_engine.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{database_name}"'))
        database_created = True
        test_engine = create_engine(test_database_url)

        from app.domain_models.progress import LearnerTargetStateModel
        from app.models import UserProfile

        UserProfile.__table__.create(test_engine)
        LearnerTargetStateModel.__table__.create(test_engine)
        yield test_engine
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


def test_learner_profile_adapts_legacy_user_profile() -> None:
    from app.domain.progress import LearnerProfile

    legacy = SimpleNamespace(
        user_id="learner-1",
        preferred_level="B1",
        daily_new_word_count=7,
    )

    profile = LearnerProfile.from_legacy(legacy)

    assert profile == LearnerProfile(
        learner_id="learner-1",
        l1="ru",
        requested_level="B1",
        daily_budget=7,
    )


def test_neutral_state_keeps_frozen_baseline_separate_from_current_values() -> None:
    from app.domain.progress import (
        BaselineKind,
        CompetenceEstimate,
        EvidenceSummary,
        LearnerTargetState,
        MemoryState,
        ProjectionBaseline,
    )

    updated_at = datetime(2026, 8, 26, 8, tzinfo=timezone.utc)

    state = LearnerTargetState.neutral(
        state_id="11111111-1111-4111-8111-111111111111",
        learner_id="learner-1",
        target_key=TARGET_KEY,
        updated_at=updated_at,
    )

    assert state == LearnerTargetState(
        state_id="11111111-1111-4111-8111-111111111111",
        learner_id="learner-1",
        target_key=TARGET_KEY,
        baseline=ProjectionBaseline(
            kind=BaselineKind.NEUTRAL,
            memory_due_at=None,
            memory_interval_days=0,
            payload={"schema_version": 1},
        ),
        competence=CompetenceEstimate(
            success_weight=0,
            failure_weight=0,
            peak=0,
            uncertainty=1,
        ),
        evidence=EvidenceSummary(count=0),
        memory=MemoryState(
            due_at=None,
            interval_days=0,
            lapses=0,
            policy_version="memory-v1",
        ),
        projection_policy_version="projection-v1",
        updated_at=updated_at,
    )


def test_legacy_baseline_has_explicit_source_and_can_differ_from_current_memory() -> None:
    from app.domain.progress import BaselineKind, MemoryState, ProjectionBaseline

    due_at = datetime(2026, 8, 27, 8, tzinfo=timezone.utc)
    baseline = ProjectionBaseline.legacy(
        memory_due_at=due_at,
        memory_interval_days=3,
        source_ref="user_word_progress:42",
        source_fingerprint="a" * 64,
    )
    current = MemoryState(
        due_at=due_at + timedelta(days=3),
        interval_days=6,
        lapses=0,
        policy_version="memory-v1",
    )

    assert (baseline, current) == (
        ProjectionBaseline(
            kind=BaselineKind.LEGACY_BOOTSTRAP,
            memory_due_at=due_at,
            memory_interval_days=3,
            payload={
                "schema_version": 1,
                "source_ref": "user_word_progress:42",
                "source_fingerprint": "a" * 64,
            },
        ),
        MemoryState(
            due_at=due_at + timedelta(days=3),
            interval_days=6,
            lapses=0,
            policy_version="memory-v1",
        ),
    )


def test_legacy_state_starts_from_frozen_baseline_without_native_evidence() -> None:
    from app.domain.progress import LearnerTargetState, ProjectionBaseline

    due_at = datetime(2026, 8, 27, 8, tzinfo=timezone.utc)
    baseline = ProjectionBaseline.legacy(
        memory_due_at=due_at,
        memory_interval_days=3,
        source_ref="user_word_progress:42",
        source_fingerprint="a" * 64,
    )

    state = LearnerTargetState.legacy_bootstrap(
        state_id="11111111-1111-4111-8111-111111111111",
        learner_id="learner-1",
        target_key=TARGET_KEY,
        baseline=baseline,
        updated_at=datetime(2026, 8, 26, 8, tzinfo=timezone.utc),
    )

    assert (
        state.baseline,
        state.evidence.count,
        state.competence.success_weight,
        state.competence.failure_weight,
        state.competence.peak,
        state.competence.uncertainty,
        state.memory.due_at,
        state.memory.interval_days,
        state.memory.lapses,
        state.memory.policy_version,
        state.projection_policy_version,
    ) == (baseline, 0, 0, 0, 0, 1, due_at, 3, 0, "legacy-bootstrap-v1", "legacy-bootstrap-v1")


@pytest.mark.parametrize(
    ("baseline_kind", "invalid_field"),
    [
        ("neutral", "competence"),
        ("neutral", "memory_due_at"),
        ("neutral", "memory_interval_days"),
        ("neutral", "memory_lapses"),
        ("neutral", "memory_policy_version"),
        ("neutral", "projection_policy_version"),
        ("legacy_bootstrap", "competence"),
        ("legacy_bootstrap", "memory_due_at"),
        ("legacy_bootstrap", "memory_interval_days"),
        ("legacy_bootstrap", "memory_lapses"),
        ("legacy_bootstrap", "memory_policy_version"),
        ("legacy_bootstrap", "projection_policy_version"),
    ],
)
def test_zero_evidence_state_requires_exact_baseline_current_values(
    baseline_kind: str,
    invalid_field: str,
) -> None:
    from app.domain.progress import (
        CompetenceEstimate,
        LearnerTargetState,
        ProjectionBaseline,
    )

    due_at = datetime(2026, 8, 27, 8, tzinfo=timezone.utc)
    updated_at = datetime(2026, 8, 26, 8, tzinfo=timezone.utc)
    if baseline_kind == "neutral":
        valid = LearnerTargetState.neutral(
            state_id="11111111-1111-4111-8111-111111111111",
            learner_id="learner-1",
            target_key=TARGET_KEY,
            updated_at=updated_at,
        )
    else:
        valid = LearnerTargetState.legacy_bootstrap(
            state_id="11111111-1111-4111-8111-111111111111",
            learner_id="learner-1",
            target_key=TARGET_KEY,
            baseline=ProjectionBaseline.legacy(
                memory_due_at=due_at,
                memory_interval_days=3,
                source_ref="user_word_progress:42",
                source_fingerprint="a" * 64,
            ),
            updated_at=updated_at,
        )

    competence = valid.competence
    memory = valid.memory
    projection_policy_version = valid.projection_policy_version
    if invalid_field == "competence":
        competence = CompetenceEstimate(0, 0, 0.25, 1)
    elif invalid_field == "memory_due_at":
        memory = replace(memory, due_at=None if memory.due_at else due_at)
    elif invalid_field == "memory_interval_days":
        memory = replace(memory, interval_days=memory.interval_days + 1)
    elif invalid_field == "memory_lapses":
        memory = replace(memory, lapses=1)
    elif invalid_field == "memory_policy_version":
        memory = replace(memory, policy_version="other-memory-v1")
    else:
        projection_policy_version = "other-projection-v1"

    with pytest.raises(ValueError, match="Zero-evidence"):
        LearnerTargetState(
            state_id=valid.state_id,
            learner_id=valid.learner_id,
            target_key=valid.target_key,
            baseline=valid.baseline,
            competence=competence,
            evidence=valid.evidence,
            memory=memory,
            projection_policy_version=projection_policy_version,
            updated_at=valid.updated_at,
        )


@pytest.mark.parametrize(
    ("kind", "due_at", "interval_days", "payload"),
    [
        ("neutral", datetime(2026, 8, 27, tzinfo=timezone.utc), 0, {"schema_version": 1}),
        ("neutral", None, 1, {"schema_version": 1}),
        ("neutral", None, 0, {"schema_version": True}),
        (
            "neutral",
            None,
            0,
            {"schema_version": 1, "source_ref": "user_word_progress:42"},
        ),
        ("legacy_bootstrap", None, 0, {"schema_version": 1}),
        (
            "legacy_bootstrap",
            None,
            0,
            {
                "schema_version": 1,
                "source_ref": "",
                "source_fingerprint": "a" * 64,
            },
        ),
        (
            "legacy_bootstrap",
            None,
            0,
            {
                "schema_version": 1,
                "source_ref": "user_word_progress:42",
                "source_fingerprint": "not-a-fingerprint",
            },
        ),
    ],
)
def test_baseline_kinds_reject_invalid_payload_or_schedule_shapes(
    kind: str,
    due_at: datetime | None,
    interval_days: int,
    payload: dict[str, object],
) -> None:
    from app.domain.progress import BaselineKind, ProjectionBaseline

    with pytest.raises(ValueError, match="baseline"):
        ProjectionBaseline(
            kind=BaselineKind(kind),
            memory_due_at=due_at,
            memory_interval_days=interval_days,
            payload=payload,
        )


@pytest.mark.parametrize(
    ("count", "last_evidence_at", "last_event_id"),
    [
        (0, datetime(2026, 8, 26, tzinfo=timezone.utc), None),
        (0, None, "22222222-2222-4222-8222-222222222222"),
        (1, None, None),
        (1, datetime(2026, 8, 26, tzinfo=timezone.utc), None),
    ],
)
def test_evidence_cursor_is_null_exactly_when_count_is_zero(
    count: int,
    last_evidence_at: datetime | None,
    last_event_id: str | None,
) -> None:
    from app.domain.progress import EvidenceSummary

    with pytest.raises(ValueError, match="cursor"):
        EvidenceSummary(
            count=count,
            last_evidence_at=last_evidence_at,
            last_event_id=last_event_id,
        )


@pytest.mark.parametrize(
    "last_event_id",
    [
        "",
        "ABCDEF12-1234-4678-9234-567812345678",
        "abcdef12123446789234567812345678",
    ],
)
def test_evidence_cursor_requires_a_canonical_event_id(last_event_id: str) -> None:
    from app.domain.progress import EvidenceSummary

    with pytest.raises(ValueError, match="last_event_id"):
        EvidenceSummary(
            count=1,
            last_evidence_at=datetime(2026, 8, 26, tzinfo=timezone.utc),
            last_event_id=last_event_id,
        )


@pytest.mark.parametrize(
    ("value_type", "kwargs"),
    [
        (
            "CompetenceEstimate",
            {"success_weight": -1, "failure_weight": 0, "peak": 0, "uncertainty": 1},
        ),
        (
            "CompetenceEstimate",
            {"success_weight": 0, "failure_weight": -1, "peak": 0, "uncertainty": 1},
        ),
        (
            "CompetenceEstimate",
            {"success_weight": 0, "failure_weight": 0, "peak": 1.01, "uncertainty": 1},
        ),
        (
            "CompetenceEstimate",
            {"success_weight": 0, "failure_weight": 0, "peak": 0, "uncertainty": -0.01},
        ),
        (
            "EvidenceSummary",
            {"count": -1},
        ),
        (
            "ProjectionBaseline",
            {
                "kind": "neutral",
                "memory_due_at": None,
                "memory_interval_days": -1,
                "payload": {"schema_version": 1},
            },
        ),
        (
            "MemoryState",
            {
                "due_at": None,
                "interval_days": -1,
                "lapses": 0,
                "policy_version": "memory-v1",
            },
        ),
        (
            "MemoryState",
            {
                "due_at": None,
                "interval_days": 0,
                "lapses": -1,
                "policy_version": "memory-v1",
            },
        ),
    ],
)
def test_progress_values_reject_sql_out_of_bounds(
    value_type: str,
    kwargs: dict[str, object],
) -> None:
    import app.domain.progress as progress

    constructor = getattr(progress, value_type)

    with pytest.raises(ValueError, match="must"):
        constructor(**kwargs)


@pytest.mark.parametrize("policy_version", ["", "x" * 121, 1])
def test_memory_policy_version_is_a_bounded_nonempty_string(
    policy_version: object,
) -> None:
    from app.domain.progress import MemoryState

    with pytest.raises(ValueError, match="policy_version"):
        MemoryState(
            due_at=None,
            interval_days=0,
            lapses=0,
            policy_version=policy_version,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("projection_policy_version", ["", "x" * 121, 1])
def test_projection_policy_version_is_a_bounded_nonempty_string(
    projection_policy_version: object,
) -> None:
    from app.domain.progress import LearnerTargetState

    state = LearnerTargetState.neutral(
        state_id="11111111-1111-4111-8111-111111111111",
        learner_id="learner-1",
        target_key=TARGET_KEY,
        updated_at=datetime(2026, 8, 26, tzinfo=timezone.utc),
    )

    with pytest.raises(ValueError, match="projection_policy_version"):
        replace(
            state,
            projection_policy_version=projection_policy_version,  # type: ignore[arg-type]
        )


def test_baseline_payload_is_deeply_frozen() -> None:
    from app.domain.progress import ProjectionBaseline

    baseline = ProjectionBaseline.legacy(
        memory_due_at=None,
        memory_interval_days=0,
        source_ref="user_word_progress:42",
        source_fingerprint="a" * 64,
    )

    with pytest.raises(TypeError):
        baseline.payload["source_ref"] = "changed"  # type: ignore[index]


def test_baseline_payload_recursively_copies_and_freezes_json_containers() -> None:
    from app.domain.progress import ProjectionBaseline

    source_ref = {
        "table": "user_word_progress",
        "key": {"parts": ["learner-1", 42]},
    }
    baseline = ProjectionBaseline.legacy(
        memory_due_at=None,
        memory_interval_days=0,
        source_ref=source_ref,
        source_fingerprint="a" * 64,
    )

    source_ref["key"]["parts"].append("changed")

    assert baseline.payload["source_ref"] == {
        "table": "user_word_progress",
        "key": {"parts": ("learner-1", 42)},
    }


@pytest.mark.parametrize(
    "source_ref",
    [
        {"bad": {"mutable"}},
        {"bad": ("tuple",)},
        {"bad": b"bytes"},
        {"bad": float("nan")},
        {1: "non-string-key"},
    ],
)
def test_baseline_payload_rejects_non_json_values(source_ref: object) -> None:
    from app.domain.progress import ProjectionBaseline

    with pytest.raises(ValueError, match="JSON"):
        ProjectionBaseline.legacy(
            memory_due_at=None,
            memory_interval_days=0,
            source_ref=source_ref,
            source_fingerprint="a" * 64,
        )


@pytest.mark.parametrize(
    "target_key",
    [
        "sense:42",
        TARGET_KEY.replace("retrieve_form", "apply_construction"),
    ],
)
def test_state_requires_a_canonical_target_key(target_key: str) -> None:
    from app.domain.progress import LearnerTargetState

    with pytest.raises(ValueError, match="target_key"):
        LearnerTargetState.neutral(
            state_id="11111111-1111-4111-8111-111111111111",
            learner_id="learner-1",
            target_key=target_key,
            updated_at=datetime(2026, 8, 26, tzinfo=timezone.utc),
        )


@pytest.mark.parametrize(
    ("state_id", "learner_id"),
    [
        ("", "learner-1"),
        ("ABCDEF12-1234-4678-9234-567812345678", "learner-1"),
        ("abcdef12123446789234567812345678", "learner-1"),
        ("11111111-1111-4111-8111-111111111111", ""),
        ("11111111-1111-4111-8111-111111111111", "x" * 81),
    ],
)
def test_state_requires_canonical_id_and_bounded_learner_identity(
    state_id: str,
    learner_id: str,
) -> None:
    from app.domain.progress import LearnerTargetState

    with pytest.raises(ValueError, match="LearnerTargetState"):
        LearnerTargetState.neutral(
            state_id=state_id,
            learner_id=learner_id,
            target_key=TARGET_KEY,
            updated_at=datetime(2026, 8, 26, tzinfo=timezone.utc),
        )


def test_state_rejects_more_competence_weight_than_evidence() -> None:
    from app.domain.progress import CompetenceEstimate, EvidenceSummary, LearnerTargetState

    state = LearnerTargetState.neutral(
        state_id="11111111-1111-4111-8111-111111111111",
        learner_id="learner-1",
        target_key=TARGET_KEY,
        updated_at=datetime(2026, 8, 26, tzinfo=timezone.utc),
    )

    with pytest.raises(ValueError, match="weights"):
        replace(
            state,
            competence=CompetenceEstimate(
                success_weight=1,
                failure_weight=1,
                peak=0.5,
                uncertainty=0.5,
            ),
            evidence=EvidenceSummary(
                count=1,
                last_evidence_at=datetime(2026, 8, 26, tzinfo=timezone.utc),
                last_event_id="22222222-2222-4222-8222-222222222222",
            ),
        )


def test_state_timestamps_are_normalized_to_utc() -> None:
    from app.domain.progress import (
        BaselineKind,
        CompetenceEstimate,
        EvidenceSummary,
        LearnerTargetState,
        MemoryState,
        ProjectionBaseline,
    )

    source_timezone = timezone(timedelta(hours=3))
    source_time = datetime(2026, 8, 26, 12, tzinfo=source_timezone)
    state = LearnerTargetState(
        state_id="11111111-1111-4111-8111-111111111111",
        learner_id="learner-1",
        target_key=TARGET_KEY,
        baseline=ProjectionBaseline(
            kind=BaselineKind.LEGACY_BOOTSTRAP,
            memory_due_at=source_time,
            memory_interval_days=1,
            payload={
                "schema_version": 1,
                "source_ref": "user_word_progress:42",
                "source_fingerprint": "a" * 64,
            },
        ),
        competence=CompetenceEstimate(0, 0, 0, 1),
        evidence=EvidenceSummary(
            count=1,
            last_evidence_at=source_time,
            last_event_id="22222222-2222-4222-8222-222222222222",
        ),
        memory=MemoryState(
            due_at=source_time,
            interval_days=1,
            lapses=0,
            policy_version="memory-v1",
        ),
        projection_policy_version="projection-v1",
        updated_at=source_time,
    )

    assert (
        state.baseline.memory_due_at.tzinfo is timezone.utc,
        state.evidence.last_evidence_at.tzinfo is timezone.utc,
        state.memory.due_at.tzinfo is timezone.utc,
        state.updated_at.tzinfo is timezone.utc,
    ) == (True, True, True, True)


@pytest.mark.parametrize(
    ("requested_level", "daily_budget"),
    [("A0", 5), ("A1", 0), ("A1", 51)],
)
def test_learner_profile_preserves_legacy_profile_bounds(
    requested_level: str,
    daily_budget: int,
) -> None:
    from app.domain.progress import LearnerProfile

    with pytest.raises(ValueError, match="LearnerProfile"):
        LearnerProfile(
            learner_id="learner-1",
            l1="ru",
            requested_level=requested_level,
            daily_budget=daily_budget,
        )


def test_learner_profile_rejects_non_string_learner_id_with_domain_error() -> None:
    from app.domain.progress import LearnerProfile

    with pytest.raises(ValueError, match="learner_id"):
        LearnerProfile(
            learner_id=1,  # type: ignore[arg-type]
            l1="ru",
            requested_level="A1",
            daily_budget=5,
        )


def test_orm_matches_sql_01_sparse_state_contract() -> None:
    from sqlalchemy import DateTime, JSON, Text, UniqueConstraint
    from sqlalchemy.dialects import postgresql
    from sqlalchemy.schema import CreateTable

    from app.domain_models.progress import LearnerTargetStateModel

    table = LearnerTargetStateModel.__table__
    unique_column_sets = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    due_index = next(
        index for index in table.indexes if index.name == "ix_learner_target_states_due"
    )
    timezone_columns = {
        name: table.c[name].type.timezone
        for name in (
            "baseline_memory_due_at",
            "last_evidence_at",
            "memory_due_at",
            "updated_at",
        )
        if isinstance(table.c[name].type, DateTime)
    }
    postgresql_ddl = str(CreateTable(table).compile(dialect=postgresql.dialect()))

    assert (
        table.name,
        unique_column_sets,
        tuple(column.name for column in due_index.columns),
        isinstance(table.c.baseline_payload.type, JSON),
        isinstance(table.c.memory_policy_version.type, Text),
        isinstance(table.c.projection_policy_version.type, Text),
        "memory_policy_version TEXT NOT NULL" in postgresql_ddl,
        "projection_policy_version TEXT NOT NULL" in postgresql_ddl,
        timezone_columns,
    ) == (
        "learner_target_states",
        {("learner_id", "target_key")},
        ("learner_id", "memory_due_at"),
        True,
        True,
        True,
        True,
        True,
        {
            "baseline_memory_due_at": True,
            "last_evidence_at": True,
            "memory_due_at": True,
            "updated_at": True,
        },
    )


def test_repository_loads_pure_profile_view(progress_session) -> None:
    from app.domain.progress import LearnerProfile
    from app.models import UserProfile
    from app.repositories.progress import ProgressRepository

    progress_session.add(
        UserProfile(
            user_id="learner-1",
            preferred_level="A2",
            daily_new_word_count=9,
        )
    )
    progress_session.commit()

    profile = ProgressRepository(progress_session).get_profile("learner-1")

    assert profile == LearnerProfile(
        learner_id="learner-1",
        l1="ru",
        requested_level="A2",
        daily_budget=9,
    )


def test_repository_ensures_one_neutral_domain_state_per_learner_target(
    progress_session,
) -> None:
    from sqlalchemy import func, select

    from app.domain.progress import BaselineKind, LearnerTargetState
    from app.domain_models.progress import LearnerTargetStateModel
    from app.models import UserProfile
    from app.repositories.progress import ProgressRepository

    progress_session.add(UserProfile(user_id="learner-1"))
    progress_session.commit()
    repository = ProgressRepository(progress_session)
    updated_at = datetime(2026, 8, 26, tzinfo=timezone.utc)

    first = repository.ensure_state(
        learner_id="learner-1",
        target_key=TARGET_KEY,
        state_id="11111111-1111-4111-8111-111111111111",
        updated_at=updated_at,
    )
    second = repository.ensure_state(
        learner_id="learner-1",
        target_key=TARGET_KEY,
        state_id="33333333-3333-4333-8333-333333333333",
        updated_at=updated_at + timedelta(minutes=1),
    )
    row_count = progress_session.scalar(
        select(func.count()).select_from(LearnerTargetStateModel)
    )

    assert (
        isinstance(first, LearnerTargetState),
        second.state_id,
        second.baseline.kind,
        row_count,
    ) == (
        True,
        first.state_id,
        BaselineKind.NEUTRAL,
        1,
    )


def test_repository_does_not_replace_an_explicit_empty_state_id(
    progress_session,
) -> None:
    from app.models import UserProfile
    from app.repositories.progress import ProgressRepository

    progress_session.add(UserProfile(user_id="learner-1"))
    progress_session.commit()

    with pytest.raises(ValueError, match="state_id"):
        ProgressRepository(progress_session).ensure_state(
            learner_id="learner-1",
            target_key=TARGET_KEY,
            state_id="",
            updated_at=datetime(2026, 8, 26, tzinfo=timezone.utc),
        )


def test_repository_does_not_replace_an_explicit_falsy_invalid_updated_at(
    progress_session,
) -> None:
    from app.models import UserProfile
    from app.repositories.progress import ProgressRepository

    progress_session.add(UserProfile(user_id="learner-1"))
    progress_session.commit()

    with pytest.raises(AttributeError, match="tzinfo"):
        ProgressRepository(progress_session).ensure_state(
            learner_id="learner-1",
            target_key=TARGET_KEY,
            state_id="11111111-1111-4111-8111-111111111111",
            updated_at=0,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("baseline_kind", ["neutral", "legacy_bootstrap"])
def test_repository_rejects_rehydrated_zero_evidence_state_that_drifted_from_baseline(
    progress_session,
    baseline_kind: str,
) -> None:
    from sqlalchemy import select

    from app.domain_models.progress import LearnerTargetStateModel
    from app.models import UserProfile
    from app.repositories.progress import ProgressRepository

    progress_session.add(UserProfile(user_id="learner-1"))
    progress_session.commit()
    repository = ProgressRepository(progress_session)
    repository.ensure_state(
        learner_id="learner-1",
        target_key=TARGET_KEY,
        state_id="11111111-1111-4111-8111-111111111111",
        updated_at=datetime(2026, 8, 26, tzinfo=timezone.utc),
    )
    row = progress_session.scalar(select(LearnerTargetStateModel))
    assert row is not None
    if baseline_kind == "neutral":
        row.competence_peak = 0.25
    else:
        due_at = datetime(2026, 8, 27, 8, tzinfo=timezone.utc)
        row.baseline_kind = "legacy_bootstrap"
        row.baseline_memory_due_at = due_at
        row.baseline_memory_interval_days = 3
        row.baseline_payload = {
            "schema_version": 1,
            "source_ref": "user_word_progress:42",
            "source_fingerprint": "a" * 64,
        }
        row.memory_due_at = due_at + timedelta(days=1)
        row.memory_interval_days = 3
        row.memory_policy_version = "legacy-bootstrap-v1"
        row.projection_policy_version = "legacy-bootstrap-v1"
    progress_session.flush()
    progress_session.expire_all()

    with pytest.raises(ValueError, match="Zero-evidence"):
        repository.get_state("learner-1", TARGET_KEY)


def test_repository_recovers_only_the_learner_target_insert_race(
    progress_session,
    monkeypatch,
) -> None:
    from app.models import UserProfile
    from app.repositories.progress import ProgressRepository

    progress_session.add(UserProfile(user_id="learner-1"))
    progress_session.commit()
    repository = ProgressRepository(progress_session)
    updated_at = datetime(2026, 8, 26, tzinfo=timezone.utc)
    existing = repository.ensure_state(
        learner_id="learner-1",
        target_key=TARGET_KEY,
        state_id="11111111-1111-4111-8111-111111111111",
        updated_at=updated_at,
    )
    original_find = repository._find_state_row
    find_calls = 0

    def stale_once(learner_id: str, target_key: str):
        nonlocal find_calls
        find_calls += 1
        if find_calls == 1:
            return None
        return original_find(learner_id, target_key)

    monkeypatch.setattr(repository, "_find_state_row", stale_once)

    recovered = repository.ensure_state(
        learner_id="learner-1",
        target_key=TARGET_KEY,
        state_id="33333333-3333-4333-8333-333333333333",
        updated_at=updated_at,
    )
    progress_session.add(UserProfile(user_id="learner-2"))
    progress_session.flush()

    assert (
        recovered.state_id,
        find_calls,
        progress_session.get(UserProfile, "learner-2") is not None,
    ) == (existing.state_id, 2, True)


def test_postgresql_concurrent_ensure_state_recovers_one_canonical_row(
    postgresql_progress_database,
) -> None:
    from sqlalchemy import func, select
    from sqlalchemy.orm import sessionmaker

    from app.domain_models.progress import LearnerTargetStateModel
    from app.models import UserProfile
    from app.repositories.progress import ProgressRepository

    SessionFactory = sessionmaker(bind=postgresql_progress_database)
    with SessionFactory() as session:
        session.add(UserProfile(user_id="learner-1"))
        session.commit()

    start = threading.Barrier(2)

    class BarrierRepository(ProgressRepository):
        def __init__(self, session) -> None:
            super().__init__(session)
            self._first_lookup = True

        def _find_state_row(self, learner_id: str, target_key: str):
            row = super()._find_state_row(learner_id, target_key)
            if self._first_lookup:
                self._first_lookup = False
                assert row is None
                start.wait(timeout=10)
            return row

    def ensure(state_id: str) -> str:
        with SessionFactory() as session:
            state = BarrierRepository(session).ensure_state(
                learner_id="learner-1",
                target_key=TARGET_KEY,
                state_id=state_id,
                updated_at=datetime(2026, 8, 26, tzinfo=timezone.utc),
            )
            session.commit()
            return state.state_id

    state_ids = (
        "11111111-1111-4111-8111-111111111111",
        "33333333-3333-4333-8333-333333333333",
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(ensure, state_id) for state_id in state_ids]
        recovered_ids = [future.result(timeout=30) for future in futures]

    with SessionFactory() as session:
        persisted_ids = session.scalars(select(LearnerTargetStateModel.id)).all()
        row_count = session.scalar(
            select(func.count()).select_from(LearnerTargetStateModel)
        )

    assert row_count == 1
    assert recovered_ids == [persisted_ids[0], persisted_ids[0]]


@pytest.mark.parametrize(
    "constraint_name",
    [
        "learner_target_states_pkey",
        "learner_target_states_learner_id_fkey",
        "ck_learner_target_states_memory_lapses",
    ],
)
def test_repository_does_not_swallow_unrelated_integrity_error_for_visible_row(
    progress_session,
    monkeypatch,
    constraint_name: str,
) -> None:
    from contextlib import nullcontext

    from sqlalchemy.exc import IntegrityError

    from app.models import UserProfile
    from app.repositories.progress import ProgressRepository

    progress_session.add(UserProfile(user_id="learner-1"))
    progress_session.commit()
    repository = ProgressRepository(progress_session)
    updated_at = datetime(2026, 8, 26, tzinfo=timezone.utc)
    repository.ensure_state(
        learner_id="learner-1",
        target_key=TARGET_KEY,
        state_id="11111111-1111-4111-8111-111111111111",
        updated_at=updated_at,
    )
    existing_row = repository._find_state_row("learner-1", TARGET_KEY)
    assert existing_row is not None
    find_calls = 0

    def stale_once(learner_id: str, target_key: str):
        nonlocal find_calls
        find_calls += 1
        if find_calls == 1:
            return None
        return existing_row

    class ConstraintViolation(Exception):
        def __init__(self, name: str) -> None:
            self.constraint_name = name
            super().__init__(name)

    def fail_flush(*args, **kwargs):
        raise IntegrityError(
            "INSERT INTO learner_target_states ...",
            {},
            ConstraintViolation(constraint_name),
        )

    monkeypatch.setattr(repository, "_find_state_row", stale_once)
    monkeypatch.setattr(progress_session, "begin_nested", nullcontext)
    monkeypatch.setattr(progress_session, "flush", fail_flush)

    with pytest.raises(IntegrityError, match=constraint_name):
        repository.ensure_state(
            learner_id="learner-1",
            target_key=TARGET_KEY,
            state_id="33333333-3333-4333-8333-333333333333",
            updated_at=updated_at,
        )
    assert find_calls == 1


def test_repository_locks_and_loads_a_domain_state(
    progress_session,
    monkeypatch,
) -> None:
    from sqlalchemy.dialects import postgresql

    from app.domain.progress import LearnerTargetState
    from app.models import UserProfile
    from app.repositories.progress import ProgressRepository

    progress_session.add(UserProfile(user_id="learner-1"))
    progress_session.commit()
    repository = ProgressRepository(progress_session)
    updated_at = datetime(2026, 8, 26, tzinfo=timezone.utc)
    repository.ensure_state(
        learner_id="learner-1",
        target_key=TARGET_KEY,
        state_id="11111111-1111-4111-8111-111111111111",
        updated_at=updated_at,
    )
    captured_sql: list[str] = []
    original_scalar = progress_session.scalar

    def capture_scalar(statement, *args, **kwargs):
        captured_sql.append(
            str(statement.compile(dialect=postgresql.dialect())).upper()
        )
        return original_scalar(statement, *args, **kwargs)

    monkeypatch.setattr(progress_session, "scalar", capture_scalar)

    state = repository.lock_state("learner-1", TARGET_KEY)

    assert (isinstance(state, LearnerTargetState), "FOR UPDATE" in captured_sql[-1]) == (
        True,
        True,
    )


def test_fake_event_source_and_memory_policy_are_ws_b_independent() -> None:
    from app.domain.memory_policy import MemoryPolicy
    from app.domain.progress import LearningEventSource, MemoryState

    class FakeEventSource:
        def events_for_target(self, *, learner_id: str, target_key: str):
            return ()

    class FakeMemoryPolicy:
        version = "fake-memory-v1"

        def apply(self, state: MemoryState, event: object) -> MemoryState:
            return state

    script = """
import json
import sys
sys.path.insert(0, '.')
import app.domain.progress
import app.domain.memory_policy
print(json.dumps(sorted(
    name for name in sys.modules
    if name.startswith(('app.domain.practice', 'app.domain_models.practice',
                        'app.repositories.practice'))
)))
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", script],
        cwd=".",
        check=True,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": "."},
    )

    assert (
        isinstance(FakeEventSource(), LearningEventSource),
        isinstance(FakeMemoryPolicy(), MemoryPolicy),
        json.loads(result.stdout),
    ) == (True, True, [])
