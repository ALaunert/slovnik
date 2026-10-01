import json
from copy import deepcopy
from pathlib import Path

from app.pilot_examples import validate_pilot_examples


ROOT = Path(__file__).parents[2]


def _files() -> tuple[dict, dict, dict]:
    paths = ("content/curricula/a1-pilot/examples.json",
             "content/curricula/a1-pilot/manifest.json", "content/sources/manifest.json")
    return tuple(json.loads((ROOT / path).read_text(encoding="utf-8")) for path in paths)


def test_draft_examples_cover_both_scripts_multitoken_and_answer_variants() -> None:
    pack, pilot, sources = _files()
    assert validate_pilot_examples(pack, pilot, sources) == []
    assert {item["script"] for item in pack["examples"]} == {"cyrillic", "latin"}
    assert any(" " in item["text"][item["target_span"][0]:item["target_span"][1]]
               for item in pack["examples"])
    assert any(len(item["accepted_answers"]) > 1 for item in pack["examples"])
    assert validate_pilot_examples(pack, pilot, sources, publication=True)


def test_invalid_span_and_nfc_offsets_are_rejected() -> None:
    pack, pilot, sources = _files()
    pack["examples"][0]["target_span"] = [0, 999]
    assert validate_pilot_examples(pack, pilot, sources)
    pack, pilot, sources = _files()
    pack["examples"][0]["text"] = "e\u0301 " + pack["examples"][0]["text"]
    assert validate_pilot_examples(pack, pilot, sources)


def test_missing_review_or_rights_blocks_publication() -> None:
    pack, pilot, sources = _files()
    pack["examples"][0]["review"]["status"] = "internally_checked"
    assert validate_pilot_examples(pack, pilot, sources, publication=True)
    sources = deepcopy(sources)
    sources["sources"][0]["rights"]["text"]["status"] = "approved"
    assert validate_pilot_examples(pack, pilot, sources, publication=True)


def test_duplicate_or_transliterated_holdout_leakage_is_rejected() -> None:
    pack, pilot, sources = _files()
    practice = next(item for item in pack["examples"] if item["role"] == "practice")
    holdout = next(item for item in pack["examples"] if item["role"] == "assessment")
    holdout["text"] = practice["text"]
    holdout["target_span"] = practice["target_span"]
    assert validate_pilot_examples(pack, pilot, sources)
    pack, pilot, sources = _files()
    holdout = next(item for item in pack["examples"] if item["role"] == "assessment")
    holdout["text"] = "Ja sam Ana."
    holdout["target_span"] = [0, 6]
    assert validate_pilot_examples(pack, pilot, sources)


def test_unequal_legacy_bilingual_lines_remain_one_raw_payload() -> None:
    from app.models import VocabularyItem
    from app.services.domain_bootstrap_service import _examples

    word = VocabularyItem(serbian_cyrillic="кућа", serbian_latin="kuća",
                          russian_translation="дом", cefr_level="A1", theme="home",
                          example_sentences="Ово је кућа.\nКућа је велика.",
                          example_translations="Это дом.")
    example, = _examples(word)
    assert example.serbian_text == "Ово је кућа.\nКућа је велика."
    assert example.translation == "Это дом."
