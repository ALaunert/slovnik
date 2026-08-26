from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from .curriculum import (
    CurriculumNode,
    CurriculumStatus,
    CurriculumVersion,
    PrerequisiteKind,
)


FRONTIER_POLICY_VERSION = "frontier-v1"
CEFR_ORDER = ("A1", "A2", "B1", "B2", "C1", "C2")


class FrontierAvailability(str, Enum):
    AVAILABLE = "available"
    NOT_YET_READY = "not_yet_ready"


class FrontierReason(str, Enum):
    READY = "ready"
    ABOVE_CEFR_ENVELOPE = "above_cefr_envelope"
    HARD_PREREQUISITE_MISSING_STATE = "hard_prerequisite_missing_state"
    HARD_PREREQUISITE_NO_NATIVE_EVIDENCE = (
        "hard_prerequisite_no_native_evidence"
    )
    HARD_PREREQUISITE_NO_DETERMINISTIC_SUCCESS = (
        "hard_prerequisite_no_deterministic_success"
    )
    HARD_PREREQUISITE_BELOW_PEAK = "hard_prerequisite_below_peak"


@dataclass(frozen=True)
class FrontierDecision:
    node: CurriculumNode
    availability: FrontierAvailability
    reason_codes: tuple[FrontierReason, ...]
    soft_ready_count: int
    policy_version: str = FRONTIER_POLICY_VERSION


class _EvidenceView(Protocol):
    count: int


class _CompetenceView(Protocol):
    success_weight: float
    peak: float


class TargetStateView(Protocol):
    evidence: _EvidenceView
    competence: _CompetenceView


def _unready_reason(state: TargetStateView | None) -> FrontierReason | None:
    if state is None:
        return FrontierReason.HARD_PREREQUISITE_MISSING_STATE
    if state.evidence.count == 0:
        return FrontierReason.HARD_PREREQUISITE_NO_NATIVE_EVIDENCE
    if state.competence.success_weight < 1:
        return FrontierReason.HARD_PREREQUISITE_NO_DETERMINISTIC_SUCCESS
    if state.competence.peak < 0.6:
        return FrontierReason.HARD_PREREQUISITE_BELOW_PEAK
    return None


def _incoming_prerequisites(
    curriculum: CurriculumVersion,
    kind: PrerequisiteKind,
) -> dict[str, list[str]]:
    incoming = {node.id: [] for node in curriculum.nodes}
    for edge in curriculum.prerequisites:
        if edge.kind is kind:
            incoming[edge.dependent_node_id].append(edge.prerequisite_node_id)
    return incoming


class CurriculumFrontierPolicy:
    def evaluate(
        self,
        curriculum: CurriculumVersion,
        *,
        states_by_target_key: Mapping[str, TargetStateView],
        requested_level: str,
    ) -> tuple[FrontierDecision, ...]:
        if curriculum.status is not CurriculumStatus.ACTIVE:
            raise ValueError("frontier requires an active curriculum")
        if requested_level not in CEFR_ORDER:
            raise ValueError("requested_level must be a CEFR level")
        requested_level_index = CEFR_ORDER.index(requested_level)
        nodes_by_id = {node.id: node for node in curriculum.nodes}
        hard_edges_by_dependent = _incoming_prerequisites(
            curriculum, PrerequisiteKind.HARD
        )
        soft_edges_by_dependent = _incoming_prerequisites(
            curriculum, PrerequisiteKind.SOFT
        )

        def decision(node: CurriculumNode) -> FrontierDecision:
            if CEFR_ORDER.index(node.outcome_code[:2]) > requested_level_index:
                return FrontierDecision(
                    node=node,
                    availability=FrontierAvailability.NOT_YET_READY,
                    reason_codes=(FrontierReason.ABOVE_CEFR_ENVELOPE,),
                    soft_ready_count=0,
                )
            reasons = tuple(
                reason
                for prerequisite_id in hard_edges_by_dependent[node.id]
                if (
                    reason := _unready_reason(
                        states_by_target_key.get(
                            nodes_by_id[prerequisite_id].target.target_key
                        )
                    )
                )
                is not None
            )
            soft_ready_count = sum(
                _unready_reason(
                    states_by_target_key.get(
                        nodes_by_id[prerequisite_id].target.target_key
                    )
                )
                is None
                for prerequisite_id in soft_edges_by_dependent[node.id]
            )
            if reasons:
                return FrontierDecision(
                    node=node,
                    availability=FrontierAvailability.NOT_YET_READY,
                    reason_codes=tuple(dict.fromkeys(reasons)),
                    soft_ready_count=soft_ready_count,
                )
            return FrontierDecision(
                node=node,
                availability=FrontierAvailability.AVAILABLE,
                reason_codes=(FrontierReason.READY,),
                soft_ready_count=soft_ready_count,
            )

        return tuple(
            decision(node) for node in curriculum.nodes
        )
