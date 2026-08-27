from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
import unicodedata
from uuid import UUID

from app.domain.practice import (
    LearningIntent,
    LegacySourceRef,
    SelfReportRating,
)


MAX_REFERENCE_LENGTH = 255
MAX_POLICY_VERSION_LENGTH = 120
MAX_TARGET_KEY_LENGTH = 255
MAX_RESULT_ITEMS = 100


class ShadowLegacySourceKind(str, Enum):
    NEW_WORD = "new_word"
    REVIEW = "review"
    QUIZ_ANSWER = "quiz_answer"


class ShadowPolicyVersion(str, Enum):
    LEGACY_NEW_WORD_V1 = "legacy-new-word-v1"
    LEGACY_REVIEW_V1 = "legacy-review-v1"
    LEGACY_QUIZ_V1 = "legacy-quiz-v1"


class ShadowReasonCode(str, Enum):
    LEGACY_NEW_WORD = "legacy_new_word"
    LEGACY_REVIEW = "legacy_review"
    LEGACY_QUIZ = "legacy_quiz"


class ShadowAdapterStatus(str, Enum):
    RECORDED = "recorded"
    DUPLICATE = "duplicate"


class ShadowComparisonCategory(str, Enum):
    AGREEMENT = "agreement"
    INTENT_DIFFERENCE = "intent_difference"
    TARGET_DIFFERENCE = "target_difference"
    SHADOW_NO_ACTIVITY = "shadow_no_activity"
    LEGACY_NO_ACTIVITY = "legacy_no_activity"


class ShadowComparisonReasonCode(str, Enum):
    LEGACY_NEW_WORD = "legacy_new_word"
    LEGACY_REVIEW = "legacy_review"
    LEGACY_QUIZ = "legacy_quiz"
    DUE_REVIEW = "due_review"
    WEAK_COMPETENCE = "weak_competence"
    NEW_TARGET = "new_target"
    ASSESSMENT_GAP = "assessment_gap"
    NO_ACTIVE_CURRICULUM = "no_active_curriculum"
    EMPTY_FRONTIER = "empty_frontier"
    DAILY_ACQUIRE_BUDGET_REACHED = "daily_acquire_budget_reached"
    NO_VALID_CANDIDATE = "no_valid_candidate"


def _bounded_text(label: str, value: object, maximum: int) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise ValueError(f"{label} must contain 1 to {maximum} characters")
    return value


def _positive_int(label: str, value: object) -> int:
    if type(value) is not int or value < 1:
        raise ValueError(f"{label} must be a positive integer")
    return value


def _utc_wire(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Shadow idempotency timestamp must be timezone-aware")
    normalized = value.astimezone(timezone.utc).isoformat()
    return normalized.removesuffix("+00:00") + "Z"


def _hashed_key(prefix: str, payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return f"legacy:{prefix}:{sha256(encoded).hexdigest()}"


def _canonical_uuid(label: str, value: object) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a canonical UUID")
    try:
        if str(UUID(value)) != value:
            raise ValueError
    except ValueError as exc:
        raise ValueError(f"{label} must be a canonical UUID") from exc
    return value


@dataclass(frozen=True)
class ShadowLegacySourceRef:
    kind: ShadowLegacySourceKind
    reference: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ShadowLegacySourceKind):
            raise ValueError("Shadow legacy source kind is invalid")
        reference = unicodedata.normalize(
            "NFC",
            _bounded_text(
                "Shadow legacy source reference",
                self.reference,
                MAX_REFERENCE_LENGTH,
            ),
        )
        object.__setattr__(self, "reference", reference)

    def to_payload(self) -> dict[str, str]:
        return {"kind": self.kind.value, "reference": self.reference}

    def to_domain(self) -> LegacySourceRef:
        return LegacySourceRef(kind=self.kind.value, reference=self.reference)


@dataclass(frozen=True)
class NewWordIdempotencyInput:
    learner_ref: str
    progress_id: int
    first_seen_at: datetime

    def __post_init__(self) -> None:
        _bounded_text("Shadow learner reference", self.learner_ref, 80)
        _positive_int("Shadow progress ID", self.progress_id)
        _utc_wire(self.first_seen_at)

    @property
    def key(self) -> str:
        return _hashed_key(
            "new-word",
            {
                "first_seen_at": _utc_wire(self.first_seen_at),
                "learner_ref": self.learner_ref,
                "progress_id": self.progress_id,
            },
        )


@dataclass(frozen=True)
class ReviewIdempotencyInput:
    progress_id: int
    locked_due_at: datetime | None
    rating: SelfReportRating

    def __post_init__(self) -> None:
        _positive_int("Shadow progress ID", self.progress_id)
        _utc_wire(self.locked_due_at)
        if not isinstance(self.rating, SelfReportRating):
            raise ValueError("Shadow review rating is invalid")

    @property
    def key(self) -> str:
        return _hashed_key(
            "review",
            {
                "locked_due_at": _utc_wire(self.locked_due_at),
                "progress_id": self.progress_id,
                "rating": self.rating.value,
            },
        )


@dataclass(frozen=True)
class QuizAnswerIdempotencyInput:
    answer_id: int

    def __post_init__(self) -> None:
        _positive_int("Shadow quiz answer ID", self.answer_id)

    @property
    def key(self) -> str:
        return f"legacy:quiz-answer:{self.answer_id}"


@dataclass(frozen=True)
class ShadowAdapterResult:
    status: ShadowAdapterStatus
    practice_run_id: str
    activity_instance_ids: tuple[str, ...]
    event_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.status, ShadowAdapterStatus):
            raise ValueError("Shadow adapter status is invalid")
        _canonical_uuid("Shadow practice run ID", self.practice_run_id)
        activity_ids = tuple(self.activity_instance_ids)
        event_ids = tuple(self.event_ids)
        if len(activity_ids) > MAX_RESULT_ITEMS or len(event_ids) > MAX_RESULT_ITEMS:
            raise ValueError("Shadow adapter result has too many items")
        for value in activity_ids:
            _canonical_uuid("Shadow activity ID", value)
        for value in event_ids:
            _canonical_uuid("Shadow event ID", value)
        object.__setattr__(self, "activity_instance_ids", activity_ids)
        object.__setattr__(self, "event_ids", event_ids)

    def to_payload(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "practice_run_id": self.practice_run_id,
            "activity_instance_ids": list(self.activity_instance_ids),
            "event_ids": list(self.event_ids),
        }


@dataclass(frozen=True)
class ShadowComparison:
    policy_version: str
    legacy_intent: LearningIntent | None
    shadow_intent: LearningIntent | None
    selected_target_key: str | None
    reason_codes: tuple[ShadowComparisonReasonCode | ShadowReasonCode, ...]
    category: ShadowComparisonCategory

    def __post_init__(self) -> None:
        _bounded_text(
            "Shadow comparison policy version",
            self.policy_version,
            MAX_POLICY_VERSION_LENGTH,
        )
        for intent in (self.legacy_intent, self.shadow_intent):
            if intent is not None and not isinstance(intent, LearningIntent):
                raise ValueError("Shadow comparison intent is invalid")
        if self.selected_target_key is not None:
            _bounded_text(
                "Shadow comparison target key",
                self.selected_target_key,
                MAX_TARGET_KEY_LENGTH,
            )
        if not isinstance(self.reason_codes, tuple):
            raise ValueError("Shadow comparison reason codes must be a tuple")
        reason_codes: list[ShadowComparisonReasonCode] = []
        for code in self.reason_codes:
            if isinstance(code, ShadowComparisonReasonCode):
                reason_codes.append(code)
            elif isinstance(code, ShadowReasonCode):
                reason_codes.append(ShadowComparisonReasonCode(code.value))
            else:
                raise ValueError("Shadow comparison reason code is invalid")
        if not reason_codes or len(reason_codes) > 10:
            raise ValueError("Shadow comparison reason codes are bounded")
        if not isinstance(self.category, ShadowComparisonCategory):
            raise ValueError("Shadow comparison category is invalid")
        object.__setattr__(self, "reason_codes", tuple(reason_codes))

    def to_payload(self) -> dict[str, object]:
        return {
            "policy_version": self.policy_version,
            "legacy_intent": (
                self.legacy_intent.value if self.legacy_intent else None
            ),
            "shadow_intent": (
                self.shadow_intent.value if self.shadow_intent else None
            ),
            "selected_target_key": self.selected_target_key,
            "reason_codes": [code.value for code in self.reason_codes],
            "category": self.category.value,
        }
