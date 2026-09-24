import json
import unicodedata
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select

from app.models import QuizAttempt, UserWordProgress, VocabularyItem


def test_new_plan_keys_stay_private_and_grade_issued_content_after_edits(client, completed_learning, db_session):
    from app.services.quiz_service import start_quiz

    started = start_quiz(db_session, "learner-1", "daily")
    stored = db_session.get(QuizAttempt, started["attempt_id"])
    plan = json.loads(stored.question_plan)
    assert all(item["answer_key_version"] == 1 for item in plan)
    assert all("answer_key" in item for item in plan)
    assert all("answer_key" not in item and "answer_key_version" not in item for item in started["questions"])

    original = {word.id: (word.serbian_latin, word.serbian_cyrillic, word.russian_translation) for word in completed_learning}
    for word in completed_learning:
        word.serbian_latin = f"changed{word.id}"
        word.serbian_cyrillic = f"измена{word.id}"
        word.russian_translation = f"changed translation {word.id}"
    db_session.commit()

    for question in started["questions"]:
        word_id = question["word_id"]
        kind = question["question_type"]
        latin, cyrillic, translation = original[word_id]
        if kind == "remembered_forgot_self_check":
            revealed = client.get(f"/api/quizzes/learner-1/{started['attempt_id']}/questions/{word_id}/{kind}/answer")
            assert revealed.json() == {"answer": translation}
            answer = "forgot"
        else:
            answer = translation if kind == "sr_to_ru_choice" else cyrillic
            accepted = client.post(f"/api/quizzes/learner-1/{started['attempt_id']}/answers", json={"word_id": word_id, "question_type": kind, "answer": answer})
            assert accepted.json()["is_correct"] is True
            continue
        for _ in range(2):
            response = client.post(f"/api/quizzes/learner-1/{started['attempt_id']}/answers", json={"word_id": word_id, "question_type": kind, "answer": answer})
            assert response.status_code == 200
    completed = client.post(f"/api/quizzes/learner-1/{started['attempt_id']}/complete")
    assert completed.status_code == 200
    assert all(
        mistake["correct_answer"] == original[mistake["word_id"]][2]
        for mistake in completed.json()["mistakes"]
    )


@pytest.mark.parametrize("script_index", [0, 1])
def test_typing_key_accepts_both_issued_scripts_after_edit(client, started_quiz, db_session, script_index):
    question = next(item for item in started_quiz["questions"] if item["question_type"] == "ru_to_sr_typing")
    word = db_session.get(VocabularyItem, question["word_id"])
    issued = (word.serbian_latin, word.serbian_cyrillic)
    word.serbian_latin = "changed"
    word.serbian_cyrillic = "измењено"
    db_session.commit()

    response = client.post(f"/api/quizzes/learner-1/{started_quiz['attempt_id']}/answers", json={"word_id": word.id, "question_type": question["question_type"], "answer": issued[script_index]})

    assert response.status_code == 200
    assert response.json()["is_correct"] is True


def test_all_new_mistake_corrections_use_issued_keys_after_edit(client, started_quiz, db_session):
    issued = {}
    for question in started_quiz["questions"]:
        word = db_session.get(VocabularyItem, question["word_id"])
        issued[(word.id, question["question_type"])] = (
            f"{word.serbian_latin} / {word.serbian_cyrillic}"
            if question["question_type"] == "ru_to_sr_typing" else word.russian_translation
        )
        word.serbian_latin = f"changed{word.id}"
        word.serbian_cyrillic = f"измена{word.id}"
        word.russian_translation = f"changed translation {word.id}"
    db_session.commit()
    for question in started_quiz["questions"]:
        payload = {"word_id": question["word_id"], "question_type": question["question_type"], "answer": "wrong"}
        first = client.post(f"/api/quizzes/learner-1/{started_quiz['attempt_id']}/answers", json=payload)
        second = client.post(f"/api/quizzes/learner-1/{started_quiz['attempt_id']}/answers", json=payload)
        assert first.json()["repeat_word"] is True
        assert second.json()["repeat_word"] is False
    completed = client.post(f"/api/quizzes/learner-1/{started_quiz['attempt_id']}/complete")
    assert completed.status_code == 200
    assert len(completed.json()["mistakes"]) == 2 * len(started_quiz["questions"])
    assert all(
        mistake["correct_answer"] == issued[(mistake["word_id"], mistake["question_type"])]
        for mistake in completed.json()["mistakes"]
    )


@pytest.mark.parametrize("bad_version", [None, True, 999])
def test_old_plan_uses_legacy_content_and_unknown_key_version_is_rejected(client, started_quiz, db_session, bad_version):
    attempt = db_session.get(QuizAttempt, started_quiz["attempt_id"])
    plan = json.loads(attempt.question_plan)
    question = plan[0]
    word = db_session.get(VocabularyItem, question["word_id"])
    question.pop("answer_key_version", None)
    question.pop("answer_key", None)
    word.russian_translation = "новый перевод"
    attempt.question_plan = json.dumps(plan, ensure_ascii=False)
    db_session.commit()

    answer = client.post(f"/api/quizzes/learner-1/{attempt.id}/answers", json={"word_id": word.id, "question_type": question["question_type"], "answer": "новый перевод"})
    assert answer.status_code == 200
    assert answer.json()["is_correct"] is True

    unknown_question = plan[1]
    unknown_question["answer_key_version"] = bad_version
    attempt.question_plan = json.dumps(plan, ensure_ascii=False)
    db_session.commit()
    unknown = client.post(f"/api/quizzes/learner-1/{attempt.id}/answers", json={"word_id": unknown_question["word_id"], "question_type": unknown_question["question_type"], "answer": "wrong"})
    assert unknown.status_code == 400


@pytest.mark.parametrize("slot", [0, 1, 2, 3])
def test_choice_correct_answer_can_occupy_each_slot(db_session, seeded_words, monkeypatch, slot):
    import app.services.quiz_service as quiz_service

    class ControlledRandom:
        def __init__(self):
            pass

        def shuffle(self, choices):
            choices.insert(slot, choices.pop(0))

    monkeypatch.setattr(quiz_service, "SystemRandom", ControlledRandom)
    choices = quiz_service._distractors(db_session, seeded_words[0])
    assert len(choices) == 4
    assert choices.index(seeded_words[0].russian_translation) == slot


def test_choice_labels_are_normalized_unique_and_scan_past_duplicates(db_session, seeded_words):
    from app.services.quiz_service import _distractors

    seeded_words[0].russian_translation = "сёло"
    seeded_words[1].russian_translation = " СЁЛО "
    seeded_words[2].russian_translation = unicodedata.normalize("NFD", "сёло")
    seeded_words[3].russian_translation = "слово 2"
    db_session.commit()

    choices = _distractors(db_session, seeded_words[0])

    assert len(choices) == 4
    assert {"сёло", "слово 2", "слово 5", "слово 6"} == set(choices)


@pytest.mark.parametrize(
    ("source", "display"),
    [
        (unicodedata.normalize("NFD", "сёло"), "сёло"),
        ("добрый   день", "добрый день"),
    ],
)
def test_normalized_issued_choice_remains_gradeable(client, weak_progress, db_session, source, display):
    word = db_session.get(VocabularyItem, weak_progress.word_id)
    word.russian_translation = source
    db_session.commit()
    started = client.post("/api/quizzes/learner-1/start", json={"quiz_type": "daily"}).json()
    choice_question = next(item for item in started["questions"] if item["question_type"] == "sr_to_ru_choice")
    assert display in choice_question["choices"]

    response = client.post(f"/api/quizzes/learner-1/{started['attempt_id']}/answers", json={
        "word_id": word.id,
        "question_type": "sr_to_ru_choice",
        "answer": display,
    })

    assert response.status_code == 200
    assert response.json()["is_correct"] is True


def test_single_word_quiz_omits_choice_but_keeps_typing_self_check_and_repeats(client, weak_progress, db_session):
    db_session.execute(delete(VocabularyItem).where(VocabularyItem.id != weak_progress.word_id))
    db_session.commit()
    started = client.post("/api/quizzes/learner-1/start", json={"quiz_type": "daily"})
    assert started.status_code == 200
    body = started.json()
    assert {item["question_type"] for item in body["questions"]} == {
        "ru_to_sr_typing", "remembered_forgot_self_check"
    }
    assert all(set(item) == {"word_id", "question_type", "prompt", "choices"} for item in body["questions"])
    attempt = db_session.get(QuizAttempt, body["attempt_id"])
    assert attempt.total_questions == 2
    for item in body["questions"]:
        payload = {"word_id": item["word_id"], "question_type": item["question_type"], "answer": "wrong"}
        first = client.post(f"/api/quizzes/learner-1/{attempt.id}/answers", json=payload)
        second = client.post(f"/api/quizzes/learner-1/{attempt.id}/answers", json=payload)
        assert first.json()["repeat_word"] is True
        assert second.json()["repeat_word"] is False
    completed = client.post(f"/api/quizzes/learner-1/{attempt.id}/complete")
    assert completed.status_code == 200
    assert completed.json()["total_questions"] == 2
    assert completed.json()["score"] == 0


def test_all_duplicate_translations_omit_choice_but_keep_other_questions(client, completed_learning, seeded_words, db_session):
    for word in seeded_words:
        word.russian_translation = "общий перевод"
    db_session.commit()

    response = client.post("/api/quizzes/learner-1/start", json={"quiz_type": "daily"})

    assert response.status_code == 200
    questions = response.json()["questions"]
    assert questions
    assert "sr_to_ru_choice" not in {item["question_type"] for item in questions}
    assert {"ru_to_sr_typing", "remembered_forgot_self_check"} <= {item["question_type"] for item in questions}


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
    assert started_quiz["questions"][0]["word_id"] in body["weak_word_ids"]
    assert body["mistakes"][0]["prompt"]
    assert body["mistakes"][0]["correct_answer"]


def test_completion_separates_first_objective_responses_recovery_and_self_report(
    client, started_quiz, db_session,
):
    objective_index = 0
    for question in started_quiz["questions"]:
        word = db_session.get(VocabularyItem, question["word_id"])
        endpoint = f"/api/quizzes/learner-1/{started_quiz['attempt_id']}/answers"
        payload = {"word_id": word.id, "question_type": question["question_type"]}
        if question["question_type"] == "remembered_forgot_self_check":
            assert client.post(endpoint, json={**payload, "answer": "remembered"}).status_code == 200
            continue
        correct = word.russian_translation if question["question_type"] == "sr_to_ru_choice" else word.serbian_latin
        if objective_index < 2:
            assert client.post(endpoint, json={**payload, "answer": "wrong"}).status_code == 200
            retry = correct if objective_index == 0 else "wrong"
            assert client.post(endpoint, json={**payload, "answer": retry}).status_code == 200
        else:
            assert client.post(endpoint, json={**payload, "answer": correct}).status_code == 200
        objective_index += 1

    completed = client.post(f"/api/quizzes/learner-1/{started_quiz['attempt_id']}/complete")

    assert completed.status_code == 200
    assert completed.json()["result_version"] == 2
    assert completed.json()["first_attempt_status"] == "available"
    assert completed.json()["first_attempt_eligible"] == 4
    assert completed.json()["first_attempt_correct"] == 2
    assert completed.json()["recovered_objective_items"] == 1
    assert completed.json()["self_report_remembered"] == 1
    assert completed.json()["self_report_total"] == 1
    assert completed.json()["score"] == 4


def test_self_check_only_completion_has_no_objective_measurement(client, started_quiz, db_session):
    attempt = db_session.get(QuizAttempt, started_quiz["attempt_id"])
    self_check = next(question for question in json.loads(attempt.question_plan)
                      if question["question_type"] == "remembered_forgot_self_check")
    attempt.question_plan = json.dumps([self_check], ensure_ascii=False)
    attempt.total_questions = 1
    db_session.commit()

    answer = client.post(f"/api/quizzes/learner-1/{attempt.id}/answers", json={
        "word_id": self_check["word_id"], "question_type": self_check["question_type"], "answer": "forgot"
    })
    assert answer.status_code == 200
    assert client.post(f"/api/quizzes/learner-1/{attempt.id}/answers", json={
        "word_id": self_check["word_id"], "question_type": self_check["question_type"], "answer": "forgot"
    }).status_code == 200
    completed = client.post(f"/api/quizzes/learner-1/{attempt.id}/complete")
    assert completed.status_code == 200
    assert completed.json()["first_attempt_status"] == "not_measured"
    assert completed.json()["first_attempt_eligible"] == 0
    assert completed.json()["first_attempt_correct"] == 0
    assert completed.json()["recovered_objective_items"] == 0
    assert completed.json()["self_report_remembered"] == 0
    assert completed.json()["self_report_total"] == 1


def test_legacy_plan_completion_marks_breakdown_unavailable(client, started_quiz, db_session):
    attempt = db_session.get(QuizAttempt, started_quiz["attempt_id"])
    plan = json.loads(attempt.question_plan)
    for question in plan:
        question.pop("answer_key_version")
        question.pop("answer_key")
        if question["question_type"] == "remembered_forgot_self_check":
            question["answer"] = db_session.get(VocabularyItem, question["word_id"]).russian_translation
    attempt.question_plan = json.dumps(plan, ensure_ascii=False)
    db_session.commit()

    for question in started_quiz["questions"]:
        word = db_session.get(VocabularyItem, question["word_id"])
        correct = {
            "sr_to_ru_choice": word.russian_translation,
            "ru_to_sr_typing": word.serbian_latin,
            "remembered_forgot_self_check": "remembered",
        }[question["question_type"]]
        assert client.post(f"/api/quizzes/learner-1/{attempt.id}/answers", json={
            "word_id": word.id, "question_type": question["question_type"], "answer": correct,
        }).status_code == 200
    completed = client.post(f"/api/quizzes/learner-1/{attempt.id}/complete")
    assert completed.status_code == 200
    assert completed.json()["score"] == len(plan)
    assert completed.json()["first_attempt_status"] == "unavailable"
    assert completed.json()["first_attempt_eligible"] == 0
    assert completed.json()["first_attempt_correct"] == 0
    assert completed.json()["recovered_objective_items"] == 0
    assert completed.json()["self_report_total"] == 0


def test_empty_quiz_completion_is_not_measured(client, db_session):
    started = client.post("/api/quizzes/empty-learner/start", json={"quiz_type": "daily"}).json()
    completed = client.post(f"/api/quizzes/empty-learner/{started['attempt_id']}/complete")
    assert completed.status_code == 200
    assert completed.json()["result_version"] == 2
    assert completed.json()["score"] == 0
    assert completed.json()["first_attempt_status"] == "not_measured"
    assert completed.json()["first_attempt_eligible"] == 0
    assert completed.json()["self_report_total"] == 0


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


def test_multiple_choice_position_is_shuffled_on_each_issuance(db_session, seeded_words, monkeypatch):
    import app.services.quiz_service as quiz_service

    class AlternatingRandom:
        next_slot = 0

        def __init__(self):
            self.slot = AlternatingRandom.next_slot
            AlternatingRandom.next_slot = 1 - AlternatingRandom.next_slot

        def shuffle(self, choices):
            choices.insert(self.slot, choices.pop(0))

    monkeypatch.setattr(quiz_service, "SystemRandom", AlternatingRandom)
    word = seeded_words[0]
    first = quiz_service._distractors(db_session, word)
    second = quiz_service._distractors(db_session, word)
    assert [choices.index(word.russian_translation) for choices in (first, second)] == [0, 1]


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
    assert all(
        set(item) == {"word_id", "question_type", "prompt", "choices"}
        for item in response.json()["questions"]
    )
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
