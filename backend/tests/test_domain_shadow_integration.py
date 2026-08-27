from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.domain_models.practice import (
    ActivityInstanceModel,
    LearningEventModel,
    PracticeRunModel,
)
from app.domain_models.progress import LearnerTargetStateModel
from app.models import QuizAnswer, UserWordProgress, VocabularyItem


@pytest.fixture()
def shadow_flow(client, db_session, monkeypatch):
    from app.config import settings
    from app.services.domain_bootstrap_service import bootstrap_catalog

    words = [
        VocabularyItem(
            serbian_cyrillic=cyrillic,
            serbian_latin=latin,
            russian_translation=translation,
            cefr_level="A1",
            theme="integration",
        )
        for cyrillic, latin, translation in (
            ("кућа", "kuća", "дом"),
            ("вода", "voda", "вода"),
            ("хлеб", "hleb", "хлеб"),
            ("град", "grad", "город"),
        )
    ]
    db_session.add_all(words)
    db_session.commit()
    bootstrap_catalog(db_session)
    monkeypatch.setattr(settings, "language_assistant_shadow_enabled", True)
    return client, db_session, words


def _row_count(session, model) -> int:
    return session.scalar(select(func.count()).select_from(model))


def _correct_answer(question, session) -> str:
    word = session.get(VocabularyItem, question["word_id"])
    return {
        "sr_to_ru_choice": word.russian_translation,
        "ru_to_sr_typing": word.serbian_latin,
        "remembered_forgot_self_check": "remembered",
    }[question["question_type"]]


def test_flag_on_learning_and_quiz_share_atomic_event_history(shadow_flow) -> None:
    client, session, words = shadow_flow
    learner_id = "shadow-integration"

    learned = client.post(
        f"/api/learning/{learner_id}/new-words/complete",
        json={"word_ids": [word.id for word in words]},
    )
    assert learned.status_code == 200
    progress = session.scalar(
        select(UserWordProgress).where(
            UserWordProgress.user_id == learner_id,
            UserWordProgress.word_id == words[0].id,
        )
    )
    progress.next_review_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    session.commit()
    reviewed = client.post(
        f"/api/learning/{learner_id}/review/answers",
        json={"word_id": words[0].id, "rating": "good"},
    )
    assert reviewed.status_code == 200
    started = client.post(
        f"/api/quizzes/{learner_id}/start",
        json={"quiz_type": "daily"},
    )
    assert started.status_code == 200
    quiz = started.json()
    question = quiz["questions"][0]
    answer_url = f"/api/quizzes/{learner_id}/{quiz['attempt_id']}/answers"

    wrong = client.post(
        answer_url,
        json={
            "word_id": question["word_id"],
            "question_type": question["question_type"],
            "answer": "incorrect",
        },
    )
    corrected = client.post(
        answer_url,
        json={
            "word_id": question["word_id"],
            "question_type": question["question_type"],
            "answer": _correct_answer(question, session),
        },
    )
    assert wrong.status_code == corrected.status_code == 200

    runs = tuple(session.scalars(select(PracticeRunModel)))
    activities = tuple(session.scalars(select(ActivityInstanceModel)))
    events = tuple(session.scalars(select(LearningEventModel)))
    assert [run.status for run in runs].count("completed") == 2
    assert [run.status for run in runs].count("active") == 1
    assert len(events) == len(words) + 3
    assert len({event.activity_instance_id for event in events}) == len(events)
    assert {event.practice_run_id for event in events} <= {run.id for run in runs}
    assert {event.activity_instance_id for event in events} <= {
        activity.id for activity in activities
    }
    assert {
        event.observation_payload["legacy_source"]["kind"] for event in events
    } == {"new_word", "review", "quiz_answer"}
    assert _row_count(session, LearnerTargetStateModel) >= len(words)


def test_quiz_shadow_failure_rolls_back_without_cross_flow_orphans(
    shadow_flow,
    monkeypatch,
) -> None:
    client, session, words = shadow_flow
    learner_id = "shadow-rollback"
    client.post(
        f"/api/learning/{learner_id}/new-words/complete",
        json={"word_ids": [word.id for word in words]},
    )
    quiz = client.post(
        f"/api/quizzes/{learner_id}/start",
        json={"quiz_type": "daily"},
    ).json()
    question = quiz["questions"][0]
    answer_url = f"/api/quizzes/{learner_id}/{quiz['attempt_id']}/answers"
    before = {
        "activities": _row_count(session, ActivityInstanceModel),
        "answers": _row_count(session, QuizAnswer),
        "events": _row_count(session, LearningEventModel),
        "states": _row_count(session, LearnerTargetStateModel),
    }
    progress = session.scalar(
        select(UserWordProgress).where(
            UserWordProgress.user_id == learner_id,
            UserWordProgress.word_id == question["word_id"],
        )
    )
    legacy_before = (progress.correct_count, progress.incorrect_count, progress.is_weak)

    from app.services.shadow_quiz_service import ShadowQuizService

    with monkeypatch.context() as patch:
        patch.setattr(
            ShadowQuizService,
            "record_answer",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                RuntimeError("injected shadow event failure")
            ),
        )
        with pytest.raises(RuntimeError, match="injected shadow event failure"):
            client.post(
                answer_url,
                json={
                    "word_id": question["word_id"],
                    "question_type": question["question_type"],
                    "answer": "incorrect",
                },
            )

    session.expire_all()
    progress = session.get(UserWordProgress, progress.id)
    assert (progress.correct_count, progress.incorrect_count, progress.is_weak) == (
        legacy_before
    )
    assert {
        "activities": _row_count(session, ActivityInstanceModel),
        "answers": _row_count(session, QuizAnswer),
        "events": _row_count(session, LearningEventModel),
        "states": _row_count(session, LearnerTargetStateModel),
    } == before

    accepted = client.post(
        answer_url,
        json={
            "word_id": question["word_id"],
            "question_type": question["question_type"],
            "answer": "incorrect",
        },
    )
    assert accepted.status_code == 200
    assert _row_count(session, QuizAnswer) == before["answers"] + 1
    assert _row_count(session, LearningEventModel) == before["events"] + 1


def test_replay_and_comparison_failure_preserve_committed_shadow_state(
    shadow_flow,
) -> None:
    client, session, words = shadow_flow
    learner_id = "shadow-replay"
    occurred_at = datetime.now(timezone.utc)
    client.post(
        f"/api/learning/{learner_id}/new-words/complete",
        json={"word_ids": [word.id for word in words]},
    )
    progress_rows = tuple(
        session.scalars(
            select(UserWordProgress)
            .where(UserWordProgress.user_id == learner_id)
            .order_by(UserWordProgress.id)
        )
    )
    before = (
        _row_count(session, PracticeRunModel),
        _row_count(session, ActivityInstanceModel),
        _row_count(session, LearningEventModel),
        _row_count(session, LearnerTargetStateModel),
    )

    from app.services.domain_shadow_contracts import ShadowAdapterStatus
    from app.services.shadow_comparison_service import (
        LegacyLearningSelection,
        LegacyLearningSelectionKind,
        ShadowComparisonService,
    )
    from app.services.shadow_learning_service import record_new_word_batch

    duplicate = record_new_word_batch(
        session,
        learner_id=learner_id,
        progress_rows=progress_rows,
        occurred_at=occurred_at,
    )
    assert duplicate.status is ShadowAdapterStatus.DUPLICATE
    comparison = ShadowComparisonService().compare(
        legacy_selection=LegacyLearningSelection(
            LegacyLearningSelectionKind.NEW,
            progress_rows[0].user_id,
        ),
        select_shadow=lambda: (_ for _ in ()).throw(
            RuntimeError("diagnostic failure")
        ),
    )
    assert comparison is None
    assert (
        _row_count(session, PracticeRunModel),
        _row_count(session, ActivityInstanceModel),
        _row_count(session, LearningEventModel),
        _row_count(session, LearnerTargetStateModel),
    ) == before
