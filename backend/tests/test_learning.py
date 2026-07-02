def test_daily_new_words_prefers_unseen_words_for_user(client, seeded_words):
    response = client.get("/api/learning/learner-1/new-words")

    assert response.status_code == 200
    assert len(response.json()["words"]) == 5


def test_complete_new_words_records_first_seen_progress(client, seeded_words):
    word_ids = [seeded_words[0].id, seeded_words[1].id]
    response = client.post("/api/learning/learner-1/new-words/complete", json={"word_ids": word_ids})

    assert response.status_code == 200
    assert all(item["status"] == "seen" for item in response.json()["progress"])


def test_review_includes_weak_words(client, db_session, weak_progress):
    response = client.get("/api/learning/learner-1/review")

    assert response.status_code == 200
    assert weak_progress.word_id in [word["id"] for word in response.json()["words"]]


def test_review_avoids_words_seen_today_when_not_weak(client, db_session, seen_today_progress):
    response = client.get("/api/learning/learner-1/review")

    assert seen_today_progress.word_id not in [word["id"] for word in response.json()["words"]]


def test_complete_review_marks_reviewing(client, seeded_words):
    client.post("/api/learning/learner-1/new-words/complete", json={"word_ids": [seeded_words[0].id]})
    response = client.post("/api/learning/learner-1/review/complete", json={"word_ids": [seeded_words[0].id]})

    assert response.status_code == 200
    assert response.json()["progress"][0]["status"] == "reviewing"
