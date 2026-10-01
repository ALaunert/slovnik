"""Versioned read-only evidence interpretation; projector v1 does not use this."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


Category = Literal[
    "exposure", "independent_first", "unassisted_first_context_unknown",
    "repeated_context", "assisted", "supported_timing_unknown", "repair", "retry",
    "self_report", "unknown",
]


@dataclass(frozen=True)
class EvidenceFact:
    event_id: str
    occurred_at: datetime
    event_type: str
    evaluation_source: str | None
    evaluation_outcome: str | None
    response_present: bool
    retry_of: str | None = None
    support: str | None = None
    support_capture_complete: bool = False
    support_timing_known: bool = True
    context_family: str | None = None
    context_history_complete: bool = False
    rating: str | None = None
    lineage_key: str | None = None


@dataclass(frozen=True)
class EvidenceClassification:
    version: Literal[1]
    event_id: str
    category: Category
    outcome: str | None
    context_status: Literal["new", "repeated", "unknown"]
    rating: str | None


def classify_history(facts: list[EvidenceFact]) -> tuple[EvidenceClassification, ...]:
    """Sort, deduplicate and classify only what the recorded facts establish."""
    seen_ids: set[str] = set()
    seen_contexts: set[tuple[str | None, str]] = set()
    outcomes: dict[str, str | None] = {}
    results: list[EvidenceClassification] = []
    for fact in sorted(facts, key=lambda item: (item.occurred_at, item.event_id)):
        if fact.event_id in seen_ids:
            continue
        seen_ids.add(fact.event_id)
        context_status: Literal["new", "repeated", "unknown"] = "unknown"
        if fact.context_history_complete and fact.context_family:
            context_status = "repeated" if (
                fact.lineage_key, fact.context_family
            ) in seen_contexts else "new"
        category: Category = "unknown"
        if fact.event_type == "exposure":
            category = "exposure"
        elif fact.event_type == "response_evaluated" and fact.response_present:
            if fact.evaluation_source == "self_report":
                category = "self_report"
            elif fact.evaluation_source != "deterministic" or fact.evaluation_outcome not in {"correct", "incorrect"}:
                category = "unknown"
            elif fact.retry_of is not None:
                category = (
                    "repair" if fact.evaluation_outcome == "correct"
                    and outcomes.get(fact.retry_of) == "incorrect" else "retry"
                )
            else:
                if fact.support in {"hint", "reveal", "correction"}:
                    category = "assisted" if fact.support_timing_known else "supported_timing_unknown"
                elif fact.support == "none" and fact.support_capture_complete:
                    category = (
                        "independent_first" if context_status == "new"
                        else "repeated_context" if context_status == "repeated"
                        else "unassisted_first_context_unknown"
                    )
        results.append(EvidenceClassification(
            version=1, event_id=fact.event_id, category=category,
            outcome=fact.evaluation_outcome, context_status=context_status,
            rating=fact.rating,
        ))
        outcomes[fact.event_id] = fact.evaluation_outcome
        if fact.context_family:
            seen_contexts.add((fact.lineage_key, fact.context_family))
    return tuple(results)
