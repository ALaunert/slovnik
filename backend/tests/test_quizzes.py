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
        f"/api/quizzes/{started_quiz['attempt_id']}/answers",
        json={"word_id": question["word_id"], "question_type": question["question_type"], "answer": "wrong"},
    )

    assert response.status_code == 200
    assert response.json()["is_correct"] is False
    assert response.json()["repeat_word"] is True


def test_complete_daily_quiz_returns_score(client, started_quiz):
    question = started_quiz["questions"][0]
    client.post(
        f"/api/quizzes/{started_quiz['attempt_id']}/answers",
        json={"word_id": question["word_id"], "question_type": question["question_type"], "answer": "wrong"},
    )

    response = client.post(f"/api/quizzes/{started_quiz['attempt_id']}/complete")

    assert response.status_code == 200
    assert response.json()["total_questions"] == 1
    assert response.json()["weak_word_ids"] == [question["word_id"]]


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
        f"/api/quizzes/{started_weekly_quiz['attempt_id']}/answers",
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
        f"/api/quizzes/{started_quiz['attempt_id']}/answers",
        json={"word_id": out_of_roster_word.id, "question_type": "sr_to_ru_choice", "answer": "wrong"},
    )

    assert response.status_code == 400


def test_backend_repeats_incorrect_answer_only_once(client, started_quiz):
    question = started_quiz["questions"][0]
    payload = {"word_id": question["word_id"], "question_type": question["question_type"], "answer": "wrong"}

    first = client.post(f"/api/quizzes/{started_quiz['attempt_id']}/answers", json=payload)
    second = client.post(f"/api/quizzes/{started_quiz['attempt_id']}/answers", json=payload)

    assert first.status_code == 200
    assert first.json()["repeat_word"] is True
    assert second.status_code == 200
    assert second.json()["repeat_word"] is False


def test_multiple_choice_does_not_always_put_correct_answer_first(client, completed_learning):
    response = client.post("/api/quizzes/learner-1/start", json={"quiz_type": "daily"})

    question = next(item for item in response.json()["questions"] if item["question_type"] == "sr_to_ru_choice")
    learned_word = next(word for word in completed_learning if word.id == question["word_id"])
    assert question["choices"][0] != learned_word.russian_translation
