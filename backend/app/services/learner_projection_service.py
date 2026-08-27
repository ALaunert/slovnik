from collections.abc import Iterable
from dataclasses import replace
from datetime import datetime, timezone

from app.domain.memory_policy import MemoryPolicyV1
from app.domain.progress import (
    PROJECTION_POLICY_VERSION,
    BaselineKind,
    CompetenceEstimate,
    EvidenceSummary,
    LearnerTargetState,
    LearningEventSource,
    LearningEventView,
)
from app.repositories.progress import ProgressRepository


MEMORY_POLICY = MemoryPolicyV1()


def _wire_value(value: object) -> object:
    return getattr(value, "value", value)


def _uncertainty(success_weight: float, failure_weight: float) -> float:
    return 2 / (2 + success_weight + failure_weight)


def _is_deterministic_response(event: LearningEventView) -> bool:
    return (
        _wire_value(getattr(event, "event_type", None)) == "response_evaluated"
        and _wire_value(getattr(event, "evaluation_source", None))
        == "deterministic"
    )


def _project_competence(
    competence: CompetenceEstimate,
    event: LearningEventView,
) -> CompetenceEstimate:
    if not _is_deterministic_response(event):
        return competence
    outcome = _wire_value(getattr(event, "evaluation_outcome", None))
    if outcome == "incorrect":
        failure_weight = competence.failure_weight + 1
        return CompetenceEstimate(
            success_weight=competence.success_weight,
            failure_weight=failure_weight,
            peak=competence.peak,
            uncertainty=_uncertainty(competence.success_weight, failure_weight),
        )
    if outcome != "correct":
        return competence
    success_weight = competence.success_weight + 1
    peak = max(
        competence.peak,
        (1 + success_weight) / (2 + success_weight + competence.failure_weight),
    )
    return CompetenceEstimate(
        success_weight=success_weight,
        failure_weight=competence.failure_weight,
        peak=peak,
        uncertainty=_uncertainty(success_weight, competence.failure_weight),
    )


def project_event(
    state: LearnerTargetState,
    event: LearningEventView,
) -> LearnerTargetState:
    return replace(
        state,
        competence=_project_competence(state.competence, event),
        evidence=EvidenceSummary(
            count=state.evidence.count + 1,
            deterministic_count=(
                state.evidence.deterministic_count
                + int(_is_deterministic_response(event))
            ),
            last_evidence_at=event.occurred_at,
            last_event_id=event.event_id,
        ),
        memory=MEMORY_POLICY.apply(state.memory, event),
        projection_policy_version=PROJECTION_POLICY_VERSION,
        updated_at=event.occurred_at,
    )


def _event_key(event: LearningEventView) -> tuple[datetime, str]:
    return event.occurred_at.astimezone(timezone.utc), event.event_id


def _cursor_key(state: LearnerTargetState) -> tuple[datetime, str] | None:
    if state.evidence.count == 0:
        return None
    assert state.evidence.last_evidence_at is not None
    assert state.evidence.last_event_id is not None
    return state.evidence.last_evidence_at, state.evidence.last_event_id


def _reset_to_baseline(state: LearnerTargetState) -> LearnerTargetState:
    if state.baseline.kind is BaselineKind.NEUTRAL:
        return LearnerTargetState.neutral(
            state_id=state.state_id,
            learner_id=state.learner_id,
            target_key=state.target_key,
            updated_at=state.updated_at,
        )
    return LearnerTargetState.legacy_bootstrap(
        state_id=state.state_id,
        learner_id=state.learner_id,
        target_key=state.target_key,
        baseline=state.baseline,
        updated_at=state.updated_at,
    )


def _canonical_events(
    events: Iterable[LearningEventView],
) -> tuple[LearningEventView, ...]:
    return tuple(sorted(events, key=_event_key))


def replay_events(
    state: LearnerTargetState,
    events: Iterable[LearningEventView],
) -> LearnerTargetState:
    projected = _reset_to_baseline(state)
    for event in _canonical_events(events):
        projected = project_event(projected, event)
    return projected


class LearnerProjectionService:
    def __init__(
        self,
        repository: ProgressRepository,
        event_source: LearningEventSource,
    ) -> None:
        self._repository = repository
        self._event_source = event_source

    def apply_event(self, event: LearningEventView) -> LearnerTargetState:
        self._repository.ensure_state(
            learner_id=event.learner_id,
            target_key=event.target_key,
            updated_at=event.occurred_at,
        )
        state = self._repository.lock_state(event.learner_id, event.target_key)
        if state is None:
            raise RuntimeError("Projection state disappeared after materialization")
        cursor_key = _cursor_key(state)
        event_key = _event_key(event)
        if cursor_key == event_key:
            return state
        if cursor_key is not None and event_key < cursor_key:
            projected = replay_events(
                state,
                self._event_source.events_for_target(
                    learner_id=event.learner_id,
                    target_key=event.target_key,
                ),
            )
        else:
            projected = project_event(state, event)
        self._repository.save_projection(projected)
        return projected
