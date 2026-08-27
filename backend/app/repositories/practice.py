from collections.abc import Mapping
from datetime import datetime, timezone
from typing import TypeVar

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.practice import (
    ActivityInstance,
    ActivityKind,
    ActivitySpec,
    ActivityStatus,
    CueLevel,
    Evaluation,
    EvaluationOutcome,
    EvaluationSource,
    ExerciseOperation,
    FeedbackSnapshot,
    GeneratorKind,
    HintKind,
    HintSnapshot,
    LearningEvent,
    LearningEventType,
    LearningIntent,
    LegacySourceRef,
    PracticeRun,
    PracticeRunStatus,
    RepairOutcome,
    ResponseKind,
    ResponseSnapshot,
    SelectionMetadata,
    SelectionReason,
)
from app.domain.shared import Modality
from app.domain.target import TargetSpec
from app.domain_models.practice import (
    ActivityInstanceModel,
    LearningEventModel,
    PracticeRunModel,
)


_RowT = TypeVar("_RowT")


def _to_utc(value: datetime | None) -> datetime | None:
    return value.astimezone(timezone.utc) if value is not None else None


def _from_db_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _flush_if_supported(session: Session) -> None:
    flush = getattr(session, "flush", None)
    if flush is not None:
        flush()


class PracticeRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_run(self, run_id: str) -> PracticeRun | None:
        row = self._session.get(PracticeRunModel, run_id)
        return _run_to_domain(row) if row is not None else None

    def get_activity(self, activity_id: str) -> ActivityInstance | None:
        row = self._session.get(ActivityInstanceModel, activity_id)
        return _activity_to_domain(row) if row is not None else None

    def lock_run(self, run_id: str) -> PracticeRun | None:
        row = self._session.scalar(
            select(PracticeRunModel)
            .where(PracticeRunModel.id == run_id)
            .with_for_update()
        )
        return _run_to_domain(row) if row is not None else None

    def lock_activity(self, activity_id: str) -> ActivityInstance | None:
        row = self._session.scalar(
            select(ActivityInstanceModel)
            .where(ActivityInstanceModel.id == activity_id)
            .with_for_update()
        )
        return _activity_to_domain(row) if row is not None else None

    def list_activities(self, run_id: str) -> tuple[ActivityInstance, ...]:
        rows = self._session.scalars(_activities_for_run(run_id))
        return tuple(_activity_to_domain(row) for row in rows)

    def lock_activities(self, run_id: str) -> tuple[ActivityInstance, ...]:
        rows = self._session.scalars(_activities_for_run(run_id).with_for_update())
        return tuple(_activity_to_domain(row) for row in rows)

    def next_sequence_number(self, run_id: str) -> int:
        current = self._session.scalar(
            select(func.max(ActivityInstanceModel.sequence_number)).where(
                ActivityInstanceModel.practice_run_id == run_id
            )
        )
        return (current or 0) + 1

    def add_run(self, run: PracticeRun) -> None:
        self._session.add(_run_to_row(run))
        _flush_if_supported(self._session)

    def add_activity(self, run: PracticeRun, activity: ActivityInstance) -> None:
        run.validate_activity(activity)
        self._session.add(_activity_to_row(activity))
        _flush_if_supported(self._session)

    def update_run(self, run: PracticeRun) -> None:
        row = _require_row(
            self._session.get(PracticeRunModel, run.id),
            "Practice run",
        )
        row.status = run.status.value
        row.ended_at = _to_utc(run.ended_at)

    def update_activity(self, activity: ActivityInstance) -> None:
        row = _require_row(
            self._session.get(ActivityInstanceModel, activity.id),
            "Practice activity",
        )
        row.status = activity.status.value
        row.terminal_at = _to_utc(activity.terminal_at)

    def database_now(self) -> datetime:
        dialect_name = self._session.get_bind().dialect.name
        if dialect_name == "postgresql":
            value = self._session.scalar(select(func.clock_timestamp()))
        elif dialect_name == "sqlite":
            raw_value = self._session.scalar(
                select(func.strftime("%Y-%m-%d %H:%M:%f", "now"))
            )
            if not isinstance(raw_value, str):
                raise ValueError("Database clock did not return a timestamp")
            value = datetime.fromisoformat(raw_value)
        else:
            value = self._session.scalar(select(func.current_timestamp()))
        if not isinstance(value, datetime):
            raise ValueError("Database clock did not return a timestamp")
        normalized = _from_db_utc(value)
        assert normalized is not None
        return normalized

    def get_learning_event(
        self,
        learner_id: str,
        idempotency_key: str,
    ) -> LearningEvent | None:
        row = self._session.scalar(
            select(LearningEventModel).where(
                LearningEventModel.learner_id == learner_id,
                LearningEventModel.idempotency_key == idempotency_key,
            )
        )
        return _event_to_domain(row) if row is not None else None

    def add_learning_event(self, event: LearningEvent) -> None:
        self._session.add(_event_to_row(event))
        _flush_if_supported(self._session)


def _require_row(row: _RowT | None, label: str) -> _RowT:
    if row is None:
        raise ValueError(f"{label} not found")
    return row


def _activities_for_run(run_id: str):
    return (
        select(ActivityInstanceModel)
        .where(ActivityInstanceModel.practice_run_id == run_id)
        .order_by(ActivityInstanceModel.sequence_number)
    )


def _run_to_row(run: PracticeRun) -> PracticeRunModel:
    return PracticeRunModel(
        id=run.id,
        learner_id=run.learner_id,
        curriculum_version_id=run.curriculum_version_id,
        legacy_quiz_attempt_id=run.legacy_quiz_attempt_id,
        status=run.status.value,
        selection_policy_version=run.selection_policy_version,
        started_at=_to_utc(run.started_at),
        ended_at=_to_utc(run.ended_at),
    )


def _activity_to_row(activity: ActivityInstance) -> ActivityInstanceModel:
    return ActivityInstanceModel(
        id=activity.id,
        practice_run_id=activity.practice_run_id,
        target_key=activity.target_key,
        learning_intent=activity.learning_intent.value,
        activity_kind=activity.activity_kind.value,
        operation=activity.operation.value if activity.operation else None,
        sequence_number=activity.sequence_number,
        retry_of_activity_instance_id=activity.retry_of_activity_instance_id,
        attempt_number=activity.attempt_number,
        spec_payload=activity.spec.to_payload(),
        selection_policy_version=activity.selection.policy_version,
        selection_reason_payload=activity.selection.to_payload(),
        selection_propensity=activity.selection.propensity,
        generator_kind=activity.generator_kind.value,
        generator_version=activity.generator_version,
        scorer_kind=activity.scorer_kind.value if activity.scorer_kind else None,
        scorer_version=activity.scorer_version,
        status=activity.status.value,
        selected_at=_to_utc(activity.selected_at),
        terminal_at=_to_utc(activity.terminal_at),
    )


def _event_to_row(event: LearningEvent) -> LearningEventModel:
    return LearningEventModel(
        id=event.event_id,
        schema_version=event.schema_version,
        learner_id=event.learner_id,
        practice_run_id=event.practice_run_id,
        activity_instance_id=event.activity_instance_id,
        target_key=event.target_key,
        event_type=event.event_type.value,
        activity_kind=event.activity_kind.value,
        observation_payload=event.to_observation_payload(),
        idempotency_key=event.idempotency_key,
        occurred_at=_to_utc(event.occurred_at),
        created_at=_to_utc(event.created_at),
    )


def _run_to_domain(row: PracticeRunModel) -> PracticeRun:
    return PracticeRun(
        id=row.id,
        learner_id=row.learner_id,
        curriculum_version_id=row.curriculum_version_id,
        legacy_quiz_attempt_id=row.legacy_quiz_attempt_id,
        status=PracticeRunStatus(row.status),
        selection_policy_version=row.selection_policy_version,
        started_at=_from_db_utc(row.started_at),
        ended_at=_from_db_utc(row.ended_at),
    )


def _activity_to_domain(row: ActivityInstanceModel) -> ActivityInstance:
    spec = ActivitySpec.from_payload(row.spec_payload)
    if row.target_key != spec.target_key:
        raise ValueError("Stored activity target_key does not match its snapshot")
    if row.activity_kind != spec.activity_kind.value:
        raise ValueError("Stored activity kind does not match its snapshot")
    stored_operation = row.operation
    snapshot_operation = spec.operation.value if spec.operation else None
    if stored_operation != snapshot_operation:
        raise ValueError("Stored activity operation does not match its snapshot")
    stored_scorer = row.scorer_kind
    snapshot_scorer = spec.scorer_kind.value if spec.scorer_kind else None
    if stored_scorer != snapshot_scorer:
        raise ValueError("Stored activity scorer does not match its snapshot")

    return ActivityInstance(
        id=row.id,
        practice_run_id=row.practice_run_id,
        spec=spec,
        learning_intent=LearningIntent(row.learning_intent),
        sequence_number=row.sequence_number,
        retry_of_activity_instance_id=row.retry_of_activity_instance_id,
        attempt_number=row.attempt_number,
        selection=SelectionMetadata(
            policy_version=row.selection_policy_version,
            reasons=tuple(
                SelectionReason(reason) for reason in row.selection_reason_payload
            ),
            propensity=row.selection_propensity,
        ),
        generator_kind=GeneratorKind(row.generator_kind),
        generator_version=row.generator_version,
        scorer_version=row.scorer_version,
        status=ActivityStatus(row.status),
        selected_at=_from_db_utc(row.selected_at),
        terminal_at=_from_db_utc(row.terminal_at),
    )


def _event_to_domain(row: LearningEventModel) -> LearningEvent:
    payload = row.observation_payload
    if not isinstance(payload, dict):
        raise ValueError("Stored learning event observation must be an object")
    expected_fields = {
        "target_spec",
        "learning_intent",
        "operation",
        "input_modality",
        "output_modality",
        "cue_level",
        "first_response",
        "final_response",
        "evaluation_source",
        "evaluation_outcome",
        "evaluation_confidence",
        "partial_score",
        "error_tags",
        "latency_ms",
        "hints",
        "learner_confidence",
        "feedback",
        "repair_outcome",
        "legacy_source",
        "generator_kind",
        "generator_version",
        "scorer_version",
        "selection_policy_version",
        "selection_reasons",
        "selection_propensity",
    }
    if set(payload) != expected_fields:
        raise ValueError("Stored learning event observation fields are invalid")
    target_payload = _mapping(payload["target_spec"], "target_spec")
    target_spec = TargetSpec.from_payload(target_payload)
    if row.target_key != target_spec.target_key:
        raise ValueError("Stored learning event target_key does not match its snapshot")
    evaluation = _evaluation_from_payload(payload)
    occurred_at = _from_db_utc(row.occurred_at)
    created_at = _from_db_utc(row.created_at)
    assert occurred_at is not None and created_at is not None
    return LearningEvent(
        event_id=row.id,
        schema_version=row.schema_version,
        learner_id=row.learner_id,
        practice_run_id=row.practice_run_id,
        activity_instance_id=row.activity_instance_id,
        target_spec=target_spec,
        event_type=LearningEventType(row.event_type),
        learning_intent=LearningIntent(payload["learning_intent"]),
        activity_kind=ActivityKind(row.activity_kind),
        operation=_optional_payload_enum(ExerciseOperation, payload["operation"]),
        input_modality=Modality(payload["input_modality"]),
        output_modality=_optional_payload_enum(Modality, payload["output_modality"]),
        cue_level=CueLevel(payload["cue_level"]),
        first_response=_response_from_payload(payload["first_response"]),
        final_response=_response_from_payload(payload["final_response"]),
        evaluation=evaluation,
        latency_ms=payload["latency_ms"],
        hints=_hints_from_payload(payload["hints"]),
        learner_confidence=payload["learner_confidence"],
        feedback=_feedback_from_payload(payload["feedback"]),
        repair_outcome=_optional_payload_enum(
            RepairOutcome,
            payload["repair_outcome"],
        ),
        legacy_source=_legacy_source_from_payload(payload["legacy_source"]),
        generator_kind=GeneratorKind(payload["generator_kind"]),
        generator_version=payload["generator_version"],
        scorer_version=payload["scorer_version"],
        selection=SelectionMetadata(
            policy_version=payload["selection_policy_version"],
            reasons=tuple(
                SelectionReason(reason) for reason in payload["selection_reasons"]
            ),
            propensity=payload["selection_propensity"],
        ),
        idempotency_key=row.idempotency_key,
        occurred_at=occurred_at,
        created_at=created_at,
    )


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"Stored learning event {label} must be an object")
    return value


def _optional_payload_enum(enum_type, value: object):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Stored optional event enum must be null or a string")
    return enum_type(value)


def _response_from_payload(value: object) -> ResponseSnapshot | None:
    if value is None:
        return None
    payload = _mapping(value, "response")
    if set(payload) != {"kind", "value", "truncated"}:
        raise ValueError("Stored learning event response fields are invalid")
    return ResponseSnapshot(
        kind=ResponseKind(payload["kind"]),
        value=payload["value"],
        truncated=payload["truncated"],
    )


def _evaluation_from_payload(payload: Mapping[str, object]) -> Evaluation | None:
    source = payload["evaluation_source"]
    outcome = payload["evaluation_outcome"]
    if source is None and outcome is None:
        if any(
            payload[field] is not None
            for field in ("evaluation_confidence", "partial_score")
        ) or payload["error_tags"] != []:
            raise ValueError("Stored exposure evaluation fields must be empty")
        return None
    if not isinstance(payload["error_tags"], list):
        raise ValueError("Stored learning event error_tags must be an array")
    return Evaluation(
        source=EvaluationSource(source),
        outcome=EvaluationOutcome(outcome),
        confidence=payload["evaluation_confidence"],
        partial_score=payload["partial_score"],
        error_tags=tuple(payload["error_tags"]),
    )


def _hints_from_payload(value: object) -> tuple[HintSnapshot, ...]:
    if not isinstance(value, list):
        raise ValueError("Stored learning event hints must be an array")
    hints: list[HintSnapshot] = []
    for item in value:
        payload = _mapping(item, "hint")
        if set(payload) != {"kind", "sequence_number"}:
            raise ValueError("Stored learning event hint fields are invalid")
        hints.append(
            HintSnapshot(
                kind=HintKind(payload["kind"]),
                sequence_number=payload["sequence_number"],
            )
        )
    return tuple(hints)


def _feedback_from_payload(value: object) -> FeedbackSnapshot | None:
    if value is None:
        return None
    payload = _mapping(value, "feedback")
    if set(payload) != {"code", "delivered_at"}:
        raise ValueError("Stored learning event feedback fields are invalid")
    delivered_at = payload["delivered_at"]
    if not isinstance(delivered_at, str):
        raise ValueError("Stored learning event feedback timestamp is invalid")
    return FeedbackSnapshot(
        code=payload["code"],
        delivered_at=datetime.fromisoformat(delivered_at.replace("Z", "+00:00")),
    )


def _legacy_source_from_payload(value: object) -> LegacySourceRef | None:
    if value is None:
        return None
    payload = _mapping(value, "legacy source")
    if set(payload) != {"kind", "reference"}:
        raise ValueError("Stored learning event legacy source fields are invalid")
    return LegacySourceRef(kind=payload["kind"], reference=payload["reference"])
