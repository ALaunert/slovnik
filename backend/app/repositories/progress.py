from collections.abc import Mapping
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.progress import (
    BaselineKind,
    CompetenceEstimate,
    EvidenceSummary,
    LearnerProfile,
    LearnerTargetState,
    MemoryState,
    ProjectionBaseline,
)
from app.domain_models.progress import LearnerTargetStateModel
from app.models import UserProfile


LEARNER_TARGET_UNIQUE_CONSTRAINT = "uq_learner_target_states_learner_target"
SQLITE_LEARNER_TARGET_UNIQUE_ERROR = (
    "UNIQUE constraint failed: learner_target_states.learner_id, "
    "learner_target_states.target_key"
)


def _is_learner_target_unique_conflict(error: IntegrityError) -> bool:
    original = error.orig
    diagnostics = getattr(original, "diag", None)
    constraint_name = getattr(diagnostics, "constraint_name", None)
    if constraint_name is None:
        constraint_name = getattr(original, "constraint_name", None)
    if constraint_name is not None:
        return constraint_name == LEARNER_TARGET_UNIQUE_CONSTRAINT
    return str(original) == SQLITE_LEARNER_TARGET_UNIQUE_ERROR


def _plain_payload(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _plain_payload(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain_payload(item) for item in value]
    return value


def _to_baseline(row: LearnerTargetStateModel) -> ProjectionBaseline:
    return ProjectionBaseline(
        kind=BaselineKind(row.baseline_kind),
        memory_due_at=row.baseline_memory_due_at,
        memory_interval_days=row.baseline_memory_interval_days,
        payload=row.baseline_payload,
    )


def _to_domain(row: LearnerTargetStateModel) -> LearnerTargetState:
    return LearnerTargetState(
        state_id=row.id,
        learner_id=row.learner_id,
        target_key=row.target_key,
        baseline=_to_baseline(row),
        competence=CompetenceEstimate(
            success_weight=row.competence_success_weight,
            failure_weight=row.competence_failure_weight,
            peak=row.competence_peak,
            uncertainty=row.uncertainty,
        ),
        evidence=EvidenceSummary(
            count=row.evidence_count,
            deterministic_count=row.deterministic_evidence_count,
            last_evidence_at=row.last_evidence_at,
            last_event_id=row.last_event_id,
        ),
        memory=MemoryState(
            due_at=row.memory_due_at,
            interval_days=row.memory_interval_days,
            lapses=row.memory_lapses,
            policy_version=row.memory_policy_version,
        ),
        projection_policy_version=row.projection_policy_version,
        updated_at=row.updated_at,
    )


def _to_model(state: LearnerTargetState) -> LearnerTargetStateModel:
    payload = _plain_payload(state.baseline.payload)
    assert isinstance(payload, dict)
    return LearnerTargetStateModel(
        id=state.state_id,
        learner_id=state.learner_id,
        target_key=state.target_key,
        competence_success_weight=state.competence.success_weight,
        competence_failure_weight=state.competence.failure_weight,
        competence_peak=state.competence.peak,
        uncertainty=state.competence.uncertainty,
        evidence_count=state.evidence.count,
        deterministic_evidence_count=state.evidence.deterministic_count,
        baseline_kind=state.baseline.kind.value,
        baseline_memory_due_at=state.baseline.memory_due_at,
        baseline_memory_interval_days=state.baseline.memory_interval_days,
        baseline_payload=payload,
        last_evidence_at=state.evidence.last_evidence_at,
        last_event_id=state.evidence.last_event_id,
        memory_due_at=state.memory.due_at,
        memory_interval_days=state.memory.interval_days,
        memory_lapses=state.memory.lapses,
        memory_policy_version=state.memory.policy_version,
        projection_policy_version=state.projection_policy_version,
        updated_at=state.updated_at,
    )


class ProgressRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_profile(self, learner_id: str) -> LearnerProfile | None:
        profile = self._session.get(UserProfile, learner_id)
        if profile is None:
            return None
        return LearnerProfile.from_legacy(profile)

    def get_state(
        self,
        learner_id: str,
        target_key: str,
    ) -> LearnerTargetState | None:
        row = self._find_state_row(learner_id, target_key)
        return None if row is None else _to_domain(row)

    load_state = get_state

    def lock_state(
        self,
        learner_id: str,
        target_key: str,
    ) -> LearnerTargetState | None:
        row = self._session.scalar(
            self._state_statement(learner_id, target_key).with_for_update()
        )
        return None if row is None else _to_domain(row)

    def ensure_state(
        self,
        *,
        learner_id: str,
        target_key: str,
        state_id: str | None = None,
        updated_at: datetime | None = None,
    ) -> LearnerTargetState:
        existing = self._find_state_row(learner_id, target_key)
        if existing is not None:
            return _to_domain(existing)

        state = LearnerTargetState.neutral(
            state_id=state_id if state_id is not None else str(uuid4()),
            learner_id=learner_id,
            target_key=target_key,
            updated_at=(
                updated_at if updated_at is not None else datetime.now(timezone.utc)
            ),
        )
        try:
            with self._session.begin_nested():
                self._session.add(_to_model(state))
                self._session.flush()
        except IntegrityError as exc:
            if not _is_learner_target_unique_conflict(exc):
                raise
            existing = self._find_state_row(learner_id, target_key)
            if existing is None:
                raise
            return _to_domain(existing)
        return state

    def save_projection(self, state: LearnerTargetState) -> None:
        row = self._session.get(LearnerTargetStateModel, state.state_id)
        if (
            row is None
            or row.learner_id != state.learner_id
            or row.target_key != state.target_key
        ):
            raise ValueError("Projection state identity does not match its stored row")
        row.competence_success_weight = state.competence.success_weight
        row.competence_failure_weight = state.competence.failure_weight
        row.competence_peak = state.competence.peak
        row.uncertainty = state.competence.uncertainty
        row.evidence_count = state.evidence.count
        row.deterministic_evidence_count = state.evidence.deterministic_count
        row.last_evidence_at = state.evidence.last_evidence_at
        row.last_event_id = state.evidence.last_event_id
        row.memory_due_at = state.memory.due_at
        row.memory_interval_days = state.memory.interval_days
        row.memory_lapses = state.memory.lapses
        row.memory_policy_version = state.memory.policy_version
        row.projection_policy_version = state.projection_policy_version
        row.updated_at = state.updated_at
        self._session.flush()

    def bootstrap_legacy_state(self, state: LearnerTargetState) -> str:
        row = self._session.scalar(
            self._state_statement(state.learner_id, state.target_key).with_for_update()
        )
        if row is None:
            try:
                with self._session.begin_nested():
                    self._session.add(_to_model(state))
                    self._session.flush()
            except IntegrityError as exc:
                if not _is_learner_target_unique_conflict(exc):
                    raise
                row = self._session.scalar(
                    self._state_statement(
                        state.learner_id,
                        state.target_key,
                    ).with_for_update()
                )
                if row is None:
                    raise
            else:
                return "created"

        existing = _to_domain(row)
        if (
            existing.baseline.kind is not BaselineKind.LEGACY_BOOTSTRAP
            or existing.evidence.count > 0
        ):
            return "skipped_frozen"
        if existing.baseline.payload == state.baseline.payload:
            return "unchanged"

        self._apply_legacy_bootstrap(row, state)
        self._session.flush()
        return "updated"

    @staticmethod
    def _apply_legacy_bootstrap(
        row: LearnerTargetStateModel,
        state: LearnerTargetState,
    ) -> None:
        payload = _plain_payload(state.baseline.payload)
        assert isinstance(payload, dict)
        row.competence_success_weight = state.competence.success_weight
        row.competence_failure_weight = state.competence.failure_weight
        row.competence_peak = state.competence.peak
        row.uncertainty = state.competence.uncertainty
        row.evidence_count = state.evidence.count
        row.deterministic_evidence_count = state.evidence.deterministic_count
        row.baseline_kind = state.baseline.kind.value
        row.baseline_memory_due_at = state.baseline.memory_due_at
        row.baseline_memory_interval_days = state.baseline.memory_interval_days
        row.baseline_payload = payload
        row.last_evidence_at = state.evidence.last_evidence_at
        row.last_event_id = state.evidence.last_event_id
        row.memory_due_at = state.memory.due_at
        row.memory_interval_days = state.memory.interval_days
        row.memory_lapses = state.memory.lapses
        row.memory_policy_version = state.memory.policy_version
        row.projection_policy_version = state.projection_policy_version
        row.updated_at = state.updated_at

    def _find_state_row(
        self,
        learner_id: str,
        target_key: str,
    ) -> LearnerTargetStateModel | None:
        return self._session.scalar(self._state_statement(learner_id, target_key))

    @staticmethod
    def _state_statement(learner_id: str, target_key: str):
        return select(LearnerTargetStateModel).where(
            LearnerTargetStateModel.learner_id == learner_id,
            LearnerTargetStateModel.target_key == target_key,
        )
