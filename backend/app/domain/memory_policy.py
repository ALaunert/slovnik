from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Protocol, runtime_checkable

from .progress import MEMORY_POLICY_VERSION, LearningEventView, MemoryState


DETERMINISTIC_INTERVAL_CAP_DAYS = 180
EASY_INTERVAL_CAP_DAYS = 365


@runtime_checkable
class MemoryPolicy(Protocol):
    version: str

    def apply(self, state: MemoryState, event: LearningEventView) -> MemoryState: ...


def _wire_value(value: object) -> object:
    return getattr(value, "value", value)


def _is_evaluation(
    event: LearningEventView,
    *,
    source: str,
    outcome: str,
) -> bool:
    return (
        _wire_value(getattr(event, "event_type", None)) == "response_evaluated"
        and _wire_value(getattr(event, "evaluation_source", None)) == source
        and _wire_value(getattr(event, "evaluation_outcome", None)) == outcome
    )


def _doubled_interval(interval_days: int) -> int:
    return (
        1
        if interval_days == 0
        else min(interval_days * 2, DETERMINISTIC_INTERVAL_CAP_DAYS)
    )


def _self_report_rating(event: LearningEventView) -> str | None:
    if not _is_evaluation(event, source="self_report", outcome="unknown"):
        return None
    response = getattr(event, "first_response", None)
    if isinstance(response, Mapping):
        kind = _wire_value(response.get("kind"))
        value = _wire_value(response.get("value"))
    else:
        kind = _wire_value(getattr(response, "kind", None))
        value = _wire_value(getattr(response, "value", None))
    if kind != "rating" or value not in {"again", "hard", "good", "easy"}:
        raise ValueError("Self-report event requires a validated rating response")
    assert isinstance(value, str)
    return value


def _rating_interval(rating: str, current_interval: int) -> int:
    if rating == "again":
        return 0
    if rating == "hard":
        return 1
    if rating == "good":
        return (
            2
            if current_interval < 2
            else min(current_interval * 2, DETERMINISTIC_INTERVAL_CAP_DAYS)
        )
    return (
        4
        if current_interval < 4
        else min(current_interval * 3, EASY_INTERVAL_CAP_DAYS)
    )


def _scheduled(
    state: MemoryState,
    *,
    due_at: datetime,
    interval_days: int,
    lapse_increment: int = 0,
) -> MemoryState:
    return MemoryState(
        due_at=due_at,
        interval_days=interval_days,
        lapses=state.lapses + lapse_increment,
        policy_version=MEMORY_POLICY_VERSION,
    )


class MemoryPolicyV1:
    version = MEMORY_POLICY_VERSION

    def apply(self, state: MemoryState, event: LearningEventView) -> MemoryState:
        if _is_evaluation(event, source="deterministic", outcome="correct"):
            interval_days = _doubled_interval(state.interval_days)
            return _scheduled(
                state,
                due_at=event.occurred_at + timedelta(days=interval_days),
                interval_days=interval_days,
            )
        if _is_evaluation(event, source="deterministic", outcome="incorrect"):
            return _scheduled(
                state,
                due_at=event.occurred_at,
                interval_days=0,
                lapse_increment=1,
            )
        rating = _self_report_rating(event)
        if rating == "again":
            return _scheduled(
                state,
                due_at=event.occurred_at + timedelta(minutes=10),
                interval_days=0,
                lapse_increment=1,
            )
        if rating == "hard":
            return _scheduled(
                state,
                due_at=event.occurred_at + timedelta(days=1),
                interval_days=1,
            )
        if rating == "good":
            interval_days = _rating_interval(rating, state.interval_days)
            return _scheduled(
                state,
                due_at=event.occurred_at + timedelta(days=interval_days),
                interval_days=interval_days,
            )
        if rating == "easy":
            interval_days = _rating_interval(rating, state.interval_days)
            return _scheduled(
                state,
                due_at=event.occurred_at + timedelta(days=interval_days),
                interval_days=interval_days,
            )
        if (
            _wire_value(getattr(event, "event_type", None)) == "exposure"
            and state.due_at is None
        ):
            return _scheduled(
                state,
                due_at=event.occurred_at + timedelta(days=1),
                interval_days=1,
            )
        return replace(state, policy_version=self.version)
