import json
from pathlib import Path

from app.models import QuizAnswer
from app.services.quiz_service import _result_breakdown


FIXTURE = Path(__file__).parent / "fixtures/learning/p0_01_histories.json"


def _answer(word_id: int, question_type: str, correct: bool) -> QuizAnswer:
    return QuizAnswer(word_id=word_id, question_type=question_type, prompt="prompt",
                      answer="answer", is_correct=correct)


def test_first_attempt_retry_and_self_report_are_separate() -> None:
    histories = json.loads(FIXTURE.read_text(encoding="utf-8"))["histories"]
    assert histories[0]["expected"]["first_unaided"] == [0, 1]
    assert histories[0]["expected"]["retry"] == [1, 1]
    plan = [
        {"word_id": 1, "question_type": "sr_to_ru_choice", "plan_version": 2,
         "answer_key": {"correct": "yes"}},
        {"word_id": 2, "question_type": "ru_to_sr_typing", "plan_version": 2,
         "answer_key": {"latin": "da", "cyrillic": "да"}},
        {"word_id": 3, "question_type": "remembered_forgot_self_check", "plan_version": 2,
         "answer_key": {"correct": "remembered", "reveal": "yes"}},
    ]
    answers = [
        _answer(1, "sr_to_ru_choice", False), _answer(1, "sr_to_ru_choice", True),
        _answer(2, "ru_to_sr_typing", False), _answer(2, "ru_to_sr_typing", False),
        _answer(3, "remembered_forgot_self_check", True),
    ]
    assert _result_breakdown(plan, answers) == {
        "breakdown_status": "available", "first_attempt_correct": 0,
        "first_attempt_eligible": 2, "recovered_objective_items": 1,
        "self_report_remembered": 1, "self_report_total": 1,
    }


def test_legacy_breakdown_is_unavailable_and_empty_is_not_measured() -> None:
    legacy = [{"word_id": 1, "question_type": "sr_to_ru_choice"}]
    assert _result_breakdown(legacy, [_answer(1, "sr_to_ru_choice", True)])["breakdown_status"] == "unavailable"
    assert _result_breakdown([], []) == {
        "breakdown_status": "available", "first_attempt_correct": 0,
        "first_attempt_eligible": 0, "recovered_objective_items": 0,
        "self_report_remembered": 0, "self_report_total": 0,
    }


def test_self_check_only_has_zero_objective_denominator() -> None:
    plan = [{"word_id": 1, "question_type": "remembered_forgot_self_check",
             "plan_version": 2, "answer_key": {"correct": "remembered", "reveal": "yes"}}]
    result = _result_breakdown(plan, [_answer(1, "remembered_forgot_self_check", True)])
    assert result["first_attempt_eligible"] == 0
    assert result["self_report_remembered"] == 1
