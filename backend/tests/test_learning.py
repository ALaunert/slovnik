from datetime import datetime, timedelta, timezone

import pytest

from app.models import UserProfile, UserWordProgress


STRUCTURED_STRESS = {
    "cyrillic_syllables": ["реч ", "1"],
    "latin_syllables": ["rec ", "1"],
    "stressed_syllable_index": 0,
}


def test_daily_new_words_prefers_unseen_words_for_user(client, seeded_words):
    response = client.get("/api/learning/learner-1/new-words")

    assert response.status_code == 200
    assert len(response.json()["words"]) == 5


def test_structured_stress_survives_new_word_and_review_projections(client, db_session, seeded_words):
    word = seeded_words[0]
    word.stress_pattern = STRUCTURED_STRESS
    db_session.commit()

    new_words_response = client.get("/api/learning/learner-1/new-words")

    assert new_words_response.status_code == 200
    new_word = next(item for item in new_words_response.json()["words"] if item["id"] == word.id)
    assert new_word["stress_pattern"] == STRUCTURED_STRESS

    db_session.add(
        UserWordProgress(
            user_id="learner-1",
            word_id=word.id,
            status="reviewing",
            is_weak=True,
        )
    )
    db_session.commit()

    review_response = client.get("/api/learning/learner-1/review")

    assert review_response.status_code == 200
    review_word = next(item for item in review_response.json()["words"] if item["id"] == word.id)
    assert review_word["stress_pattern"] == STRUCTURED_STRESS


def test_complete_new_words_records_first_seen_progress(client, seeded_words):
    word_ids = [seeded_words[0].id, seeded_words[1].id]
    response = client.post("/api/learning/learner-1/new-words/complete", json={"word_ids": word_ids})

    assert response.status_code == 200
    assert all(item["status"] == "seen" for item in response.json()["progress"])


def test_complete_new_words_schedules_first_review_in_about_one_day(client, seeded_words):
    before_due = datetime.now(timezone.utc) + timedelta(hours=23, minutes=59)

    response = client.post(
        "/api/learning/learner-1/new-words/complete",
        json={"word_ids": [seeded_words[0].id]},
    )

    after_due = datetime.now(timezone.utc) + timedelta(days=1, minutes=1)
    assert response.status_code == 200
    next_review_at = datetime.fromisoformat(response.json()["progress"][0]["next_review_at"])
    if next_review_at.tzinfo is None:
        next_review_at = next_review_at.replace(tzinfo=timezone.utc)
    assert before_due <= next_review_at <= after_due


def test_review_includes_weak_words(client, db_session, weak_progress):
    response = client.get("/api/learning/learner-1/review")

    assert response.status_code == 200
    assert weak_progress.word_id in [word["id"] for word in response.json()["words"]]


def test_review_excludes_future_scheduled_word(client, db_session, seeded_words):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db_session.add(UserProfile(user_id="future-review"))
    db_session.add(
        UserWordProgress(
            user_id="future-review",
            word_id=seeded_words[0].id,
            status="reviewing",
            first_seen_at=now - timedelta(days=10),
            last_seen_at=now - timedelta(days=3),
            next_review_at=now + timedelta(days=1),
            is_weak=True,
            weak_since=now - timedelta(days=1),
        )
    )
    db_session.commit()

    response = client.get("/api/learning/future-review/review")

    assert response.status_code == 200
    assert response.json()["words"] == []


def test_review_includes_overdue_scheduled_word(client, db_session, seeded_words):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db_session.add(UserProfile(user_id="overdue-review"))
    db_session.add(
        UserWordProgress(
            user_id="overdue-review",
            word_id=seeded_words[0].id,
            status="reviewing",
            first_seen_at=now - timedelta(days=10),
            last_seen_at=now - timedelta(days=3),
            next_review_at=now - timedelta(minutes=1),
        )
    )
    db_session.commit()

    response = client.get("/api/learning/overdue-review/review")

    assert response.status_code == 200
    assert [word["id"] for word in response.json()["words"]] == [seeded_words[0].id]


def test_review_legacy_fallback_excludes_same_day_first_or_last_seen(
    client, db_session, seeded_words
):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db_session.add(UserProfile(user_id="legacy-review"))
    db_session.add_all(
        [
            UserWordProgress(
                user_id="legacy-review",
                word_id=seeded_words[0].id,
                status="reviewing",
                first_seen_at=now - timedelta(days=2),
                last_seen_at=now,
                next_review_at=None,
            ),
            UserWordProgress(
                user_id="legacy-review",
                word_id=seeded_words[1].id,
                status="reviewing",
                first_seen_at=now,
                last_seen_at=now - timedelta(days=2),
                next_review_at=None,
            ),
            UserWordProgress(
                user_id="legacy-review",
                word_id=seeded_words[2].id,
                status="reviewing",
                first_seen_at=now - timedelta(days=3),
                last_seen_at=now - timedelta(days=2),
                next_review_at=None,
            ),
        ]
    )
    db_session.commit()

    response = client.get("/api/learning/legacy-review/review")

    assert response.status_code == 200
    assert [word["id"] for word in response.json()["words"]] == [seeded_words[2].id]


def test_review_legacy_fallback_includes_status_eligible_row_without_timestamps(
    client, db_session, seeded_words
):
    db_session.add(UserProfile(user_id="legacy-null-review"))
    db_session.add(
        UserWordProgress(
            user_id="legacy-null-review",
            word_id=seeded_words[0].id,
            status="reviewing",
            next_review_at=None,
        )
    )
    db_session.commit()

    response = client.get("/api/learning/legacy-null-review/review")

    assert response.status_code == 200
    assert [word["id"] for word in response.json()["words"]] == [seeded_words[0].id]


def test_review_orders_weak_words_before_other_due_words(client, db_session, seeded_words):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db_session.add(UserProfile(user_id="ordered-review"))
    db_session.add_all(
        [
            UserWordProgress(
                user_id="ordered-review",
                word_id=seeded_words[0].id,
                status="reviewing",
                first_seen_at=now - timedelta(days=10),
                last_seen_at=now - timedelta(days=4),
                next_review_at=now - timedelta(days=3),
            ),
            UserWordProgress(
                user_id="ordered-review",
                word_id=seeded_words[1].id,
                status="reviewing",
                first_seen_at=now - timedelta(days=10),
                last_seen_at=now - timedelta(days=2),
                next_review_at=now - timedelta(days=1),
                is_weak=True,
                weak_since=now - timedelta(days=1),
            ),
        ]
    )
    db_session.commit()

    response = client.get("/api/learning/ordered-review/review")

    assert response.status_code == 200
    assert [word["id"] for word in response.json()["words"]] == [
        seeded_words[1].id,
        seeded_words[0].id,
    ]


def test_review_orders_null_schedule_then_due_time_then_last_seen(
    client, db_session, seeded_words
):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db_session.add(UserProfile(user_id="due-order-review"))
    db_session.add_all(
        [
            UserWordProgress(
                user_id="due-order-review",
                word_id=seeded_words[0].id,
                status="reviewing",
                first_seen_at=now - timedelta(days=10),
                last_seen_at=now - timedelta(days=6),
                next_review_at=now - timedelta(days=1),
            ),
            UserWordProgress(
                user_id="due-order-review",
                word_id=seeded_words[1].id,
                status="reviewing",
                first_seen_at=now - timedelta(days=10),
                last_seen_at=now - timedelta(days=2),
                next_review_at=None,
            ),
            UserWordProgress(
                user_id="due-order-review",
                word_id=seeded_words[2].id,
                status="reviewing",
                first_seen_at=now - timedelta(days=10),
                last_seen_at=now - timedelta(days=5),
                next_review_at=now - timedelta(days=3),
            ),
            UserWordProgress(
                user_id="due-order-review",
                word_id=seeded_words[3].id,
                status="reviewing",
                first_seen_at=now - timedelta(days=10),
                last_seen_at=now - timedelta(days=4),
                next_review_at=now - timedelta(days=3),
            ),
        ]
    )
    db_session.commit()

    response = client.get("/api/learning/due-order-review/review")

    assert response.status_code == 200
    assert [word["id"] for word in response.json()["words"]] == [
        seeded_words[1].id,
        seeded_words[2].id,
        seeded_words[3].id,
        seeded_words[0].id,
    ]


def test_review_avoids_words_seen_today_when_not_weak(client, db_session, seen_today_progress):
    response = client.get("/api/learning/learner-1/review")

    assert seen_today_progress.word_id not in [word["id"] for word in response.json()["words"]]


def test_complete_review_marks_reviewing(client, weak_progress):
    response = client.post("/api/learning/learner-1/review/complete", json={"word_ids": [weak_progress.word_id]})

    assert response.status_code == 200
    assert response.json()["progress"][0]["status"] == "reviewing"


def test_complete_review_schedules_next_day_and_resets_streak_without_other_changes(
    client, db_session, seeded_words
):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    weak_since = now - timedelta(days=5)
    db_session.add(UserProfile(user_id="legacy-batch"))
    progress = UserWordProgress(
        user_id="legacy-batch",
        word_id=seeded_words[0].id,
        status="learned",
        first_seen_at=now - timedelta(days=20),
        last_seen_at=now - timedelta(days=2),
        next_review_at=now - timedelta(minutes=1),
        review_interval_days=12,
        review_streak=2,
        is_weak=True,
        weak_since=weak_since,
    )
    db_session.add(progress)
    db_session.commit()
    before_due = datetime.now(timezone.utc) + timedelta(hours=23, minutes=59)

    response = client.post(
        "/api/learning/legacy-batch/review/complete",
        json={"word_ids": [seeded_words[0].id]},
    )

    after_due = datetime.now(timezone.utc) + timedelta(days=1, minutes=1)
    assert response.status_code == 200
    body = response.json()["progress"][0]
    next_review_at = datetime.fromisoformat(body["next_review_at"])
    if next_review_at.tzinfo is None:
        next_review_at = next_review_at.replace(tzinfo=timezone.utc)
    assert before_due <= next_review_at <= after_due
    assert body["review_streak"] == 0
    assert body["review_interval_days"] == 12
    assert body["status"] == "learned"
    assert body["is_weak"] is True
    db_session.refresh(progress)
    assert progress.weak_since == weak_since


def test_review_returns_progress_metadata(client, weak_progress):
    response = client.get("/api/learning/learner-1/review")

    assert response.status_code == 200
    word = next(item for item in response.json()["words"] if item["id"] == weak_progress.word_id)
    assert word["is_weak"] is True
    assert word["incorrect_count"] == 1


def test_complete_new_words_rejects_unknown_word_id(client):
    response = client.post("/api/learning/learner-1/new-words/complete", json={"word_ids": [999]})

    assert response.status_code == 400


def test_complete_review_rejects_unknown_word_id(client):
    response = client.post("/api/learning/learner-1/review/complete", json={"word_ids": [999]})

    assert response.status_code == 400


def test_complete_new_words_rejects_existing_word_outside_selected_session(client, seeded_words):
    response = client.post("/api/learning/learner-1/new-words/complete", json={"word_ids": [seeded_words[-1].id]})

    assert response.status_code == 400


def test_complete_review_rejects_existing_word_outside_selected_session(client, seen_today_progress):
    response = client.post("/api/learning/learner-1/review/complete", json={"word_ids": [seen_today_progress.word_id]})

    assert response.status_code == 400


def test_learning_routes_reject_too_long_user_id(client):
    response = client.get(f"/api/learning/{'x' * 81}/new-words")

    assert response.status_code == 422


@pytest.mark.parametrize(
    (
        "rating",
        "expected_interval",
        "expected_delay",
        "expected_streak",
        "expected_weak",
    ),
    [
        ("again", 0, timedelta(minutes=10), 0, True),
        ("hard", 1, timedelta(days=1), 0, True),
        ("good", 2, timedelta(days=2), 1, False),
        ("easy", 4, timedelta(days=4), 1, False),
    ],
)
def test_review_answer_applies_rating_transition(
    client,
    db_session,
    seeded_words,
    rating,
    expected_interval,
    expected_delay,
    expected_streak,
    expected_weak,
):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    weak_since = now - timedelta(days=2)
    db_session.add(UserProfile(user_id="rating-user"))
    progress = UserWordProgress(
        user_id="rating-user",
        word_id=seeded_words[0].id,
        status="reviewing",
        first_seen_at=now - timedelta(days=10),
        last_seen_at=now - timedelta(days=3),
        next_review_at=now - timedelta(minutes=1),
        review_interval_days=0,
        review_streak=0,
        is_weak=True,
        weak_since=weak_since,
    )
    db_session.add(progress)
    db_session.commit()
    before = datetime.now(timezone.utc)

    response = client.post(
        "/api/learning/rating-user/review/answers",
        json={"word_id": seeded_words[0].id, "rating": rating},
    )

    after = datetime.now(timezone.utc)
    assert response.status_code == 200
    assert set(response.json()) == {"progress"}
    body = response.json()["progress"]
    assert body["word_id"] == seeded_words[0].id
    assert body["status"] == "reviewing"
    assert body["review_interval_days"] == expected_interval
    assert body["review_streak"] == expected_streak
    assert body["is_weak"] is expected_weak
    next_review_at = datetime.fromisoformat(body["next_review_at"])
    if next_review_at.tzinfo is None:
        next_review_at = next_review_at.replace(tzinfo=timezone.utc)
    assert before + expected_delay <= next_review_at <= after + expected_delay
    db_session.refresh(progress)
    last_seen_at = progress.last_seen_at
    if last_seen_at.tzinfo is None:
        last_seen_at = last_seen_at.replace(tzinfo=timezone.utc)
    assert before <= last_seen_at <= after
    if rating in {"again", "hard"}:
        assert progress.weak_since == weak_since
    else:
        assert progress.weak_since is None


@pytest.mark.parametrize(
    ("rating", "current_interval", "expected_interval"),
    [
        ("good", 5, 10),
        ("good", 100, 180),
        ("easy", 5, 15),
        ("easy", 200, 365),
    ],
)
def test_review_rating_uses_multipliers_and_caps(
    rating, current_interval, expected_interval
):
    from app.services.learning_service import apply_review_rating

    now = datetime(2026, 7, 25, 12, tzinfo=timezone.utc)
    progress = UserWordProgress(
        review_interval_days=current_interval,
        review_streak=0,
    )

    apply_review_rating(progress, rating, now)

    assert progress.review_interval_days == expected_interval
    assert progress.next_review_at == now + timedelta(days=expected_interval)


def test_three_consecutive_good_or_easy_reviews_mark_word_learned():
    from app.services.learning_service import apply_review_rating

    now = datetime(2026, 7, 25, 12, tzinfo=timezone.utc)
    progress = UserWordProgress(
        status="seen",
        review_interval_days=0,
        review_streak=0,
    )

    apply_review_rating(progress, "good", now)
    assert progress.status == "reviewing"
    apply_review_rating(progress, "easy", now)
    assert progress.status == "reviewing"
    apply_review_rating(progress, "good", now)

    assert progress.review_streak == 3
    assert progress.status == "learned"


def test_again_sets_weak_since_when_word_was_not_already_weak():
    from app.services.learning_service import apply_review_rating

    now = datetime(2026, 7, 25, 12, tzinfo=timezone.utc)
    progress = UserWordProgress(is_weak=False, weak_since=None)

    apply_review_rating(progress, "again", now)

    assert progress.is_weak is True
    assert progress.weak_since == now


def test_review_answer_rejects_invalid_rating(client, weak_progress):
    response = client.post(
        "/api/learning/learner-1/review/answers",
        json={"word_id": weak_progress.word_id, "rating": "perfect"},
    )

    assert response.status_code == 422


def test_review_answer_rejects_unknown_word(client):
    response = client.post(
        "/api/learning/learner-1/review/answers",
        json={"word_id": 999, "rating": "good"},
    )

    assert response.status_code == 400


def test_review_answer_rejects_unseen_word(client, seeded_words):
    response = client.post(
        "/api/learning/learner-1/review/answers",
        json={"word_id": seeded_words[0].id, "rating": "good"},
    )

    assert response.status_code == 400


def test_review_answer_rejects_progress_owned_by_another_user(
    client, db_session, seeded_words
):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db_session.add(UserProfile(user_id="other-user"))
    db_session.add(
        UserWordProgress(
            user_id="other-user",
            word_id=seeded_words[0].id,
            status="reviewing",
            first_seen_at=now - timedelta(days=2),
            last_seen_at=now - timedelta(days=1),
            next_review_at=now - timedelta(minutes=1),
        )
    )
    db_session.commit()

    response = client.post(
        "/api/learning/learner-1/review/answers",
        json={"word_id": seeded_words[0].id, "rating": "good"},
    )

    assert response.status_code == 400


def test_review_answer_rejects_future_due_word_even_when_weak(
    client, db_session, seeded_words
):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db_session.add(UserProfile(user_id="future-answer"))
    db_session.add(
        UserWordProgress(
            user_id="future-answer",
            word_id=seeded_words[0].id,
            status="reviewing",
            first_seen_at=now - timedelta(days=2),
            last_seen_at=now - timedelta(days=1),
            next_review_at=now + timedelta(minutes=10),
            is_weak=True,
            weak_since=now - timedelta(days=1),
        )
    )
    db_session.commit()

    response = client.post(
        "/api/learning/future-answer/review/answers",
        json={"word_id": seeded_words[0].id, "rating": "again"},
    )

    assert response.status_code == 400
