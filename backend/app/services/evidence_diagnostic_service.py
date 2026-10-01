"""Read-only adapter from stored practice events/activities to diagnostic facts."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.domain.evidence_diagnostics import EvidenceClassification, EvidenceFact, classify_history


def _wire(value: Any) -> str | None:
    if value is None:
        return None
    return str(getattr(value, "value", value))


def diagnose_events(
    pairs: Iterable[tuple[Any, Any]],
) -> tuple[EvidenceClassification, ...]:
    """Classify loaded events; never persist, replay or update learner state."""
    loaded = list(pairs)
    event_id_by_activity = {activity.id: event.event_id for event, activity in loaded}
    facts: list[EvidenceFact] = []
    for event, activity in loaded:
        snapshot = activity.spec.snapshot
        hints = tuple(event.hints)
        support = _wire(hints[0].kind) if hints else (
            "none" if snapshot.get("support_capture_complete") is True else None
        )
        if support == "cue":
            support = "hint"
        response = event.first_response
        facts.append(EvidenceFact(
            event_id=event.event_id,
            occurred_at=event.occurred_at,
            event_type=_wire(event.event_type) or "unknown",
            evaluation_source=_wire(event.evaluation_source),
            evaluation_outcome=_wire(event.evaluation_outcome),
            response_present=response is not None,
            retry_of=event_id_by_activity.get(
                activity.retry_of_activity_instance_id,
                activity.retry_of_activity_instance_id,
            )
            if activity.retry_of_activity_instance_id else None,
            support=support,
            support_capture_complete=snapshot.get("support_capture_complete") is True,
            support_timing_known=snapshot.get("support_before_first") is True if hints else True,
            context_family=snapshot.get("context_family_id")
            if isinstance(snapshot.get("context_family_id"), str) else None,
            context_history_complete=snapshot.get("context_history_complete") is True,
            rating=_wire(getattr(response, "value", None))
            if _wire(event.evaluation_source) == "self_report" else None,
            lineage_key=f"{event.learner_id}:{event.target_key}"
            if hasattr(event, "learner_id") and hasattr(event, "target_key") else None,
        ))
    return classify_history(facts)
