from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from math import isfinite
from types import MappingProxyType
from typing import Any, Mapping
from uuid import UUID


class EntryKind(str, Enum):
    WORD = "word"
    MWE = "mwe"


class ContentStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    RETIRED = "retired"


class RetirementPolicyDecision(str, Enum):
    ALLOWED = "allowed"
    ACTIVE_REFERENCE = "active_reference"


class FormKind(str, Enum):
    CITATION = "citation"
    INFLECTED = "inflected"
    FIXED = "fixed"


class Script(str, Enum):
    CYRILLIC = "cyrillic"
    LATIN = "latin"


class _FrozenSequence(tuple):
    def __eq__(self, other: object) -> bool:
        if isinstance(other, (list, tuple)):
            return tuple.__eq__(self, tuple(other))
        return False

    __hash__ = tuple.__hash__


def _canonical_id(value: str, field_name: str = "id") -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a UUID string")
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"{field_name} must be a UUID string") from exc
    if str(parsed) != value:
        raise ValueError(f"{field_name} must be a canonical lowercase UUID")
    return value


def _revision(value: int) -> int:
    if type(value) is not int or value < 1:
        raise ValueError("revision must be an integer greater than or equal to 1")
    return value


def _status(value: ContentStatus) -> None:
    if not isinstance(value, ContentStatus):
        raise ValueError("status must be a ContentStatus")


def _require_retirement_allowed(decision: RetirementPolicyDecision) -> None:
    if not isinstance(decision, RetirementPolicyDecision):
        raise ValueError("policy_decision must be a RetirementPolicyDecision")
    if decision is RetirementPolicyDecision.ACTIVE_REFERENCE:
        raise ValueError("content referenced by active curriculum cannot be retired")


def _required_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must not be empty")
    return unicodedata.normalize("NFC", value.strip())


def _preserved_text(value: str, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    return unicodedata.normalize("NFC", value)


def _raw_text(value: str, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    return value


def _optional_text(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    text = _raw_text(value, field_name)
    if not text.strip():
        raise ValueError(f"{field_name} must not be empty when supplied")
    return text


def _typed_tuple(value: Any, item_type: Any, field_name: str) -> tuple[Any, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name} must be a sequence")
    items = tuple(value)
    if not all(isinstance(item, item_type) for item in items):
        raise ValueError(f"{field_name} contains an invalid value")
    return items


def _uses_script(text: str, required: str, forbidden: str) -> bool:
    letter_names = [unicodedata.name(character, "") for character in text if character.isalpha()]
    return any(required in name for name in letter_names) and not any(
        forbidden in name for name in letter_names
    )


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError("timestamps must be datetime values")
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _freeze_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        frozen: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("JSON object keys must be strings")
            frozen[key] = _freeze_json(item)
        return MappingProxyType(frozen)
    if isinstance(value, list) or isinstance(value, _FrozenSequence):
        return _FrozenSequence(_freeze_json(item) for item in value)
    if isinstance(value, tuple):
        raise ValueError("JSON arrays must be supplied as lists")
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError("JSON numbers must be finite")
        return value
    raise ValueError("unsupported JSON value")


def plain_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: plain_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [plain_json(item) for item in value]
    return value


@dataclass(frozen=True)
class OrthographicForm:
    script: Script
    text: str

    def __post_init__(self) -> None:
        if not isinstance(self.script, Script):
            raise ValueError("script must be a Script")
        object.__setattr__(self, "text", _preserved_text(self.text, "orthographic text"))


@dataclass(frozen=True)
class Gloss:
    language: str
    text: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "language", _required_text(self.language, "gloss language"))
        object.__setattr__(self, "text", _preserved_text(self.text, "gloss text"))


@dataclass(frozen=True)
class UsageExample:
    serbian_text: str
    translation: str | None = None
    target_annotation: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "serbian_text", _raw_text(self.serbian_text, "example text"))
        object.__setattr__(
            self,
            "translation",
            _optional_text(self.translation, "translation"),
        )
        object.__setattr__(
            self,
            "target_annotation",
            _optional_text(self.target_annotation, "target_annotation"),
        )
        if not self.serbian_text.strip():
            raise ValueError("UsageExample Serbian text must not be empty")


@dataclass(frozen=True)
class LegacyExamplePayload:
    serbian_text: str | None
    translation: str | None

    def __post_init__(self) -> None:
        if self.serbian_text is not None:
            object.__setattr__(
                self,
                "serbian_text",
                _raw_text(self.serbian_text, "legacy example text"),
            )
        if self.translation is not None:
            object.__setattr__(
                self,
                "translation",
                _raw_text(self.translation, "legacy example translation"),
            )

    @property
    def has_serbian_text(self) -> bool:
        return self.serbian_text is not None and bool(self.serbian_text.strip())


@dataclass(frozen=True)
class StressPattern:
    structured: Mapping[str, Any] | None = None
    legacy_marker: str | None = None
    legacy_raw: Any | None = None

    def __post_init__(self) -> None:
        if self.structured is not None and not isinstance(self.structured, Mapping):
            raise ValueError("structured stress must be an object")
        if self.structured is not None:
            object.__setattr__(self, "structured", _freeze_json(self.structured))
        if self.legacy_raw is not None:
            object.__setattr__(self, "legacy_raw", _freeze_json(self.legacy_raw))
        if self.legacy_marker is not None:
            object.__setattr__(self, "legacy_marker", _raw_text(self.legacy_marker, "legacy marker"))

    def to_payload(self) -> dict[str, Any]:
        return {
            "structured": plain_json(self.structured),
            "legacy_marker": self.legacy_marker,
            "legacy_raw": plain_json(self.legacy_raw),
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any] | None) -> StressPattern | None:
        if payload is None:
            return None
        return cls(
            structured=payload.get("structured"),
            legacy_marker=payload.get("legacy_marker"),
            legacy_raw=payload.get("legacy_raw"),
        )


@dataclass(frozen=True)
class Sense:
    id: str
    lexical_unit_id: str
    glosses: tuple[Gloss, ...]
    notes: str | None = None
    examples: tuple[UsageExample | LegacyExamplePayload, ...] = ()
    status: ContentStatus = ContentStatus.DRAFT
    revision: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "glosses", _typed_tuple(self.glosses, Gloss, "glosses"))
        object.__setattr__(
            self,
            "examples",
            _typed_tuple(
                self.examples,
                (UsageExample, LegacyExamplePayload),
                "examples",
            ),
        )
        _canonical_id(self.id)
        _canonical_id(self.lexical_unit_id, "lexical_unit_id")
        _revision(self.revision)
        _status(self.status)

    @property
    def has_gloss(self) -> bool:
        return any(gloss.text.strip() for gloss in self.glosses)

    @property
    def is_publishable(self) -> bool:
        return self.has_gloss and all(
            isinstance(example, UsageExample) or example.has_serbian_text
            for example in self.examples
        )


@dataclass(frozen=True)
class Form:
    id: str
    lexical_unit_id: str
    form_kind: FormKind
    orthographies: tuple[OrthographicForm, ...]
    morph_features: Mapping[str, Any] = field(default_factory=dict)
    stress_pattern: StressPattern | None = None
    status: ContentStatus = ContentStatus.DRAFT
    revision: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "orthographies",
            _typed_tuple(self.orthographies, OrthographicForm, "orthographies"),
        )
        _canonical_id(self.id)
        _canonical_id(self.lexical_unit_id, "lexical_unit_id")
        _revision(self.revision)
        if not isinstance(self.form_kind, FormKind):
            raise ValueError("form_kind must be a FormKind")
        _status(self.status)
        if not isinstance(self.morph_features, Mapping):
            raise ValueError("morph_features must be a Mapping")
        if self.stress_pattern is not None and not isinstance(
            self.stress_pattern, StressPattern
        ):
            raise ValueError("stress_pattern must be a StressPattern or None")
        object.__setattr__(self, "morph_features", _freeze_json(self.morph_features))

    @property
    def has_required_serbian_scripts(self) -> bool:
        by_script = {orthography.script: orthography.text for orthography in self.orthographies}
        cyrillic = by_script.get(Script.CYRILLIC)
        latin = by_script.get(Script.LATIN)
        return bool(
            cyrillic
            and latin
            and _uses_script(cyrillic, "CYRILLIC", "LATIN")
            and _uses_script(latin, "LATIN", "CYRILLIC")
        )


@dataclass(frozen=True)
class LexicalUnit:
    id: str
    kind: EntryKind
    status: ContentStatus = ContentStatus.DRAFT
    revision: int = 1
    legacy_vocabulary_item_id: int | None = None
    senses: tuple[Sense, ...] = ()
    forms: tuple[Form, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def _forms_match_entry_kind(self) -> bool:
        if self.kind is EntryKind.MWE:
            return all(form.form_kind is FormKind.FIXED for form in self.forms)
        return all(form.form_kind in (FormKind.CITATION, FormKind.INFLECTED) for form in self.forms)

    def __post_init__(self) -> None:
        object.__setattr__(self, "senses", _typed_tuple(self.senses, Sense, "senses"))
        object.__setattr__(self, "forms", _typed_tuple(self.forms, Form, "forms"))
        _canonical_id(self.id)
        _revision(self.revision)
        if not isinstance(self.kind, EntryKind):
            raise ValueError("kind must be an EntryKind")
        _status(self.status)
        object.__setattr__(self, "created_at", _utc(self.created_at))
        object.__setattr__(self, "updated_at", _utc(self.updated_at))
        if any(sense.lexical_unit_id != self.id for sense in self.senses):
            raise ValueError("Sense must belong to the LexicalUnit")
        if any(form.lexical_unit_id != self.id for form in self.forms):
            raise ValueError("Form must belong to the LexicalUnit")
        children = self.senses + self.forms
        if any(child.status is not self.status for child in children):
            raise ValueError("LexicalUnit and child statuses must match")
        if self.status is not ContentStatus.DRAFT:
            if not self.senses or not all(sense.is_publishable for sense in self.senses):
                raise ValueError(f"{self.status.value} LexicalUnit requires valid Senses")
            if not self.forms or not all(
                form.has_required_serbian_scripts for form in self.forms
            ):
                raise ValueError(
                    f"{self.status.value} LexicalUnit requires a written Form with Serbian "
                    "Cyrillic and Latin"
                )
            if not self._forms_match_entry_kind():
                raise ValueError("FormKind is incompatible with EntryKind")

    def publish(self, *, at: datetime | None = None) -> LexicalUnit:
        if self.status is not ContentStatus.DRAFT:
            raise ValueError("only draft content can be published")
        if not self.senses or not all(sense.is_publishable for sense in self.senses):
            raise ValueError("every Sense must have a gloss before publication")
        if not self.forms or not all(form.has_required_serbian_scripts for form in self.forms):
            raise ValueError(
                "every Form must have Serbian Cyrillic and Latin before publication"
            )
        if not self._forms_match_entry_kind():
            raise ValueError("FormKind is incompatible with EntryKind")
        return replace(
            self,
            status=ContentStatus.PUBLISHED,
            revision=self.revision + 1,
            senses=tuple(
                replace(sense, status=ContentStatus.PUBLISHED, revision=sense.revision + 1)
                for sense in self.senses
            ),
            forms=tuple(
                replace(form, status=ContentStatus.PUBLISHED, revision=form.revision + 1)
                for form in self.forms
            ),
            updated_at=at or datetime.now(timezone.utc),
        )

    def retire(
        self,
        *,
        policy_decision: RetirementPolicyDecision,
        at: datetime | None = None,
    ) -> LexicalUnit:
        if self.status is not ContentStatus.PUBLISHED:
            raise ValueError("only published content can be retired")
        _require_retirement_allowed(policy_decision)
        return replace(
            self,
            status=ContentStatus.RETIRED,
            revision=self.revision + 1,
            senses=tuple(
                replace(sense, status=ContentStatus.RETIRED, revision=sense.revision + 1)
                for sense in self.senses
            ),
            forms=tuple(
                replace(form, status=ContentStatus.RETIRED, revision=form.revision + 1)
                for form in self.forms
            ),
            updated_at=at or datetime.now(timezone.utc),
        )


@dataclass(frozen=True)
class Construction:
    id: str
    code: str
    title: str
    description: str
    morph_features: Mapping[str, Any] = field(default_factory=dict)
    examples: tuple[UsageExample, ...] = ()
    status: ContentStatus = ContentStatus.DRAFT
    revision: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "examples",
            _typed_tuple(self.examples, UsageExample, "construction examples"),
        )
        _canonical_id(self.id)
        _revision(self.revision)
        _status(self.status)
        object.__setattr__(self, "code", _required_text(self.code, "construction code"))
        object.__setattr__(self, "title", _required_text(self.title, "construction title"))
        object.__setattr__(
            self,
            "description",
            _required_text(self.description, "construction description"),
        )
        if not isinstance(self.morph_features, Mapping):
            raise ValueError("morph_features must be a Mapping")
        object.__setattr__(self, "morph_features", _freeze_json(self.morph_features))
        if self.status is not ContentStatus.DRAFT and not self.examples:
            raise ValueError(
                f"{self.status.value} Construction requires an example: "
                "at least one valid UsageExample"
            )

    def publish(self) -> Construction:
        if self.status is not ContentStatus.DRAFT:
            raise ValueError("only draft content can be published")
        return replace(
            self,
            status=ContentStatus.PUBLISHED,
            revision=self.revision + 1,
        )

    def retire(self, *, policy_decision: RetirementPolicyDecision) -> Construction:
        if self.status is not ContentStatus.PUBLISHED:
            raise ValueError("only published content can be retired")
        _require_retirement_allowed(policy_decision)
        return replace(
            self,
            status=ContentStatus.RETIRED,
            revision=self.revision + 1,
        )
