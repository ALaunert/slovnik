import json
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, field
from hashlib import sha256
from types import MappingProxyType
from uuid import UUID

from .shared import Capability, Modality, TargetKind


_ALLOWED_TARGET_CAPABILITIES = {
    (TargetKind.SENSE, Capability.RECOGNIZE_MEANING),
    (TargetKind.SENSE, Capability.RETRIEVE_FORM),
    (TargetKind.CONSTRUCTION, Capability.APPLY_CONSTRUCTION),
    (TargetKind.FORM, Capability.RETRIEVE_FORM),
}

_PAYLOAD_FIELD_TYPES = (
    ("schema_version", int),
    ("target_kind", str),
    ("target_id", str),
    ("capability", str),
    ("modality", str),
    ("condition", Mapping),
    ("target_key", str),
)


def _canonicalize_json(value: object) -> object:
    if value is None or isinstance(value, bool) or isinstance(value, int):
        return value
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, float):
        raise ValueError("TargetSpec condition must not contain floats")
    if isinstance(value, list):
        return [_canonicalize_json(item) for item in value]
    if isinstance(value, dict):
        normalized: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("TargetSpec condition object keys must be strings")
            normalized_key = unicodedata.normalize("NFC", key)
            if normalized_key in normalized:
                raise ValueError("TargetSpec condition has an NFC key collision")
            normalized[normalized_key] = _canonicalize_json(item)
        return normalized
    raise ValueError("TargetSpec condition contains an unsupported value")


def _freeze_json(value: object) -> object:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze_json(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze_json(item) for item in value)
    return value


def _to_plain_json(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _to_plain_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_plain_json(item) for item in value]
    return value


def _build_target_key(
    target_kind: TargetKind,
    target_id: str,
    capability: Capability,
    modality: Modality,
    condition: dict[str, object],
) -> str:
    canonical_condition = json.dumps(
        condition,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )
    condition_hash = sha256(canonical_condition.encode("utf-8")).hexdigest()
    return ":".join(
        (
            "v1",
            target_kind.value,
            target_id.lower(),
            capability.value,
            modality.value,
            condition_hash,
        )
    )


@dataclass(frozen=True)
class TargetSpec:
    target_kind: TargetKind
    target_id: str
    capability: Capability
    modality: Modality
    condition: Mapping[str, object] = field(
        default_factory=dict,
        compare=False,
        hash=False,
    )
    schema_version: int = 1
    target_key: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("TargetSpec schema_version must be 1")
        enum_fields = (
            ("target_kind", self.target_kind, TargetKind),
            ("capability", self.capability, Capability),
            ("modality", self.modality, Modality),
        )
        for field_name, value, enum_type in enum_fields:
            if not isinstance(value, enum_type):
                raise ValueError(
                    f"TargetSpec {field_name} must be a {enum_type.__name__}"
                )
        if not isinstance(self.target_id, str):
            raise ValueError("TargetSpec target_id must be a UUID string")
        try:
            parsed_target_id = UUID(self.target_id)
        except ValueError as exc:
            raise ValueError("TargetSpec target_id must be a UUID string") from exc
        if str(parsed_target_id) != self.target_id:
            raise ValueError("TargetSpec target_id must be a canonical lowercase UUID")
        if not isinstance(self.condition, dict):
            raise ValueError("TargetSpec condition must be an object")
        canonical_condition_value = _canonicalize_json(self.condition)
        assert isinstance(canonical_condition_value, dict)

        if (self.target_kind, self.capability) not in _ALLOWED_TARGET_CAPABILITIES:
            raise ValueError("Unsupported target kind and capability pairing")
        if self.target_kind is TargetKind.FORM and not canonical_condition_value:
            raise ValueError("Form retrieval requires a form-specific condition")

        target_key = _build_target_key(
            self.target_kind,
            self.target_id,
            self.capability,
            self.modality,
            canonical_condition_value,
        )
        if len(target_key) > 255:
            raise ValueError("TargetSpec target_key must not exceed 255 characters")
        object.__setattr__(self, "condition", _freeze_json(canonical_condition_value))
        object.__setattr__(self, "target_key", target_key)

    def to_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "target_kind": self.target_kind.value,
            "target_id": self.target_id,
            "capability": self.capability.value,
            "modality": self.modality.value,
            "condition": _to_plain_json(self.condition),
            "target_key": self.target_key,
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "TargetSpec":
        if not isinstance(payload, Mapping):
            raise ValueError("TargetSpec payload must be an object")

        for field_name, expected_type in _PAYLOAD_FIELD_TYPES:
            if field_name not in payload:
                raise ValueError(f"TargetSpec payload requires {field_name}")
            value = payload[field_name]
            if expected_type is int:
                valid_type = type(value) is int
            else:
                valid_type = isinstance(value, expected_type)
            if not valid_type:
                raise ValueError(f"TargetSpec payload {field_name} has an invalid type")

        condition_payload = payload["condition"]
        assert isinstance(condition_payload, Mapping)
        condition = dict(condition_payload)
        try:
            target_kind = TargetKind(payload["target_kind"])
            capability = Capability(payload["capability"])
            modality = Modality(payload["modality"])
        except ValueError as exc:
            raise ValueError("TargetSpec payload contains an invalid enum wire value") from exc

        spec = cls(
            schema_version=payload["schema_version"],
            target_kind=target_kind,
            target_id=payload["target_id"],
            capability=capability,
            modality=modality,
            condition=condition,
        )
        if payload["target_key"] != spec.target_key:
            raise ValueError("TargetSpec payload target_key does not match its fields")
        return spec
