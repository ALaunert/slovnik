from collections import Counter
import json
from pathlib import Path

import pytest

from app.reviewed_example_bank import bank_digest
from app.domain.shared import Capability
from app.services.answer_policy import AnswerVerdict, ReviewedAnswerPolicy


BANK = json.loads(
    (Path(__file__).parents[2] / "content/examples/a1-written-v1.json").read_text()
)
EXAMPLES = {item["id"].removeprefix("a1-written-"): item for item in BANK["examples"]}


def policy(name: str) -> ReviewedAnswerPolicy:
    return ReviewedAnswerPolicy.from_reviewed_example(
        EXAMPLES[name], capability=Capability.APPLY_CONSTRUCTION
    )


@pytest.mark.parametrize("name", sorted(EXAMPLES))
def test_all_owner_approved_exact_answers_are_correct(name):
    candidate = policy(name)
    for answer in EXAMPLES[name]["accepted_answers"]:
        result = candidate.evaluate(answer)
        assert result.verdict is AnswerVerdict.CORRECT
        assert result.source == "deterministic"
        assert result.policy_id == EXAMPLES[name]["answer_policy"]["id"]


def test_normalization_is_nfc_and_outer_trim_only():
    candidate = policy("location-library")
    assert candidate.evaluate("  Састанак је у школи.  ").verdict is AnswerVerdict.CORRECT
    assert candidate.evaluate("Sastanak je u s\u030ckoli.").verdict is AnswerVerdict.CORRECT
    assert candidate.evaluate("састанак је у школи.").verdict is AnswerVerdict.UNRESOLVED
    assert candidate.evaluate("Састанак  је у школи.").verdict is AnswerVerdict.UNRESOLVED
    assert candidate.evaluate("Sastanak je u skoli.").verdict is AnswerVerdict.UNRESOLVED


def test_explicit_cross_script_alias_only():
    assert policy("request-counter").evaluate("Molim vodu.").verdict is AnswerVerdict.CORRECT
    assert policy("request-counter").evaluate("Molim čaj.").verdict is AnswerVerdict.UNRESOLVED
    assert policy("location-office").evaluate("Састанак је у хотелу.").verdict is AnswerVerdict.CORRECT


def test_price_known_wrong_number_is_incorrect_but_rephrasing_is_unresolved():
    candidate = policy("price-shop")
    assert candidate.evaluate("150").verdict is AnswerVerdict.INCORRECT
    assert candidate.evaluate("150").error_category == "wrong_numeral"
    assert candidate.evaluate("шездесет").verdict is AnswerVerdict.UNRESOLVED
    assert candidate.evaluate("60 RSD").verdict is AnswerVerdict.UNRESOLVED
    assert candidate.evaluate("060").verdict is AnswerVerdict.UNRESOLVED


def test_form_fields_can_reorder_or_use_reviewed_script_aliases():
    candidate = policy("personal-profile")
    answer = "Grad: Niš\nPrezime: Pavlović\nIme: Nina"
    assert candidate.evaluate(answer).verdict is AnswerVerdict.CORRECT
    missing = candidate.evaluate("Име: Нина\nПрезиме: Павловић")
    assert missing.verdict is AnswerVerdict.INCORRECT
    assert missing.error_category == "missing_field"
    empty_value = candidate.evaluate("Име: Нина\nПрезиме: Павловић\nГрад: ")
    assert empty_value.verdict is AnswerVerdict.INCORRECT
    assert empty_value.error_category == "missing_field"
    assert candidate.evaluate("Ime: Nina\nPrezime: Pavlovic\nGrad: Niš").verdict is AnswerVerdict.UNRESOLVED


def test_ambiguous_and_malformed_candidates_do_not_gain_credit():
    candidate = policy("request-counter")
    assert candidate.evaluate("Желим воду.").verdict is AnswerVerdict.UNRESOLVED
    assert candidate.evaluate("Воду молим.").verdict is AnswerVerdict.UNRESOLVED
    assert candidate.evaluate("Молим вода.").verdict is AnswerVerdict.UNRESOLVED
    assert candidate.evaluate("Молим чај.").verdict is AnswerVerdict.UNRESOLVED
    assert policy("location-library").evaluate("У школи.").verdict is AnswerVerdict.UNRESOLVED
    assert policy("location-library").evaluate("Састанак је у хотелу.").verdict is AnswerVerdict.UNRESOLVED
    assert candidate.evaluate("  ").verdict is AnswerVerdict.INCORRECT
    assert policy("personal-profile").evaluate(
        "Ime: Nina\nIme: Nina\nGrad: Niš\nPrezime: Pavlović"
    ).verdict is AnswerVerdict.UNRESOLVED


def test_stale_or_invalid_reviewed_example_is_rejected():
    example = dict(EXAMPLES["request-counter"])
    example["target_span"] = [100, 110]
    with pytest.raises(ValueError, match="hash|span"):
        ReviewedAnswerPolicy.from_reviewed_example(
            example, capability=Capability.APPLY_CONSTRUCTION
        )
    example = dict(EXAMPLES["request-counter"])
    example["answer_policy"] = {**example["answer_policy"], "normalization": ["casefold"]}
    with pytest.raises(ValueError, match="normalization"):
        ReviewedAnswerPolicy.from_reviewed_example(
            example, capability=Capability.APPLY_CONSTRUCTION
        )


def test_frozen_internal_answer_cases_and_class_counts():
    fixture = json.loads(
        (Path(__file__).parent / "fixtures/learning/p1_05a_answer_cases.json").read_text()
    )
    assert fixture["bank_digest"] == bank_digest(BANK)
    assert fixture["review_kind"] == "internal_source_and_task_check"
    assert fixture["human_gold"] is False
    rows = fixture["cases"]
    assert len(rows) == 20
    assert len({row["id"] for row in rows}) == len(rows)
    by_id = {item["id"]: item for item in BANK["examples"]}
    counts = Counter()
    per_class = Counter()
    for row in rows:
        item = by_id[row["example_id"]]
        scorer = ReviewedAnswerPolicy.from_reviewed_example(
            item, capability=Capability.APPLY_CONSTRUCTION
        )
        verdict = scorer.evaluate(row["answer"]).verdict.value
        assert verdict == row["expected_verdict"], row["id"]
        counts[(row["reference_label"], verdict)] += 1
        per_class[(row["class"], row["reference_label"], verdict)] += 1
    assert counts == {
        ("correct", "correct"): 12,
        ("incorrect", "incorrect"): 2,
        ("incorrect", "unresolved"): 2,
        (None, "unresolved"): 4,
    }
    assert per_class[("wrong_referent", "incorrect", "unresolved")] == 2
    assert per_class[("inflection", None, "unresolved")] == 1
