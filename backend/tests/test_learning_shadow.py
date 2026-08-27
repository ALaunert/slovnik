from __future__ import annotations

import os
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.domain_models.practice import (
    ActivityInstanceModel,
    LearningEventModel,
    PracticeRunModel,
)
from app.domain_models.catalog import LanguageLexicalUnit, LanguageSense
from app.domain_models.progress import LearnerTargetStateModel
from app.models import UserProfile, UserWordProgress, VocabularyItem
from app.services.domain_bootstrap_service import bootstrap_catalog


@pytest.fixture()
def shadow_words(db_session):
    values = [
        VocabularyItem(
            serbian_cyrillic="реч",
            serbian_latin="reč",
            russian_translation="слово",
            cefr_level="A1",
            theme="shadow",
        ),
        VocabularyItem(
            serbian_cyrillic="вода",
            serbian_latin="voda",
            russian_translation="вода",
            cefr_level="A1",
            theme="shadow",
        ),
    ]
    db_session.add_all(values)
    db_session.commit()
    bootstrap_catalog(db_session)
    return values


def _utc(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def test_new_word_batch_records_one_exposure_event_per_accepted_word(
    client,
    db_session,
    shadow_words,
    monkeypatch,
) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "language_assistant_shadow_enabled", True)

    response = client.post(
        "/api/learning/shadow-new/new-words/complete",
        json={"word_ids": [shadow_words[1].id, shadow_words[0].id]},
    )

    assert response.status_code == 200
    assert db_session.scalar(select(func.count()).select_from(LearningEventModel)) == 2


def test_empty_new_word_completion_remains_a_legacy_noop_when_shadow_is_on(
    client,
    db_session,
    monkeypatch,
) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "language_assistant_shadow_enabled", True)

    response = client.post(
        "/api/learning/shadow-empty/new-words/complete",
        json={"word_ids": []},
    )

    assert response.status_code == 200
    assert response.json() == {"progress": []}
    assert db_session.scalar(select(func.count()).select_from(PracticeRunModel)) == 0


def test_duplicate_word_ids_preserve_legacy_response_and_dedupe_shadow_evidence(
    client,
    db_session,
    shadow_words,
    monkeypatch,
) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "language_assistant_shadow_enabled", True)

    response = client.post(
        "/api/learning/shadow-duplicate/new-words/complete",
        json={"word_ids": [shadow_words[0].id, shadow_words[0].id]},
    )

    assert response.status_code == 200
    assert [item["word_id"] for item in response.json()["progress"]] == [
        shadow_words[0].id,
        shadow_words[0].id,
    ]
    assert db_session.scalar(select(func.count()).select_from(LearningEventModel)) == 1
    assert db_session.scalar(select(func.count()).select_from(ActivityInstanceModel)) == 1


def test_new_word_batch_preserves_order_mapping_metadata_and_memory_only_projection(
    client,
    db_session,
    shadow_words,
    monkeypatch,
) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "language_assistant_shadow_enabled", True)

    response = client.post(
        "/api/learning/shadow-mapping/new-words/complete",
        json={"word_ids": [shadow_words[1].id, shadow_words[0].id]},
    )

    assert response.status_code == 200
    run = db_session.scalar(select(PracticeRunModel))
    activities = tuple(
        db_session.scalars(
            select(ActivityInstanceModel).order_by(ActivityInstanceModel.sequence_number)
        )
    )
    events = tuple(
        db_session.scalars(
            select(LearningEventModel).order_by(LearningEventModel.occurred_at)
        )
    )
    states = tuple(
        db_session.scalars(
            select(LearnerTargetStateModel).order_by(LearnerTargetStateModel.target_key)
        )
    )
    progress_due_by_word = {
        item["word_id"]: _utc(item["next_review_at"])
        for item in response.json()["progress"]
    }

    assert run.status == "completed"
    assert [activity.sequence_number for activity in activities] == [1, 2]
    assert [
        activity.spec_payload["snapshot"]["citation_form"]["orthographies"][0][
            "text"
        ]
        for activity in activities
    ] == [shadow_words[1].serbian_cyrillic, shadow_words[0].serbian_cyrillic]
    assert all(
        activity.spec_payload["target_spec"]["target_kind"] == "sense"
        and activity.spec_payload["target_spec"]["capability"] == "retrieve_form"
        and activity.learning_intent == "acquire"
        and activity.activity_kind == "exposure"
        and activity.operation is None
        and activity.scorer_kind is None
        and activity.selection_policy_version == "legacy-new-word-v1"
        and activity.selection_reason_payload == ["legacy_new_word"]
        and activity.status == "completed"
        for activity in activities
    )
    assert all(
        event.event_type == "exposure"
        and event.observation_payload["legacy_source"]["kind"] == "new_word"
        and event.observation_payload["evaluation_source"] is None
        for event in events
    )
    assert len(states) == 2
    assert all(
        state.competence_success_weight == 0
        and state.competence_failure_weight == 0
        and state.competence_peak == 0
        and state.evidence_count == 1
        and state.memory_interval_days == 1
        and _utc(state.memory_due_at)
        in set(progress_due_by_word.values())
        for state in states
    )


def test_shadow_event_creation_and_receipt_use_database_clock(
    client,
    db_session,
    shadow_words,
    monkeypatch,
) -> None:
    from app.config import settings
    from app.repositories.practice import PracticeRepository
    from app.services import shadow_learning_service

    database_now = datetime.now(timezone.utc) + timedelta(minutes=1)
    captured_timestamps = []
    build_event = shadow_learning_service.build_learning_event

    def capture_timestamps(activity, request, *, created_at, received_at):
        captured_timestamps.append((created_at, received_at))
        return build_event(
            activity,
            request,
            created_at=created_at,
            received_at=received_at,
        )

    monkeypatch.setattr(settings, "language_assistant_shadow_enabled", True)
    monkeypatch.setattr(
        PracticeRepository,
        "database_now",
        lambda self: database_now,
    )
    monkeypatch.setattr(
        shadow_learning_service,
        "build_learning_event",
        capture_timestamps,
    )

    response = client.post(
        "/api/learning/shadow-db-clock/new-words/complete",
        json={"word_ids": [shadow_words[0].id]},
    )

    event = db_session.scalar(select(LearningEventModel))
    assert response.status_code == 200
    assert _utc(event.created_at) == database_now
    assert captured_timestamps == [(database_now, database_now)]


@pytest.mark.parametrize(
    ("rating", "expected_interval"),
    [("again", 0), ("hard", 1), ("good", 2), ("easy", 4)],
)
def test_review_rating_records_one_self_report_event_and_memory_only_projection(
    db_session,
    shadow_words,
    monkeypatch,
    rating,
    expected_interval,
) -> None:
    from app.config import settings
    from app.services.learning_service import grade_review

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    progress = UserWordProgress(
        user_id="shadow-review",
        word_id=shadow_words[0].id,
        status="reviewing",
        first_seen_at=now - timedelta(days=2),
        last_seen_at=now - timedelta(days=1),
        next_review_at=now - timedelta(minutes=1),
        review_interval_days=0,
    )
    db_session.add(UserProfile(user_id="shadow-review"))
    db_session.add(progress)
    db_session.commit()
    monkeypatch.setattr(settings, "language_assistant_shadow_enabled", True)

    result = grade_review(
        db_session,
        "shadow-review",
        shadow_words[0].id,
        rating,
    )

    event = db_session.scalar(select(LearningEventModel))
    activity = db_session.scalar(select(ActivityInstanceModel))
    run = db_session.scalar(select(PracticeRunModel))
    state = db_session.scalar(select(LearnerTargetStateModel))
    assert result.review_interval_days == expected_interval
    assert event.event_type == "response_evaluated"
    assert event.observation_payload["evaluation_source"] == "self_report"
    assert event.observation_payload["evaluation_outcome"] == "unknown"
    assert event.observation_payload["first_response"] == {
        "kind": "rating",
        "value": rating,
        "truncated": False,
    }
    assert event.observation_payload["legacy_source"]["kind"] == "review"
    assert activity.learning_intent == "review"
    assert activity.operation == "retrieve"
    assert activity.scorer_kind == "self_report"
    assert activity.scorer_version == "memory-v1"
    assert activity.selection_policy_version == "legacy-review-v1"
    assert activity.selection_reason_payload == ["legacy_review"]
    assert activity.status == "completed"
    assert run.status == "completed"
    assert state.competence_success_weight == 0
    assert state.competence_failure_weight == 0
    assert state.competence_peak == 0
    assert state.evidence_count == 1
    assert state.memory_interval_days == expected_interval
    assert _utc(state.memory_due_at) == _utc(result.next_review_at)


def test_new_word_shadow_retry_returns_original_evidence_without_orphans(
    client,
    db_session,
    shadow_words,
    monkeypatch,
) -> None:
    from app.config import settings
    from app.services.domain_shadow_contracts import ShadowAdapterStatus
    from app.services.shadow_learning_service import record_new_word_batch

    monkeypatch.setattr(settings, "language_assistant_shadow_enabled", True)
    response = client.post(
        "/api/learning/shadow-new-retry/new-words/complete",
        json={"word_ids": [shadow_words[0].id]},
    )
    progress = db_session.scalar(
        select(UserWordProgress).where(
            UserWordProgress.user_id == "shadow-new-retry"
        )
    )
    original_event = db_session.scalar(select(LearningEventModel))
    mapping = db_session.scalar(
        select(LanguageLexicalUnit).where(
            LanguageLexicalUnit.legacy_vocabulary_item_id == shadow_words[0].id
        )
    )
    db_session.delete(mapping)
    db_session.commit()

    duplicate = record_new_word_batch(
        db_session,
        learner_id="shadow-new-retry",
        progress_rows=(progress,),
        occurred_at=datetime.now(timezone.utc),
    )

    assert response.status_code == 200
    assert duplicate.status is ShadowAdapterStatus.DUPLICATE
    assert duplicate.practice_run_id == original_event.practice_run_id
    assert duplicate.event_ids == (original_event.id,)
    assert db_session.scalar(select(func.count()).select_from(PracticeRunModel)) == 1
    assert db_session.scalar(select(func.count()).select_from(ActivityInstanceModel)) == 1
    assert db_session.scalar(select(func.count()).select_from(LearningEventModel)) == 1


def test_review_lost_response_retry_creates_no_second_event(
    client,
    db_session,
    shadow_words,
    monkeypatch,
) -> None:
    from app.config import settings

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db_session.add(UserProfile(user_id="shadow-review-retry"))
    db_session.add(
        UserWordProgress(
            user_id="shadow-review-retry",
            word_id=shadow_words[0].id,
            status="reviewing",
            first_seen_at=now - timedelta(days=2),
            last_seen_at=now - timedelta(days=1),
            next_review_at=now - timedelta(minutes=1),
        )
    )
    db_session.commit()
    monkeypatch.setattr(settings, "language_assistant_shadow_enabled", True)

    first = client.post(
        "/api/learning/shadow-review-retry/review/answers",
        json={"word_id": shadow_words[0].id, "rating": "good"},
    )
    second = client.post(
        "/api/learning/shadow-review-retry/review/answers",
        json={"word_id": shadow_words[0].id, "rating": "good"},
    )

    assert first.status_code == 200
    assert second.status_code == 400
    assert second.json()["detail"] == "Word is not currently due for review"
    assert db_session.scalar(select(func.count()).select_from(LearningEventModel)) == 1
    assert db_session.scalar(select(func.count()).select_from(PracticeRunModel)) == 1


@pytest.fixture()
def postgresql_shadow_engine():
    admin_url_value = os.getenv("SLOVNIK_TEST_POSTGRES_ADMIN_URL")
    if not admin_url_value:
        pytest.skip("SLOVNIK_TEST_POSTGRES_ADMIN_URL is not configured")
    admin_url = make_url(admin_url_value)
    if admin_url.get_backend_name() != "postgresql":
        raise ValueError("SLOVNIK_TEST_POSTGRES_ADMIN_URL must use PostgreSQL")
    database_name = f"slovnik_learning_shadow_{uuid4().hex}"
    database_url = admin_url.set(database=database_name)
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    engine = None
    try:
        with admin_engine.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{database_name}"'))
        engine = create_engine(database_url)
        from app.db import Base

        Base.metadata.create_all(engine)
        yield engine
    finally:
        if engine is not None:
            engine.dispose()
        with admin_engine.connect() as connection:
            connection.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :name AND pid <> pg_backend_pid()"
                ),
                {"name": database_name},
            )
            connection.execute(text(f'DROP DATABASE IF EXISTS "{database_name}"'))
        admin_engine.dispose()


def test_postgresql_concurrent_review_serializes_one_transition_and_event(
    postgresql_shadow_engine,
    monkeypatch,
) -> None:
    from app.config import settings
    from app.services.learning_service import grade_review

    factory = sessionmaker(bind=postgresql_shadow_engine)
    now = datetime.now(timezone.utc)
    with factory() as session:
        word = VocabularyItem(
            serbian_cyrillic="реч",
            serbian_latin="reč",
            russian_translation="слово",
            cefr_level="A1",
            theme="shadow",
        )
        session.add(UserProfile(user_id="shadow-concurrent"))
        session.add(word)
        session.flush()
        word_id = word.id
        session.add(
            UserWordProgress(
                user_id="shadow-concurrent",
                word_id=word_id,
                status="reviewing",
                first_seen_at=now - timedelta(days=2),
                last_seen_at=now - timedelta(days=1),
                next_review_at=now - timedelta(minutes=1),
            )
        )
        session.commit()
        bootstrap_catalog(session)
    monkeypatch.setattr(settings, "language_assistant_shadow_enabled", True)
    start = threading.Barrier(2)

    def grade() -> str:
        with factory() as session:
            start.wait(timeout=10)
            try:
                grade_review(
                    session,
                    "shadow-concurrent",
                    word_id,
                    "good",
                )
            except ValueError as exc:
                return str(exc)
            return "accepted"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = [future.result(timeout=30) for future in (executor.submit(grade), executor.submit(grade))]

    with factory() as session:
        event_count = session.scalar(
            select(func.count()).select_from(LearningEventModel)
        )
        progress = session.scalar(
            select(UserWordProgress).where(
                UserWordProgress.user_id == "shadow-concurrent"
            )
        )

    assert sorted(outcomes) == ["Word is not currently due for review", "accepted"]
    assert event_count == 1
    assert progress.review_interval_days == 2


def test_shadow_failure_rolls_back_legacy_progress_and_domain_rows(
    db_session,
    shadow_words,
    monkeypatch,
) -> None:
    from app.config import settings
    from app.services import shadow_learning_service
    from app.services.learning_service import complete_new_words
    from app.services.shadow_learning_service import ShadowLearningFailure

    monkeypatch.setattr(settings, "language_assistant_shadow_enabled", True)

    def fail_projection(self, event):
        raise RuntimeError("injected projector failure")

    monkeypatch.setattr(
        shadow_learning_service.LearnerProjectionService,
        "apply_event",
        fail_projection,
    )

    with pytest.raises(ShadowLearningFailure, match="Learning shadow write failed"):
        complete_new_words(
            db_session,
            "shadow-rollback",
            [shadow_words[0].id],
        )

    assert db_session.scalar(select(func.count()).select_from(UserWordProgress)) == 0
    assert db_session.scalar(select(func.count()).select_from(PracticeRunModel)) == 0
    assert db_session.scalar(select(func.count()).select_from(ActivityInstanceModel)) == 0
    assert db_session.scalar(select(func.count()).select_from(LearningEventModel)) == 0
    assert db_session.scalar(select(func.count()).select_from(LearnerTargetStateModel)) == 0


def test_shadow_failure_logs_are_redacted(
    db_session,
    shadow_words,
    monkeypatch,
    caplog,
) -> None:
    from app.config import settings
    from app.services import shadow_learning_service
    from app.services.learning_service import complete_new_words
    from app.services.shadow_learning_service import ShadowLearningFailure

    monkeypatch.setattr(settings, "language_assistant_shadow_enabled", True)
    learner_secret = "private-learner"
    response_secret = "raw-answer-text"
    provider_secret = "provider-secret-value"

    def fail_projection(self, event):
        raise ValueError(f"{learner_secret} {response_secret} {provider_secret}")

    monkeypatch.setattr(
        shadow_learning_service.LearnerProjectionService,
        "apply_event",
        fail_projection,
    )

    with pytest.raises(ShadowLearningFailure) as error:
        complete_new_words(
            db_session,
            learner_secret,
            [shadow_words[0].id],
        )

    formatted_error = "".join(traceback.format_exception(error.value))
    assert error.value.__cause__ is None
    assert error.value.__context__ is None
    assert learner_secret not in formatted_error
    assert response_secret not in formatted_error
    assert provider_secret not in formatted_error
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "Learning shadow write failed" in messages
    assert learner_secret not in messages
    assert response_secret not in messages
    assert provider_secret not in messages


def test_event_write_failure_rolls_back_legacy_progress_and_domain_rows(
    db_session,
    shadow_words,
    monkeypatch,
) -> None:
    from app.config import settings
    from app.repositories.practice import PracticeRepository
    from app.services.learning_service import complete_new_words
    from app.services.shadow_learning_service import ShadowLearningFailure

    monkeypatch.setattr(settings, "language_assistant_shadow_enabled", True)
    learner_secret = "event-write-private-learner"
    response_secret = "raw-answer"
    provider_secret = "provider-secret"
    add_learning_event = PracticeRepository.add_learning_event

    def fail_after_event_insert(self, event):
        add_learning_event(self, event)
        raise RuntimeError(f"{response_secret} event-write {provider_secret}")

    monkeypatch.setattr(
        PracticeRepository,
        "add_learning_event",
        fail_after_event_insert,
    )

    with pytest.raises(ShadowLearningFailure) as error:
        complete_new_words(
            db_session,
            learner_secret,
            [shadow_words[0].id],
        )

    formatted_error = "".join(traceback.format_exception(error.value))
    assert error.value.__cause__ is None
    assert error.value.__context__ is None
    assert learner_secret not in formatted_error
    assert response_secret not in formatted_error
    assert provider_secret not in formatted_error
    assert db_session.scalar(select(func.count()).select_from(UserWordProgress)) == 0
    assert db_session.scalar(select(func.count()).select_from(PracticeRunModel)) == 0
    assert db_session.scalar(select(func.count()).select_from(ActivityInstanceModel)) == 0
    assert db_session.scalar(select(func.count()).select_from(LearningEventModel)) == 0
    assert db_session.scalar(select(func.count()).select_from(LearnerTargetStateModel)) == 0


@pytest.mark.parametrize("mapping_failure", ["missing", "ambiguous"])
def test_mapping_failure_aborts_without_legacy_or_domain_rows(
    db_session,
    shadow_words,
    monkeypatch,
    mapping_failure,
) -> None:
    from app.config import settings
    from app.services.learning_service import complete_new_words
    from app.services.shadow_learning_service import ShadowLearningFailure

    if mapping_failure == "missing":
        word = VocabularyItem(
            serbian_cyrillic="млеко",
            serbian_latin="mleko",
            russian_translation="молоко",
            cefr_level="A1",
            theme="shadow",
        )
        db_session.add(word)
        db_session.commit()
    else:
        word = shadow_words[0]
        lexical_unit_id = db_session.scalar(
            select(LanguageLexicalUnit.id).where(
                LanguageLexicalUnit.legacy_vocabulary_item_id == word.id
            )
        )
        db_session.add(
            LanguageSense(
                id=str(uuid4()),
                lexical_unit_id=lexical_unit_id,
                glosses=[{"language": "ru", "text": "другое"}],
                notes=None,
                examples=[],
                status="published",
                revision=1,
            )
        )
        db_session.commit()
    monkeypatch.setattr(settings, "language_assistant_shadow_enabled", True)

    with pytest.raises(ShadowLearningFailure, match="unique published lexical mapping"):
        complete_new_words(db_session, "shadow-mapping-failure", [word.id])

    assert db_session.scalar(select(func.count()).select_from(UserWordProgress)) == 0
    assert db_session.scalar(select(func.count()).select_from(LearningEventModel)) == 0
    assert db_session.scalar(select(func.count()).select_from(PracticeRunModel)) == 0
