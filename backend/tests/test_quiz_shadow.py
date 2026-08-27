import os
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import select


@pytest.fixture(autouse=True)
def isolate_legacy_learning_setup_when_shadow_is_enabled_from_environment(
    client,
    monkeypatch,
) -> None:
    from app.config import settings

    original_post = client.post

    def post(url, *args, **kwargs):
        if (
            settings.language_assistant_shadow_enabled
            and str(url).endswith("/new-words/complete")
        ):
            settings.language_assistant_shadow_enabled = False
            try:
                return original_post(url, *args, **kwargs)
            finally:
                settings.language_assistant_shadow_enabled = True
        return original_post(url, *args, **kwargs)

    monkeypatch.setattr(client, "post", post)


@pytest.fixture()
def postgresql_quiz_database():
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    admin_url_value = os.getenv("SLOVNIK_TEST_POSTGRES_ADMIN_URL")
    if not admin_url_value:
        pytest.skip("SLOVNIK_TEST_POSTGRES_ADMIN_URL is not configured")
    admin_url = make_url(admin_url_value)
    if admin_url.get_backend_name() != "postgresql":
        raise ValueError("SLOVNIK_TEST_POSTGRES_ADMIN_URL must use PostgreSQL")

    database_name = f"slovnik_quiz_shadow_test_{uuid4().hex}"
    test_database_url = admin_url.set(database=database_name)
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    test_engine = None
    database_created = False
    try:
        with admin_engine.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{database_name}"'))
        database_created = True
        test_engine = create_engine(test_database_url)
        from app.db import Base, load_model_registry

        load_model_registry()
        Base.metadata.create_all(test_engine)
        yield test_engine
    finally:
        if test_engine is not None:
            test_engine.dispose()
        if database_created:
            with admin_engine.connect() as connection:
                connection.execute(
                    text(
                        """
                        SELECT pg_terminate_backend(pid)
                        FROM pg_stat_activity
                        WHERE datname = :database_name
                          AND pid <> pg_backend_pid()
                        """
                    ),
                    {"database_name": database_name},
                )
                connection.execute(text(f'DROP DATABASE "{database_name}"'))
        admin_engine.dispose()


def _answer_for(question, db_session) -> str:
    from app.models import VocabularyItem

    word = db_session.get(VocabularyItem, question["word_id"])
    return {
        "sr_to_ru_choice": word.russian_translation,
        "ru_to_sr_typing": word.serbian_latin,
        "remembered_forgot_self_check": "remembered",
    }[question["question_type"]]


def _enable_shadow(db_session, monkeypatch) -> None:
    from app.config import settings
    from app.services.domain_bootstrap_service import bootstrap_catalog

    bootstrap_catalog(db_session)
    monkeypatch.setattr(settings, "language_assistant_shadow_enabled", True)


def test_flag_on_start_creates_one_linked_active_run(
    client,
    db_session,
    completed_learning,
    monkeypatch,
) -> None:
    from app.domain_models.practice import PracticeRunModel

    _enable_shadow(db_session, monkeypatch)

    response = client.post(
        "/api/quizzes/learner-1/start",
        json={"quiz_type": "daily"},
    )

    assert response.status_code == 200
    runs = tuple(db_session.scalars(select(PracticeRunModel)))
    assert len(runs) == 1
    assert runs[0].legacy_quiz_attempt_id == response.json()["attempt_id"]
    assert runs[0].learner_id == "learner-1"
    assert runs[0].status == "active"
    assert runs[0].selection_policy_version == "legacy-quiz-v1"


def test_stale_catalog_mapping_aborts_quiz_start_without_rows(
    client,
    db_session,
    completed_learning,
    monkeypatch,
) -> None:
    from app.domain_models.practice import PracticeRunModel
    from app.models import QuizAttempt
    from app.services.shadow_quiz_service import ShadowQuizFailure

    _enable_shadow(db_session, monkeypatch)
    completed_learning[0].russian_translation = "изменённый перевод"
    db_session.commit()

    with pytest.raises(ShadowQuizFailure, match="Shadow quiz operation failed"):
        client.post(
            "/api/quizzes/learner-1/start",
            json={"quiz_type": "daily"},
        )

    assert not tuple(db_session.scalars(select(QuizAttempt)))
    assert not tuple(db_session.scalars(select(PracticeRunModel)))


def test_catalog_edit_after_quiz_start_aborts_answer_evidence(
    client,
    db_session,
    completed_learning,
    monkeypatch,
) -> None:
    from app.domain_models.practice import LearningEventModel
    from app.models import QuizAnswer, VocabularyItem
    from app.services.shadow_quiz_service import ShadowQuizFailure

    _enable_shadow(db_session, monkeypatch)
    started = client.post(
        "/api/quizzes/learner-1/start", json={"quiz_type": "daily"}
    ).json()
    question = started["questions"][0]
    word = db_session.get(VocabularyItem, question["word_id"])
    word.russian_translation = "изменённый перевод"
    db_session.commit()

    with pytest.raises(ShadowQuizFailure, match="Shadow quiz operation failed"):
        client.post(
            f"/api/quizzes/learner-1/{started['attempt_id']}/answers",
            json={**question, "answer": "ответ"},
        )

    assert not tuple(db_session.scalars(select(QuizAnswer)))
    assert not tuple(db_session.scalars(select(LearningEventModel)))


def test_flag_on_empty_quiz_preserves_legacy_completion_without_synthetic_run(
    client,
    db_session,
    seeded_words,
    monkeypatch,
) -> None:
    from app.domain_models.practice import PracticeRunModel

    _enable_shadow(db_session, monkeypatch)

    started = client.post(
        "/api/quizzes/new-learner/start",
        json={"quiz_type": "daily"},
    )
    assert started.status_code == 200
    assert started.json()["questions"] == []
    assert not tuple(db_session.scalars(select(PracticeRunModel)))

    completed = client.post(
        f"/api/quizzes/new-learner/{started.json()['attempt_id']}/complete"
    )
    assert completed.status_code == 200
    assert completed.json()["total_questions"] == 0


def test_flag_enabled_after_legacy_start_keeps_attempt_legacy_only(
    client,
    db_session,
    completed_learning,
    monkeypatch,
) -> None:
    from app.config import settings
    from app.domain_models.practice import LearningEventModel, PracticeRunModel

    monkeypatch.setattr(settings, "language_assistant_shadow_enabled", False)
    started = client.post(
        "/api/quizzes/learner-1/start", json={"quiz_type": "daily"}
    ).json()
    monkeypatch.setattr(settings, "language_assistant_shadow_enabled", True)
    question = started["questions"][0]

    response = client.post(
        f"/api/quizzes/learner-1/{started['attempt_id']}/answers",
        json={**question, "answer": _answer_for(question, db_session)},
    )

    assert response.status_code == 200
    assert not tuple(db_session.scalars(select(PracticeRunModel)))
    assert not tuple(db_session.scalars(select(LearningEventModel)))


def test_flag_gap_abandons_shadow_run_and_continues_legacy(
    client,
    db_session,
    completed_learning,
    monkeypatch,
    caplog,
) -> None:
    from app.config import settings
    from app.domain_models.practice import LearningEventModel, PracticeRunModel

    _enable_shadow(db_session, monkeypatch)
    started = client.post(
        "/api/quizzes/learner-1/start", json={"quiz_type": "daily"}
    ).json()
    first, second = started["questions"][:2]
    monkeypatch.setattr(settings, "language_assistant_shadow_enabled", False)
    assert client.post(
        f"/api/quizzes/learner-1/{started['attempt_id']}/answers",
        json={**first, "answer": _answer_for(first, db_session)},
    ).status_code == 200
    monkeypatch.setattr(settings, "language_assistant_shadow_enabled", True)

    response = client.post(
        f"/api/quizzes/learner-1/{started['attempt_id']}/answers",
        json={**second, "answer": _answer_for(second, db_session)},
    )

    assert response.status_code == 200
    run = db_session.scalar(select(PracticeRunModel))
    assert run.status == "abandoned"
    assert not tuple(db_session.scalars(select(LearningEventModel)))
    assert "quiz_shadow_enrollment_gap" in caplog.text


def test_flag_on_start_snapshots_each_planned_question_without_events(
    client,
    db_session,
    completed_learning,
    monkeypatch,
) -> None:
    from app.domain_models.practice import ActivityInstanceModel, LearningEventModel

    _enable_shadow(db_session, monkeypatch)

    payload = client.post(
        "/api/quizzes/learner-1/start",
        json={"quiz_type": "daily"},
    ).json()

    activities = tuple(
        db_session.scalars(
            select(ActivityInstanceModel).order_by(ActivityInstanceModel.sequence_number)
        )
    )
    assert len(activities) == len(payload["questions"])
    assert tuple(row.sequence_number for row in activities) == tuple(
        range(1, len(activities) + 1)
    )
    assert not tuple(db_session.scalars(select(LearningEventModel)))
    for row, question in zip(activities, payload["questions"], strict=True):
        snapshot = row.spec_payload["snapshot"]
        assert row.status == "pending"
        assert row.learning_intent == "assess"
        assert row.selection_reason_payload == ["legacy_quiz"]
        assert snapshot == {
            "answer_version": 1,
            "choices": question["choices"],
            "legacy_question_type": question["question_type"],
            "legacy_word_id": question["word_id"],
            "plan_index": row.sequence_number - 1,
            "prompt": question["prompt"],
        }
        target = row.spec_payload["target_spec"]
        assert target["target_kind"] == "sense"
        assert target["modality"] == "written"
        expected_capability = (
            "retrieve_form"
            if question["question_type"] == "ru_to_sr_typing"
            else "recognize_meaning"
        )
        assert target["capability"] == expected_capability
        if question["question_type"] == "remembered_forgot_self_check":
            assert row.scorer_kind == "self_report"
        else:
            assert row.scorer_kind == "deterministic"


def test_accepted_answers_create_exact_events_and_complete_their_activities(
    client,
    db_session,
    completed_learning,
    monkeypatch,
) -> None:
    from app.domain_models.practice import ActivityInstanceModel, LearningEventModel
    from app.models import QuizAnswer

    _enable_shadow(db_session, monkeypatch)
    started = client.post(
        "/api/quizzes/learner-1/start", json={"quiz_type": "daily"}
    ).json()

    for question in started["questions"]:
        response = client.post(
            f"/api/quizzes/learner-1/{started['attempt_id']}/answers",
            json={
                "word_id": question["word_id"],
                "question_type": question["question_type"],
                "answer": _answer_for(question, db_session),
            },
        )
        assert response.status_code == 200

    answers = tuple(db_session.scalars(select(QuizAnswer).order_by(QuizAnswer.id)))
    events = tuple(db_session.scalars(select(LearningEventModel)))
    events_by_answer_id = {
        int(event.observation_payload["legacy_source"]["reference"]): event
        for event in events
    }
    activities = {
        row.id: row for row in db_session.scalars(select(ActivityInstanceModel))
    }
    assert len(events) == len(answers) == len(started["questions"])
    for answer in answers:
        event = events_by_answer_id[answer.id]
        observation = event.observation_payload
        activity = activities[event.activity_instance_id]
        assert event.idempotency_key == f"legacy:quiz-answer:{answer.id}"
        assert event.event_type == "response_evaluated"
        assert event.learner_id == "learner-1"
        assert activity.status == "completed"
        assert observation["legacy_source"] == {
            "kind": "quiz_answer",
            "reference": str(answer.id),
        }
        if answer.question_type == "remembered_forgot_self_check":
            assert observation["evaluation_source"] == "self_report"
            assert observation["evaluation_outcome"] == "unknown"
            assert observation["first_response"]["kind"] == "rating"
            assert observation["first_response"]["value"] == "good"
        else:
            assert observation["evaluation_source"] == "deterministic"
            assert observation["evaluation_outcome"] == "correct"


def test_incorrect_answer_creates_chronological_retry_owned_by_second_event(
    client,
    db_session,
    completed_learning,
    monkeypatch,
) -> None:
    from app.domain_models.practice import ActivityInstanceModel, LearningEventModel
    from app.domain_models.progress import LearnerTargetStateModel
    from app.models import QuizAnswer
    from app.services.shadow_quiz_service import ShadowQuizService

    _enable_shadow(db_session, monkeypatch)
    started = client.post(
        "/api/quizzes/learner-1/start", json={"quiz_type": "daily"}
    ).json()
    question = started["questions"][0]
    payload = {
        "word_id": question["word_id"],
        "question_type": question["question_type"],
        "answer": "wrong",
    }

    assert client.post(
        f"/api/quizzes/learner-1/{started['attempt_id']}/answers", json=payload
    ).status_code == 200
    after_first = tuple(
        db_session.scalars(
            select(ActivityInstanceModel).order_by(ActivityInstanceModel.sequence_number)
        )
    )
    retry = after_first[-1]
    original = next(
        row
        for row in after_first
        if row.spec_payload["snapshot"]["plan_index"] == 0
        and row.retry_of_activity_instance_id is None
    )
    assert original.status == "completed"
    assert retry.status == "pending"
    assert retry.retry_of_activity_instance_id == original.id
    assert retry.attempt_number == 2
    assert retry.sequence_number == len(started["questions"]) + 1
    first_answer = db_session.scalar(select(QuizAnswer))
    duplicate = ShadowQuizService(db_session).record_answer(
        first_answer,
        create_retry=True,
    )
    assert duplicate.idempotency_key == f"legacy:quiz-answer:{first_answer.id}"
    assert len(tuple(db_session.scalars(select(ActivityInstanceModel)))) == len(
        after_first
    )
    assert len(tuple(db_session.scalars(select(LearningEventModel)))) == 1

    corrected_payload = {
        **payload,
        "answer": _answer_for(question, db_session),
    }
    assert client.post(
        f"/api/quizzes/learner-1/{started['attempt_id']}/answers",
        json=corrected_payload,
    ).status_code == 200
    events = tuple(db_session.scalars(select(LearningEventModel)))
    assert len(events) == 2
    assert {event.activity_instance_id for event in events} == {original.id, retry.id}
    events_by_answer_id = {
        int(event.observation_payload["legacy_source"]["reference"]): event
        for event in events
    }
    answer_ids = tuple(
        db_session.scalars(select(QuizAnswer.id).order_by(QuizAnswer.id))
    )
    assert events_by_answer_id[answer_ids[0]].occurred_at < events_by_answer_id[
        answer_ids[1]
    ].occurred_at
    assert events_by_answer_id[answer_ids[1]].id < events_by_answer_id[answer_ids[0]].id
    state = db_session.scalar(
        select(LearnerTargetStateModel).where(
            LearnerTargetStateModel.target_key
            == events_by_answer_id[answer_ids[1]].target_key
        )
    )
    assert state.memory_due_at > events_by_answer_id[answer_ids[1]].occurred_at
    db_session.refresh(retry)
    assert retry.status == "completed"


def test_unbounded_legacy_choice_is_recorded_as_bounded_shadow_response(
    client,
    db_session,
    completed_learning,
    monkeypatch,
) -> None:
    from app.domain_models.practice import LearningEventModel

    _enable_shadow(db_session, monkeypatch)
    started = client.post(
        "/api/quizzes/learner-1/start", json={"quiz_type": "daily"}
    ).json()
    question = next(
        item
        for item in started["questions"]
        if item["question_type"] == "sr_to_ru_choice"
    )
    for answer in ("", "x" * 121):
        response = client.post(
            f"/api/quizzes/learner-1/{started['attempt_id']}/answers",
            json={
                "word_id": question["word_id"],
                "question_type": question["question_type"],
                "answer": answer,
            },
        )
        assert response.status_code == 200

    events = tuple(db_session.scalars(select(LearningEventModel)))
    assert len(events) == 2
    for event in events:
        response = event.observation_payload["first_response"]
        assert response["kind"] == "choice"
        assert 1 <= len(response["value"]) <= 120
        assert response["value"].startswith("legacy-choice-sha256:")


def test_forgot_self_check_maps_to_again_without_competence_gain(
    client,
    db_session,
    completed_learning,
    monkeypatch,
) -> None:
    from app.domain_models.practice import ActivityInstanceModel, LearningEventModel
    from app.domain_models.progress import LearnerTargetStateModel

    _enable_shadow(db_session, monkeypatch)
    started = client.post(
        "/api/quizzes/learner-1/start", json={"quiz_type": "daily"}
    ).json()
    question = next(
        item
        for item in started["questions"]
        if item["question_type"] == "remembered_forgot_self_check"
    )

    response = client.post(
        f"/api/quizzes/learner-1/{started['attempt_id']}/answers",
        json={
            "word_id": question["word_id"],
            "question_type": question["question_type"],
            "answer": "forgot",
        },
    )

    assert response.status_code == 200
    event = db_session.scalar(select(LearningEventModel))
    activity = db_session.get(ActivityInstanceModel, event.activity_instance_id)
    state = db_session.scalar(
        select(LearnerTargetStateModel).where(
            LearnerTargetStateModel.target_key == event.target_key
        )
    )
    assert activity.scorer_kind == "self_report"
    assert activity.scorer_version == "memory-v1"
    assert event.observation_payload["first_response"] == {
        "kind": "rating",
        "value": "again",
        "truncated": False,
    }
    assert state.competence_success_weight == 0
    assert state.competence_failure_weight == 0
    assert state.memory_lapses == 1
    assert state.memory_due_at is not None


def test_domain_run_completion_follows_successful_legacy_completion(
    client,
    db_session,
    completed_learning,
    monkeypatch,
) -> None:
    from app.domain_models.practice import LearningEventModel, PracticeRunModel
    from app.models import QuizAnswer

    _enable_shadow(db_session, monkeypatch)
    started = client.post(
        "/api/quizzes/learner-1/start", json={"quiz_type": "daily"}
    ).json()
    for question in started["questions"]:
        payload = {
            "word_id": question["word_id"],
            "question_type": question["question_type"],
            "answer": "wrong",
        }
        client.post(
            f"/api/quizzes/learner-1/{started['attempt_id']}/answers", json=payload
        )
        client.post(
            f"/api/quizzes/learner-1/{started['attempt_id']}/answers", json=payload
        )

    run = db_session.scalar(select(PracticeRunModel))
    assert run.status == "active"
    assert client.post(
        f"/api/quizzes/learner-1/{started['attempt_id']}/complete"
    ).status_code == 200
    db_session.refresh(run)
    assert run.status == "completed"
    assert run.ended_at is not None
    answer_count = len(tuple(db_session.scalars(select(QuizAnswer))))
    event_count = len(tuple(db_session.scalars(select(LearningEventModel))))
    question = started["questions"][0]
    rejected = client.post(
        f"/api/quizzes/learner-1/{started['attempt_id']}/answers",
        json={
            "word_id": question["word_id"],
            "question_type": question["question_type"],
            "answer": "wrong",
        },
    )
    assert rejected.status_code == 400
    assert len(tuple(db_session.scalars(select(QuizAnswer)))) == answer_count
    assert len(tuple(db_session.scalars(select(LearningEventModel)))) == event_count


def test_shadow_failure_rolls_back_legacy_answer_and_progress(
    client,
    db_session,
    completed_learning,
    monkeypatch,
) -> None:
    from app.domain_models.practice import ActivityInstanceModel, LearningEventModel
    from app.models import QuizAnswer, UserWordProgress
    from app.services import shadow_quiz_service

    _enable_shadow(db_session, monkeypatch)
    started = client.post(
        "/api/quizzes/learner-1/start", json={"quiz_type": "daily"}
    ).json()
    question = started["questions"][0]
    progress = db_session.scalar(
        select(UserWordProgress).where(
            UserWordProgress.user_id == "learner-1",
            UserWordProgress.word_id == question["word_id"],
        )
    )
    before = (progress.correct_count, progress.incorrect_count, progress.is_weak)

    secret = "SECRET-ANSWER-AND-PROVIDER-PAYLOAD"

    def fail_after_shadow_event_write(self, event):
        raise RuntimeError(secret)

    monkeypatch.setattr(
        shadow_quiz_service.LearnerProjectionService,
        "apply_event",
        fail_after_shadow_event_write,
    )
    from app.services.shadow_quiz_service import ShadowQuizFailure

    with pytest.raises(ShadowQuizFailure, match="Shadow quiz operation failed") as error:
        client.post(
            f"/api/quizzes/learner-1/{started['attempt_id']}/answers",
            json={
                "word_id": question["word_id"],
                "question_type": question["question_type"],
                "answer": secret,
            },
        )

    assert secret not in "".join(traceback.format_exception(error.value))
    assert error.value.__cause__ is None
    assert error.value.__suppress_context__ is True

    current = db_session.scalar(
        select(UserWordProgress).where(
            UserWordProgress.user_id == "learner-1",
            UserWordProgress.word_id == question["word_id"],
        )
    )
    assert (current.correct_count, current.incorrect_count, current.is_weak) == before
    assert not tuple(db_session.scalars(select(QuizAnswer)))
    assert not tuple(db_session.scalars(select(LearningEventModel)))
    activities = tuple(db_session.scalars(select(ActivityInstanceModel)))
    assert len(activities) == len(started["questions"])
    assert all(activity.status == "pending" for activity in activities)


def test_rejected_shadow_answers_create_no_legacy_or_domain_rows(
    client,
    db_session,
    completed_learning,
    seeded_words,
    monkeypatch,
) -> None:
    from app.domain_models.practice import LearningEventModel
    from app.models import QuizAnswer

    _enable_shadow(db_session, monkeypatch)
    started = client.post(
        "/api/quizzes/learner-1/start", json={"quiz_type": "daily"}
    ).json()
    question = started["questions"][0]

    wrong_user = client.post(
        f"/api/quizzes/learner-2/{started['attempt_id']}/answers",
        json={**question, "answer": "wrong"},
    )
    out_of_plan = client.post(
        f"/api/quizzes/learner-1/{started['attempt_id']}/answers",
        json={
            "word_id": seeded_words[-1].id,
            "question_type": question["question_type"],
            "answer": "wrong",
        },
    )

    assert wrong_user.status_code == 404
    assert out_of_plan.status_code == 400
    assert not tuple(db_session.scalars(select(QuizAnswer)))
    assert not tuple(db_session.scalars(select(LearningEventModel)))


def test_concurrent_first_quiz_answers(postgresql_quiz_database, monkeypatch) -> None:
    from datetime import datetime, timezone

    from sqlalchemy.orm import sessionmaker

    from app.config import settings
    from app.domain_models.practice import LearningEventModel
    from app.models import QuizAnswer, UserProfile, UserWordProgress, VocabularyItem
    from app.services.domain_bootstrap_service import bootstrap_catalog
    from app.services.quiz_service import InvalidQuizSubmission, start_quiz, submit_answer

    SessionFactory = sessionmaker(bind=postgresql_quiz_database, expire_on_commit=False)
    with SessionFactory() as session:
        words = [
            VocabularyItem(
                serbian_cyrillic=f"реч {index}",
                serbian_latin=f"rec {index}",
                russian_translation=f"слово {index}",
                cefr_level="A1",
                theme="daily",
            )
            for index in range(1, 5)
        ]
        session.add(UserProfile(user_id="learner-1"))
        session.add_all(words)
        session.flush()
        for word in words:
            session.add(
                UserWordProgress(
                    user_id="learner-1",
                    word_id=word.id,
                    status="seen",
                    first_seen_at=datetime.now(timezone.utc),
                )
            )
        session.commit()
        bootstrap_catalog(session)
        monkeypatch.setattr(settings, "language_assistant_shadow_enabled", True)
        started = start_quiz(session, "learner-1", "daily")
        question = started["questions"][0]
        word = session.get(VocabularyItem, question["word_id"])
        answer = word.russian_translation

    barrier = threading.Barrier(2)

    def submit():
        with SessionFactory() as session:
            barrier.wait(timeout=10)
            try:
                return submit_answer(
                    session,
                    "learner-1",
                    started["attempt_id"],
                    question["word_id"],
                    question["question_type"],
                    answer,
                )
            except InvalidQuizSubmission as exc:
                return exc

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(executor.map(lambda _: submit(), range(2)))

    assert sum(isinstance(result, dict) for result in results) == 1
    errors = [result for result in results if isinstance(result, InvalidQuizSubmission)]
    assert len(errors) == 1
    assert str(errors[0]) == "Question has already reached its answer limit"
    with SessionFactory() as session:
        assert len(tuple(session.scalars(select(QuizAnswer)))) == 1
        assert len(tuple(session.scalars(select(LearningEventModel)))) == 1
