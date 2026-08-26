import json
import subprocess
import sys
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import JSON, ForeignKeyConstraint, UniqueConstraint


NOW = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)
RUN_ID = "10000000-0000-4000-8000-000000000001"
TARGET_ID = "20000000-0000-4000-8000-000000000001"
ACTIVITY_ID = "30000000-0000-4000-8000-000000000001"
RETRY_ID = "30000000-0000-4000-8000-000000000002"
INVALID_UUIDS = [
    "not-a-uuid",
    "ABCDEF12-1234-5678-9234-567812345678",
    "abcdef12123456789234567812345678",
]


def make_target():
    from app.domain.shared import Capability, Modality, TargetKind
    from app.domain.target import TargetSpec

    return TargetSpec(
        target_kind=TargetKind.SENSE,
        target_id=TARGET_ID,
        capability=Capability.RETRIEVE_FORM,
        modality=Modality.WRITTEN,
    )


def make_run():
    from app.domain.practice import PracticeRun, PracticeRunStatus

    return PracticeRun(
        id=RUN_ID,
        learner_id="learner-1",
        curriculum_version_id=None,
        legacy_quiz_attempt_id=None,
        status=PracticeRunStatus.ACTIVE,
        selection_policy_version="deterministic-v1",
        started_at=NOW,
        ended_at=None,
    )


def make_activity():
    from app.domain.practice import (
        ActivityInstance,
        ActivityKind,
        ActivitySpec,
        ActivityStatus,
        CueLevel,
        GeneratorKind,
        LearningIntent,
        SelectionMetadata,
        SelectionReason,
    )

    return ActivityInstance(
        id=ACTIVITY_ID,
        practice_run_id=RUN_ID,
        spec=ActivitySpec(
            target_spec=make_target(),
            activity_kind=ActivityKind.EXPOSURE,
            operation=None,
            cue_level=CueLevel.FULL,
            output_modality=None,
            scorer_kind=None,
            snapshot={"prompt": "кућа"},
        ),
        learning_intent=LearningIntent.ACQUIRE,
        sequence_number=1,
        retry_of_activity_instance_id=None,
        attempt_number=1,
        selection=SelectionMetadata(
            policy_version="deterministic-v1",
            reasons=(SelectionReason.NEW_TARGET,),
        ),
        generator_kind=GeneratorKind.CURATED,
        generator_version="curated-v1",
        scorer_version=None,
        status=ActivityStatus.PENDING,
        selected_at=NOW,
        terminal_at=None,
    )


def test_practice_run_requires_terminal_timestamp_only_after_active_state() -> None:
    from app.domain.practice import PracticeRun, PracticeRunStatus

    active = PracticeRun(
        id=RUN_ID,
        learner_id="learner-1",
        curriculum_version_id=None,
        legacy_quiz_attempt_id=None,
        status=PracticeRunStatus.ACTIVE,
        selection_policy_version="deterministic-v1",
        started_at=NOW,
        ended_at=None,
    )

    assert active.ended_at is None
    with pytest.raises(ValueError, match="ended_at"):
        PracticeRun(
            id=RUN_ID,
            learner_id="learner-1",
            curriculum_version_id=None,
            legacy_quiz_attempt_id=None,
            status=PracticeRunStatus.COMPLETED,
            selection_policy_version="deterministic-v1",
            started_at=NOW,
            ended_at=None,
        )


def test_practice_enum_wire_values_match_sql01_and_event01() -> None:
    from app.domain.practice import (
        ActivityKind,
        ActivityStatus,
        EvaluationOutcome,
        EvaluationSource,
        ExerciseOperation,
        GeneratorKind,
        LearningIntent,
        PracticeRunStatus,
    )

    assert [value.value for value in PracticeRunStatus] == [
        "active",
        "completed",
        "abandoned",
    ]
    assert [value.value for value in ActivityStatus] == [
        "pending",
        "completed",
        "cancelled",
    ]
    assert [value.value for value in LearningIntent] == [
        "acquire",
        "review",
        "strengthen",
        "assess",
    ]
    assert [value.value for value in ActivityKind] == ["exposure", "exercise"]
    assert [value.value for value in ExerciseOperation] == [
        "recognize",
        "retrieve",
        "complete",
        "transform",
    ]
    assert [value.value for value in GeneratorKind] == ["curated", "model_assisted"]
    assert [value.value for value in EvaluationSource] == [
        "deterministic",
        "self_report",
        "model_assisted",
    ]
    assert [value.value for value in EvaluationOutcome] == [
        "correct",
        "partial",
        "incorrect",
        "unknown",
    ]


def test_practice_state_rejects_untyped_wire_values_before_persistence() -> None:
    with pytest.raises(ValueError, match="PracticeRun status"):
        replace(make_run(), status="active")
    with pytest.raises(ValueError, match="Activity status"):
        replace(make_activity(), status="pending")


@pytest.mark.parametrize("field_name", ["id", "curriculum_version_id"])
@pytest.mark.parametrize("invalid_uuid", INVALID_UUIDS)
def test_practice_run_rejects_noncanonical_uuid_fields(
    field_name: str, invalid_uuid: str
) -> None:
    with pytest.raises(ValueError, match="canonical lowercase UUID"):
        replace(make_run(), **{field_name: invalid_uuid})


@pytest.mark.parametrize(
    "field_name", ["id", "practice_run_id", "retry_of_activity_instance_id"]
)
@pytest.mark.parametrize("invalid_uuid", INVALID_UUIDS)
def test_activity_rejects_noncanonical_uuid_fields(
    field_name: str, invalid_uuid: str
) -> None:
    changes = {field_name: invalid_uuid}
    if field_name == "retry_of_activity_instance_id":
        changes["attempt_number"] = 2

    with pytest.raises(ValueError, match="canonical lowercase UUID"):
        replace(make_activity(), **changes)


def test_activity_spec_distinguishes_exposure_from_exercise_shape() -> None:
    from app.domain.practice import (
        ActivityKind,
        ActivitySpec,
        CueLevel,
        ExerciseOperation,
        ScorerKind,
    )

    exposure = ActivitySpec(
        target_spec=make_target(),
        activity_kind=ActivityKind.EXPOSURE,
        operation=None,
        cue_level=CueLevel.FULL,
        output_modality=None,
        scorer_kind=None,
        snapshot={"prompt": "кућа"},
    )
    exercise = ActivitySpec(
        target_spec=make_target(),
        activity_kind=ActivityKind.EXERCISE,
        operation=ExerciseOperation.RETRIEVE,
        cue_level=CueLevel.MINIMAL,
        output_modality=make_target().modality,
        scorer_kind=ScorerKind.DETERMINISTIC,
        snapshot={"prompt": "дом", "expected_form_id": TARGET_ID},
    )

    assert exposure.operation is None and exposure.scorer_kind is None
    assert exercise.operation is ExerciseOperation.RETRIEVE
    with pytest.raises(ValueError, match="Exposure"):
        ActivitySpec(
            target_spec=make_target(),
            activity_kind=ActivityKind.EXPOSURE,
            operation=ExerciseOperation.RECOGNIZE,
            cue_level=CueLevel.FULL,
            output_modality=None,
            scorer_kind=None,
            snapshot={},
        )
    with pytest.raises(ValueError, match="Exercise"):
        ActivitySpec(
            target_spec=make_target(),
            activity_kind=ActivityKind.EXERCISE,
            operation=None,
            cue_level=CueLevel.MINIMAL,
            output_modality=make_target().modality,
            scorer_kind=ScorerKind.DETERMINISTIC,
            snapshot={},
        )


def test_activity_spec_owns_one_target_and_is_bounded_to_64_kib() -> None:
    from app.domain.practice import ActivityKind, ActivitySpec, CueLevel

    spec = ActivitySpec(
        target_spec=make_target(),
        activity_kind=ActivityKind.EXPOSURE,
        operation=None,
        cue_level=CueLevel.FULL,
        output_modality=None,
        scorer_kind=None,
        snapshot={"prompt": "кућа"},
    )

    assert spec.target_key == make_target().target_key
    assert spec.to_payload()["target_spec"] == make_target().to_payload()
    with pytest.raises(ValueError, match="primary target"):
        ActivitySpec(
            target_spec=make_target(),
            activity_kind=ActivityKind.EXPOSURE,
            operation=None,
            cue_level=CueLevel.FULL,
            output_modality=None,
            scorer_kind=None,
            snapshot={"target_spec": make_target().to_payload()},
        )
    with pytest.raises(ValueError, match="64 KiB"):
        ActivitySpec(
            target_spec=make_target(),
            activity_kind=ActivityKind.EXPOSURE,
            operation=None,
            cue_level=CueLevel.FULL,
            output_modality=None,
            scorer_kind=None,
            snapshot={"prompt": "x" * (64 * 1024)},
        )


def test_activity_spec_persisted_payload_is_closed_and_versioned() -> None:
    from app.domain.practice import ActivitySpec

    payload = make_activity().spec.to_payload()

    assert payload["schema_version"] == 1
    with pytest.raises(ValueError, match="Invalid ActivitySpec payload"):
        ActivitySpec.from_payload({**payload, "schema_version": 2})
    with pytest.raises(ValueError, match="Invalid ActivitySpec payload"):
        ActivitySpec.from_payload({**payload, "secondary_target": make_target().to_payload()})


@pytest.mark.parametrize("invalid_version", [True, 1.0, "1"])
def test_activity_spec_payload_requires_integer_schema_version_one(
    invalid_version: object,
) -> None:
    from app.domain.practice import ActivitySpec

    payload = make_activity().spec.to_payload()

    with pytest.raises(ValueError, match="Invalid ActivitySpec payload"):
        ActivitySpec.from_payload({**payload, "schema_version": invalid_version})


def test_activity_spec_snapshot_participates_in_equality_and_round_trip() -> None:
    from app.domain.practice import ActivitySpec

    first = make_activity().spec
    second = replace(first, snapshot={"prompt": "другачије"})
    restored = ActivitySpec.from_payload(first.to_payload())

    assert first != second
    assert restored == first
    assert restored.to_payload() == first.to_payload()


@pytest.mark.parametrize("field_name", ["operation", "output_modality", "scorer_kind"])
@pytest.mark.parametrize("invalid_value", [False, 0, [], {}])
def test_activity_spec_payload_rejects_non_string_optional_enum_values(
    field_name: str, invalid_value: object
) -> None:
    from app.domain.practice import ActivitySpec

    payload = make_activity().spec.to_payload()

    with pytest.raises(ValueError, match="Invalid ActivitySpec payload"):
        ActivitySpec.from_payload({**payload, field_name: invalid_value})


def test_selection_metadata_is_bounded_and_deterministic_v1_has_null_propensity() -> None:
    from app.domain.practice import SelectionMetadata, SelectionReason

    metadata = SelectionMetadata(
        policy_version="deterministic-v1",
        reasons=(SelectionReason.DUE_REVIEW, SelectionReason.WEAK_COMPETENCE),
        propensity=None,
    )

    assert metadata.to_payload() == ["due_review", "weak_competence"]
    with pytest.raises(ValueError, match="propensity"):
        SelectionMetadata(
            policy_version="deterministic-v1",
            reasons=(SelectionReason.NEW_TARGET,),
            propensity=0.5,
        )
    with pytest.raises(ValueError, match="at most 10"):
        SelectionMetadata(
            policy_version="future-v2",
            reasons=(SelectionReason.NEW_TARGET,) * 11,
            propensity=0.5,
        )


@pytest.mark.parametrize(
    "invalid_propensity",
    [True, False, float("nan"), float("inf"), float("-inf"), "0.5", [], {}],
)
def test_selection_propensity_requires_finite_numeric_non_boolean_unit_interval(
    invalid_propensity: object,
) -> None:
    from app.domain.practice import SelectionMetadata, SelectionReason

    with pytest.raises(ValueError, match="propensity"):
        SelectionMetadata(
            policy_version="future-v2",
            reasons=(SelectionReason.NEW_TARGET,),
            propensity=invalid_propensity,
        )


def test_activity_inherits_run_selection_policy_and_owns_one_target_key() -> None:
    from app.domain.practice import SelectionMetadata, SelectionReason

    run = make_run()
    activity = make_activity()

    run.validate_activity(activity)
    assert activity.target_spec is activity.spec.target_spec
    assert activity.target_key == activity.spec.target_key

    mismatched = replace(
        activity,
        selection=SelectionMetadata(
            policy_version="other-v2",
            reasons=(SelectionReason.NEW_TARGET,),
        ),
    )
    with pytest.raises(ValueError, match="inherit"):
        run.validate_activity(mismatched)


def test_response_submission_and_evaluation_are_bounded_event_values() -> None:
    from app.domain.practice import (
        Evaluation,
        EvaluationOutcome,
        EvaluationSource,
        ResponseKind,
        ResponseSnapshot,
        ResponseSubmission,
    )

    submission = ResponseSubmission(
        activity_instance_id=ACTIVITY_ID,
        response=ResponseSnapshot(kind=ResponseKind.TEXT, value="кућа"),
        idempotency_key="attempt-1",
        occurred_at=NOW,
    )
    evaluation = Evaluation(
        source=EvaluationSource.DETERMINISTIC,
        outcome=EvaluationOutcome.CORRECT,
    )

    assert submission.response.to_payload() == {
        "kind": "text",
        "value": "кућа",
        "truncated": False,
    }
    assert evaluation.partial_score is None
    with pytest.raises(ValueError, match="2000"):
        ResponseSnapshot(kind=ResponseKind.TEXT, value="x" * 2001)
    with pytest.raises(ValueError, match="partial_score"):
        Evaluation(
            source=EvaluationSource.DETERMINISTIC,
            outcome=EvaluationOutcome.PARTIAL,
            partial_score=None,
        )
    with pytest.raises(ValueError, match="confidence"):
        Evaluation(
            source=EvaluationSource.MODEL_ASSISTED,
            outcome=EvaluationOutcome.CORRECT,
            confidence=None,
        )


@pytest.mark.parametrize("invalid_truncated", [0, 1, None, "false", []])
def test_response_snapshot_requires_boolean_truncated_flag(
    invalid_truncated: object,
) -> None:
    from app.domain.practice import ResponseKind, ResponseSnapshot

    with pytest.raises(ValueError, match="truncated"):
        ResponseSnapshot(
            kind=ResponseKind.TEXT,
            value="кућа",
            truncated=invalid_truncated,
        )


@pytest.mark.parametrize(
    "invalid_activity_id",
    [
        "not-a-uuid",
        "ABCDEF12-1234-5678-9234-567812345678",
        "abcdef12123456789234567812345678",
    ],
)
def test_response_submission_requires_canonical_lowercase_activity_uuid(
    invalid_activity_id: str,
) -> None:
    from app.domain.practice import ResponseKind, ResponseSnapshot, ResponseSubmission

    with pytest.raises(ValueError, match="canonical UUID"):
        ResponseSubmission(
            activity_instance_id=invalid_activity_id,
            response=ResponseSnapshot(kind=ResponseKind.TEXT, value="кућа"),
            idempotency_key="attempt-1",
            occurred_at=NOW,
        )


@pytest.mark.parametrize("invalid_key", [1, True, [], {}, None, "x" * 256])
def test_response_submission_requires_string_bounded_idempotency_key(
    invalid_key: object,
) -> None:
    from app.domain.practice import ResponseKind, ResponseSnapshot, ResponseSubmission

    with pytest.raises(ValueError, match="Idempotency key"):
        ResponseSubmission(
            activity_instance_id=ACTIVITY_ID,
            response=ResponseSnapshot(kind=ResponseKind.TEXT, value="кућа"),
            idempotency_key=invalid_key,
            occurred_at=NOW,
        )


@pytest.mark.parametrize(
    "invalid_tags",
    [
        [],
        ["mutable"],
        ("valid", 1),
        ("",),
        ("x" * 65,),
        tuple(f"tag-{index}" for index in range(33)),
    ],
)
def test_evaluation_error_tags_require_bounded_immutable_string_tuple(
    invalid_tags: object,
) -> None:
    from app.domain.practice import Evaluation, EvaluationOutcome, EvaluationSource

    with pytest.raises(ValueError, match="error_tags"):
        Evaluation(
            source=EvaluationSource.DETERMINISTIC,
            outcome=EvaluationOutcome.CORRECT,
            error_tags=invalid_tags,
        )


def test_retry_is_a_new_activity_with_same_run_target_and_next_attempt() -> None:
    parent = make_activity()
    retry = replace(
        parent,
        id=RETRY_ID,
        sequence_number=2,
        retry_of_activity_instance_id=parent.id,
        attempt_number=2,
    )

    retry.validate_retry_of(parent)
    with pytest.raises(ValueError, match="attempt 1"):
        replace(parent, attempt_number=2)
    with pytest.raises(ValueError, match="same run"):
        retry.validate_retry_of(
            replace(parent, practice_run_id="10000000-0000-4000-8000-000000000002")
        )


def test_activity_terminal_state_has_one_timestamp_and_cannot_terminalize_twice() -> None:
    terminal_at = NOW + timedelta(seconds=10)
    pending = make_activity()

    completed = pending.complete(terminal_at)

    assert completed.status.value == "completed"
    assert completed.terminal_at == terminal_at
    with pytest.raises(ValueError, match="already terminal"):
        completed.cancel(terminal_at + timedelta(seconds=1))
    with pytest.raises(ValueError, match="terminal_at"):
        replace(pending, terminal_at=terminal_at)


def test_activity_sequence_and_timestamps_respect_sql01_bounds() -> None:
    pending = make_activity()

    with pytest.raises(ValueError, match="sequence_number"):
        replace(pending, sequence_number=0)
    with pytest.raises(ValueError, match="timezone-aware"):
        replace(pending, selected_at=NOW.replace(tzinfo=None))


def test_terminal_timestamps_cannot_precede_run_or_activity_start() -> None:
    from app.domain.practice import ActivityStatus, PracticeRunStatus

    run_boundary = replace(
        make_run(),
        status=PracticeRunStatus.COMPLETED,
        ended_at=NOW,
    )
    activity_boundary = replace(
        make_activity(),
        status=ActivityStatus.COMPLETED,
        terminal_at=NOW,
    )

    assert run_boundary.ended_at == run_boundary.started_at
    assert activity_boundary.terminal_at == activity_boundary.selected_at
    with pytest.raises(ValueError, match="ended_at.*before"):
        replace(run_boundary, ended_at=NOW - timedelta(microseconds=1))
    with pytest.raises(ValueError, match="terminal_at.*before"):
        replace(activity_boundary, terminal_at=NOW - timedelta(microseconds=1))


def test_response_evaluator_port_is_structural_and_import_isolated() -> None:
    from app.domain.practice import Evaluation, EvaluationOutcome, EvaluationSource
    from app.domain.practice_ports import ResponseEvaluator

    class FakeEvaluator:
        version = "fake-v1"
        source = EvaluationSource.DETERMINISTIC

        def evaluate(self, activity, submission):
            return Evaluation(
                source=EvaluationSource.DETERMINISTIC,
                outcome=EvaluationOutcome.CORRECT,
            )

    assert isinstance(FakeEvaluator(), ResponseEvaluator)

    script = """
import json
import sys
sys.path.insert(0, '.')
before = set(sys.modules)
import app.domain.practice_ports
blocked = {'fastapi', 'sqlalchemy', 'pydantic', 'openai'}
print(json.dumps(sorted(
    name for name in set(sys.modules) - before
    if name.split('.', 1)[0] in blocked
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
    assert json.loads(result.stdout) == []


def test_practice_orm_matches_sql01_composite_ownership_and_portable_json() -> None:
    from app.domain_models.practice import (
        ActivityInstanceModel,
        LearningEventModel,
        PracticeRunModel,
    )

    run_table = PracticeRunModel.__table__
    activity_table = ActivityInstanceModel.__table__
    event_table = LearningEventModel.__table__

    run_uniques = {
        tuple(constraint.columns.keys())
        for constraint in run_table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert ("id", "learner_id") in run_uniques
    assert ("id", "selection_policy_version") in run_uniques

    activity_foreign_keys = {
        (
            tuple(constraint.columns.keys()),
            tuple(element.target_fullname for element in constraint.elements),
        )
        for constraint in activity_table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    }
    assert (
        ("practice_run_id", "selection_policy_version"),
        ("practice_runs.id", "practice_runs.selection_policy_version"),
    ) in activity_foreign_keys
    assert (
        ("practice_run_id", "retry_of_activity_instance_id", "target_key"),
        (
            "activity_instances.practice_run_id",
            "activity_instances.id",
            "activity_instances.target_key",
        ),
    ) in activity_foreign_keys

    event_foreign_keys = {
        tuple(constraint.columns.keys())
        for constraint in event_table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    }
    assert ("practice_run_id", "learner_id") in event_foreign_keys
    assert (
        "practice_run_id",
        "activity_instance_id",
        "target_key",
        "activity_kind",
    ) in event_foreign_keys
    assert isinstance(activity_table.c.spec_payload.type, JSON)
    assert isinstance(activity_table.c.selection_reason_payload.type, JSON)
    assert isinstance(event_table.c.observation_payload.type, JSON)


def test_practice_repository_returns_domain_values_not_orm_rows() -> None:
    from app.domain.practice import ActivityInstance, PracticeRun
    from app.domain_models.practice import ActivityInstanceModel, PracticeRunModel
    from app.repositories.practice import PracticeRepository

    run = make_run()
    activity = make_activity()
    rows = {
        (PracticeRunModel, run.id): PracticeRunModel(
            id=run.id,
            learner_id=run.learner_id,
            curriculum_version_id=run.curriculum_version_id,
            legacy_quiz_attempt_id=run.legacy_quiz_attempt_id,
            status=run.status.value,
            selection_policy_version=run.selection_policy_version,
            started_at=run.started_at,
            ended_at=run.ended_at,
        ),
        (ActivityInstanceModel, activity.id): ActivityInstanceModel(
            id=activity.id,
            practice_run_id=activity.practice_run_id,
            target_key=activity.target_key,
            learning_intent=activity.learning_intent.value,
            activity_kind=activity.activity_kind.value,
            operation=None,
            sequence_number=activity.sequence_number,
            retry_of_activity_instance_id=activity.retry_of_activity_instance_id,
            attempt_number=activity.attempt_number,
            spec_payload=activity.spec.to_payload(),
            selection_policy_version=activity.selection.policy_version,
            selection_reason_payload=activity.selection.to_payload(),
            selection_propensity=activity.selection.propensity,
            generator_kind=activity.generator_kind.value,
            generator_version=activity.generator_version,
            scorer_kind=None,
            scorer_version=None,
            status=activity.status.value,
            selected_at=activity.selected_at,
            terminal_at=activity.terminal_at,
        ),
    }

    class FakeSession:
        def get(self, model, identity):
            return rows.get((model, identity))

    repository = PracticeRepository(FakeSession())

    loaded_run = repository.get_run(run.id)
    loaded_activity = repository.get_activity(activity.id)
    assert isinstance(loaded_run, PracticeRun)
    assert isinstance(loaded_activity, ActivityInstance)
    assert loaded_run == run
    assert loaded_activity == activity


def test_practice_repository_adds_rows_without_committing_and_checks_run_policy() -> None:
    from app.domain.practice import SelectionMetadata, SelectionReason
    from app.domain_models.practice import ActivityInstanceModel, PracticeRunModel
    from app.repositories.practice import PracticeRepository

    added = []

    class FakeSession:
        def add(self, row):
            added.append(row)

    repository = PracticeRepository(FakeSession())
    run = make_run()
    activity = make_activity()

    repository.add_run(run)
    repository.add_activity(run, activity)

    assert [type(row) for row in added] == [PracticeRunModel, ActivityInstanceModel]
    assert added[1].spec_payload == activity.spec.to_payload()
    assert added[1].selection_reason_payload == ["new_target"]
    mismatched = replace(
        activity,
        selection=SelectionMetadata(
            policy_version="other-v2",
            reasons=(SelectionReason.NEW_TARGET,),
        ),
    )
    with pytest.raises(ValueError, match="inherit"):
        repository.add_activity(run, mismatched)


def test_practice_repository_sqlite_round_trip_normalizes_timestamps_to_utc() -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.domain.practice import ActivityStatus, PracticeRunStatus
    from app.domain_models.practice import ActivityInstanceModel, PracticeRunModel
    from app.repositories.practice import (
        PracticeRepository,
        _activity_to_row,
        _run_to_row,
    )

    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE practice_runs (
                id TEXT PRIMARY KEY,
                learner_id TEXT NOT NULL,
                curriculum_version_id TEXT,
                legacy_quiz_attempt_id INTEGER,
                status TEXT NOT NULL,
                selection_policy_version TEXT NOT NULL,
                started_at TIMESTAMP NOT NULL,
                ended_at TIMESTAMP
            )
            """
        )
        connection.exec_driver_sql(
            """
            CREATE TABLE activity_instances (
                id TEXT PRIMARY KEY,
                practice_run_id TEXT NOT NULL,
                target_key TEXT NOT NULL,
                learning_intent TEXT NOT NULL,
                activity_kind TEXT NOT NULL,
                operation TEXT,
                sequence_number INTEGER NOT NULL,
                retry_of_activity_instance_id TEXT,
                attempt_number INTEGER NOT NULL,
                spec_payload JSON NOT NULL,
                selection_policy_version TEXT NOT NULL,
                selection_reason_payload JSON NOT NULL,
                selection_propensity REAL,
                generator_kind TEXT NOT NULL,
                generator_version TEXT NOT NULL,
                scorer_kind TEXT,
                scorer_version TEXT,
                status TEXT NOT NULL,
                selected_at TIMESTAMP NOT NULL,
                terminal_at TIMESTAMP
            )
            """
        )

    plus_two = timezone(timedelta(hours=2))
    local_time = datetime(2026, 8, 26, 12, 0, tzinfo=plus_two)
    local_terminal = local_time + timedelta(minutes=5)
    run = replace(
        make_run(),
        status=PracticeRunStatus.COMPLETED,
        started_at=local_time,
        ended_at=local_terminal,
    )
    activity = replace(
        make_activity(),
        status=ActivityStatus.COMPLETED,
        selected_at=local_time,
        terminal_at=local_terminal,
    )

    run_row = _run_to_row(run)
    activity_row = _activity_to_row(activity)
    run_values = {
        column.name: getattr(run_row, column.name)
        for column in PracticeRunModel.__table__.columns
    }
    activity_values = {
        column.name: getattr(activity_row, column.name)
        for column in ActivityInstanceModel.__table__.columns
    }
    with engine.begin() as connection:
        connection.execute(PracticeRunModel.__table__.insert(), run_values)
        connection.execute(ActivityInstanceModel.__table__.insert(), activity_values)

    with Session(engine) as session:
        repository = PracticeRepository(session)
        loaded_run = repository.get_run(run.id)
        loaded_activity = repository.get_activity(activity.id)

    expected = datetime(2026, 8, 26, 10, 0, tzinfo=timezone.utc)
    expected_terminal = expected + timedelta(minutes=5)
    assert loaded_run is not None and loaded_run.started_at == expected
    assert loaded_run.started_at.tzinfo is timezone.utc
    assert loaded_run.ended_at == expected_terminal
    assert loaded_run.ended_at.tzinfo is timezone.utc
    assert loaded_activity is not None and loaded_activity.selected_at == expected
    assert loaded_activity.selected_at.tzinfo is timezone.utc
    assert loaded_activity.terminal_at == expected_terminal
    assert loaded_activity.terminal_at.tzinfo is timezone.utc
