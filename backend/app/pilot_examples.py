"""Validation of unpublished written-pilot examples and answer candidates."""

from __future__ import annotations

import unicodedata
from typing import Any

from app.content_provenance import validate_source_manifest


_CYR_TO_LAT = str.maketrans({
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "ђ": "đ", "е": "e",
    "ж": "ž", "з": "z", "и": "i", "ј": "j", "к": "k", "л": "l", "љ": "lj",
    "м": "m", "н": "n", "њ": "nj", "о": "o", "п": "p", "р": "r", "с": "s",
    "т": "t", "ћ": "ć", "у": "u", "ф": "f", "х": "h", "ц": "c", "ч": "č",
    "џ": "dž", "ш": "š",
})


def _comparison_text(value: str) -> str:
    return " ".join(value.casefold().translate(_CYR_TO_LAT).split()).strip(" .!?…")


def validate_pilot_examples(
    pack: dict[str, Any], pilot: dict[str, Any], sources: dict[str, Any],
    *, publication: bool = False,
) -> list[str]:
    """Check file references, exact spans and practice/assessment separation."""
    if pack.get("schema_version") not in {1, 2} or not isinstance(pack.get("examples"), list):
        return ["unsupported example pack"]
    if pack["schema_version"] == 2:
        from app.reviewed_example_bank import validate_bank_shape
        shape_errors = validate_bank_shape(pack)
        if shape_errors:
            return shape_errors
    outcomes = {item["id"]: item for item in pilot.get("outcomes", [])}
    source_ids = {item.get("id") for item in sources.get("sources", [])}
    errors: list[str] = []
    seen_ids: set[str] = set()
    practice_texts: set[str] = set()
    assessment_texts: set[str] = set()
    for item in pack["examples"]:
        item_id = item.get("id")
        if not item_id or item_id in seen_ids:
            errors.append(f"{item_id}: missing or duplicate example ID")
        seen_ids.add(item_id)
        outcome = outcomes.get(item.get("outcome_id"))
        if outcome is None:
            errors.append(f"{item_id}: unknown outcome")
            continue
        role = item.get("role")
        family = item.get("context_family")
        valid_families = (outcome["practice_families"] if role == "practice"
                          else [outcome["assessment_family"]] if role == "assessment" else [])
        if family not in valid_families:
            errors.append(f"{item_id}: invalid context family/role")
        if item.get("target_ref") != outcome["primary_target"]["id"]:
            errors.append(f"{item_id}: target reference mismatch")
        if item.get("source_id") not in source_ids:
            errors.append(f"{item_id}: source missing")
        text = item.get("text")
        translation = item.get("translation")
        if not isinstance(text, str) or not text.strip() or unicodedata.normalize("NFC", text) != text:
            errors.append(f"{item_id}: text missing or non-NFC")
            continue
        if not isinstance(translation, str) or not translation.strip() or unicodedata.normalize("NFC", translation) != translation:
            errors.append(f"{item_id}: translation missing or non-NFC")
        span = item.get("target_span")
        if (not isinstance(span, list) or len(span) != 2
                or any(type(index) is not int for index in span)
                or not 0 <= span[0] < span[1] <= len(text)
                or not text[span[0]:span[1]].strip()):
            errors.append(f"{item_id}: invalid NFC target span")
        answers = item.get("accepted_answers")
        if (not isinstance(answers, list) or not answers
                or any(not isinstance(answer, str) or not answer.strip()
                       or unicodedata.normalize("NFC", answer) != answer for answer in answers)
                or len({_comparison_text(answer) for answer in answers}) != len(answers)):
            errors.append(f"{item_id}: invalid answer candidates")
        if item.get("script") not in {"latin", "cyrillic"}:
            errors.append(f"{item_id}: invalid script")
        review = item.get("review", {})
        if publication and (review.get("status") != "internally_checked"
                            or not review.get("reviewer") or not review.get("date")
                            or not review.get("source_locators")):
            errors.append(f"{item_id}: internal language review missing")
        comparison = _comparison_text(text)
        if role == "practice":
            practice_texts.add(comparison)
        elif role == "assessment":
            assessment_texts.add(comparison)
    if practice_texts & assessment_texts:
        errors.append("assessment duplicates or transliterates practice text")
    if publication:
        used_sources = {item.get("source_id") for item in pack["examples"]}
        for source in sources.get("sources", []):
            if source.get("id") in used_sources:
                errors.extend(validate_source_manifest(
                    {"schema_version": 1, "sources": [source]},
                    use="pilot_display", media=("text", "translation"),
                ))
    if pack["schema_version"] == 2:
        from app.reviewed_example_bank import validate_bank_details
        errors.extend(validate_bank_details(pack, sources, publication=publication))
    return errors
