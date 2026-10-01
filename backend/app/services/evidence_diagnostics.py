"""Read-only diagnostic adapter for retained learning events."""

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import timedelta, timezone

from app.domain.evidence import EvidenceClass, EvidenceObservation, classify_observation


def _wire(value: object) -> str | None:
    value = getattr(value, "value", value)
    return value if isinstance(value, str) else None


def observe_learning_event(activity: object | None, event: object) -> EvidenceObservation:
    """Use only persisted metadata; missing historical fields remain unknown."""
    spec = getattr(activity, "spec", None)
    snapshot = getattr(spec, "snapshot", None)
    if not isinstance(snapshot, Mapping):
        snapshot = {}
    raw_hints = getattr(event, "hints", None)
    hints = None if raw_hints is None else tuple(_wire(getattr(hint, "kind", hint)) or "unknown" for hint in raw_hints)
    return EvidenceObservation(
        event_id=str(getattr(event, "event_id")),
        target_key=str(getattr(event, "target_key")),
        occurred_at=getattr(event, "occurred_at"),
        event_type=_wire(getattr(event, "event_type", None)),
        evaluation_source=_wire(getattr(event, "evaluation_source", None)),
        evaluation_outcome=_wire(getattr(event, "evaluation_outcome", None)),
        has_first_response=getattr(event, "first_response", None) is not None,
        hints=hints,
        retry_of_activity_id=getattr(activity, "retry_of_activity_instance_id", None),
        attempt_number=getattr(activity, "attempt_number", None),
        context_family_id=snapshot.get("context_family_id") if isinstance(snapshot.get("context_family_id"), str) else None,
        content_revision_id=snapshot.get("content_revision_id") if isinstance(snapshot.get("content_revision_id"), str) else None,
        activity_instance_id=getattr(event, "activity_instance_id", None),
        has_final_response=getattr(event, "final_response", None) is not None,
        repair_outcome=_wire(getattr(event, "repair_outcome", None)),
        support_timing=_wire(getattr(event, "support_timing", None)),
        held_out=snapshot.get("held_out") if type(snapshot.get("held_out")) is bool else None,
    )


@dataclass(frozen=True)
class EvidenceDiagnostics:
    version: int
    counts: Mapping[str, int]
    first_eligible: int
    first_correct: int
    recovered: int
    assisted_correct: int
    self_reports: int
    unresolved: int
    distinct_contexts: int
    targets_with_multiple_contexts: int
    context_unknown: int
    delayed_new_context_eligible: int
    delayed_new_context_correct: int


def diagnose_observations(observations: Iterable[EvidenceObservation]) -> EvidenceDiagnostics:
    """Reconcile observations without writing events, projections, or schedules."""
    by_id: dict[str, EvidenceObservation] = {}
    for observation in observations:
        previous = by_id.setdefault(observation.event_id, observation)
        if previous != observation:
            raise ValueError("Conflicting observations share an event ID")
    ordered = sorted(
        by_id.values(),
        key=lambda item: (item.occurred_at.astimezone(timezone.utc), item.event_id),
    )
    counts: Counter[str] = Counter()
    parents: dict[str, list[EvidenceObservation]] = defaultdict(list)
    for observation in ordered:
        if observation.activity_instance_id and observation.event_type == "response_evaluated":
            parents[observation.activity_instance_id].append(observation)
    first_at: dict[str, object] = {}
    contexts: dict[str, set[str]] = defaultdict(set)
    distinct_contexts = context_unknown = delayed_eligible = delayed_correct = 0
    for observation in ordered:
        category = classify_observation(observation)
        if category is EvidenceClass.RETRY_CORRECT:
            parent_events = parents.get(observation.retry_of_activity_id or "", [])
            if (
                len(parent_events) == 1
                and parent_events[0].target_key == observation.target_key
                and parent_events[0].occurred_at < observation.occurred_at
                and classify_observation(parent_events[0]) is EvidenceClass.FIRST_UNAIDED_INCORRECT
            ):
                category = EvidenceClass.RECOVERED
        counts[category.value] += 1
        if category not in {EvidenceClass.FIRST_UNAIDED_CORRECT, EvidenceClass.FIRST_UNAIDED_INCORRECT}:
            continue
        target = observation.target_key
        first_at.setdefault(target, observation.occurred_at)
        family = observation.context_family_id
        revision = observation.content_revision_id
        if not family or not revision:
            context_unknown += 1
            continue
        if family in contexts[target]:
            continue
        has_prior_known_family = bool(contexts[target])
        contexts[target].add(family)
        distinct_contexts += 1
        if (
            has_prior_known_family
            and observation.held_out is True
            and observation.occurred_at - first_at[target] >= timedelta(days=7)
        ):
            delayed_eligible += 1
            delayed_correct += int(category is EvidenceClass.FIRST_UNAIDED_CORRECT)
    return EvidenceDiagnostics(
        version=1,
        counts=dict(counts),
        first_eligible=counts[EvidenceClass.FIRST_UNAIDED_CORRECT.value] + counts[EvidenceClass.FIRST_UNAIDED_INCORRECT.value],
        first_correct=counts[EvidenceClass.FIRST_UNAIDED_CORRECT.value],
        recovered=counts[EvidenceClass.RECOVERED.value],
        assisted_correct=counts[EvidenceClass.ASSISTED_CORRECT.value],
        self_reports=counts[EvidenceClass.SELF_REPORT.value],
        unresolved=counts[EvidenceClass.UNRESOLVED.value],
        distinct_contexts=distinct_contexts,
        targets_with_multiple_contexts=sum(len(families) >= 2 for families in contexts.values()),
        context_unknown=context_unknown,
        delayed_new_context_eligible=delayed_eligible,
        delayed_new_context_correct=delayed_correct,
    )


def diagnose_learner_history(session, learner_id: str) -> EvidenceDiagnostics:
    """Read persisted events for one learner without flushing or changing projections."""
    from sqlalchemy import select

    from app.domain_models.practice import LearningEventModel
    from app.repositories.practice import PracticeRepository

    repository = PracticeRepository(session)
    observations: list[EvidenceObservation] = []
    with session.no_autoflush:
        keys = tuple(
            session.scalars(
                select(LearningEventModel.idempotency_key)
                .where(LearningEventModel.learner_id == learner_id)
                .order_by(LearningEventModel.occurred_at, LearningEventModel.id)
            )
        )
        for key in keys:
            event = repository.get_learning_event(learner_id, key)
            if event is None:
                raise RuntimeError("Stored learning event disappeared during diagnostics")
            activity = repository.get_activity(event.activity_instance_id)
            observations.append(observe_learning_event(activity, event))
    return diagnose_observations(observations)
