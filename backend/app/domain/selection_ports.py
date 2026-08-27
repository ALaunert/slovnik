from __future__ import annotations

from abc import abstractmethod
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import math
from string import hexdigits
from types import MappingProxyType
from typing import Protocol, runtime_checkable
import unicodedata

from .curriculum import PrerequisiteKind
from .practice import ActivitySpec, GeneratorKind, LearningIntent
from .progress import LearnerProfile, LearnerTargetState
from .shared import TargetKind
from .target import TargetSpec


MAX_DIFFICULTY_FEATURE_BYTES = 4 * 1024


def _freeze(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _normalize_difficulty_value(value: object) -> object:
    if value is None or isinstance(value, bool) or isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("difficulty_features numbers must be finite")
        return value
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, (list, tuple)):
        return [_normalize_difficulty_value(item) for item in value]
    if isinstance(value, Mapping):
        normalized: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("difficulty_features keys must be strings")
            normalized_key = unicodedata.normalize("NFC", key)
            if normalized_key in normalized:
                raise ValueError("difficulty_features keys collide after normalization")
            normalized[normalized_key] = _normalize_difficulty_value(item)
        return {key: normalized[key] for key in sorted(normalized)}
    raise ValueError("difficulty_features must contain portable JSON values")


def freeze_difficulty_features(
    value: Mapping[str, object],
) -> Mapping[str, object]:
    normalized = _normalize_difficulty_value(value)
    assert isinstance(normalized, dict)
    payload_size = len(
        json.dumps(
            normalized,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    )
    if payload_size > MAX_DIFFICULTY_FEATURE_BYTES:
        raise ValueError("difficulty_features must not exceed 4 KiB")
    frozen = _freeze(normalized)
    assert isinstance(frozen, Mapping)
    return frozen


@dataclass(frozen=True)
class NonTargetItem:
    target_kind: TargetKind
    known: bool
    prerequisite_kind: PrerequisiteKind | None = None
    gloss: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.target_kind, TargetKind) or type(self.known) is not bool:
            raise ValueError("Non-target item has invalid fields")
        if self.prerequisite_kind is not None and not isinstance(
            self.prerequisite_kind,
            PrerequisiteKind,
        ):
            raise ValueError("Non-target prerequisite kind is invalid")
        if self.gloss is not None and (
            not isinstance(self.gloss, str) or not self.gloss.strip()
        ):
            raise ValueError("Non-target gloss must be non-empty when present")


@dataclass(frozen=True)
class CurriculumTarget:
    target_spec: TargetSpec
    priority: int
    outcome_code: str
    hard_ready: bool
    soft_ready_count: int
    content_published: bool
    stimulus_snapshot: Mapping[str, object] = field(hash=False)
    non_target_items: tuple[NonTargetItem, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.target_spec, TargetSpec):
            raise ValueError("Curriculum target requires a TargetSpec")
        if type(self.priority) is not int or not 0 <= self.priority <= 100:
            raise ValueError("Curriculum target priority must be between 0 and 100")
        if not isinstance(self.outcome_code, str) or not self.outcome_code:
            raise ValueError("Curriculum target outcome_code must be non-empty")
        if type(self.hard_ready) is not bool or type(self.content_published) is not bool:
            raise ValueError("Curriculum target readiness markers must be booleans")
        if type(self.soft_ready_count) is not int or self.soft_ready_count < 0:
            raise ValueError("Curriculum target soft_ready_count must be non-negative")
        if not isinstance(self.stimulus_snapshot, Mapping):
            raise ValueError("Curriculum target stimulus_snapshot must be an object")
        items = tuple(self.non_target_items)
        if not all(isinstance(item, NonTargetItem) for item in items):
            raise ValueError("Curriculum target non_target_items are invalid")
        object.__setattr__(self, "stimulus_snapshot", _freeze(self.stimulus_snapshot))
        object.__setattr__(self, "non_target_items", items)


@dataclass(frozen=True)
class ActivityCandidate:
    activity_spec: ActivitySpec
    curriculum_target: CurriculumTarget
    generator_kind: GeneratorKind
    generator_version: str
    scorer_version: str
    feedback_policy_version: str
    difficulty_features: Mapping[str, object] = field(default_factory=dict, hash=False)

    def __post_init__(self) -> None:
        if not isinstance(self.activity_spec, ActivitySpec):
            raise ValueError("Activity candidate requires an ActivitySpec")
        if not isinstance(self.curriculum_target, CurriculumTarget):
            raise ValueError("Activity candidate requires curriculum context")
        if not isinstance(self.generator_kind, GeneratorKind):
            raise ValueError("Activity candidate generator kind is invalid")
        versions = (
            self.generator_version,
            self.scorer_version,
            self.feedback_policy_version,
        )
        if any(not isinstance(value, str) or not value for value in versions):
            raise ValueError("Activity candidate versions must be non-empty")
        if not isinstance(self.difficulty_features, Mapping):
            raise ValueError("Activity candidate difficulty_features must be an object")
        object.__setattr__(
            self,
            "difficulty_features",
            freeze_difficulty_features(self.difficulty_features),
        )


@dataclass(frozen=True)
class CompletedActivity:
    target_key: str
    intent: LearningIntent
    activity_fingerprint: str
    completed_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.target_key, str) or not 1 <= len(self.target_key) <= 255:
            raise ValueError("Completed activity target_key is invalid")
        if not isinstance(self.intent, LearningIntent):
            raise ValueError("Completed activity intent is invalid")
        if (
            not isinstance(self.activity_fingerprint, str)
            or len(self.activity_fingerprint) != 64
            or any(
                character not in hexdigits.lower()
                for character in self.activity_fingerprint
            )
        ):
            raise ValueError("Completed activity fingerprint must be lowercase SHA-256")
        if self.completed_at.tzinfo is None or self.completed_at.utcoffset() is None:
            raise ValueError("Completed activity timestamp must be timezone-aware")
        object.__setattr__(
            self,
            "completed_at",
            self.completed_at.astimezone(timezone.utc),
        )


@runtime_checkable
class ActivityCandidateProvider(Protocol):
    @abstractmethod
    def candidates_for(
        self,
        curriculum_target: CurriculumTarget,
    ) -> Iterable[ActivityCandidate]: ...


@runtime_checkable
class AiActivityCandidateProvider(ActivityCandidateProvider, Protocol):
    """Optional AI boundary; foundation intentionally provides no adapter."""


@runtime_checkable
class LearnerProfilePort(Protocol):
    @abstractmethod
    def get_profile(self, learner_id: str) -> LearnerProfile | None: ...


@runtime_checkable
class CurriculumSelectionPort(Protocol):
    @abstractmethod
    def active_frontier(
        self,
        profile: LearnerProfile,
    ) -> Iterable[CurriculumTarget] | None: ...


@runtime_checkable
class LearnerProgressPort(Protocol):
    @abstractmethod
    def states_for_targets(
        self,
        *,
        learner_id: str,
        target_keys: Iterable[str],
    ) -> Mapping[str, LearnerTargetState]: ...


@runtime_checkable
class SelectionHistoryPort(Protocol):
    @abstractmethod
    def first_acquired_target_keys(
        self,
        *,
        learner_id: str,
        started_at: datetime,
        ended_at: datetime,
    ) -> Iterable[str]: ...

    @abstractmethod
    def completed_activities(
        self,
        *,
        learner_id: str,
        started_at: datetime,
        ended_at: datetime,
    ) -> Iterable[CompletedActivity]: ...
