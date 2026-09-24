"""Versioned read-only labels for learning observations; no projection policy changes."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class EvidenceClass(str, Enum):
    EXPOSURE = "exposure"
    FIRST_UNAIDED_CORRECT = "first_unaided_correct"
    FIRST_UNAIDED_INCORRECT = "first_unaided_incorrect"
    ASSISTED_CORRECT = "assisted_correct"
    ASSISTED_INCORRECT = "assisted_incorrect"
    RECOVERED = "recovered"
    RETRY_CORRECT = "retry_correct"
    RETRY_INCORRECT = "retry_incorrect"
    SELF_REPORT = "self_report"
    UNRESOLVED = "unresolved"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class EvidenceObservation:
    event_id: str
    target_key: str
    occurred_at: datetime
    event_type: str | None
    evaluation_source: str | None
    evaluation_outcome: str | None
    has_first_response: bool
    hints: tuple[str, ...] | None
    retry_of_activity_id: str | None
    attempt_number: int | None
    context_family_id: str | None
    content_revision_id: str | None
    activity_instance_id: str | None = None
    has_final_response: bool = False
    repair_outcome: str | None = None
    support_timing: str | None = None
    held_out: bool | None = None


def classify_observation(observation: EvidenceObservation) -> EvidenceClass:
    """Conservatively label one frozen event without deriving a mastery state."""
    if observation.event_type == "exposure":
        return EvidenceClass.EXPOSURE
    if observation.event_type != "response_evaluated" or not observation.has_first_response:
        return EvidenceClass.UNKNOWN
    if observation.evaluation_source == "self_report":
        return EvidenceClass.SELF_REPORT
    # A single verdict may describe the final response, not the first.
    if observation.has_final_response or observation.repair_outcome is not None:
        return EvidenceClass.UNKNOWN
    if observation.evaluation_source == "model_assisted" or observation.evaluation_outcome in {
        "partial", "unknown"
    }:
        return EvidenceClass.UNRESOLVED
    if (
        observation.evaluation_source != "deterministic"
        or observation.evaluation_outcome not in {"correct", "incorrect"}
        or observation.hints is None
        or observation.attempt_number is None
        or observation.attempt_number < 1
    ):
        return EvidenceClass.UNKNOWN
    correct = observation.evaluation_outcome == "correct"
    if observation.hints:
        if observation.support_timing != "before_first":
            return EvidenceClass.UNKNOWN
        return EvidenceClass.ASSISTED_CORRECT if correct else EvidenceClass.ASSISTED_INCORRECT
    if observation.attempt_number > 1:
        if not observation.retry_of_activity_id:
            return EvidenceClass.UNKNOWN
        return EvidenceClass.RETRY_CORRECT if correct else EvidenceClass.RETRY_INCORRECT
    if observation.retry_of_activity_id:
        return EvidenceClass.UNKNOWN
    return EvidenceClass.FIRST_UNAIDED_CORRECT if correct else EvidenceClass.FIRST_UNAIDED_INCORRECT
