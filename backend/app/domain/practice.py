from __future__ import annotations

import hashlib
import json
import math
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
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


class LearningEventType(str, Enum):
    EXPOSURE = "exposure"
    RESPONSE_EVALUATED = "response_evaluated"


class HintKind(str, Enum):
    CUE = "cue"
    REVEAL = "reveal"
    CORRECTION = "correction"


class RepairOutcome(str, Enum):
    REPAIRED = "repaired"
    NOT_REPAIRED = "not_repaired"
    NOT_ATTEMPTED = "not_attempted"


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

    @classmethod
    def from_input(cls, *, kind: ResponseKind, value: str) -> ResponseSnapshot:
        if kind is ResponseKind.TEXT and isinstance(value, str):
            normalized = unicodedata.normalize("NFC", value)
            return cls(
                kind=kind,
                value=normalized[:2000],
                truncated=len(normalized) > 2000,
            )
        return cls(kind=kind, value=value)


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
        if activity.selected_at < self.started_at:
            raise ValueError("Activity cannot be selected before its run started")

    def validate_new_activity(self, activity: ActivityInstance) -> None:
        self.validate_activity(activity)
        if activity.status is not ActivityStatus.PENDING:
            raise ValueError("New practice activity must be pending")
        if activity.retry_of_activity_instance_id is not None:
            raise ValueError("Retries must use create_retry")

    def _validate_activities(self, activities: tuple[ActivityInstance, ...]) -> None:
        for activity in activities:
            self.validate_activity(activity)

    def _validate_end_time(
        self,
        activities: tuple[ActivityInstance, ...],
        ended_at: datetime,
    ) -> None:
        _require_aware_timestamp(ended_at, "PracticeRun ended_at")
        if any(
            ended_at < (activity.terminal_at or activity.selected_at)
            for activity in activities
        ):
            raise ValueError("Practice run end cannot precede its activities")

    def complete(
        self,
        activities: tuple[ActivityInstance, ...],
        ended_at: datetime,
    ) -> PracticeRun:
        if self.status.is_terminal:
            raise ValueError("Practice run is already terminal")
        if not activities:
            raise ValueError("Practice run requires at least one activity")
        self._validate_activities(activities)
        if any(activity.status is not ActivityStatus.COMPLETED for activity in activities):
            raise ValueError("Practice run can complete only when all activities are completed")
        self._validate_end_time(activities, ended_at)
        return replace(self, status=PracticeRunStatus.COMPLETED, ended_at=ended_at)

    def abandon(
        self,
        activities: tuple[ActivityInstance, ...],
        ended_at: datetime,
    ) -> tuple[PracticeRun, tuple[ActivityInstance, ...]]:
        if self.status.is_terminal:
            raise ValueError("Practice run is already terminal")
        self._validate_activities(activities)
        self._validate_end_time(activities, ended_at)
        cancelled = tuple(
            activity.cancel(ended_at)
            for activity in activities
            if activity.status is ActivityStatus.PENDING
        )
        abandoned = replace(
            self,
            status=PracticeRunStatus.ABANDONED,
            ended_at=ended_at,
        )
        return abandoned, cancelled


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
    feedback_policy_version: str
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
        if (
            not isinstance(self.feedback_policy_version, str)
            or not 1 <= len(self.feedback_policy_version) <= 120
        ):
            raise ValueError(
                "Activity feedback_policy_version must contain 1 to 120 characters"
            )
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

    def retry(
        self,
        *,
        retry_id: str,
        sequence_number: int,
        selected_at: datetime,
    ) -> ActivityInstance:
        if self.status is not ActivityStatus.COMPLETED:
            raise ValueError("Retry parent must be completed")
        parent_terminal_at = self.terminal_at
        if parent_terminal_at is None:
            raise ValueError("Completed retry parent requires terminal_at")
        _require_aware_timestamp(selected_at, "Retry selected_at")
        if selected_at < parent_terminal_at:
            raise ValueError("Retry cannot be selected before its parent completed")
        retry = replace(
            self,
            id=retry_id,
            sequence_number=sequence_number,
            retry_of_activity_instance_id=self.id,
            attempt_number=self.attempt_number + 1,
            status=ActivityStatus.PENDING,
            selected_at=selected_at,
            terminal_at=None,
        )
        retry.validate_retry_of(self)
        return retry

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


@dataclass(frozen=True)
class HintSnapshot:
    kind: HintKind
    sequence_number: int

    def __post_init__(self) -> None:
        if not isinstance(self.kind, HintKind):
            raise ValueError("Hint kind must use a registered wire value")
        if type(self.sequence_number) is not int or self.sequence_number < 1:
            raise ValueError("Hint sequence_number must be at least 1")

    def to_payload(self) -> dict[str, object]:
        return {"kind": self.kind.value, "sequence_number": self.sequence_number}


@dataclass(frozen=True)
class FeedbackSnapshot:
    code: str
    delivered_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.code, str) or not self.code or len(self.code) > 64:
            raise ValueError("Feedback code must contain at most 64 characters")
        _require_aware_timestamp(self.delivered_at, "Feedback delivered_at")
        object.__setattr__(self, "code", unicodedata.normalize("NFC", self.code))

    def to_payload(self) -> dict[str, object]:
        return {
            "code": self.code,
            "delivered_at": _utc_text(self.delivered_at),
        }


@dataclass(frozen=True)
class LegacySourceRef:
    kind: str
    reference: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.kind, str)
            or not self.kind
            or len(self.kind) > 64
            or not isinstance(self.reference, str)
            or not self.reference
            or len(self.reference) > 255
        ):
            raise ValueError("Legacy source requires bounded kind and stable reference")
        object.__setattr__(self, "kind", unicodedata.normalize("NFC", self.kind))
        object.__setattr__(
            self,
            "reference",
            unicodedata.normalize("NFC", self.reference),
        )

    def to_payload(self) -> dict[str, object]:
        return {"kind": self.kind, "reference": self.reference}


@dataclass(frozen=True)
class LearningEventRequest:
    event_id: str
    learner_id: str
    activity_instance_id: str
    idempotency_key: str
    occurred_at: datetime
    first_response: ResponseSnapshot | None = None
    final_response: ResponseSnapshot | None = None
    evaluation: Evaluation | None = None
    latency_ms: int | None = None
    hints: tuple[HintSnapshot, ...] = ()
    learner_confidence: float | None = None
    feedback: FeedbackSnapshot | None = None
    repair_outcome: RepairOutcome | None = None
    legacy_source: LegacySourceRef | None = None

    def __post_init__(self) -> None:
        _require_canonical_uuid(self.event_id, "LearningEvent event_id")
        _require_canonical_uuid(
            self.activity_instance_id,
            "LearningEvent activity_instance_id",
        )
        if not isinstance(self.learner_id, str) or not self.learner_id:
            raise ValueError("LearningEvent learner_id is required")
        if (
            not isinstance(self.idempotency_key, str)
            or not self.idempotency_key
            or len(self.idempotency_key) > 255
        ):
            raise ValueError("LearningEvent idempotency key must contain at most 255 characters")
        _require_aware_timestamp(self.occurred_at, "LearningEvent occurred_at")
        for response in (self.first_response, self.final_response):
            if response is not None and not isinstance(response, ResponseSnapshot):
                raise ValueError("LearningEvent responses must be bounded snapshots")
        if self.evaluation is not None and not isinstance(self.evaluation, Evaluation):
            raise ValueError("LearningEvent evaluation must be bounded")
        if self.latency_ms is not None and (
            type(self.latency_ms) is not int or self.latency_ms < 0
        ):
            raise ValueError("LearningEvent latency_ms must be a nonnegative integer")
        if (
            not isinstance(self.hints, tuple)
            or len(self.hints) > 10
            or any(not isinstance(hint, HintSnapshot) for hint in self.hints)
        ):
            raise ValueError("LearningEvent hints are bounded to 10 immutable objects")
        if self.learner_confidence is not None and not _is_unit_interval(
            self.learner_confidence
        ):
            raise ValueError("Learner confidence must be finite and between 0 and 1")
        if self.feedback is not None and not isinstance(self.feedback, FeedbackSnapshot):
            raise ValueError("LearningEvent feedback must be bounded metadata")
        if self.repair_outcome is not None and not isinstance(
            self.repair_outcome, RepairOutcome
        ):
            raise ValueError("LearningEvent repair outcome must use a registered value")
        if self.legacy_source is not None and not isinstance(
            self.legacy_source, LegacySourceRef
        ):
            raise ValueError("LearningEvent legacy source must be a stable reference")

    def semantic_payload(self) -> dict[str, object]:
        return {
            "activity_instance_id": self.activity_instance_id,
            "first_response": _response_payload(self.first_response),
            "final_response": _response_payload(self.final_response),
            "legacy_source": (
                self.legacy_source.to_payload() if self.legacy_source else None
            ),
        }

    @property
    def semantic_fingerprint(self) -> str:
        encoded = json.dumps(
            self.semantic_payload(),
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class LearningEvent:
    event_id: str
    schema_version: int
    learner_id: str
    practice_run_id: str
    activity_instance_id: str
    target_spec: TargetSpec
    event_type: LearningEventType
    learning_intent: LearningIntent
    activity_kind: ActivityKind
    operation: ExerciseOperation | None
    input_modality: Modality
    output_modality: Modality | None
    cue_level: CueLevel
    first_response: ResponseSnapshot | None
    final_response: ResponseSnapshot | None
    evaluation: Evaluation | None
    latency_ms: int | None
    hints: tuple[HintSnapshot, ...]
    learner_confidence: float | None
    feedback: FeedbackSnapshot | None
    repair_outcome: RepairOutcome | None
    legacy_source: LegacySourceRef | None
    generator_kind: GeneratorKind
    generator_version: str
    scorer_version: str | None
    selection: SelectionMetadata
    idempotency_key: str
    occurred_at: datetime
    created_at: datetime

    def __post_init__(self) -> None:
        if self.schema_version != 1 or type(self.schema_version) is not int:
            raise ValueError("LearningEvent schema_version must be 1")
        _require_canonical_uuid(self.event_id, "LearningEvent event_id")
        _require_canonical_uuid(self.practice_run_id, "LearningEvent practice_run_id")
        _require_canonical_uuid(
            self.activity_instance_id,
            "LearningEvent activity_instance_id",
        )
        _require_aware_timestamp(self.occurred_at, "LearningEvent occurred_at")
        _require_aware_timestamp(self.created_at, "LearningEvent created_at")
        if not isinstance(self.target_spec, TargetSpec):
            raise ValueError("LearningEvent requires a canonical target snapshot")
        event_enums = (
            (self.event_type, LearningEventType),
            (self.learning_intent, LearningIntent),
            (self.activity_kind, ActivityKind),
            (self.input_modality, Modality),
            (self.cue_level, CueLevel),
            (self.generator_kind, GeneratorKind),
        )
        if any(not isinstance(value, enum_type) for value, enum_type in event_enums):
            raise ValueError("LearningEvent enum fields must use registered wire values")
        if self.operation is not None and not isinstance(
            self.operation, ExerciseOperation
        ):
            raise ValueError("LearningEvent operation must use a registered wire value")
        if self.output_modality is not None and not isinstance(
            self.output_modality, Modality
        ):
            raise ValueError("LearningEvent output modality must use a registered value")
        if not isinstance(self.selection, SelectionMetadata):
            raise ValueError("LearningEvent requires bounded selection metadata")
        invalid_scorer_version = self.scorer_version is not None and (
            not isinstance(self.scorer_version, str)
            or not self.scorer_version
            or len(self.scorer_version) > 120
        )
        if (
            not isinstance(self.generator_version, str)
            or not self.generator_version
            or len(self.generator_version) > 120
            or invalid_scorer_version
        ):
            raise ValueError("LearningEvent generator/scorer versions are bounded")
        request = self.as_request()
        if self.activity_kind is ActivityKind.EXPOSURE:
            if (
                self.event_type is not LearningEventType.EXPOSURE
                or self.operation is not None
                or self.output_modality is not None
                or self.scorer_version is not None
                or request.first_response is not None
                or request.final_response is not None
                or request.evaluation is not None
            ):
                raise ValueError("Exposure event has an incompatible shape")
        elif (
            self.event_type is not LearningEventType.RESPONSE_EVALUATED
            or self.operation is None
            or self.output_modality is None
            or self.scorer_version is None
            or request.first_response is None
            or request.evaluation is None
        ):
            raise ValueError("Exercise event has an incompatible shape")
        if request.evaluation is not None:
            responses = tuple(
                response
                for response in (request.first_response, request.final_response)
                if response is not None
            )
            if request.evaluation.source is EvaluationSource.SELF_REPORT:
                if any(response.kind is not ResponseKind.RATING for response in responses):
                    raise ValueError("Self-report requires rating response snapshots")
            elif any(response.kind is ResponseKind.RATING for response in responses):
                raise ValueError("Rating responses are reserved for self-report")
        if _canonical_json_size(self.to_observation_payload()) > 16 * 1024:
            raise ValueError("LearningEvent observation payload must not exceed 16 KiB")

    @property
    def target_key(self) -> str:
        return self.target_spec.target_key

    @property
    def evaluation_source(self) -> EvaluationSource | None:
        return self.evaluation.source if self.evaluation else None

    @property
    def evaluation_outcome(self) -> EvaluationOutcome | None:
        return self.evaluation.outcome if self.evaluation else None

    @property
    def evaluation_confidence(self) -> float | None:
        return self.evaluation.confidence if self.evaluation else None

    @property
    def partial_score(self) -> float | None:
        return self.evaluation.partial_score if self.evaluation else None

    @property
    def error_tags(self) -> tuple[str, ...]:
        return self.evaluation.error_tags if self.evaluation else ()

    @property
    def selection_policy_version(self) -> str:
        return self.selection.policy_version

    @property
    def selection_reasons(self) -> tuple[SelectionReason, ...]:
        return self.selection.reasons

    @property
    def selection_propensity(self) -> float | None:
        return self.selection.propensity

    @property
    def semantic_fingerprint(self) -> str:
        return self.as_request().semantic_fingerprint

    def as_request(self) -> LearningEventRequest:
        return LearningEventRequest(
            event_id=self.event_id,
            learner_id=self.learner_id,
            activity_instance_id=self.activity_instance_id,
            idempotency_key=self.idempotency_key,
            occurred_at=self.occurred_at,
            first_response=self.first_response,
            final_response=self.final_response,
            evaluation=self.evaluation,
            latency_ms=self.latency_ms,
            hints=self.hints,
            learner_confidence=self.learner_confidence,
            feedback=self.feedback,
            repair_outcome=self.repair_outcome,
            legacy_source=self.legacy_source,
        )

    def to_observation_payload(self) -> dict[str, object]:
        evaluation = self.evaluation
        return {
            "target_spec": self.target_spec.to_payload(),
            "learning_intent": self.learning_intent.value,
            "operation": self.operation.value if self.operation else None,
            "input_modality": self.input_modality.value,
            "output_modality": (
                self.output_modality.value if self.output_modality else None
            ),
            "cue_level": self.cue_level.value,
            "first_response": _response_payload(self.first_response),
            "final_response": _response_payload(self.final_response),
            "evaluation_source": evaluation.source.value if evaluation else None,
            "evaluation_outcome": evaluation.outcome.value if evaluation else None,
            "evaluation_confidence": evaluation.confidence if evaluation else None,
            "partial_score": evaluation.partial_score if evaluation else None,
            "error_tags": list(evaluation.error_tags) if evaluation else [],
            "latency_ms": self.latency_ms,
            "hints": [hint.to_payload() for hint in self.hints],
            "learner_confidence": self.learner_confidence,
            "feedback": self.feedback.to_payload() if self.feedback else None,
            "repair_outcome": (
                self.repair_outcome.value if self.repair_outcome else None
            ),
            "legacy_source": (
                self.legacy_source.to_payload() if self.legacy_source else None
            ),
            "generator_kind": self.generator_kind.value,
            "generator_version": self.generator_version,
            "scorer_version": self.scorer_version,
            "selection_policy_version": self.selection.policy_version,
            "selection_reasons": self.selection.to_payload(),
            "selection_propensity": self.selection.propensity,
        }


def build_learning_event(
    activity: ActivityInstance,
    request: LearningEventRequest,
    *,
    created_at: datetime,
    received_at: datetime,
) -> LearningEvent:
    if activity.id != request.activity_instance_id:
        raise ValueError("LearningEvent request must reference its stored activity")
    _require_aware_timestamp(received_at, "LearningEvent received_at")
    if request.occurred_at < activity.selected_at:
        raise ValueError("LearningEvent cannot occur before activity selection")
    if request.occurred_at > received_at + timedelta(minutes=5):
        raise ValueError("LearningEvent cannot occur more than five minutes in the future")
    if activity.activity_kind is ActivityKind.EXPOSURE:
        if any(
            value is not None
            for value in (
                request.first_response,
                request.final_response,
                request.evaluation,
            )
        ):
            raise ValueError("Exposure cannot contain response or evaluation")
        event_type = LearningEventType.EXPOSURE
    else:
        evaluation = request.evaluation
        if request.first_response is None or evaluation is None:
            raise ValueError("Exercise requires response and evaluation")
        if activity.scorer_kind is None or evaluation.source.value != activity.scorer_kind.value:
            raise ValueError("Evaluation source must match stored activity scorer")
        if activity.scorer_kind is ScorerKind.SELF_REPORT:
            if request.first_response.kind is not ResponseKind.RATING:
                raise ValueError("Self-report requires a rating response")
        elif request.first_response.kind is ResponseKind.RATING:
            raise ValueError("Rating responses are reserved for self-report")
        event_type = LearningEventType.RESPONSE_EVALUATED
    return LearningEvent(
        event_id=request.event_id,
        schema_version=1,
        learner_id=request.learner_id,
        practice_run_id=activity.practice_run_id,
        activity_instance_id=activity.id,
        target_spec=activity.target_spec,
        event_type=event_type,
        learning_intent=activity.learning_intent,
        activity_kind=activity.activity_kind,
        operation=activity.operation,
        input_modality=activity.spec.input_modality,
        output_modality=activity.spec.output_modality,
        cue_level=activity.spec.cue_level,
        first_response=request.first_response,
        final_response=request.final_response,
        evaluation=request.evaluation,
        latency_ms=request.latency_ms,
        hints=request.hints,
        learner_confidence=request.learner_confidence,
        feedback=request.feedback,
        repair_outcome=request.repair_outcome,
        legacy_source=request.legacy_source,
        generator_kind=activity.generator_kind,
        generator_version=activity.generator_version,
        scorer_version=activity.scorer_version,
        selection=activity.selection,
        idempotency_key=request.idempotency_key,
        occurred_at=request.occurred_at,
        created_at=created_at,
    )


def _response_payload(response: ResponseSnapshot | None) -> dict[str, object] | None:
    return response.to_payload() if response else None


def _utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
