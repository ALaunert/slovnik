import json
import subprocess
import sys
from copy import deepcopy
from dataclasses import FrozenInstanceError
from hashlib import sha256

import pytest


TARGET_ID = "abcdef12-1234-5678-9234-567812345678"
GOLDEN_CONDITION_JSON = (
    '{"a":{"case":"locative","učenik":"ђак"},'
    '"z":[null,true,7,"café"]}'
)
GOLDEN_TARGET_KEY = (
    f"v1:sense:{TARGET_ID}:recognize_meaning:written:"
    "bb795b51984d4ce9bbc534d605fd5ad87de03cfab2dab84ddce6cdcdee0f7319"
)


def test_public_wire_enums_and_imports() -> None:
    from app.domain import Capability, Modality, TargetKind, TargetSpec
    from app.domain.shared import Capability as SharedCapability
    from app.domain.shared import Modality as SharedModality
    from app.domain.shared import TargetKind as SharedTargetKind
    from app.domain.target import TargetSpec as ModuleTargetSpec

    assert TargetKind is SharedTargetKind
    assert Capability is SharedCapability
    assert Modality is SharedModality
    assert TargetSpec is ModuleTargetSpec
    assert [member.value for member in TargetKind] == [
        "sense",
        "form",
        "construction",
    ]
    assert [member.value for member in Capability] == [
        "recognize_meaning",
        "retrieve_form",
        "apply_construction",
    ]
    assert [member.value for member in Modality] == ["written"]


def test_domain_imports_are_standard_library_only() -> None:
    blocked_roots = {"fastapi", "sqlalchemy", "pydantic", "pydantic_settings", "openai"}
    script = """
import json
import sys
sys.path.insert(0, '.')
before = set(sys.modules)
import app.domain
loaded = sorted(
    name for name in set(sys.modules) - before
    if name.split('.', 1)[0] in %r
)
print(json.dumps(loaded))
""" % (blocked_roots,)

    result = subprocess.run(
        [sys.executable, "-I", "-c", script],
        cwd=".",
        check=True,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": "."},
    )

    assert json.loads(result.stdout) == []


@pytest.mark.parametrize(
    ("target_kind", "capability"),
    [
        ("sense", "recognize_meaning"),
        ("sense", "retrieve_form"),
        ("construction", "apply_construction"),
    ],
)
def test_target_spec_accepts_allowed_mvp_pairings(
    target_kind: str, capability: str
) -> None:
    from app.domain import Capability, Modality, TargetKind, TargetSpec

    spec = TargetSpec(
        target_kind=TargetKind(target_kind),
        target_id=TARGET_ID,
        capability=Capability(capability),
        modality=Modality.WRITTEN,
    )

    assert spec.target_kind.value == target_kind
    assert spec.capability.value == capability


def test_ordinary_sense_recall_does_not_add_expected_form_to_identity() -> None:
    from app.domain import Capability, Modality, TargetKind, TargetSpec

    first = TargetSpec(
        target_kind=TargetKind.SENSE,
        target_id=TARGET_ID,
        capability=Capability.RETRIEVE_FORM,
        modality=Modality.WRITTEN,
    )
    second = TargetSpec(
        target_kind=TargetKind.SENSE,
        target_id=TARGET_ID,
        capability=Capability.RETRIEVE_FORM,
        modality=Modality.WRITTEN,
    )

    assert first == second
    assert first.target_key == second.target_key


def test_form_specific_recall_requires_and_accepts_a_condition() -> None:
    from app.domain import Capability, Modality, TargetKind, TargetSpec

    spec = TargetSpec(
        target_kind=TargetKind.FORM,
        target_id=TARGET_ID,
        capability=Capability.RETRIEVE_FORM,
        modality=Modality.WRITTEN,
        condition={"case": "locative"},
    )

    assert spec.condition == {"case": "locative"}


@pytest.mark.parametrize(
    ("target_kind", "capability", "condition"),
    [
        ("sense", "apply_construction", {}),
        ("construction", "recognize_meaning", {}),
        ("construction", "retrieve_form", {}),
        ("form", "recognize_meaning", {"case": "locative"}),
        ("form", "apply_construction", {"case": "locative"}),
        ("form", "retrieve_form", {}),
    ],
)
def test_target_spec_rejects_invalid_mvp_pairings(
    target_kind: str, capability: str, condition: dict[str, str]
) -> None:
    from app.domain import Capability, Modality, TargetKind, TargetSpec

    with pytest.raises(ValueError):
        TargetSpec(
            target_kind=TargetKind(target_kind),
            target_id=TARGET_ID,
            capability=Capability(capability),
            modality=Modality.WRITTEN,
            condition=condition,
        )


@pytest.mark.parametrize(
    "target_id",
    [
        "not-a-uuid",
        TARGET_ID.upper(),
        TARGET_ID.replace("-", ""),
    ],
)
def test_target_spec_rejects_noncanonical_uuid(target_id: str) -> None:
    from app.domain import Capability, Modality, TargetKind, TargetSpec

    with pytest.raises(ValueError):
        TargetSpec(
            target_kind=TargetKind.SENSE,
            target_id=target_id,
            capability=Capability.RECOGNIZE_MEANING,
            modality=Modality.WRITTEN,
        )


def test_target_spec_has_schema_version_one_and_exact_canonical_key() -> None:
    from app.domain import Capability, Modality, TargetKind, TargetSpec

    spec = TargetSpec(
        target_kind=TargetKind.SENSE,
        target_id=TARGET_ID,
        capability=Capability.RECOGNIZE_MEANING,
        modality=Modality.WRITTEN,
    )
    condition_hash = sha256(b"{}").hexdigest()

    assert spec.schema_version == 1
    assert spec.target_key == (
        f"v1:sense:{TARGET_ID}:recognize_meaning:written:{condition_hash}"
    )
    assert len(spec.target_key) <= 255


def test_target_spec_rejects_other_schema_versions() -> None:
    from app.domain import Capability, Modality, TargetKind, TargetSpec

    with pytest.raises(ValueError):
        TargetSpec(
            target_kind=TargetKind.SENSE,
            target_id=TARGET_ID,
            capability=Capability.RECOGNIZE_MEANING,
            modality=Modality.WRITTEN,
            schema_version=2,
        )


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("target_kind", "word"),
        ("capability", "translate"),
        ("modality", "spoken"),
    ],
)
def test_target_spec_rejects_non_enum_values(
    field_name: str, invalid_value: str
) -> None:
    from app.domain import Capability, Modality, TargetKind, TargetSpec

    fields = {
        "target_kind": TargetKind.SENSE,
        "target_id": TARGET_ID,
        "capability": Capability.RECOGNIZE_MEANING,
        "modality": Modality.WRITTEN,
    }
    fields[field_name] = invalid_value

    with pytest.raises(ValueError):
        TargetSpec(**fields)


def test_target_spec_is_immutable() -> None:
    from app.domain import Capability, Modality, TargetKind, TargetSpec

    spec = TargetSpec(
        target_kind=TargetKind.SENSE,
        target_id=TARGET_ID,
        capability=Capability.RECOGNIZE_MEANING,
        modality=Modality.WRITTEN,
    )

    with pytest.raises(FrozenInstanceError):
        spec.target_id = "87654321-4321-6789-a234-567812345678"


def _conditioned_sense(condition: object):
    from app.domain import Capability, Modality, TargetKind, TargetSpec

    return TargetSpec(
        target_kind=TargetKind.SENSE,
        target_id=TARGET_ID,
        capability=Capability.RECOGNIZE_MEANING,
        modality=Modality.WRITTEN,
        condition=condition,
    )


def test_condition_key_order_is_canonical_recursively() -> None:
    first = _conditioned_sense(
        {"features": {"number": "plural", "case": "locative"}, "cue": "text"}
    )
    second = _conditioned_sense(
        {"cue": "text", "features": {"case": "locative", "number": "plural"}}
    )

    assert first.target_key == second.target_key


def test_condition_normalizes_keys_and_strings_to_nfc_recursively() -> None:
    decomposed = _conditioned_sense(
        {"cafe\u0301": ["cafe\u0301", {"role": "uc\u030cenik"}]}
    )
    composed = _conditioned_sense({"café": ["café", {"role": "učenik"}]})

    assert decomposed == composed
    assert decomposed.target_key == composed.target_key


def test_condition_rejects_nfc_key_collisions() -> None:
    with pytest.raises(ValueError, match="collision"):
        _conditioned_sense({"cafe\u0301": "one", "café": "two"})


@pytest.mark.parametrize("value", [1.5, float("nan")])
def test_condition_rejects_all_floats(value: float) -> None:
    with pytest.raises(ValueError, match="condition"):
        _conditioned_sense({"value": value})


def test_condition_keeps_boolean_distinct_from_integer() -> None:
    boolean = _conditioned_sense({"value": True})
    integer = _conditioned_sense({"value": 1})

    assert boolean.target_key != integer.target_key


def test_condition_accepts_all_non_float_json_value_types_recursively() -> None:
    spec = _conditioned_sense(
        {"null": None, "boolean": False, "integer": 0, "string": "", "list": [{}]}
    )

    assert spec.condition == {
        "null": None,
        "boolean": False,
        "integer": 0,
        "string": "",
        "list": ({},),
    }


def test_condition_rejects_non_string_object_keys() -> None:
    with pytest.raises(ValueError, match="string"):
        _conditioned_sense({"nested": [{1: "value"}]})


@pytest.mark.parametrize("value", [("tuple",), {"set"}])
def test_condition_rejects_unsupported_objects(value: object) -> None:
    with pytest.raises(ValueError, match="condition"):
        _conditioned_sense({"value": value})


@pytest.mark.parametrize("condition", [None, [], "condition"])
def test_condition_root_must_be_an_object(condition: object) -> None:
    with pytest.raises(ValueError, match="object"):
        _conditioned_sense(condition)


def test_condition_is_defensively_immutable() -> None:
    source = {"features": {"case": "locative"}, "cues": ["written"]}
    spec = _conditioned_sense(source)
    original_key = spec.target_key

    source["features"]["case"] = "accusative"
    source["cues"].append("hinted")

    assert spec.condition == {
        "features": {"case": "locative"},
        "cues": ("written",),
    }
    assert spec.target_key == original_key
    with pytest.raises(TypeError):
        spec.condition["new"] = "value"
    with pytest.raises(TypeError):
        spec.condition["features"]["case"] = "accusative"


def test_target_spec_payload_is_detached_json_and_round_trips() -> None:
    from app.domain import TargetSpec

    spec = _conditioned_sense(
        {"features": {"case": "locative"}, "cues": ["written", None]}
    )

    payload = spec.to_payload()
    untouched_payload = deepcopy(payload)
    restored = TargetSpec.from_payload(payload)

    assert list(payload) == [
        "schema_version",
        "target_kind",
        "target_id",
        "capability",
        "modality",
        "condition",
        "target_key",
    ]
    assert payload["target_kind"] == "sense"
    assert payload["capability"] == "recognize_meaning"
    assert payload["modality"] == "written"
    assert type(payload["condition"]) is dict
    assert type(payload["condition"]["cues"]) is list
    assert json.loads(json.dumps(payload, ensure_ascii=False)) == payload
    assert restored == spec
    assert payload == untouched_payload

    payload["condition"]["features"]["case"] = "accusative"
    payload["condition"]["cues"].append("hinted")
    assert spec.to_payload() == untouched_payload
    assert restored.to_payload() == untouched_payload


def test_target_spec_payload_ignores_additive_unknown_fields() -> None:
    from app.domain import TargetSpec

    spec = _conditioned_sense({"case": "locative"})
    payload = {**spec.to_payload(), "future_field": {"ignored": True}}

    assert TargetSpec.from_payload(payload) == spec


@pytest.mark.parametrize(
    "missing_field",
    [
        "schema_version",
        "target_kind",
        "target_id",
        "capability",
        "modality",
        "condition",
        "target_key",
    ],
)
def test_target_spec_payload_requires_every_known_field(missing_field: str) -> None:
    from app.domain import TargetSpec

    payload = _conditioned_sense({}).to_payload()
    del payload[missing_field]

    with pytest.raises(ValueError, match=missing_field):
        TargetSpec.from_payload(payload)


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("schema_version", True),
        ("target_kind", 1),
        ("target_id", 1),
        ("capability", 1),
        ("modality", 1),
        ("condition", []),
        ("target_key", 1),
    ],
)
def test_target_spec_payload_validates_known_field_types(
    field_name: str, invalid_value: object
) -> None:
    from app.domain import TargetSpec

    payload = _conditioned_sense({}).to_payload()
    payload[field_name] = invalid_value

    with pytest.raises(ValueError, match=field_name):
        TargetSpec.from_payload(payload)


def test_target_spec_payload_rejects_a_mismatched_target_key() -> None:
    from app.domain import TargetSpec

    payload = _conditioned_sense({}).to_payload()
    payload["target_key"] = "v1:tampered"

    with pytest.raises(ValueError, match="target_key"):
        TargetSpec.from_payload(payload)


@pytest.mark.parametrize(
    "invalid_value",
    [("tuple",), {"set"}, object(), 1.5, float("nan")],
)
def test_target_spec_payload_rejects_invalid_nested_condition_values(
    invalid_value: object,
) -> None:
    from app.domain import TargetSpec

    payload = _conditioned_sense({}).to_payload()
    payload["condition"] = {"nested": invalid_value}

    with pytest.raises(ValueError, match="condition"):
        TargetSpec.from_payload(payload)


def test_target_spec_payload_rejects_non_string_condition_keys() -> None:
    from app.domain import TargetSpec

    payload = _conditioned_sense({}).to_payload()
    payload["condition"] = {"nested": [{1: "value"}]}

    with pytest.raises(ValueError, match="string"):
        TargetSpec.from_payload(payload)


def test_target_spec_payload_rejects_nfc_colliding_condition_keys() -> None:
    from app.domain import TargetSpec

    payload = _conditioned_sense({}).to_payload()
    payload["condition"] = {"cafe\u0301": "one", "café": "two"}

    with pytest.raises(ValueError, match="collision"):
        TargetSpec.from_payload(payload)


def test_nested_unicode_condition_matches_independent_golden_vector() -> None:
    spec = _conditioned_sense(
        {
            "z": [None, True, 7, "cafe\u0301"],
            "a": {"uc\u030cenik": "ђак", "case": "locative"},
        }
    )
    canonical_condition = json.dumps(
        spec.to_payload()["condition"],
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )

    assert canonical_condition == GOLDEN_CONDITION_JSON
    assert spec.target_key == GOLDEN_TARGET_KEY
