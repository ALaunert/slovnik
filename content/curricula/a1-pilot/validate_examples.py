"""Validate draft example/answer fixtures against pilot and P0-04 source contracts."""

import argparse
import importlib.util
import json
import sys
import unicodedata
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))
from app.source_manifest import validate_manifest  # noqa: E402

_manifest_spec = importlib.util.spec_from_file_location(
    "a1_pilot_manifest_validator", Path(__file__).with_name("validate.py")
)
if _manifest_spec is None or _manifest_spec.loader is None:
    raise ImportError("pilot manifest validator unavailable")
_manifest_module = importlib.util.module_from_spec(_manifest_spec)
_manifest_spec.loader.exec_module(_manifest_module)
validate_curriculum = _manifest_module.validate


CYR_TO_LAT = str.maketrans({
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "ђ": "đ", "е": "e",
    "ж": "ž", "з": "z", "и": "i", "ј": "j", "к": "k", "л": "l", "љ": "lj",
    "м": "m", "н": "n", "њ": "nj", "о": "o", "п": "p", "р": "r", "с": "s",
    "т": "t", "ћ": "ć", "у": "u", "ф": "f", "х": "h", "ц": "c", "ч": "č",
    "џ": "dž", "ш": "š",
})


def _nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def _normalized_key(text, transliterate=False):
    text = unicodedata.normalize("NFC", text).casefold()
    if transliterate:
        text = text.translate(CYR_TO_LAT)
    return "".join(char for char in text if char.isalnum())


def validate(examples, curriculum, sources, publish=False):
    errors = []
    try:
        validate_curriculum(curriculum)
    except (ValueError, KeyError, TypeError, IndexError) as error:
        return [f"pilot manifest invalid: {error}"]
    if examples.get("schema_version") != 1:
        errors.append("unsupported example schema version")
    if examples.get("status") != "synthetic_test_only" and not publish:
        errors.append("draft validation requires explicit synthetic_test_only status")
    if publish and examples.get("status") != "reviewed":
        errors.append("synthetic/draft pack cannot publish")

    outcome_by_id = {item["id"]: item for item in curriculum["outcomes"]}
    target_ids = {item["id"] for item in curriculum["targets"]}
    source_items = {
        (source["source_id"], item["item_id"]): item
        for source in sources["sources"] for item in source["items"]
    }
    synthetic_items = {
        (source["source_id"], item_id)
        for source in examples.get("synthetic_sources", [])
        if source.get("status") == "synthetic_test_only"
        for item_id in source.get("item_ids", [])
    }
    seen_ids, policy_ids = set(), set()
    split_keys = {"assessment": set(), "other": set()}
    covered_outcome_roles = set()
    requested_items = set()
    for item in examples["examples"]:
        example_id = item["id"]
        if example_id in seen_ids:
            errors.append(f"duplicate example id: {example_id}")
        seen_ids.add(example_id)
        outcome = outcome_by_id.get(item["outcome_id"])
        if outcome is None:
            errors.append(f"unknown outcome: {example_id}")
            continue
        target = item["target"]
        if target["id"] not in target_ids or target["id"] not in outcome["target_ids"]:
            errors.append(f"unknown target for outcome: {example_id}")
        role = item["role"]
        if role not in ("input", "practice", "assessment") or item["family_id"] not in outcome["families"].get(role, []):
            errors.append(f"unresolved family: {example_id}")
        source_ref = (item["source"]["source_id"], item["source"]["item_id"])
        if source_ref not in source_items and source_ref not in synthetic_items:
            errors.append(f"unresolved source item: {example_id}")
        if source_ref in synthetic_items and publish:
            errors.append(f"synthetic source cannot publish: {example_id}")
        if source_ref in source_items:
            requested_items.add(source_ref[1])
        if item["review_status"] != "draft_unreviewed" and not publish:
            errors.append(f"unexpected review status in synthetic draft: {example_id}")
        if publish and item["review_status"] != "approved":
            errors.append(f"draft/unreviewed example cannot publish: {example_id}")

        text = item["text_nfc"]
        translation = item["translation_ru_nfc"]
        if not _nonempty(text) or not _nonempty(translation) or any(
            unicodedata.normalize("NFC", value) != value for value in (text, translation)
        ):
            errors.append(f"NFC text/translation required: {example_id}")
        if item["script"] not in outcome["script_conditions"]:
            errors.append(f"unsupported script: {example_id}")
        elif item["script"] == "serbian_cyrillic" and not any("CYRILLIC" in unicodedata.name(c, "") for c in text):
            errors.append(f"Cyrillic text required: {example_id}")
        elif item["script"] == "serbian_latin" and any("CYRILLIC" in unicodedata.name(c, "") for c in text):
            errors.append(f"Latin text required: {example_id}")
        start, end = target["start"], target["end"]
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text) or text[start:end] != target["surface"]:
            errors.append(f"target span does not reconstruct: {example_id}")
        answer = item["answer_policy"]
        if answer["id"] in policy_ids:
            errors.append(f"duplicate answer policy id: {answer['id']}")
        policy_ids.add(answer["id"])
        if answer["revision"] < 1 or not answer["accepted_variants"] or not all(
            _nonempty(variant) and unicodedata.normalize("NFC", variant) == variant
            for variant in answer["accepted_variants"]
        ):
            errors.append(f"answer variants missing/non-NFC: {example_id}")
        if publish and answer["review_status"] != "approved":
            errors.append(f"draft answer policy cannot publish: {example_id}")
        if not publish and answer["review_status"] != "draft_unreviewed":
            errors.append(f"synthetic answer policy must remain draft: {example_id}")
        if (publish and role in ("input", "practice", "assessment")
                and source_ref in source_items and item["review_status"] == "approved"
                and answer["review_status"] == "approved"):
            covered_outcome_roles.add((item["outcome_id"], role))
        if not _nonempty(item["leakage_group"]):
            errors.append(f"leakage group missing: {example_id}")
        bucket = "assessment" if role == "assessment" else "other"
        for key in (
            "group:" + item["leakage_group"],
            "serbian:" + _normalized_key(text, transliterate=True),
            "translation:" + _normalized_key(translation),
        ):
            split_keys[bucket].add(key)
        for variant in answer["accepted_variants"]:
            if _nonempty(variant):
                split_keys[bucket].add("serbian:" + _normalized_key(variant, transliterate=True))

    if publish:
        for outcome in curriculum["outcomes"]:
            for role in ("input", "practice", "assessment"):
                if (outcome["id"], role) not in covered_outcome_roles:
                    errors.append(f"missing publish coverage: {outcome['id']}/{role}")
    if split_keys["assessment"] & split_keys["other"]:
        errors.append("holdout leakage: same group, Serbian text/answer variant or translation across split")
    if publish and requested_items:
        errors.extend(validate_manifest(
            sources, requested_uses={"redistribution", "adaptation"},
            requested_item_ids=requested_items,
            requested_materials={"text", "translation"},
        ))
        for source in sources["sources"]:
            for source_item in source["items"]:
                if source_item["item_id"] in requested_items:
                    for material in ("text", "translation"):
                        if material not in source_item["materials"]:
                            errors.append(f"source {material} rights missing: {source_item['item_id']}")
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--examples", type=Path, default=Path(__file__).with_name("examples.synthetic.json"))
    parser.add_argument("--curriculum", type=Path, default=Path(__file__).with_name("manifest.json"))
    parser.add_argument("--sources", type=Path, default=ROOT / "content/sources/manifest.json")
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    try:
        files = [json.loads(path.read_text(encoding="utf-8")) for path in
                 (args.examples, args.curriculum, args.sources)]
        errors = validate(*files, publish=args.publish)
    except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
        errors = [str(error)]
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("synthetic example contract valid; publication not implied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
