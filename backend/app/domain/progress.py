import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
from math import isfinite
from string import hexdigits
from types import MappingProxyType
from typing import Protocol, runtime_checkable
from uuid import UUID

from .shared import Capability, Modality, TargetKind


LEGACY_L1 = "ru"
MEMORY_POLICY_VERSION = "memory-v1"
PROJECTION_POLICY_VERSION = "projection-v1"
LEGACY_BOOTSTRAP_POLICY_VERSION = "legacy-bootstrap-v1"
CEFR_LEVELS = frozenset({"A1", "A2", "B1", "B2", "C1", "C2"})
ALLOWED_TARGET_CAPABILITIES = frozenset(
    {
        (TargetKind.SENSE, Capability.RECOGNIZE_MEANING),
        (TargetKind.SENSE, Capability.RETRIEVE_FORM),
        (TargetKind.CONSTRUCTION, Capability.APPLY_CONSTRUCTION),
        (TargetKind.FORM, Capability.RETRIEVE_FORM),
    }
)
EMPTY_CONDITION_HASH = sha256(b"{}").hexdigest()
NEUTRAL_BASELINE_FIELDS = frozenset({"schema_version"})
LEGACY_BASELINE_FIELDS = frozenset(
    {"schema_version", "source_ref", "source_fingerprint"}
)


def _require_nonnegative_int(field_name: str, value: object) -> None:
    if type(value) is not int or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")


def _is_finite_number(value: object) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and isfinite(value)
    )


def _require_nonnegative_number(field_name: str, value: object) -> None:
    if not _is_finite_number(value) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative finite number")


def _require_unit_interval(field_name: str, value: object) -> None:
    if not _is_finite_number(value) or not 0 <= value <= 1:
        raise ValueError(f"{field_name} must be between zero and one")


def _require_policy_version(field_name: str, value: object) -> None:
    if not isinstance(value, str) or not 1 <= len(value) <= 120:
        raise ValueError(f"{field_name} must contain 1 to 120 characters")


def _freeze_json(value: object) -> object:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError("Projection baseline payload must contain finite JSON values")
        return value
    if isinstance(value, Mapping):
        frozen: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("Projection baseline JSON object keys must be strings")
            frozen[key] = _freeze_json(item)
        return MappingProxyType(frozen)
    if isinstance(value, list):
        return tuple(_freeze_json(item) for item in value)
    raise ValueError("Projection baseline payload contains a non-JSON value")


def _plain_json(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _plain_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain_json(item) for item in value]
    return value


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _utc_optional(value: datetime | None) -> datetime | None:
    return None if value is None else _utc(value)


def _require_canonical_uuid(field_name: str, value: object) -> None:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a canonical lowercase UUID")
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a canonical lowercase UUID") from exc
    if str(parsed) != value:
        raise ValueError(f"{field_name} must be a canonical lowercase UUID")


def _validate_baseline_shape(
    *,
    kind: "BaselineKind",
    memory_due_at: datetime | None,
    memory_interval_days: int,
    payload: Mapping[str, object],
) -> None:
    schema_version = payload.get("schema_version")
    if type(schema_version) is not int or schema_version != 1:
        raise ValueError("Projection baseline schema_version must be 1")
    fields = frozenset(payload)
    if kind is BaselineKind.NEUTRAL:
        if (
            fields != NEUTRAL_BASELINE_FIELDS
            or memory_due_at is not None
            or memory_interval_days != 0
        ):
            raise ValueError("Neutral baseline must have a null, zero schedule")
        return
    if fields != LEGACY_BASELINE_FIELDS:
        raise ValueError("Legacy baseline must contain source_ref and source_fingerprint")
    source_ref = payload["source_ref"]
    fingerprint = payload["source_fingerprint"]
    valid_source_ref = (
        isinstance(source_ref, str) and 0 < len(source_ref) <= 255
    ) or (isinstance(source_ref, Mapping) and bool(source_ref))
    if not valid_source_ref:
        raise ValueError("Legacy baseline source_ref must be a stable JSON reference")
    if (
        not isinstance(fingerprint, str)
        or len(fingerprint) != 64
        or any(character not in hexdigits.lower() for character in fingerprint)
    ):
        raise ValueError("Legacy baseline source_fingerprint must be lowercase SHA-256")


def _validate_target_key(target_key: object) -> None:
    if not isinstance(target_key, str) or len(target_key) > 255:
        raise ValueError("LearnerTargetState target_key must be canonical")
    parts = target_key.split(":")
    if len(parts) != 6 or parts[0] != "v1":
        raise ValueError("LearnerTargetState target_key must be canonical")
    _, target_kind, target_id, capability, modality, condition_hash = parts
    try:
        parsed_target_id = UUID(target_id)
        parsed_target_kind = TargetKind(target_kind)
        parsed_capability = Capability(capability)
        Modality(modality)
    except ValueError as exc:
        raise ValueError("LearnerTargetState target_key must be canonical") from exc
    is_lower_hex = len(condition_hash) == 64 and all(
        character in hexdigits.lower() for character in condition_hash
    )
    if str(parsed_target_id) != target_id or not is_lower_hex:
        raise ValueError("LearnerTargetState target_key must be canonical")
    if (parsed_target_kind, parsed_capability) not in ALLOWED_TARGET_CAPABILITIES:
        raise ValueError("LearnerTargetState target_key must be canonical")
    if (
        parsed_target_kind is TargetKind.FORM
        and condition_hash == EMPTY_CONDITION_HASH
    ):
        raise ValueError("LearnerTargetState target_key must be canonical")


class LegacyUserProfile(Protocol):
    user_id: str
    preferred_level: str
    daily_new_word_count: int


class LearningEventView(Protocol):
    event_id: str
    learner_id: str
    occurred_at: datetime


@runtime_checkable
class LearningEventSource(Protocol):
    def events_for_target(
        self,
        *,
        learner_id: str,
        target_key: str,
    ) -> Iterable[LearningEventView]: ...


@dataclass(frozen=True)
class LearnerProfile:
    learner_id: str
    l1: str
    requested_level: str
    daily_budget: int

    def __post_init__(self) -> None:
        if (
            not isinstance(self.learner_id, str)
            or not 1 <= len(self.learner_id) <= 80
        ):
            raise ValueError("LearnerProfile learner_id must contain 1 to 80 characters")
        if self.l1 != LEGACY_L1:
            raise ValueError("LearnerProfile l1 must be ru for the MVP")
        if self.requested_level not in CEFR_LEVELS:
            raise ValueError("LearnerProfile requested_level must be a CEFR level")
        if type(self.daily_budget) is not int or not 1 <= self.daily_budget <= 50:
            raise ValueError("LearnerProfile daily_budget must be between 1 and 50")

    @classmethod
    def from_legacy(cls, profile: LegacyUserProfile) -> "LearnerProfile":
        return cls(
            learner_id=profile.user_id,
            l1=LEGACY_L1,
            requested_level=profile.preferred_level,
            daily_budget=profile.daily_new_word_count,
        )


class BaselineKind(str, Enum):
    NEUTRAL = "neutral"
    LEGACY_BOOTSTRAP = "legacy_bootstrap"


@dataclass(frozen=True)
class ProjectionBaseline:
    kind: BaselineKind
    memory_due_at: datetime | None
    memory_interval_days: int
    payload: Mapping[str, object]

    def __post_init__(self) -> None:
        if not isinstance(self.kind, BaselineKind):
            raise ValueError("Baseline kind must be a BaselineKind")
        _require_nonnegative_int(
            "Baseline memory_interval_days", self.memory_interval_days
        )
        if not isinstance(self.payload, Mapping):
            raise ValueError("Projection baseline payload must be an object")
        frozen_payload = _freeze_json(self.payload)
        assert isinstance(frozen_payload, Mapping)
        serialized_payload = json.dumps(
            _plain_json(frozen_payload),
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        )
        if len(serialized_payload.encode("utf-8")) > 4096:
            raise ValueError("Projection baseline payload must not exceed 4 KiB")
        _validate_baseline_shape(
            kind=self.kind,
            memory_due_at=self.memory_due_at,
            memory_interval_days=self.memory_interval_days,
            payload=frozen_payload,
        )
        object.__setattr__(
            self, "memory_due_at", _utc_optional(self.memory_due_at)
        )
        object.__setattr__(self, "payload", frozen_payload)

    @classmethod
    def neutral(cls) -> "ProjectionBaseline":
        return cls(
            kind=BaselineKind.NEUTRAL,
            memory_due_at=None,
            memory_interval_days=0,
            payload={"schema_version": 1},
        )

    @classmethod
    def legacy(
        cls,
        *,
        memory_due_at: datetime | None,
        memory_interval_days: int,
        source_ref: object,
        source_fingerprint: str,
    ) -> "ProjectionBaseline":
        return cls(
            kind=BaselineKind.LEGACY_BOOTSTRAP,
            memory_due_at=memory_due_at,
            memory_interval_days=memory_interval_days,
            payload={
                "schema_version": 1,
                "source_ref": source_ref,
                "source_fingerprint": source_fingerprint,
            },
        )


@dataclass(frozen=True)
class CompetenceEstimate:
    success_weight: float
    failure_weight: float
    peak: float
    uncertainty: float

    def __post_init__(self) -> None:
        _require_nonnegative_number("Competence success_weight", self.success_weight)
        _require_nonnegative_number("Competence failure_weight", self.failure_weight)
        _require_unit_interval("Competence peak", self.peak)
        _require_unit_interval("Competence uncertainty", self.uncertainty)

    @classmethod
    def neutral(cls) -> "CompetenceEstimate":
        return cls(success_weight=0, failure_weight=0, peak=0, uncertainty=1)


@dataclass(frozen=True)
class EvidenceSummary:
    count: int
    last_evidence_at: datetime | None = None
    last_event_id: str | None = None

    def __post_init__(self) -> None:
        _require_nonnegative_int("Evidence count", self.count)
        has_timestamp = self.last_evidence_at is not None
        has_event_id = self.last_event_id is not None
        if has_timestamp != has_event_id or (self.count > 0) != has_timestamp:
            raise ValueError("Evidence cursor must be null exactly when count is zero")
        if self.last_event_id is not None:
            _require_canonical_uuid(
                "EvidenceSummary last_event_id", self.last_event_id
            )
        object.__setattr__(
            self, "last_evidence_at", _utc_optional(self.last_evidence_at)
        )

    @classmethod
    def empty(cls) -> "EvidenceSummary":
        return cls(count=0)


@dataclass(frozen=True)
class MemoryState:
    due_at: datetime | None
    interval_days: int
    lapses: int
    policy_version: str

    def __post_init__(self) -> None:
        _require_nonnegative_int("Memory interval_days", self.interval_days)
        _require_nonnegative_int("Memory lapses", self.lapses)
        _require_policy_version("Memory policy_version", self.policy_version)
        object.__setattr__(self, "due_at", _utc_optional(self.due_at))


@dataclass(frozen=True)
class LearnerTargetState:
    state_id: str
    learner_id: str
    target_key: str
    baseline: ProjectionBaseline
    competence: CompetenceEstimate
    evidence: EvidenceSummary
    memory: MemoryState
    projection_policy_version: str
    updated_at: datetime

    def __post_init__(self) -> None:
        _require_canonical_uuid("LearnerTargetState state_id", self.state_id)
        if not isinstance(self.learner_id, str) or not 1 <= len(self.learner_id) <= 80:
            raise ValueError(
                "LearnerTargetState learner_id must contain 1 to 80 characters"
            )
        _validate_target_key(self.target_key)
        total_weight = (
            self.competence.success_weight + self.competence.failure_weight
        )
        if total_weight > self.evidence.count:
            raise ValueError("Competence weights must not exceed evidence count")
        _require_policy_version(
            "LearnerTargetState projection_policy_version",
            self.projection_policy_version,
        )
        if self.evidence.count == 0:
            if self.baseline.kind is BaselineKind.NEUTRAL:
                expected_memory_policy = MEMORY_POLICY_VERSION
                expected_projection_policy = PROJECTION_POLICY_VERSION
            else:
                expected_memory_policy = LEGACY_BOOTSTRAP_POLICY_VERSION
                expected_projection_policy = LEGACY_BOOTSTRAP_POLICY_VERSION
            if (
                self.competence != CompetenceEstimate.neutral()
                or self.memory.due_at != self.baseline.memory_due_at
                or self.memory.interval_days != self.baseline.memory_interval_days
                or self.memory.lapses != 0
                or self.memory.policy_version != expected_memory_policy
                or self.projection_policy_version
                != expected_projection_policy
            ):
                raise ValueError(
                    "Zero-evidence state must exactly match its baseline kind"
                )
        object.__setattr__(self, "updated_at", _utc(self.updated_at))

    @classmethod
    def neutral(
        cls,
        *,
        state_id: str,
        learner_id: str,
        target_key: str,
        updated_at: datetime,
    ) -> "LearnerTargetState":
        return cls(
            state_id=state_id,
            learner_id=learner_id,
            target_key=target_key,
            baseline=ProjectionBaseline.neutral(),
            competence=CompetenceEstimate.neutral(),
            evidence=EvidenceSummary.empty(),
            memory=MemoryState(
                due_at=None,
                interval_days=0,
                lapses=0,
                policy_version=MEMORY_POLICY_VERSION,
            ),
            projection_policy_version=PROJECTION_POLICY_VERSION,
            updated_at=updated_at,
        )

    @classmethod
    def legacy_bootstrap(
        cls,
        *,
        state_id: str,
        learner_id: str,
        target_key: str,
        baseline: ProjectionBaseline,
        updated_at: datetime,
    ) -> "LearnerTargetState":
        if baseline.kind is not BaselineKind.LEGACY_BOOTSTRAP:
            raise ValueError("Legacy state requires a legacy_bootstrap baseline")
        return cls(
            state_id=state_id,
            learner_id=learner_id,
            target_key=target_key,
            baseline=baseline,
            competence=CompetenceEstimate.neutral(),
            evidence=EvidenceSummary.empty(),
            memory=MemoryState(
                due_at=baseline.memory_due_at,
                interval_days=baseline.memory_interval_days,
                lapses=0,
                policy_version=LEGACY_BOOTSTRAP_POLICY_VERSION,
            ),
            projection_policy_version=LEGACY_BOOTSTRAP_POLICY_VERSION,
            updated_at=updated_at,
        )
