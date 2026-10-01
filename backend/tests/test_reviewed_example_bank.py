"""Publication gates for reviewed file revisions; approvals below are synthetic."""

from copy import deepcopy
from pathlib import Path
import json

import pytest

from app.pilot_examples import validate_pilot_examples


ROOT = Path(__file__).resolve().parents[2]


def _bank():
    pack = json.loads((ROOT / "content/curricula/a1-pilot/examples.json").read_text())
    pilot = json.loads((ROOT / "content/curricula/a1-pilot/manifest.json").read_text())
    sources = json.loads((ROOT / "content/sources/manifest.json").read_text())
    pack["schema_version"] = 2
    pack["publication_decision"] = {"status": "pending_owner"}
    for item in pack["examples"]:
        item.update({
            "revision": 1, "source_item_key": item["id"],
            "original_text": item["text"], "register": "neutral",
            "duplicate_cluster": item["id"], "privacy": "fictional",
            "task": {"input": "Fictional context", "instruction_ru": "Напишите ответ.",
                     "format": "sentence", "response_mode": "finite_reviewed_set"},
            "provenance": {"text": "original_model_assisted", "translation": "original_model_assisted"},
            "answer_policy": {"id": item["id"] + "-answers", "revision": 1,
                              "unlisted": "unresolved", "normalization": ["NFC", "trim"]},
            "translation_status": "internally_checked",
            "answer_policy_status": "internally_checked",
            "review": {"status": "internally_checked", "reviewer": "synthetic",
                       "date": "2026-09-27", "source_locators": ["synthetic:1"],
                       "naturalness": "bounded formula", "target_alignment": "checked",
                       "answerability": "finite", "variants": "unlisted unresolved",
                       "translation": "meaning checked", "disagreements": []},
        })
    return pack, pilot, sources


def test_v2_pending_bank_can_be_validated_without_publication() -> None:
    from app.reviewed_example_bank import example_revision_hash
    pack, pilot, sources = _bank()
    for item in pack["examples"]:
        item["content_hash"] = example_revision_hash(item)
    assert validate_pilot_examples(pack, pilot, sources) == []


@pytest.mark.parametrize("change, reason", [
    ("privacy", "fictional"), ("target", "target"), ("fragment", "fragment"),
    ("translation", "translation"), ("review", "review"), ("hash", "hash"),
    ("variant", "unresolved"), ("cluster", "cluster"),
])
def test_v2_rejects_unsafe_or_unreviewed_candidates(change, reason) -> None:
    from app.reviewed_example_bank import example_revision_hash
    pack, pilot, sources = _bank()
    item = pack["examples"][0]
    if change == "privacy":
        item["privacy"] = "real_person"
    elif change == "target":
        item["target_ref"] = [item["target_ref"], "ambiguous"]
    elif change == "fragment":
        item["task"]["format"] = "unresolved_fragment"
    elif change == "translation":
        item["translation_status"] = "draft"
    elif change == "review":
        del item["review"]["naturalness"]
    elif change == "variant":
        item["answer_policy"]["unlisted"] = "wrong"
    elif change == "cluster":
        pack["examples"][1]["duplicate_cluster"] = item["duplicate_cluster"]
    for entry in pack["examples"]:
        entry["content_hash"] = example_revision_hash(entry)
    if change == "hash":
        item["text"] += " Changed."
    assert any(reason in error for error in validate_pilot_examples(pack, pilot, sources))


def test_reimport_preserves_identity_and_immutable_revision() -> None:
    from app.reviewed_example_bank import example_revision_hash, validate_reimport
    pack, _, _ = _bank()
    for item in pack["examples"]:
        item["content_hash"] = example_revision_hash(item)
    assert validate_reimport(deepcopy(pack), pack) == []
    renamed = deepcopy(pack)
    renamed["examples"][0]["id"] = "new-import-generated-id"
    assert any("identity" in error for error in validate_reimport(renamed, pack))
    edited = deepcopy(pack)
    edited["examples"][0]["translation"] = "Новое значение."
    edited["examples"][0]["content_hash"] = example_revision_hash(edited["examples"][0])
    assert any("immutable" in error for error in validate_reimport(edited, pack))
    reassigned = deepcopy(pack)
    reassigned["examples"][0]["source_item_key"] = "other-original"
    assert any("identity" in error for error in validate_reimport(reassigned, pack))


def test_publication_requires_owner_decision_bound_to_exact_content_and_rights() -> None:
    from app.reviewed_example_bank import bank_digest, example_revision_hash, rights_digest
    pack, pilot, sources = _bank()
    for item in pack["examples"]:
        item["content_hash"] = example_revision_hash(item)
    right = {"status": "approved", "uses": ["analysis", "pilot_display"],
             "license": "synthetic permission", "evidence": "agreement:test-only",
             "reviewer": "synthetic-owner", "reviewed_at": "2026-09-27"}
    sources["sources"][0]["rights"]["text"] = deepcopy(right)
    sources["sources"][0]["rights"]["translation"] = deepcopy(right)
    assert any("owner" in error for error in validate_pilot_examples(
        pack, pilot, sources, publication=True
    ))
    pack["publication_decision"] = {
        "status": "approved", "owner": "synthetic-owner", "date": "2026-09-27",
        "content_digest": bank_digest(pack), "rights_digest": rights_digest(sources),
    }
    assert validate_pilot_examples(pack, pilot, sources, publication=True) == []
    sources["sources"][0]["rights"]["translation"]["evidence"] = "agreement:changed"
    assert any("rights digest" in error for error in validate_pilot_examples(
        pack, pilot, sources, publication=True
    ))


def test_review_export_is_sorted_and_includes_context_keys_and_open_gate() -> None:
    from app.reviewed_example_bank import review_markdown
    pack, _, _ = _bank()
    exported = review_markdown(pack)
    assert "pending_owner" in exported
    assert "Напишите ответ." in exported
    assert "unresolved" in exported
    assert exported == review_markdown({**pack, "examples": list(reversed(pack["examples"]))})


def _checked_files():
    return tuple(json.loads((ROOT / path).read_text()) for path in (
        "content/examples/a1-written-v1.json", "content/curricula/a1-pilot/manifest.json",
        "content/sources/a1-written-v1.json",
    ))


def test_owner_approved_bank_covers_each_task_and_keeps_separate_permission_gates() -> None:
    pack, pilot, sources = _checked_files()
    assert validate_pilot_examples(pack, pilot, sources) == []
    for outcome in pilot["outcomes"]:
        assert {item["role"] for item in pack["examples"] if item["outcome_id"] == outcome["id"]} == {"practice", "assessment"}
    assert validate_pilot_examples(pack, pilot, sources, publication=True) == []
    pack["publication_decision"] = {"status": "pending_owner"}
    sources["sources"][0]["rights"]["translation"]["status"] = "unknown"
    errors = validate_pilot_examples(pack, pilot, sources, publication=True)
    assert any("owner" in error for error in errors)
    assert any("permission" in error for error in errors)


@pytest.mark.parametrize("change, reason", [
    ("script_alias", "equivalent"), ("field_alias", "field"),
    ("display", "display"), ("source_pin", "checksum"), ("contact", "private"),
    ("field_value", "field"), ("numeral", "numeral"),
    ("fragment", "fragment"), ("script", "script"),
])
def test_rejects_bad_transliteration_or_stale_source_pin(change, reason) -> None:
    from app.reviewed_example_bank import example_revision_hash
    pack, pilot, sources = _checked_files()
    if change == "script_alias":
        item = next(item for item in pack["examples"] if item["id"] == "a1-written-location-office")
        item["answer_policy"]["equivalent_script_answers"] = ["Састанак је у хотелю."]
    elif change == "field_alias":
        item = next(item for item in pack["examples"] if item["id"] == "a1-written-personal-profile")
        item["answer_policy"]["fields"]["prezime"] = ["Павловић", "Pavlovic"]
    elif change == "display":
        item = pack["examples"][0]
        item["text"] = "Wrong display text."
    elif change == "source_pin":
        item = pack["examples"][0]
        item["translation"] = "Новый перевод."
    elif change == "field_value":
        item = pack["examples"][0]
        item["answer_policy"]["fields"]["ime"] = ["Мила", "Mila"]
    elif change == "numeral":
        item = next(item for item in pack["examples"] if item["id"] == "a1-written-price-shop")
        item["answer_policy"]["expected_numeral"] = "95"
    elif change == "fragment":
        item = next(item for item in pack["examples"] if item["id"] == "a1-written-request-counter")
        item["text"] = item["original_text"] = "Молим."
    elif change == "script":
        item = pack["examples"][0]
        item["script"] = "latin"
    else:
        item = pack["examples"][0]
        item["task"]["input"] += " mail@example.test"
    item["content_hash"] = example_revision_hash(item)
    assert any(reason in error for error in validate_pilot_examples(pack, pilot, sources))


@pytest.mark.parametrize("field", ["review", "task", "provenance", "answer_policy", "source_id"])
def test_malformed_v2_objects_return_rejection_instead_of_crashing(field) -> None:
    pack, pilot, sources = _checked_files()
    pack["examples"][0][field] = []
    assert validate_pilot_examples(pack, pilot, sources)


@pytest.mark.parametrize("field, value", [
    ("script", []), ("role", []), ("register", []), ("revision", "1"),
    ("task.input", ["x"]), ("task.instruction_ru", True), ("task.format", []),
    ("review.source_locators", [1]), ("review.naturalness", {"fake": "text"}),
])
def test_malformed_nested_values_cannot_pass_validation(field, value) -> None:
    from app.reviewed_example_bank import bank_digest, example_revision_hash
    pack, pilot, sources = _checked_files()
    item = pack["examples"][0]
    if "." in field:
        parent, child = field.split(".")
        item[parent][child] = value
    else:
        item[field] = value
    item["content_hash"] = example_revision_hash(item)
    sources["sources"][0]["checksum"] = sources["sources"][0]["pinned_checksum"] = bank_digest(pack)
    assert validate_pilot_examples(pack, pilot, sources)


def test_bank_cannot_assign_one_source_item_to_multiple_ids_or_revisions() -> None:
    from app.reviewed_example_bank import bank_digest, example_revision_hash, validate_reimport
    pack, pilot, sources = _checked_files()
    pack["examples"][1]["source_item_key"] = pack["examples"][0]["source_item_key"]
    pack["examples"][1]["revision"] = 2
    pack["examples"][1]["content_hash"] = example_revision_hash(pack["examples"][1])
    sources["sources"][0]["checksum"] = sources["sources"][0]["pinned_checksum"] = bank_digest(pack)
    assert any("identity" in error for error in validate_pilot_examples(pack, pilot, sources))
    assert any("identity" in error for error in validate_reimport(pack, pack))


def test_reimport_rejects_malformed_previous_revision_before_comparing() -> None:
    from app.reviewed_example_bank import validate_reimport
    pack, _, _ = _checked_files()
    previous = deepcopy(pack)
    previous["examples"][0]["revision"] = "1"
    assert validate_reimport(pack, previous)


def test_cli_exports_review_and_refuses_unapproved_bank(tmp_path) -> None:
    import subprocess
    import sys

    export = tmp_path / "review.md"
    command = [sys.executable, "-m", "app.reviewed_example_bank",
               str(ROOT / "content/examples/a1-written-v1.json"),
               "--pilot", str(ROOT / "content/curricula/a1-pilot/manifest.json"),
               "--sources", str(ROOT / "content/sources/a1-written-v1.json")]
    result = subprocess.run([*command, "--review-export", str(export)], capture_output=True, text=True)
    assert result.returncode == 0
    assert "Молим воду." in export.read_text()
    result = subprocess.run([*command, "--publication"], capture_output=True, text=True)
    assert result.returncode == 0
    pack, _, _ = _checked_files()
    pack["publication_decision"] = {"status": "pending_owner"}
    pending = tmp_path / "pending.json"
    pending.write_text(json.dumps(pack))
    command[3] = str(pending)
    result = subprocess.run([*command, "--publication"], capture_output=True, text=True)
    assert result.returncode == 1
    assert any("owner" in error for error in json.loads(result.stdout)["rejected"])
