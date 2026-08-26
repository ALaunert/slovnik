from datetime import datetime, timezone
from typing import TypeVar

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.practice import (
    ActivityInstance,
    ActivitySpec,
    ActivityStatus,
    GeneratorKind,
    LearningIntent,
    PracticeRun,
    PracticeRunStatus,
    SelectionMetadata,
    SelectionReason,
)
from app.domain_models.practice import ActivityInstanceModel, PracticeRunModel


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
