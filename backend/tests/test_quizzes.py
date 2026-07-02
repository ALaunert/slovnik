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
