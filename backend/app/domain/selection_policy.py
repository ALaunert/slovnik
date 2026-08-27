from __future__ import annotations

import json
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
from types import MappingProxyType

from .curriculum import PrerequisiteKind
from .practice import (
    ActivityKind,
    ActivitySpec,
    CueLevel,
    ExerciseOperation,
    GeneratorKind,
    LearningIntent,
    ScorerKind,
    SelectionReason,
)
from .selection_ports import (
    ActivityCandidate,
    CurriculumTarget,
    freeze_difficulty_features,
)
from .shared import Capability, Modality, TargetKind


CURATED_GENERATOR_VERSION = "curated-v1"
DETERMINISTIC_SCORER_VERSION = "deterministic-v1"
FEEDBACK_POLICY_VERSION = "feedback-v1"
SELECTION_POLICY_VERSION = "selector-v1"
MAX_RECOGNITION_CUE_CODEPOINTS = 2000
MAX_CHOICE_OPTION_CODEPOINTS = 120
_ALLOWED_OPERATIONS = {
    (TargetKind.SENSE, Capability.RECOGNIZE_MEANING): frozenset(
        {ExerciseOperation.RECOGNIZE}
    ),
    (TargetKind.SENSE, Capability.RETRIEVE_FORM): frozenset(
        {ExerciseOperation.RETRIEVE}
    ),
    (TargetKind.CONSTRUCTION, Capability.APPLY_CONSTRUCTION): frozenset(
        {ExerciseOperation.COMPLETE, ExerciseOperation.TRANSFORM}
    ),
}


class DecisionCode(str, Enum):
    DAILY_ACQUIRE_BUDGET_REACHED = "daily_acquire_budget_reached"
    NO_ACTIVE_CURRICULUM = "no_active_curriculum"
    EMPTY_FRONTIER = "empty_frontier"
    NO_VALID_CANDIDATE = "no_valid_candidate"


def _rank_payload(
    *,
    target_key: str,
    activity_fingerprint_value: str,
) -> dict[str, object]:
    return {
        "target_key": target_key,
        "activity_fingerprint": activity_fingerprint_value,
    }


@dataclass(frozen=True)
class ReviewRankComponents:
    memory_due_at: datetime
    priority: int
    repetition_count_7d: int
    target_key: str
    activity_fingerprint: str

    def to_payload(self) -> dict[str, object]:
        return {
            "memory_due_at": self.memory_due_at.astimezone(timezone.utc).isoformat(),
            "priority": self.priority,
            "repetition_count_7d": self.repetition_count_7d,
            **_rank_payload(
                target_key=self.target_key,
                activity_fingerprint_value=self.activity_fingerprint,
            ),
        }


@dataclass(frozen=True)
class StrengthenRankComponents:
    weakness_gap: float
    priority: int
    repetition_count_7d: int
    target_key: str
    activity_fingerprint: str

    def to_payload(self) -> dict[str, object]:
        return {
            "weakness_gap": self.weakness_gap,
            "priority": self.priority,
            "repetition_count_7d": self.repetition_count_7d,
            **_rank_payload(
                target_key=self.target_key,
                activity_fingerprint_value=self.activity_fingerprint,
            ),
        }


@dataclass(frozen=True)
class AcquireRankComponents:
    priority: int
    soft_ready_count: int
    repetition_count_7d: int
    target_key: str
    activity_fingerprint: str

    def to_payload(self) -> dict[str, object]:
        return {
            "priority": self.priority,
            "soft_ready_count": self.soft_ready_count,
            "repetition_count_7d": self.repetition_count_7d,
            **_rank_payload(
                target_key=self.target_key,
                activity_fingerprint_value=self.activity_fingerprint,
            ),
        }


@dataclass(frozen=True)
class AssessRankComponents:
    uncertainty: float
    last_evidence_at: datetime | None
    priority: int
    target_key: str
    activity_fingerprint: str

    def to_payload(self) -> dict[str, object]:
        return {
            "uncertainty": self.uncertainty,
            "last_evidence_at": (
                None
                if self.last_evidence_at is None
                else self.last_evidence_at.astimezone(timezone.utc).isoformat()
            ),
            "priority": self.priority,
            **_rank_payload(
                target_key=self.target_key,
                activity_fingerprint_value=self.activity_fingerprint,
            ),
        }


RankComponents = (
    ReviewRankComponents
    | StrengthenRankComponents
    | AcquireRankComponents
    | AssessRankComponents
)


@dataclass(frozen=True)
class NextActivityDecision:
    activity_spec: ActivitySpec | None
    intent: LearningIntent | None
    target_key: str | None
    reason_codes: tuple[SelectionReason, ...]
    decision_code: DecisionCode | None
    policy_version: str = SELECTION_POLICY_VERSION
    rank_components: RankComponents | None = None
    activity_fingerprint: str | None = None
    reason_metadata: Mapping[str, object] = field(default_factory=dict, hash=False)

    def __post_init__(self) -> None:
        has_activity = self.activity_spec is not None
        if has_activity != (self.intent is not None):
            raise ValueError("Selection intent must match activity presence")
        if has_activity != (self.target_key is not None):
            raise ValueError("Selection target must match activity presence")
        if has_activity == (self.decision_code is not None):
            raise ValueError("Selection decision must have activity or no-activity code")
        if has_activity and self.activity_spec.target_key != self.target_key:
            raise ValueError("Selection target must match activity target")
        if has_activity != (self.rank_components is not None):
            raise ValueError("Selection rank components must match activity presence")
        if has_activity != (self.activity_fingerprint is not None):
            raise ValueError("Selection fingerprint must match activity presence")
        if self.policy_version != SELECTION_POLICY_VERSION:
            raise ValueError("Selection decision policy version must be selector-v1")
        if not isinstance(self.reason_metadata, Mapping):
            raise ValueError("Selection reason_metadata must be an object")
        if has_activity:
            if set(self.reason_metadata) != {"difficulty_features"}:
                raise ValueError(
                    "Activity reason_metadata requires difficulty_features"
                )
            difficulty_features = self.reason_metadata["difficulty_features"]
            if not isinstance(difficulty_features, Mapping):
                raise ValueError("difficulty_features must be an object")
            frozen_metadata = MappingProxyType(
                {
                    "difficulty_features": freeze_difficulty_features(
                        difficulty_features
                    )
                }
            )
        else:
            if self.reason_metadata:
                raise ValueError("No-activity reason_metadata must be empty")
            frozen_metadata = MappingProxyType({})
        object.__setattr__(self, "reason_metadata", frozen_metadata)

    def to_payload(self) -> dict[str, object]:
        return {
            "policy_version": self.policy_version,
            "activity_spec": (
                None if self.activity_spec is None else self.activity_spec.to_payload()
            ),
            "intent": None if self.intent is None else self.intent.value,
            "target_key": self.target_key,
            "reason_codes": [reason.value for reason in self.reason_codes],
            "decision_code": (
                None if self.decision_code is None else self.decision_code.value
            ),
            "rank_components": (
                None
                if self.rank_components is None
                else self.rank_components.to_payload()
            ),
            "activity_fingerprint": self.activity_fingerprint,
            "reason_metadata": _plain(self.reason_metadata),
        }

    @classmethod
    def no_activity(cls, decision_code: DecisionCode) -> NextActivityDecision:
        return cls(
            activity_spec=None,
            intent=None,
            target_key=None,
            reason_codes=(),
            decision_code=decision_code,
        )


def _plain(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value


def _canonicalize(value: object) -> object:
    if value is None or isinstance(value, bool) or isinstance(value, int):
        return value
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, (list, tuple)):
        return [_canonicalize(item) for item in value]
    if isinstance(value, Mapping):
        normalized: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("Activity fingerprint keys must be strings")
            normalized_key = unicodedata.normalize("NFC", key)
            if normalized_key in normalized:
                raise ValueError("Activity fingerprint keys collide after NFC normalization")
            normalized[normalized_key] = _canonicalize(item)
        return normalized
    raise ValueError("Activity fingerprint contains a non-canonical JSON value")


def activity_fingerprint(candidate: ActivityCandidate) -> str:
    spec = candidate.activity_spec
    payload = {
        "schema_version": 1,
        "target_key": spec.target_key,
        "activity_kind": spec.activity_kind.value,
        "operation": None if spec.operation is None else spec.operation.value,
        "input_modality": spec.input_modality.value,
        "output_modality": (
            None if spec.output_modality is None else spec.output_modality.value
        ),
        "cue_policy": spec.cue_level.value,
        "stimulus_snapshot": spec.to_payload()["snapshot"],
        "feedback_policy_version": candidate.feedback_policy_version,
        "generator_kind": candidate.generator_kind.value,
        "generator_version": candidate.generator_version,
        "scorer_kind": (
            None if spec.scorer_kind is None else spec.scorer_kind.value
        ),
        "scorer_version": candidate.scorer_version,
    }
    canonical_payload = _canonicalize(payload)
    serialized = json.dumps(
        canonical_payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )
    return sha256(serialized.encode("utf-8")).hexdigest()


def _operation_shapes(
    curriculum_target: CurriculumTarget,
) -> tuple[tuple[ExerciseOperation, CueLevel, dict[str, object]], ...]:
    target = curriculum_target.target_spec
    if (
        target.target_kind is TargetKind.SENSE
        and target.capability is Capability.RECOGNIZE_MEANING
    ):
        return (
            (
                ExerciseOperation.RECOGNIZE,
                CueLevel.FULL,
                {"kind": "choice", "max_options": 4},
            ),
        )
    if (
        target.target_kind is TargetKind.SENSE
        and target.capability is Capability.RETRIEVE_FORM
    ):
        return (
            (
                ExerciseOperation.RETRIEVE,
                CueLevel.FULL,
                {"kind": "text", "max_codepoints": 2000},
            ),
        )
    if (
        target.target_kind is TargetKind.CONSTRUCTION
        and target.capability is Capability.APPLY_CONSTRUCTION
    ):
        response = {"kind": "text", "max_codepoints": 2000}
        return (
            (ExerciseOperation.COMPLETE, CueLevel.PARTIAL, response),
            (ExerciseOperation.TRANSFORM, CueLevel.FULL, response),
        )
    return ()


def _valid_operation(candidate: ActivityCandidate) -> bool:
    spec = candidate.activity_spec
    target = candidate.curriculum_target.target_spec
    expected_operations = _ALLOWED_OPERATIONS.get(
        (target.target_kind, target.capability),
        frozenset(),
    )
    return spec.operation in expected_operations


def _valid_response_contract(candidate: ActivityCandidate) -> bool:
    response = candidate.activity_spec.snapshot.get("response_contract")
    if not isinstance(response, Mapping):
        return False
    operation = candidate.activity_spec.operation
    if operation is ExerciseOperation.RECOGNIZE:
        max_options = response.get("max_options")
        return (
            response.get("kind") == "choice"
            and type(max_options) is int
            and 2 <= max_options <= 8
        )
    max_codepoints = response.get("max_codepoints")
    return (
        response.get("kind") == "text"
        and type(max_codepoints) is int
        and 1 <= max_codepoints <= 2000
    )


def _valid_recognition_stimulus(candidate: ActivityCandidate) -> bool:
    spec = candidate.activity_spec
    if spec.operation is not ExerciseOperation.RECOGNIZE:
        return True
    snapshot = spec.snapshot
    response = snapshot.get("response_contract")
    options = snapshot.get("options")
    expected = snapshot.get("expected")
    if not isinstance(response, Mapping) or not isinstance(options, (list, tuple)):
        return False
    max_options = response.get("max_options")
    if type(max_options) is not int or not 2 <= len(options) <= max_options:
        return False
    cue = snapshot.get("cue")
    if (
        not isinstance(cue, str)
        or not cue.strip()
        or len(cue) > MAX_RECOGNITION_CUE_CODEPOINTS
    ):
        return False
    if (
        not isinstance(expected, str)
        or not expected.strip()
        or len(expected) > MAX_CHOICE_OPTION_CODEPOINTS
    ):
        return False
    if not all(
        isinstance(option, str)
        and bool(option.strip())
        and len(option) <= MAX_CHOICE_OPTION_CODEPOINTS
        for option in options
    ):
        return False
    if len(set(options)) != len(options):
        return False
    return expected in options


def _valid_non_target_burden(candidate: ActivityCandidate) -> bool:
    target = candidate.curriculum_target
    unknown_items = tuple(
        item for item in target.non_target_items if not item.known
    )
    if target.target_spec.target_kind is not TargetKind.CONSTRUCTION:
        return not unknown_items
    if len(unknown_items) > 1:
        return False
    return all(
        item.target_kind in (TargetKind.SENSE, TargetKind.FORM)
        and item.prerequisite_kind is PrerequisiteKind.SOFT
        and item.gloss is not None
        for item in unknown_items
    )


def _has_fingerprint_compatible_snapshot(candidate: ActivityCandidate) -> bool:
    try:
        _canonicalize(candidate.activity_spec.snapshot)
    except ValueError:
        return False
    return True


class ActivityValidityPolicy:
    def is_valid(self, candidate: ActivityCandidate) -> bool:
        spec = candidate.activity_spec
        target = candidate.curriculum_target
        return (
            target.content_published
            and target.hard_ready
            and spec.target_key == target.target_spec.target_key
            and spec.activity_kind is ActivityKind.EXERCISE
            and spec.scorer_kind is ScorerKind.DETERMINISTIC
            and spec.input_modality is Modality.WRITTEN
            and spec.output_modality is Modality.WRITTEN
            and _valid_operation(candidate)
            and _valid_response_contract(candidate)
            and _valid_recognition_stimulus(candidate)
            and _valid_non_target_burden(candidate)
            and _has_fingerprint_compatible_snapshot(candidate)
        )


class CuratedActivityCandidateProvider:
    @staticmethod
    def _candidate(
        curriculum_target: CurriculumTarget,
        operation: ExerciseOperation,
        cue_level: CueLevel,
        response_contract: dict[str, object],
    ) -> ActivityCandidate:
        snapshot = _plain(curriculum_target.stimulus_snapshot)
        assert isinstance(snapshot, dict)
        snapshot["response_contract"] = response_contract
        activity_spec = ActivitySpec(
            target_spec=curriculum_target.target_spec,
            activity_kind=ActivityKind.EXERCISE,
            operation=operation,
            input_modality=Modality.WRITTEN,
            output_modality=Modality.WRITTEN,
            cue_level=cue_level,
            scorer_kind=ScorerKind.DETERMINISTIC,
            snapshot=snapshot,
        )
        return ActivityCandidate(
            activity_spec=activity_spec,
            curriculum_target=curriculum_target,
            generator_kind=GeneratorKind.CURATED,
            generator_version=CURATED_GENERATOR_VERSION,
            scorer_version=DETERMINISTIC_SCORER_VERSION,
            feedback_policy_version=FEEDBACK_POLICY_VERSION,
            difficulty_features={
                "non_target_item_count": len(curriculum_target.non_target_items),
            },
        )

    def candidates_for(
        self,
        curriculum_target: CurriculumTarget,
    ) -> tuple[ActivityCandidate, ...]:
        return tuple(
            self._candidate(
                curriculum_target,
                operation,
                cue_level,
                response_contract,
            )
            for operation, cue_level, response_contract in _operation_shapes(
                curriculum_target
            )
        )
