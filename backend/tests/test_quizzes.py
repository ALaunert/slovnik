from datetime import datetime, timedelta, timezone


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


def test_multiple_choice_does_not_always_put_correct_answer_first(client, completed_learning):
    response = client.post("/api/quizzes/learner-1/start", json={"quiz_type": "daily"})

    question = next(item for item in response.json()["questions"] if item["question_type"] == "sr_to_ru_choice")
    learned_word = next(word for word in completed_learning if word.id == question["word_id"])
    assert question["choices"][0] != learned_word.russian_translation


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
