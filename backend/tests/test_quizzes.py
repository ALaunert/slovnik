from datetime import datetime, timedelta, timezone
import json

import pytest
from sqlalchemy import select

from app.models import QuizAttempt, UserWordProgress, VocabularyItem


@pytest.fixture(autouse=True)
def prepare_catalog_for_shadow_quiz_flows(client, db_session, monkeypatch):
    from app.config import settings
    from app.services.domain_bootstrap_service import bootstrap_catalog

    original_post = client.post

    def post(url, *args, **kwargs):
        url_text = str(url)
        shadow_enabled = settings.language_assistant_shadow_enabled
        if shadow_enabled and url_text.endswith("/new-words/complete"):
            settings.language_assistant_shadow_enabled = False
            try:
                return original_post(url, *args, **kwargs)
            finally:
                settings.language_assistant_shadow_enabled = True
        if shadow_enabled and url_text.endswith("/start"):
            bootstrap_catalog(db_session)
        return original_post(url, *args, **kwargs)

    monkeypatch.setattr(client, "post", post)


def test_start_daily_quiz_returns_supported_question_types(client, completed_learning):
    response = client.post("/api/quizzes/learner-1/start", json={"quiz_type": "daily"})

    assert response.status_code == 200
    question_types = {question["question_type"] for question in response.json()["questions"]}
    assert "sr_to_ru_choice" in question_types
    assert "ru_to_sr_typing" in question_types
    assert "remembered_forgot_self_check" in question_types


def test_new_quiz_keys_are_private_and_survive_vocabulary_edit(client, db_session, started_quiz):
    attempt_id = started_quiz["attempt_id"]
    attempt = db_session.get(QuizAttempt, attempt_id)
    plan = json.loads(attempt.question_plan)
    assert all(item["plan_version"] == 2 and item["answer_key"] for item in plan)
    assert all("answer_key" not in item and "answer" not in item for item in started_quiz["questions"])
    from app.services.quiz_service import start_quiz

    service_result = start_quiz(db_session, "learner-1", "daily")
    assert all("answer_key" not in item and "answer" not in item
               for item in service_result["questions"])
    typing = next(item for item in plan if item["question_type"] == "ru_to_sr_typing")
    self_check = next(item for item in plan if item["question_type"] == "remembered_forgot_self_check")
    original_latin = typing["answer_key"]["latin"]
    original_cyrillic = typing["answer_key"]["cyrillic"]
    original_reveal = self_check["answer_key"]["reveal"]
    word = db_session.get(VocabularyItem, typing["word_id"])
    word.serbian_latin = "izmenjeno"
    word.serbian_cyrillic = "измењено"
    db_session.get(VocabularyItem, self_check["word_id"]).russian_translation = "новый перевод"
    db_session.commit()
    reveal = client.get(
        f"/api/quizzes/learner-1/{attempt_id}/questions/{self_check['word_id']}/remembered_forgot_self_check/answer"
    )
    assert reveal.json() == {"answer": original_reveal}
    response = client.post(f"/api/quizzes/learner-1/{attempt_id}/answers", json={
        "word_id": typing["word_id"], "question_type": "ru_to_sr_typing", "answer": original_latin,
    })
    assert response.json()["is_correct"] is True
    response = client.post(f"/api/quizzes/learner-1/{service_result['attempt_id']}/answers", json={
        "word_id": typing["word_id"], "question_type": "ru_to_sr_typing", "answer": original_cyrillic,
    })
    assert response.json()["is_correct"] is True
    assert original_cyrillic != "измењено"


def test_frozen_choice_and_correction_use_issued_key(client, db_session, started_quiz):
    attempt_id = started_quiz["attempt_id"]
    plan = json.loads(db_session.get(QuizAttempt, attempt_id).question_plan)
    choice = next(item for item in plan if item["question_type"] == "sr_to_ru_choice")
    original = choice["answer_key"]["correct"]
    second = client.post("/api/quizzes/learner-1/start", json={"quiz_type": "daily"}).json()
    db_session.get(VocabularyItem, choice["word_id"]).russian_translation = "новое значение"
    db_session.commit()
    frozen_correct = client.post(f"/api/quizzes/learner-1/{second['attempt_id']}/answers", json={
        "word_id": choice["word_id"], "question_type": "sr_to_ru_choice", "answer": original,
    })
    assert frozen_correct.json()["is_correct"] is True
    answer_url = f"/api/quizzes/learner-1/{attempt_id}/answers"
    assert client.post(answer_url, json={"word_id": choice["word_id"],
        "question_type": "sr_to_ru_choice", "answer": "wrong"}).json()["is_correct"] is False
    for question in plan:
        if question is choice:
            continue
        key = question["answer_key"]
        answer = (key["latin"] if question["question_type"] == "ru_to_sr_typing"
                  else "remembered" if question["question_type"] == "remembered_forgot_self_check"
                  else key["correct"])
        submitted = client.post(answer_url, json={"word_id": question["word_id"],
            "question_type": question["question_type"], "answer": answer})
        assert submitted.status_code == 200 and submitted.json()["is_correct"] is True, (question, submitted.json())
    assert client.post(answer_url, json={"word_id": choice["word_id"],
        "question_type": "sr_to_ru_choice", "answer": "wrong"}).status_code == 200
    result = client.post(f"/api/quizzes/learner-1/{attempt_id}/complete").json()
    assert result.get("answer_key_status") == "frozen", result
    assert all(item["correct_answer"] == original for item in result["mistakes"])


def test_old_plan_remains_legacy_and_unknown_version_is_rejected(client, db_session, started_quiz):
    attempt = db_session.get(QuizAttempt, started_quiz["attempt_id"])
    plan = json.loads(attempt.question_plan)
    question = plan[0]
    question["plan_version"] = 999
    attempt.question_plan = json.dumps(plan)
    db_session.commit()
    payload = {"word_id": question["word_id"], "question_type": question["question_type"], "answer": "wrong"}
    assert client.post(f"/api/quizzes/learner-1/{attempt.id}/answers", json=payload).status_code == 400
    question.pop("plan_version")
    question.pop("answer_key")
    attempt.question_plan = json.dumps(plan)
    db_session.commit()
    word = db_session.get(VocabularyItem, question["word_id"])
    word.russian_translation = "новое значение"
    db_session.commit()
    response = client.post(f"/api/quizzes/learner-1/{attempt.id}/answers", json={**payload, "answer": word.russian_translation})
    assert response.status_code == 200
    assert response.json()["is_correct"] is True


def test_old_active_plan_completes_with_unavailable_breakdown(client, db_session, started_quiz):
    attempt = db_session.get(QuizAttempt, started_quiz["attempt_id"])
    plan = json.loads(attempt.question_plan)
    for question in plan:
        key = question.pop("answer_key")
        question.pop("plan_version")
        if question["question_type"] == "remembered_forgot_self_check":
            question["answer"] = key["reveal"]
    attempt.question_plan = json.dumps(plan)
    db_session.commit()
    for question in plan:
        word = db_session.get(VocabularyItem, question["word_id"])
        answer = (word.serbian_latin if question["question_type"] == "ru_to_sr_typing"
                  else "remembered" if question["question_type"] == "remembered_forgot_self_check"
                  else word.russian_translation)
        submitted = client.post(f"/api/quizzes/learner-1/{attempt.id}/answers", json={
            "word_id": question["word_id"], "question_type": question["question_type"],
            "answer": answer,
        })
        assert submitted.status_code == 200 and submitted.json()["is_correct"] is True
    result = client.post(f"/api/quizzes/learner-1/{attempt.id}/complete").json()
    assert result["score"] == len(plan)
    assert result["answer_key_status"] == "legacy"
    assert result["breakdown_status"] == "unavailable"
    assert result["first_attempt_correct"] is None


def test_empty_quiz_has_not_measured_breakdown(client):
    started = client.post("/api/quizzes/empty-learner/start", json={"quiz_type": "daily"}).json()
    assert started["questions"] == []
    result = client.post(f"/api/quizzes/empty-learner/{started['attempt_id']}/complete").json()
    assert result["score"] == 0 and result["total_questions"] == 0
    assert result["first_attempt_eligible"] == 0


def test_submit_incorrect_answer_marks_word_weak(client, started_quiz):
    question = started_quiz["questions"][0]
    response = client.post(
        f"/api/quizzes/learner-1/{started_quiz['attempt_id']}/answers",
        json={"word_id": question["word_id"], "question_type": question["question_type"], "answer": "wrong"},
    )

    assert response.status_code == 200
    assert response.json()["is_correct"] is False
    assert response.json()["repeat_word"] is True


def test_incorrect_quiz_answer_clears_future_review_schedule(
    client, db_session, started_quiz
):
    question = started_quiz["questions"][0]
    progress = db_session.scalar(
        select(UserWordProgress).where(
            UserWordProgress.user_id == "learner-1",
            UserWordProgress.word_id == question["word_id"],
        )
    )
    progress.next_review_at = (
        datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=5)
    )
    db_session.commit()

    response = client.post(
        f"/api/quizzes/learner-1/{started_quiz['attempt_id']}/answers",
        json={
            "word_id": question["word_id"],
            "question_type": question["question_type"],
            "answer": "wrong",
        },
    )

    assert response.status_code == 200
    db_session.refresh(progress)
    assert progress.next_review_at is None


def test_correct_quiz_answer_preserves_future_review_schedule(
    client, db_session, started_quiz
):
    question = started_quiz["questions"][0]
    progress = db_session.scalar(
        select(UserWordProgress).where(
            UserWordProgress.user_id == "learner-1",
            UserWordProgress.word_id == question["word_id"],
        )
    )
    future_review = (
        datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=5)
    )
    progress.next_review_at = future_review
    db_session.commit()
    word = db_session.get(VocabularyItem, question["word_id"])
    answer = {
        "sr_to_ru_choice": word.russian_translation,
        "ru_to_sr_typing": word.serbian_latin,
        "remembered_forgot_self_check": "remembered",
    }[question["question_type"]]

    response = client.post(
        f"/api/quizzes/learner-1/{started_quiz['attempt_id']}/answers",
        json={
            "word_id": question["word_id"],
            "question_type": question["question_type"],
            "answer": answer,
        },
    )

    assert response.status_code == 200
    db_session.refresh(progress)
    assert progress.next_review_at == future_review


def test_complete_daily_quiz_returns_score(client, started_quiz):
    for question in started_quiz["questions"]:
        payload = {"word_id": question["word_id"], "question_type": question["question_type"], "answer": "wrong"}
        client.post(f"/api/quizzes/learner-1/{started_quiz['attempt_id']}/answers", json=payload)
        client.post(f"/api/quizzes/learner-1/{started_quiz['attempt_id']}/answers", json=payload)

    response = client.post(f"/api/quizzes/learner-1/{started_quiz['attempt_id']}/complete")

    assert response.status_code == 200
    body = response.json()
    assert body["total_questions"] == len(started_quiz["questions"])
    assert body["score"] == 0
    assert body["result_version"] == 2
    assert body["breakdown_status"] == "available"
    assert body["first_attempt_correct"] == 0
    assert body["first_attempt_eligible"] == sum(
        question["question_type"] != "remembered_forgot_self_check"
        for question in started_quiz["questions"]
    )
    assert body["recovered_objective_items"] == 0
    assert started_quiz["questions"][0]["word_id"] in body["weak_word_ids"]
    assert body["mistakes"][0]["prompt"]
    assert body["mistakes"][0]["correct_answer"]


def test_correct_retry_changes_recovery_but_not_first_answer_count(client, db_session, started_quiz):
    plan = json.loads(db_session.get(QuizAttempt, started_quiz["attempt_id"]).question_plan)
    target = next(question for question in plan if question["question_type"] != "remembered_forgot_self_check")
    url = f"/api/quizzes/learner-1/{started_quiz['attempt_id']}/answers"
    for question in plan:
        key = question["answer_key"]
        answer = (key["latin"] if question["question_type"] == "ru_to_sr_typing"
                  else "remembered" if question["question_type"] == "remembered_forgot_self_check"
                  else key["correct"])
        if question is target:
            assert client.post(url, json={"word_id": question["word_id"],
                "question_type": question["question_type"], "answer": "wrong"}).json()["repeat_word"] is True
        assert client.post(url, json={"word_id": question["word_id"],
            "question_type": question["question_type"], "answer": answer}).json()["is_correct"] is True
    result = client.post(f"/api/quizzes/learner-1/{started_quiz['attempt_id']}/complete").json()
    assert result["score"] == result["total_questions"]
    assert result["recovered_objective_items"] == 1
    assert result["first_attempt_correct"] == result["first_attempt_eligible"] - 1


def test_weekly_quiz_includes_this_weeks_words_and_weak_words(client, weekly_progress):
    response = client.post("/api/quizzes/learner-1/start", json={"quiz_type": "weekly"})

    assert response.status_code == 200
    returned_ids = {question["word_id"] for question in response.json()["questions"]}
    assert weekly_progress["this_week_word_id"] in returned_ids
    assert weekly_progress["weak_word_id"] in returned_ids


def test_correct_weekly_answer_removes_weak_status(client, started_weekly_quiz, weak_word):
    question = next(q for q in started_weekly_quiz["questions"] if q["word_id"] == weak_word.id)
    answer = (
        weak_word.russian_translation
        if question["question_type"] == "sr_to_ru_choice"
        else weak_word.serbian_latin
    )

    response = client.post(
        f"/api/quizzes/learner-1/{started_weekly_quiz['attempt_id']}/answers",
        json={
            "word_id": weak_word.id,
            "question_type": question["question_type"],
            "answer": answer,
        },
    )

    assert response.status_code == 200
    assert response.json()["is_correct"] is True
    assert response.json()["is_weak"] is False


def test_quiz_rejects_word_that_is_not_in_attempt(client, started_quiz, seeded_words):
    out_of_roster_word = seeded_words[-1]

    response = client.post(
        f"/api/quizzes/learner-1/{started_quiz['attempt_id']}/answers",
        json={"word_id": out_of_roster_word.id, "question_type": "sr_to_ru_choice", "answer": "wrong"},
    )

    assert response.status_code == 400


def test_backend_repeats_incorrect_answer_only_once(client, started_quiz):
    question = started_quiz["questions"][0]
    payload = {"word_id": question["word_id"], "question_type": question["question_type"], "answer": "wrong"}

    first = client.post(f"/api/quizzes/learner-1/{started_quiz['attempt_id']}/answers", json=payload)
    second = client.post(f"/api/quizzes/learner-1/{started_quiz['attempt_id']}/answers", json=payload)

    assert first.status_code == 200
    assert first.json()["repeat_word"] is True
    assert second.status_code == 200
    assert second.json()["repeat_word"] is False


def test_multiple_choice_can_place_answer_in_every_slot(db_session):
    from app.services.quiz_service import _distractors

    words = [VocabularyItem(serbian_cyrillic=f"реч {index}", serbian_latin=f"reč {index}",
                            russian_translation=f"значение {index}", cefr_level="A1", theme="x")
             for index in range(12)]
    db_session.add_all(words)
    db_session.commit()
    positions = [
        _distractors(db_session, word).index(word.russian_translation)
        for word in words
    ]
    assert set(positions) == {0, 1, 2, 3}


def test_choice_labels_deduplicate_after_normalization(db_session):
    from app.services.quiz_service import _distractors

    words = [VocabularyItem(serbian_cyrillic=f"реч {index}", serbian_latin=f"reč {index}",
                            russian_translation=translation, cefr_level="A1", theme="x")
             for index, translation in enumerate(("Вода", " вода  ", "ВОДА", "хлеб", "сок"))]
    db_session.add_all(words)
    db_session.commit()
    choices = _distractors(db_session, words[0])
    assert len(choices) == 3
    assert len({" ".join(label.split()).casefold() for label in choices}) == 3


def test_single_word_pool_keeps_typing_and_self_check_without_choice(client, db_session):
    from app.models import UserProfile

    word = VocabularyItem(serbian_cyrillic="вода", serbian_latin="voda",
                          russian_translation="вода", cefr_level="A1", theme="x")
    db_session.add_all([UserProfile(user_id="solo"), word])
    db_session.commit()
    db_session.add(UserWordProgress(user_id="solo", word_id=word.id, status="seen",
                                    first_seen_at=datetime.now(timezone.utc)))
    db_session.commit()
    started = client.post("/api/quizzes/solo/start", json={"quiz_type": "daily"}).json()
    assert {question["question_type"] for question in started["questions"]} == {
        "ru_to_sr_typing", "remembered_forgot_self_check"
    }
    for question in started["questions"]:
        answer = "voda" if question["question_type"] == "ru_to_sr_typing" else "remembered"
        assert client.post(f"/api/quizzes/solo/{started['attempt_id']}/answers", json={
            "word_id": word.id, "question_type": question["question_type"], "answer": answer,
        }).json()["is_correct"] is True
    result = client.post(f"/api/quizzes/solo/{started['attempt_id']}/complete").json()
    assert result["total_questions"] == 2 and result["score"] == 2


def test_weekly_quiz_uses_calendar_week_boundary(client, db_session, monkeypatch):
    from app.models import UserProfile, UserWordProgress, VocabularyItem
    import app.services.quiz_service as quiz_service

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            value = datetime(2026, 7, 6, 12, tzinfo=timezone.utc)
            return value if tz is None else value.astimezone(tz)

    monkeypatch.setattr(quiz_service, "datetime", FixedDateTime)
    db_session.add(UserProfile(user_id="learner-week"))
    previous_week_word = VocabularyItem(
        serbian_cyrillic="недеља",
        serbian_latin="nedelja",
        russian_translation="воскресенье",
        cefr_level="A1",
        theme="calendar",
    )
    current_week_word = VocabularyItem(
        serbian_cyrillic="понедељак",
        serbian_latin="ponedeljak",
        russian_translation="понедельник",
        cefr_level="A1",
        theme="calendar",
    )
    db_session.add_all([previous_week_word, current_week_word])
    db_session.commit()
    previous_sunday = datetime(2026, 7, 5, 12, tzinfo=timezone.utc)
    current_monday = datetime(2026, 7, 6, 9, tzinfo=timezone.utc)
    db_session.add_all([
        UserWordProgress(
            user_id="learner-week",
            word_id=previous_week_word.id,
            status="reviewing",
            first_seen_at=previous_sunday,
            last_seen_at=previous_sunday,
        ),
        UserWordProgress(
            user_id="learner-week",
            word_id=current_week_word.id,
            status="reviewing",
            first_seen_at=current_monday,
            last_seen_at=current_monday,
        ),
    ])
    db_session.commit()

    response = client.post("/api/quizzes/learner-week/start", json={"quiz_type": "weekly"})

    assert response.status_code == 200
    returned_ids = {question["word_id"] for question in response.json()["questions"]}
    assert current_week_word.id in returned_ids
    assert previous_week_word.id not in returned_ids


def test_daily_quiz_prioritizes_words_touched_today_under_cap(client, db_session):
    from app.models import UserProfile, UserWordProgress, VocabularyItem

    db_session.add(UserProfile(user_id="learner-many"))
    words = [
        VocabularyItem(
            serbian_cyrillic=f"реч {index}",
            serbian_latin=f"rec {index}",
            russian_translation=f"слово {index}",
            cefr_level="A1",
            theme="daily",
        )
        for index in range(1, 26)
    ]
    db_session.add_all(words)
    db_session.commit()
    old_touch = datetime.now(timezone.utc) - timedelta(days=10)
    today_touch = datetime.now(timezone.utc)
    progress_rows = [
        UserWordProgress(
            user_id="learner-many",
            word_id=word.id,
            status="reviewing",
            first_seen_at=old_touch,
            last_seen_at=old_touch,
        )
        for word in words[:-1]
    ]
    progress_rows.append(
        UserWordProgress(
            user_id="learner-many",
            word_id=words[-1].id,
            status="seen",
            first_seen_at=today_touch,
            last_seen_at=today_touch,
        )
    )
    db_session.add_all(progress_rows)
    db_session.commit()

    response = client.post("/api/quizzes/learner-many/start", json={"quiz_type": "daily"})

    assert response.status_code == 200
    returned_ids = {question["word_id"] for question in response.json()["questions"]}
    assert words[-1].id in returned_ids


def test_quiz_rejects_submissions_after_repeat_limit(client, started_quiz):
    question = started_quiz["questions"][0]
    payload = {"word_id": question["word_id"], "question_type": question["question_type"], "answer": "wrong"}

    first = client.post(f"/api/quizzes/learner-1/{started_quiz['attempt_id']}/answers", json=payload)
    second = client.post(f"/api/quizzes/learner-1/{started_quiz['attempt_id']}/answers", json=payload)
    third = client.post(f"/api/quizzes/learner-1/{started_quiz['attempt_id']}/answers", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 400


def test_quiz_answer_rejects_wrong_user(client, started_quiz):
    question = started_quiz["questions"][0]

    response = client.post(
        f"/api/quizzes/learner-2/{started_quiz['attempt_id']}/answers",
        json={"word_id": question["word_id"], "question_type": question["question_type"], "answer": "wrong"},
    )

    assert response.status_code == 404


def test_complete_quiz_rejects_wrong_user(client, started_quiz):
    response = client.post(f"/api/quizzes/learner-2/{started_quiz['attempt_id']}/complete")

    assert response.status_code == 404


def test_complete_quiz_rejects_unanswered_planned_questions(client, started_quiz):
    response = client.post(f"/api/quizzes/learner-1/{started_quiz['attempt_id']}/complete")

    assert response.status_code == 400


def test_complete_quiz_rejects_skipped_required_repeats(client, started_quiz):
    for question in started_quiz["questions"]:
        client.post(
            f"/api/quizzes/learner-1/{started_quiz['attempt_id']}/answers",
            json={"word_id": question["word_id"], "question_type": question["question_type"], "answer": "wrong"},
        )

    response = client.post(f"/api/quizzes/learner-1/{started_quiz['attempt_id']}/complete")

    assert response.status_code == 400


def test_start_quiz_does_not_expose_self_check_answer(client, completed_learning):
    response = client.post("/api/quizzes/learner-1/start", json={"quiz_type": "daily"})

    assert response.status_code == 200
    question = next(
        item for item in response.json()["questions"] if item["question_type"] == "remembered_forgot_self_check"
    )
    assert "answer" not in question


def test_reveal_self_check_answer_returns_translation(client, started_quiz, db_session):
    from app.models import VocabularyItem

    question = next(
        item for item in started_quiz["questions"] if item["question_type"] == "remembered_forgot_self_check"
    )
    word = db_session.get(VocabularyItem, question["word_id"])

    response = client.get(
        f"/api/quizzes/learner-1/{started_quiz['attempt_id']}/questions/"
        f"{question['word_id']}/{question['question_type']}/answer"
    )

    assert response.status_code == 200
    assert response.json()["answer"] == word.russian_translation


def test_reveal_answer_rejects_non_self_check_question(client, started_quiz):
    question = next(item for item in started_quiz["questions"] if item["question_type"] != "remembered_forgot_self_check")

    response = client.get(
        f"/api/quizzes/learner-1/{started_quiz['attempt_id']}/questions/"
        f"{question['word_id']}/{question['question_type']}/answer"
    )

    assert response.status_code == 400


def test_complete_quiz_rejects_already_completed_attempt(client, started_quiz):
    for question in started_quiz["questions"]:
        payload = {"word_id": question["word_id"], "question_type": question["question_type"], "answer": "wrong"}
        client.post(f"/api/quizzes/learner-1/{started_quiz['attempt_id']}/answers", json=payload)
        client.post(f"/api/quizzes/learner-1/{started_quiz['attempt_id']}/answers", json=payload)

    first = client.post(f"/api/quizzes/learner-1/{started_quiz['attempt_id']}/complete")
    second = client.post(f"/api/quizzes/learner-1/{started_quiz['attempt_id']}/complete")

    assert first.status_code == 200
    assert second.status_code == 400


def test_shadow_flag_off_keeps_quiz_paths_free_of_domain_work(
    client,
    completed_learning,
    monkeypatch,
):
    import app.services.quiz_service as quiz_service

    class UnexpectedShadowService:
        def __init__(self, _session):
            raise AssertionError("flag-off quiz path constructed the shadow adapter")

    monkeypatch.setattr(
        quiz_service.settings,
        "language_assistant_shadow_enabled",
        False,
    )
    monkeypatch.setattr(quiz_service, "ShadowQuizService", UnexpectedShadowService)

    started = client.post(
        "/api/quizzes/learner-1/start",
        json={"quiz_type": "daily"},
    )
    assert started.status_code == 200
    body = started.json()
    for question in body["questions"]:
        payload = {
            "word_id": question["word_id"],
            "question_type": question["question_type"],
            "answer": "wrong",
        }
        assert client.post(
            f"/api/quizzes/learner-1/{body['attempt_id']}/answers",
            json=payload,
        ).status_code == 200
        assert client.post(
            f"/api/quizzes/learner-1/{body['attempt_id']}/answers",
            json=payload,
        ).status_code == 200

    completed = client.post(
        f"/api/quizzes/learner-1/{body['attempt_id']}/complete"
    )
    assert completed.status_code == 200
    assert completed.json()["total_questions"] == len(body["questions"])
