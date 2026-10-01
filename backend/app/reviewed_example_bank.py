"""Extra gates and review export for version-2 file-backed example revisions."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import unicodedata
from typing import Any


_CONTENT_FIELDS = (
    "original_text", "text", "translation", "script", "target_ref", "target_span",
    "accepted_answers", "task", "answer_policy", "provenance", "register", "privacy",
    "source_id", "source_item_key", "context_family", "duplicate_cluster", "outcome_id", "role",
)
_REVIEW_FIELDS = (
    "naturalness", "target_alignment", "answerability", "variants", "translation",
)
_ALPHABETS = {
    "latin": set("abcčćdđefghijklmnoprsštuvzž"),
    "cyrillic": set("абвгдђежзијклљмнњопрстћуфхцчџш"),
}


def _digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()


def example_revision_hash(item: dict[str, Any]) -> str:
    return _digest({key: item.get(key) for key in _CONTENT_FIELDS})


def bank_digest(pack: dict[str, Any]) -> str:
    return _digest({key: value for key, value in pack.items() if key != "publication_decision"})


def rights_digest(sources: dict[str, Any]) -> str:
    return _digest(sources)


def validate_bank_shape(pack: dict[str, Any]) -> list[str]:
    errors = []
    if not isinstance(pack.get("examples"), list):
        return ["example bank must contain a list of examples"]
    decision = pack.get("publication_decision")
    if not isinstance(decision, dict):
        errors.append("owner publication decision must be an object")
    elif decision.get("status") == "approved" and any(
        not isinstance(decision.get(field), str) or not decision[field].strip()
        for field in ("owner", "date", "content_digest", "rights_digest")
    ):
        errors.append("approved owner decision must contain textual identity/date/digests")
    identities: set[tuple[str, str]] = set()
    for item in pack["examples"]:
        if not isinstance(item, dict):
            errors.append("example must be an object")
            continue
        for field in (
            "id", "source_id", "source_item_key", "outcome_id", "target_ref",
            "role", "context_family", "script", "register", "privacy", "duplicate_cluster",
        ):
            if not isinstance(item.get(field), str) or not item[field]:
                errors.append(f"{item.get('id')}: {field} must be one nonempty reference")
        for field in ("review", "task", "provenance", "answer_policy"):
            if not isinstance(item.get(field), dict):
                errors.append(f"{item.get('id')}: {field} must be an object")
        if type(item.get("revision")) is not int or item["revision"] < 1:
            errors.append(f"{item.get('id')}: revision identity must be a positive integer")
        if all(isinstance(item.get(field), str) for field in ("source_id", "source_item_key")):
            identity = (item["source_id"], item["source_item_key"])
            if identity in identities:
                errors.append(f"{item.get('id')}: conflicting stable source identity")
            identities.add(identity)
        for parent, fields in (
            ("task", ("input", "instruction_ru", "format", "response_mode")),
            ("review", (*_REVIEW_FIELDS, "reviewer", "date", "status")),
            ("provenance", ("text", "translation")),
        ):
            value = item.get(parent)
            if isinstance(value, dict):
                for field in fields:
                    if not isinstance(value.get(field), str) or not value[field].strip():
                        errors.append(f"{item.get('id')}: {parent}.{field} must be nonempty text")
        review = item.get("review")
        if isinstance(review, dict):
            locators = review.get("source_locators")
            if not isinstance(locators, list) or not locators or any(
                not isinstance(locator, str) or not locator.strip() for locator in locators
            ):
                errors.append(f"{item.get('id')}: review source locators must be nonempty text references")
    return errors


def validate_bank_details(
    pack: dict[str, Any], sources: dict[str, Any], *, publication: bool,
) -> list[str]:
    from app.pilot_examples import _comparison_text

    errors: list[str] = []
    clusters: dict[str, set[str]] = {}
    identities: set[tuple[str, str, int]] = set()
    for item in pack["examples"]:
        label = item.get("id")
        revision = item.get("revision")
        if type(revision) is not int or revision < 1 or not item.get("source_item_key"):
            errors.append(f"{label}: source item/revision identity missing")
        else:
            identity = (item.get("source_id"), item["source_item_key"], revision)
            if identity in identities:
                errors.append(f"{label}: duplicate source revision identity")
            identities.add(identity)
        if item.get("content_hash") != example_revision_hash(item):
            errors.append(f"{label}: content hash mismatch")
        if not isinstance(item.get("original_text"), str) or not item["original_text"].strip():
            errors.append(f"{label}: original text missing")
        elif (unicodedata.normalize("NFC", item["original_text"]) != item["original_text"]
              or not isinstance(item.get("text"), str)
              or _comparison_text(item["original_text"]) != _comparison_text(item["text"])):
            errors.append(f"{label}: display is not the NFC original or its equivalent script")
        display_text = item.get("text")
        if isinstance(display_text, str) and item.get("script") in _ALPHABETS:
            letters = {letter for letter in display_text.replace("RSD", "").casefold() if letter.isalpha()}
            if not letters <= _ALPHABETS[item["script"]]:
                errors.append(f"{label}: display letters do not match the declared script")
        if item.get("privacy") != "fictional":
            errors.append(f"{label}: only fictional data admitted to the pilot")
        task = item.get("task", {})
        if not isinstance(task, dict):
            errors.append(f"{label}: task missing")
            task = {}
        if not task.get("input") or not task.get("instruction_ru"):
            errors.append(f"{label}: task input/instruction missing")
        if task.get("format") not in {"form", "price_notice", "sentence"}:
            errors.append(f"{label}: unsupported task or unresolved fragment")
        if task.get("format") == "sentence":
            text = item.get("text", "")
            if not isinstance(text, str) or len(text.split()) < 2 or not text.endswith((".", "!", "?")):
                errors.append(f"{label}: unresolved sentence fragment")
        displayed = " ".join(str(value) for value in (
            item.get("text"), item.get("translation"), task.get("input"), task.get("instruction_ru")
        ))
        if re.search(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}|\d{7,}", displayed):
            errors.append(f"{label}: possible private contact data")
        if item.get("register") not in {"neutral", "polite_neutral"}:
            errors.append(f"{label}: register missing or unresolved")
        provenance = item.get("provenance", {})
        if not isinstance(provenance, dict) or not all(
            provenance.get(medium) for medium in ("text", "translation")
        ):
            errors.append(f"{label}: text/translation provenance missing")
        for field in ("translation_status", "answer_policy_status"):
            if item.get(field) != "internally_checked":
                errors.append(f"{label}: {field} is not internally checked")
        review = item.get("review", {})
        if (review.get("status") != "internally_checked"
                or not all(review.get(field) for field in (*_REVIEW_FIELDS, "reviewer", "date", "source_locators"))
                or not isinstance(review.get("disagreements"), list)):
            errors.append(f"{label}: separate language/translation/answer review missing")
        policy = item.get("answer_policy", {})
        if not isinstance(policy, dict):
            policy = {}
        if not policy.get("id") or type(policy.get("revision")) is not int or policy.get("revision", 0) < 1:
            errors.append(f"{label}: answer-policy revision missing")
        if policy.get("unlisted") != "unresolved":
            errors.append(f"{label}: unlisted plausible answers must remain unresolved")
        if policy.get("normalization") != ["NFC", "trim"]:
            errors.append(f"{label}: unsupported answer normalization")
        answers = item.get("accepted_answers", [])
        answers = answers if isinstance(answers, list) else []
        comparisons = {_comparison_text(answer) for answer in answers if isinstance(answer, str)}
        equivalents = policy.get("equivalent_script_answers", [])
        if not isinstance(equivalents, list) or any(
            not isinstance(answer, str) or _comparison_text(answer) not in comparisons
            for answer in equivalents
        ):
            errors.append(f"{label}: equivalent-script answer does not match a reviewed answer")
        if task.get("format") == "form":
            fields = policy.get("fields")
            if not isinstance(fields, dict) or not fields:
                errors.append(f"{label}: form field keys missing")
            else:
                for name, aliases in fields.items():
                    if (not isinstance(aliases, list) or not aliases
                            or any(not isinstance(alias, str) or not alias.strip() for alias in aliases)
                            or len({_comparison_text(alias) for alias in aliases if isinstance(alias, str)}) != 1):
                        errors.append(f"{label}: field {name} aliases are not equivalent spellings")
                for answer in answers:
                    if not isinstance(answer, str):
                        continue
                    entries = [line.split(":", 1) for line in answer.splitlines()]
                    if (any(len(entry) != 2 for entry in entries)
                            or len(entries) != len(fields)):
                        errors.append(f"{label}: canonical form answer has missing/duplicate fields")
                        continue
                    values = {_comparison_text(name): value.strip() for name, value in entries}
                    if set(values) != set(fields) or any(
                        value not in fields.get(name, []) for name, value in values.items()
                    ):
                        errors.append(f"{label}: canonical answer contradicts field keys")
        if task.get("format") == "price_notice":
            numeral = policy.get("expected_numeral")
            span = item.get("target_span", [])
            if (not isinstance(numeral, str) or not numeral.isascii() or not numeral.isdigit()
                    or answers != [numeral] or not isinstance(span, list) or len(span) != 2
                    or any(type(index) is not int for index in span)
                    or not isinstance(display_text, str)
                    or display_text[span[0]:span[1]] != numeral):
                errors.append(f"{label}: price numeral key contradicts the target span")
        cluster = item.get("duplicate_cluster")
        if not isinstance(cluster, str) or not cluster:
            errors.append(f"{label}: duplicate cluster missing")
        else:
            clusters.setdefault(cluster, set()).add(item.get("role"))
    if any(roles == {"practice", "assessment"} for roles in clusters.values()):
        errors.append("assessment shares a duplicate cluster with practice")
    for source in sources.get("sources", []):
        if (source.get("checksum_scope") == "bank_digest excluding publication_decision"
                and source.get("checksum") != bank_digest(pack)):
            errors.append(f"{source.get('id')}: bank source checksum is stale")
    if publication:
        decision = pack.get("publication_decision", {})
        if (decision.get("status") != "approved"
                or not decision.get("owner") or not decision.get("date")):
            errors.append("project owner inclusion decision missing")
        if decision.get("content_digest") != bank_digest(pack):
            errors.append("owner decision content digest mismatch")
        if decision.get("rights_digest") != rights_digest(sources):
            errors.append("owner decision rights digest mismatch")
    return errors


def validate_reimport(pack: dict[str, Any], previous: dict[str, Any]) -> list[str]:
    """Compare with a retained prior export; never silently reassign source IDs."""
    if pack.get("schema_version") != 2 or previous.get("schema_version") != 2:
        return ["re-import requires version-2 review exports; drafts cannot auto-promote"]
    shape_errors = validate_bank_shape(pack) + validate_bank_shape(previous)
    if shape_errors:
        return shape_errors
    old = {(item["source_id"], item["source_item_key"]): item for item in previous["examples"]}
    old_by_id = {item["id"]: item for item in previous["examples"]}
    errors: list[str] = []
    for item in pack["examples"]:
        same_id = old_by_id.get(item["id"])
        if same_id is not None and (
            item["source_id"], item["source_item_key"]
        ) != (same_id["source_id"], same_id["source_item_key"]):
            errors.append(f"{item['id']}: re-import reassigned source identity")
        existing = old.get((item["source_id"], item["source_item_key"]))
        if existing is None:
            continue
        if item["id"] != existing["id"]:
            errors.append(f"{item['id']}: re-import changed source identity")
        if item["revision"] < existing["revision"]:
            errors.append(f"{item['id']}: re-import regressed revision")
        elif item["revision"] == existing["revision"] and (
            example_revision_hash(item) != example_revision_hash(existing)
        ):
            errors.append(f"{item['id']}: immutable revision changed")
    return errors


def review_markdown(pack: dict[str, Any]) -> str:
    lines = ["# Письменный пилот: пакет для решения владельца", "",
             f"Статус включения: `{pack.get('publication_decision', {}).get('status')}`.", "",
             "Это внутренняя модельная проверка по источникам, не независимая языковая экспертиза.",
             "Пакет не загружается в приложение. Неперечисленный ответ: `unresolved`.", ""]
    for item in sorted(pack["examples"], key=lambda entry: entry["id"]):
        task, review, policy = item["task"], item["review"], item["answer_policy"]
        lines.extend([
            f"## {item['id']} · revision {item['revision']}", "",
            f"{item['outcome_id']} · {item['role']} · `{item['context_family']}`", "",
            "### Контекст и задание", "", task["input"], "", task["instruction_ru"], "",
            "### Текст / образец ответа", "", "```text", item["text"], "```", "",
            "Русский смысл: " + item["translation"], "",
            "Допустимые ответы: " + json.dumps(item["accepted_answers"], ensure_ascii=False), "",
            "Политика ответа: " + json.dumps(policy, ensure_ascii=False, sort_keys=True), "",
            "### Внутренние решения", "",
        ])
        for field in _REVIEW_FIELDS:
            lines.append(f"- **{field}:** {review[field]}")
        lines.extend(["- **Источники:** " + "; ".join(review["source_locators"]),
                      "- **Разногласия/исключения:** " + json.dumps(review["disagreements"], ensure_ascii=False),
                      "", f"Content hash: `{item.get('content_hash')}`.", ""])
    return "\n".join(lines)


def main() -> int:
    from app.pilot_examples import validate_pilot_examples

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bank", type=Path)
    parser.add_argument("--pilot", required=True, type=Path)
    parser.add_argument("--sources", required=True, type=Path)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--publication", action="store_true")
    parser.add_argument("--review-export", type=Path)
    args = parser.parse_args()
    pack, pilot, sources = (
        json.loads(path.read_text(encoding="utf-8"))
        for path in (args.bank, args.pilot, args.sources)
    )
    errors = (
        validate_pilot_examples(pack, pilot, sources, publication=args.publication)
        if pack.get("schema_version") == 2 else ["review export requires a version-2 bank"]
    )
    if not errors and args.previous:
        errors.extend(validate_reimport(pack, json.loads(args.previous.read_text(encoding="utf-8"))))
    print(json.dumps({"examples": len(pack.get("examples", [])), "rejected": errors},
                     ensure_ascii=False, indent=2))
    if not errors and args.review_export:
        args.review_export.write_text(review_markdown(pack), encoding="utf-8")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
