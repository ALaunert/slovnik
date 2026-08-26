from __future__ import annotations

import json
import math
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from uuid import UUID

from .shared import Modality
from .target import TargetSpec


MAX_ACTIVITY_SPEC_BYTES = 64 * 1024
_ACTIVITY_SPEC_FIELDS = {
    "schema_version",
    "target_spec",
    "activity_kind",
    "operation",
    "input_modality",
    "output_modality",
    "cue_level",
    "scorer_kind",
    "snapshot",
}


def _normalize_json(value: object) -> object:
    if value is None or isinstance(value, bool) or isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("JSON numbers must be finite")
        return value
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, list):
        return [_normalize_json(item) for item in value]
    if isinstance(value, dict):
        normalized: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("JSON object keys must be strings")
            normalized_key = unicodedata.normalize("NFC", key)
            if normalized_key in normalized:
                raise ValueError("JSON object keys collide after NFC normalization")
            normalized[normalized_key] = _normalize_json(item)
        return normalized
    raise ValueError("Value is not portable JSON")


def _freeze_json(value: object) -> object:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze_json(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze_json(item) for item in value)
    return value


def _plain_json(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _plain_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain_json(item) for item in value]
    return value


def _canonical_json_size(payload: Mapping[str, object]) -> int:
    return len(
        json.dumps(
            payload,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    )


def _optional_enum(enum_type, value: object):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Optional enum payload must be null or a string")
    return enum_type(value)


def _is_canonical_uuid(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return str(UUID(value)) == value
    except ValueError:
        return False


def _require_canonical_uuid(value: object, field_name: str) -> None:
    if not _is_canonical_uuid(value):
        raise ValueError(f"{field_name} must be a canonical lowercase UUID string")


class PracticeRunStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"

    @property
    def is_terminal(self) -> bool:
        return self is not PracticeRunStatus.ACTIVE


class ActivityKind(str, Enum):
    EXPOSURE = "exposure"
    EXERCISE = "exercise"


class ActivityStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        return self is not ActivityStatus.PENDING


class LearningIntent(str, Enum):
    ACQUIRE = "acquire"
    REVIEW = "review"
    STRENGTHEN = "strengthen"
    ASSESS = "assess"


class ExerciseOperation(str, Enum):
    RECOGNIZE = "recognize"
    RETRIEVE = "retrieve"
    COMPLETE = "complete"
    TRANSFORM = "transform"


class CueLevel(str, Enum):
    FULL = "full"
    PARTIAL = "partial"
    MINIMAL = "minimal"
    NONE = "none"


class ScorerKind(str, Enum):
    DETERMINISTIC = "deterministic"
    SELF_REPORT = "self_report"
    MODEL_ASSISTED = "model_assisted"


class GeneratorKind(str, Enum):
    CURATED = "curated"
    MODEL_ASSISTED = "model_assisted"


class ResponseKind(str, Enum):
    TEXT = "text"
    CHOICE = "choice"
    RATING = "rating"


class SelfReportRating(str, Enum):
    AGAIN = "again"
    HARD = "hard"
    GOOD = "good"
    EASY = "easy"


class EvaluationSource(str, Enum):
    DETERMINISTIC = "deterministic"
    SELF_REPORT = "self_report"
    MODEL_ASSISTED = "model_assisted"


class EvaluationOutcome(str, Enum):
    CORRECT = "correct"
    PARTIAL = "partial"
    INCORRECT = "incorrect"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ResponseSnapshot:
    kind: ResponseKind
    value: str
    truncated: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ResponseKind) or not isinstance(self.value, str):
            raise ValueError("Response snapshot requires a registered kind and string value")
        if type(self.truncated) is not bool:
            raise ValueError("Response snapshot truncated must be a boolean")
        normalized = unicodedata.normalize("NFC", self.value)
        if self.kind is ResponseKind.TEXT and len(normalized) > 2000:
            raise ValueError("Response text must contain at most 2000 code points")
        if self.kind is ResponseKind.CHOICE and (not normalized or len(normalized) > 120):
            raise ValueError("Choice response must contain 1 to 120 code points")
        if self.kind is ResponseKind.RATING:
            try:
                SelfReportRating(normalized)
            except ValueError as exc:
                raise ValueError("Rating response must use a registered value") from exc
        object.__setattr__(self, "value", normalized)

    def to_payload(self) -> dict[str, object]:
        return {
            "kind": self.kind.value,
            "value": self.value,
            "truncated": self.truncated,
        }


@dataclass(frozen=True)
class ResponseSubmission:
    activity_instance_id: str
    response: ResponseSnapshot
    idempotency_key: str
    occurred_at: datetime

    def __post_init__(self) -> None:
        if not _is_canonical_uuid(self.activity_instance_id):
            raise ValueError("Response activity ID must be a canonical UUID string")
        if not isinstance(self.response, ResponseSnapshot):
            raise ValueError("Response submission requires a bounded response snapshot")
        if (
            not isinstance(self.idempotency_key, str)
            or not self.idempotency_key
            or len(self.idempotency_key) > 255
        ):
            raise ValueError("Idempotency key must contain at most 255 characters")
        _require_aware_timestamp(self.occurred_at, "Response occurred_at")


@dataclass(frozen=True)
class Evaluation:
    source: EvaluationSource
    outcome: EvaluationOutcome
    confidence: float | None = None
    partial_score: float | None = None
    error_tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.source, EvaluationSource) or not isinstance(
            self.outcome, EvaluationOutcome
        ):
            raise ValueError("Evaluation source and outcome must use registered wire values")
        if self.outcome is EvaluationOutcome.PARTIAL:
            if self.partial_score is None:
                raise ValueError("partial_score is required for a partial evaluation")
        elif self.partial_score is not None:
            raise ValueError("partial_score is only allowed for a partial evaluation")
        if self.partial_score is not None and not _is_unit_interval(self.partial_score):
            raise ValueError("partial_score must be finite and between 0 and 1")
        if self.source is EvaluationSource.MODEL_ASSISTED:
            if self.confidence is None or not _is_unit_interval(self.confidence):
                raise ValueError("Model-assisted evaluation requires finite confidence")
        elif self.confidence is not None:
            raise ValueError("Evaluation confidence is only allowed for model-assisted scoring")
        if self.source is EvaluationSource.SELF_REPORT:
            if self.outcome is not EvaluationOutcome.UNKNOWN:
                raise ValueError("Self-report evaluation outcome must be unknown")
        elif self.outcome is EvaluationOutcome.UNKNOWN:
            raise ValueError("Unknown outcome is reserved for self-report evaluation")
        if not isinstance(self.error_tags, tuple) or len(self.error_tags) > 32 or any(
            not isinstance(tag, str) or not tag or len(tag) > 64
            for tag in self.error_tags
        ):
            raise ValueError("Evaluation error_tags are bounded to 32 values of 64 characters")


def _is_unit_interval(value: object) -> bool:
    return (
        type(value) in (int, float)
        and math.isfinite(value)
        and 0 <= value <= 1
    )


def _require_aware_timestamp(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


class SelectionReason(str, Enum):
    DUE_REVIEW = "due_review"
    WEAK_COMPETENCE = "weak_competence"
    NEW_TARGET = "new_target"
    ASSESSMENT_GAP = "assessment_gap"
    LEGACY_NEW_WORD = "legacy_new_word"
    LEGACY_REVIEW = "legacy_review"
    LEGACY_QUIZ = "legacy_quiz"


@dataclass(frozen=True)
class SelectionMetadata:
    policy_version: str
    reasons: tuple[SelectionReason, ...]
    propensity: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.policy_version, str) or not isinstance(self.reasons, tuple):
            raise ValueError("Selection metadata has invalid value types")
        if not self.policy_version or len(self.policy_version) > 120:
            raise ValueError("Selection policy version must contain at most 120 characters")
        if len(self.reasons) > 10:
            raise ValueError("Selection metadata has at most 10 reasons")
        if any(not isinstance(reason, SelectionReason) for reason in self.reasons):
            raise ValueError("Selection reason must use a registered wire value")
        if len(set(self.reasons)) != len(self.reasons):
            raise ValueError("Selection reasons must be unique")
        if self.is_deterministic_v1 and self.propensity is not None:
            raise ValueError("deterministic-v1 selection propensity must be null")
        if self.propensity is not None and not _is_unit_interval(self.propensity):
            raise ValueError("Selection propensity must be finite and between 0 and 1")

    def to_payload(self) -> list[str]:
        return [reason.value for reason in self.reasons]

    @property
    def is_deterministic_v1(self) -> bool:
        return self.policy_version == "deterministic-v1"


@dataclass(frozen=True)
class ActivitySpec:
    target_spec: TargetSpec
    activity_kind: ActivityKind
    operation: ExerciseOperation | None
    cue_level: CueLevel
    output_modality: Modality | None
    scorer_kind: ScorerKind | None
    snapshot: Mapping[str, object] = field(hash=False)
    input_modality: Modality = Modality.WRITTEN

    def __post_init__(self) -> None:
        if not isinstance(self.target_spec, TargetSpec):
            raise ValueError("ActivitySpec requires one canonical primary target")
        enum_values = (
            (self.activity_kind, ActivityKind),
            (self.cue_level, CueLevel),
            (self.input_modality, Modality),
        )
        if any(not isinstance(value, enum_type) for value, enum_type in enum_values):
            raise ValueError("ActivitySpec enum fields must use registered wire values")
        if self.operation is not None and not isinstance(
            self.operation, ExerciseOperation
        ):
            raise ValueError("ActivitySpec operation must use a registered wire value")
        if self.output_modality is not None and not isinstance(
            self.output_modality, Modality
        ):
            raise ValueError("ActivitySpec output modality must use a registered wire value")
        if self.scorer_kind is not None and not isinstance(self.scorer_kind, ScorerKind):
            raise ValueError("ActivitySpec scorer must use a registered wire value")
        self._validate_shape()
        if not isinstance(self.snapshot, dict):
            raise ValueError("ActivitySpec snapshot must be an object")
        if "target_spec" in self.snapshot:
            raise ValueError("ActivitySpec snapshot cannot contain another primary target")
        normalized = _normalize_json(self.snapshot)
        assert isinstance(normalized, dict)
        object.__setattr__(self, "snapshot", _freeze_json(normalized))
        if _canonical_json_size(self.to_payload()) > MAX_ACTIVITY_SPEC_BYTES:
            raise ValueError("ActivitySpec canonical payload must not exceed 64 KiB")

    def _validate_shape(self) -> None:
        exposure_values = (self.operation, self.scorer_kind, self.output_modality)
        if self.activity_kind is ActivityKind.EXPOSURE and any(
            value is not None for value in exposure_values
        ):
            raise ValueError("Exposure must not define operation, scorer, or output modality")
        if self.activity_kind is ActivityKind.EXERCISE and any(
            value is None for value in exposure_values
        ):
            raise ValueError("Exercise requires operation, scorer, and output modality")

    @property
    def target_key(self) -> str:
        return self.target_spec.target_key

    def to_payload(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "target_spec": self.target_spec.to_payload(),
            "activity_kind": self.activity_kind.value,
            "operation": self.operation.value if self.operation else None,
            "input_modality": self.input_modality.value,
            "output_modality": (
                self.output_modality.value if self.output_modality else None
            ),
            "cue_level": self.cue_level.value,
            "scorer_kind": self.scorer_kind.value if self.scorer_kind else None,
            "snapshot": _plain_json(self.snapshot),
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "ActivitySpec":
        try:
            schema_version = payload["schema_version"]
            if (
                set(payload) != _ACTIVITY_SPEC_FIELDS
                or type(schema_version) is not int
                or schema_version != 1
            ):
                raise ValueError("ActivitySpec payload fields or version are invalid")
            target_payload = payload["target_spec"]
            snapshot = payload["snapshot"]
            if not isinstance(target_payload, Mapping) or not isinstance(snapshot, dict):
                raise ValueError("ActivitySpec payload has invalid objects")
            operation_value = payload["operation"]
            output_modality_value = payload["output_modality"]
            scorer_kind_value = payload["scorer_kind"]
            return cls(
                target_spec=TargetSpec.from_payload(target_payload),
                activity_kind=ActivityKind(payload["activity_kind"]),
                operation=_optional_enum(ExerciseOperation, operation_value),
                input_modality=Modality(payload["input_modality"]),
                output_modality=_optional_enum(Modality, output_modality_value),
                cue_level=CueLevel(payload["cue_level"]),
                scorer_kind=_optional_enum(ScorerKind, scorer_kind_value),
                snapshot=snapshot,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Invalid ActivitySpec payload") from exc


@dataclass(frozen=True)
class PracticeRun:
    id: str
    learner_id: str
    curriculum_version_id: str | None
    legacy_quiz_attempt_id: int | None
    status: PracticeRunStatus
    selection_policy_version: str
    started_at: datetime
    ended_at: datetime | None

    def __post_init__(self) -> None:
        _require_canonical_uuid(self.id, "PracticeRun id")
        if self.curriculum_version_id is not None:
            _require_canonical_uuid(
                self.curriculum_version_id,
                "PracticeRun curriculum_version_id",
            )
        if not isinstance(self.status, PracticeRunStatus):
            raise ValueError("PracticeRun status must use a registered wire value")
        _require_aware_timestamp(self.started_at, "PracticeRun started_at")
        if self.ended_at is not None:
            _require_aware_timestamp(self.ended_at, "PracticeRun ended_at")
            if self.ended_at < self.started_at:
                raise ValueError("PracticeRun ended_at cannot be before started_at")
        if self.status.is_terminal != (self.ended_at is not None):
            raise ValueError("PracticeRun ended_at must match status")

    def validate_activity(self, activity: ActivityInstance) -> None:
        if activity.practice_run_id != self.id:
            raise ValueError("Activity must belong to its PracticeRun")
        if activity.selection.policy_version != self.selection_policy_version:
            raise ValueError("Activity must inherit the run selection policy version")


@dataclass(frozen=True)
class ActivityInstance:
    id: str
    practice_run_id: str
    spec: ActivitySpec
    learning_intent: LearningIntent
    sequence_number: int
    retry_of_activity_instance_id: str | None
    attempt_number: int
    selection: SelectionMetadata
    generator_kind: GeneratorKind
    generator_version: str
    scorer_version: str | None
    status: ActivityStatus
    selected_at: datetime
    terminal_at: datetime | None

    def __post_init__(self) -> None:
        _require_canonical_uuid(self.id, "Activity id")
        _require_canonical_uuid(self.practice_run_id, "Activity practice_run_id")
        if self.retry_of_activity_instance_id is not None:
            _require_canonical_uuid(
                self.retry_of_activity_instance_id,
                "Activity retry_of_activity_instance_id",
            )
        if not isinstance(self.status, ActivityStatus):
            raise ValueError("Activity status must use a registered wire value")
        if not isinstance(self.spec, ActivitySpec):
            raise ValueError("Activity requires a bounded ActivitySpec")
        if not isinstance(self.learning_intent, LearningIntent):
            raise ValueError("Activity intent must use a registered wire value")
        if not isinstance(self.selection, SelectionMetadata):
            raise ValueError("Activity requires bounded selection metadata")
        if not isinstance(self.generator_kind, GeneratorKind):
            raise ValueError("Activity generator must use a registered wire value")
        if type(self.sequence_number) is not int or self.sequence_number < 1:
            raise ValueError("Activity sequence_number must be at least 1")
        if type(self.attempt_number) is not int or self.attempt_number < 1:
            raise ValueError("Activity attempt_number must be at least 1")
        _require_aware_timestamp(self.selected_at, "Activity selected_at")
        if self.terminal_at is not None:
            _require_aware_timestamp(self.terminal_at, "Activity terminal_at")
            if self.terminal_at < self.selected_at:
                raise ValueError("Activity terminal_at cannot be before selected_at")
        if self.retry_of_activity_instance_id is None and self.attempt_number != 1:
            raise ValueError("An activity without a retry parent must be attempt 1")
        if self.retry_of_activity_instance_id is not None and (
            self.retry_of_activity_instance_id == self.id or self.attempt_number < 2
        ):
            raise ValueError("A retry must reference another activity and be attempt 2 or later")
        if self.status.is_terminal != (self.terminal_at is not None):
            raise ValueError("Activity terminal_at must match status")
        if self.spec.activity_kind is ActivityKind.EXPOSURE:
            if self.scorer_version is not None:
                raise ValueError("Exposure must not define scorer version")
        elif not self.scorer_version:
            raise ValueError("Exercise requires scorer version")

    @property
    def target_spec(self) -> TargetSpec:
        return self.spec.target_spec

    @property
    def target_key(self) -> str:
        return self.spec.target_key

    @property
    def activity_kind(self) -> ActivityKind:
        return self.spec.activity_kind

    @property
    def operation(self) -> ExerciseOperation | None:
        return self.spec.operation

    @property
    def scorer_kind(self) -> ScorerKind | None:
        return self.spec.scorer_kind

    def validate_retry_of(self, parent: ActivityInstance) -> None:
        if self.retry_of_activity_instance_id != parent.id:
            raise ValueError("Retry must reference its parent activity")
        if self.practice_run_id != parent.practice_run_id:
            raise ValueError("Retry must belong to the same run as its parent")
        if self.target_key != parent.target_key:
            raise ValueError("Retry must have the same target as its parent")
        if self.attempt_number != parent.attempt_number + 1:
            raise ValueError("Retry must use the next attempt number")
        if self.sequence_number <= parent.sequence_number:
            raise ValueError("Retry must follow its parent in run sequence")

    def complete(self, terminal_at: datetime) -> ActivityInstance:
        return self._terminalize(ActivityStatus.COMPLETED, terminal_at)

    def cancel(self, terminal_at: datetime) -> ActivityInstance:
        return self._terminalize(ActivityStatus.CANCELLED, terminal_at)

    def _terminalize(
        self, status: ActivityStatus, terminal_at: datetime
    ) -> ActivityInstance:
        if self.status.is_terminal:
            raise ValueError("Activity is already terminal")
        return replace(self, status=status, terminal_at=terminal_at)
