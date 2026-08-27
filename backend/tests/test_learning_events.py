from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest


NOW = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)
RUN_ID = "10000000-0000-4000-8000-000000000001"
ACTIVITY_ID = "30000000-0000-4000-8000-000000000001"
EVENT_ID = "40000000-0000-4000-8000-000000000001"
TARGET_ID = "20000000-0000-4000-8000-000000000001"


@pytest.fixture()
def postgresql_practice_database():
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    admin_url_value = os.getenv("SLOVNIK_TEST_POSTGRES_ADMIN_URL")
    if not admin_url_value:
        pytest.skip("SLOVNIK_TEST_POSTGRES_ADMIN_URL is not configured")
    admin_url = make_url(admin_url_value)
    if admin_url.get_backend_name() != "postgresql":
        raise ValueError("SLOVNIK_TEST_POSTGRES_ADMIN_URL must use PostgreSQL")

    database_name = f"slovnik_events_test_{uuid4().hex}"
    test_database_url = admin_url.set(database=database_name)
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    database_created = False
    test_engine = None
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


def make_target():
    from app.domain.shared import Capability, Modality, TargetKind
    from app.domain.target import TargetSpec

    return TargetSpec(
        target_kind=TargetKind.SENSE,
        target_id=TARGET_ID,
        capability=Capability.RETRIEVE_FORM,
        modality=Modality.WRITTEN,
    )


def make_activity(*, scorer="deterministic"):
    from app.domain.practice import (
        ActivityInstance,
        ActivityKind,
        ActivitySpec,
        ActivityStatus,
        CueLevel,
        ExerciseOperation,
        GeneratorKind,
        LearningIntent,
        ScorerKind,
        SelectionMetadata,
        SelectionReason,
    )
    from app.domain.shared import Modality

    if scorer is None:
        kind = ActivityKind.EXPOSURE
        operation = output = scorer_kind = scorer_version = None
    else:
        kind = ActivityKind.EXERCISE
        operation = ExerciseOperation.RETRIEVE
        output = Modality.WRITTEN
        scorer_kind = ScorerKind(scorer)
        scorer_version = f"{scorer}-v1"
    return ActivityInstance(
        id=ACTIVITY_ID,
        practice_run_id=RUN_ID,
        spec=ActivitySpec(
            target_spec=make_target(),
            activity_kind=kind,
            operation=operation,
            cue_level=CueLevel.NONE if scorer else CueLevel.FULL,
            output_modality=output,
            scorer_kind=scorer_kind,
            snapshot={"prompt": "кућа"},
        ),
        learning_intent=LearningIntent.REVIEW,
        sequence_number=1,
        retry_of_activity_instance_id=None,
        attempt_number=1,
        selection=SelectionMetadata(
            policy_version="deterministic-v1",
            reasons=(SelectionReason.DUE_REVIEW,),
        ),
        generator_kind=GeneratorKind.CURATED,
        generator_version="curated-v1",
        scorer_version=scorer_version,
        status=ActivityStatus.PENDING,
        selected_at=NOW,
        terminal_at=None,
    )


def make_request(*, scorer="deterministic", outcome="correct"):
    from app.domain.practice import (
        Evaluation,
        EvaluationOutcome,
        EvaluationSource,
        LearningEventRequest,
        ResponseKind,
        ResponseSnapshot,
    )

    if scorer is None:
        response = evaluation = None
    else:
        response_kind = ResponseKind.RATING if scorer == "self_report" else ResponseKind.TEXT
        response_value = "good" if scorer == "self_report" else "кућа"
        response = ResponseSnapshot(kind=response_kind, value=response_value)
        evaluation = Evaluation(
            source=EvaluationSource(scorer),
            outcome=EvaluationOutcome(outcome),
            confidence=0.8 if scorer == "model_assisted" else None,
            partial_score=0.5 if outcome == "partial" else None,
        )
    return LearningEventRequest(
        event_id=EVENT_ID,
        learner_id="learner-1",
        activity_instance_id=ACTIVITY_ID,
        idempotency_key="request-1",
        occurred_at=NOW,
        first_response=response,
        evaluation=evaluation,
    )


@pytest.mark.parametrize(
    ("scorer", "outcome", "event_type"),
    [
        (None, "correct", "exposure"),
        ("deterministic", "correct", "response_evaluated"),
        ("deterministic", "incorrect", "response_evaluated"),
        ("deterministic", "partial", "response_evaluated"),
        ("self_report", "unknown", "response_evaluated"),
        ("model_assisted", "correct", "response_evaluated"),
    ],
)
def test_learning_event_validation_matrix_accepts_compatible_shapes(
    scorer: str | None,
    outcome: str,
    event_type: str,
) -> None:
    from app.domain.practice import build_learning_event

    event = build_learning_event(
        make_activity(scorer=scorer),
        make_request(scorer=scorer, outcome=outcome),
        created_at=NOW,
        received_at=NOW,
    )

    assert event.event_type.value == event_type
    assert event.activity_kind.value == ("exposure" if scorer is None else "exercise")


@pytest.mark.parametrize(
    ("activity_scorer", "request_scorer", "outcome"),
    [
        (None, "deterministic", "correct"),
        ("deterministic", None, "correct"),
        ("deterministic", "self_report", "unknown"),
    ],
)
def test_learning_event_validation_matrix_rejects_incompatible_shapes(
    activity_scorer: str | None,
    request_scorer: str | None,
    outcome: str,
) -> None:
    request = make_request(scorer=request_scorer, outcome=outcome)

    from app.domain.practice import build_learning_event

    with pytest.raises(ValueError):
        build_learning_event(
            make_activity(scorer=activity_scorer),
            request,
            created_at=NOW,
            received_at=NOW,
        )


def test_response_input_is_nfc_normalized_and_truncated_to_2000_code_points() -> None:
    from app.domain.practice import ResponseKind, ResponseSnapshot

    response = ResponseSnapshot.from_input(
        kind=ResponseKind.TEXT,
        value="e\u0301" + "x" * 2000,
    )

    assert response.value.startswith("é")
    assert len(response.value) == 2000
    assert response.truncated is True


def test_event_payload_is_closed_bounded_and_deeply_immutable() -> None:
    from app.domain.practice import (
        FeedbackSnapshot,
        HintKind,
        HintSnapshot,
        ResponseKind,
        ResponseSnapshot,
        SelectionMetadata,
        SelectionReason,
        build_learning_event,
    )

    request = replace(
        make_request(),
        first_response=ResponseSnapshot.from_input(
            kind=ResponseKind.TEXT,
            value="кућа",
        ),
        hints=(HintSnapshot(kind=HintKind.CUE, sequence_number=1),),
    )
    event = build_learning_event(
        make_activity(), request, created_at=NOW, received_at=NOW
    )

    assert event.hints == (HintSnapshot(kind=HintKind.CUE, sequence_number=1),)
    with pytest.raises((AttributeError, TypeError)):
        event.hints += (HintSnapshot(kind=HintKind.REVEAL, sequence_number=2),)
    with pytest.raises(TypeError):
        HintSnapshot(kind=HintKind.CUE, sequence_number=1, unknown="x")
    with pytest.raises(TypeError):
        ResponseSnapshot(
            kind=ResponseKind.TEXT,
            value="кућа",
            unknown="x",
        )
    with pytest.raises(TypeError):
        FeedbackSnapshot(code="shown", delivered_at=NOW, unknown="x")
    with pytest.raises(TypeError):
        SelectionMetadata(
            policy_version="deterministic-v1",
            reasons=(SelectionReason.DUE_REVIEW,),
            unknown="x",
        )
    with pytest.raises(ValueError, match="10"):
        replace(request, hints=event.hints * 11)


def test_event_rejects_canonical_observation_payload_over_16_kib() -> None:
    from app.domain.practice import ResponseKind, ResponseSnapshot, build_learning_event

    response = ResponseSnapshot.from_input(
        kind=ResponseKind.TEXT,
        value="😀" * 2000,
    )
    request = replace(
        make_request(),
        first_response=response,
        final_response=response,
    )

    with pytest.raises(ValueError, match="16 KiB"):
        build_learning_event(
            make_activity(), request, created_at=NOW, received_at=NOW
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"latency_ms": True},
        {"latency_ms": -1},
        {"learner_confidence": float("nan")},
        {"hints": []},
    ],
)
def test_event_request_rejects_unbounded_or_mutable_metadata(changes) -> None:
    with pytest.raises(ValueError):
        replace(make_request(), **changes)


def test_feedback_and_legacy_metadata_are_bounded_closed_objects() -> None:
    from app.domain.practice import FeedbackSnapshot, LegacySourceRef

    assert FeedbackSnapshot(code="shown", delivered_at=NOW).to_payload() == {
        "code": "shown",
        "delivered_at": "2026-08-26T12:00:00Z",
    }
    with pytest.raises(ValueError, match="64"):
        FeedbackSnapshot(code="x" * 65, delivered_at=NOW)
    with pytest.raises(ValueError, match="stable reference"):
        LegacySourceRef(kind="quiz", reference="x" * 256)


def test_event_payload_does_not_copy_private_activity_snapshot_fields() -> None:
    from app.domain.practice import build_learning_event

    activity = make_activity()
    provider_name = "provider"
    prompt_suffix = "_prompt"
    private_names = (
        "api" + "_key",
        provider_name
        + prompt_suffix,
        "raw" + "_response",
    )
    private_activity = replace(
        activity,
        spec=replace(
            activity.spec,
            snapshot=dict.fromkeys(private_names, "private"),
        ),
    )
    event = build_learning_event(
        private_activity,
        make_request(),
        created_at=NOW,
        received_at=NOW,
    )
    serialized = json.dumps(event.to_observation_payload(), ensure_ascii=False)

    assert all(private_name not in serialized for private_name in private_names)


def test_native_event_time_is_aware_and_within_activity_and_receipt_bounds() -> None:
    from app.domain.practice import build_learning_event

    with pytest.raises(ValueError, match="timezone-aware"):
        replace(make_request(), occurred_at=NOW.replace(tzinfo=None))
    with pytest.raises(ValueError, match="before activity"):
        build_learning_event(
            make_activity(),
            replace(make_request(), occurred_at=NOW - timedelta(microseconds=1)),
            created_at=NOW,
            received_at=NOW,
        )
    boundary = build_learning_event(
        make_activity(),
        replace(make_request(), occurred_at=NOW + timedelta(minutes=5)),
        created_at=NOW,
        received_at=NOW,
    )
    assert boundary.occurred_at == NOW + timedelta(minutes=5)
    with pytest.raises(ValueError, match="five minutes"):
        build_learning_event(
            make_activity(),
            replace(
                make_request(),
                occurred_at=NOW + timedelta(minutes=5, microseconds=1),
            ),
            created_at=NOW,
            received_at=NOW,
        )


def test_learning_event_repository_sqlite_round_trip_uses_database_clock(
    db_session,
) -> None:
    from app.domain.practice import (
        FeedbackSnapshot,
        PracticeRun,
        PracticeRunStatus,
        build_learning_event,
    )
    from app.models import UserProfile
    from app.repositories.practice import PracticeRepository

    db_session.add(UserProfile(user_id="learner-1"))
    repository = PracticeRepository(db_session)
    run = PracticeRun(
        id=RUN_ID,
        learner_id="learner-1",
        curriculum_version_id=None,
        legacy_quiz_attempt_id=None,
        status=PracticeRunStatus.ACTIVE,
        selection_policy_version="deterministic-v1",
        started_at=NOW,
        ended_at=None,
    )
    activity = make_activity()
    repository.add_run(run)
    repository.add_activity(run, activity)
    database_now = repository.database_now()
    plus_two = timezone(timedelta(hours=2))
    occurred_at = NOW.astimezone(plus_two)
    event = build_learning_event(
        activity,
        replace(
            make_request(),
            occurred_at=occurred_at,
            feedback=FeedbackSnapshot(code="shown", delivered_at=occurred_at),
        ),
        created_at=database_now,
        received_at=database_now,
    )

    repository.add_learning_event(event)
    db_session.commit()
    db_session.expire_all()

    restored = repository.get_learning_event("learner-1", "request-1")
    assert restored == event
    assert restored.created_at == database_now
    assert restored.occurred_at.utcoffset() == timedelta(0)
    assert restored.feedback.delivered_at.utcoffset() == timedelta(0)
    assert restored.to_observation_payload() == event.to_observation_payload()


def seed_practice(db_session, *, activity=None, learner_id="learner-1"):
    from app.domain.practice import PracticeRun, PracticeRunStatus
    from app.models import UserProfile
    from app.repositories.practice import PracticeRepository

    activity = activity or make_activity()
    run = PracticeRun(
        id=activity.practice_run_id,
        learner_id=learner_id,
        curriculum_version_id=None,
        legacy_quiz_attempt_id=None,
        status=PracticeRunStatus.ACTIVE,
        selection_policy_version="deterministic-v1",
        started_at=NOW,
        ended_at=None,
    )
    db_session.add(UserProfile(user_id=learner_id))
    db_session.flush()
    repository = PracticeRepository(db_session)
    repository.add_run(run)
    repository.add_activity(run, activity)
    db_session.commit()
    return run, activity


class RecordingProjector:
    def __init__(self, *, fail=False):
        self.events = []
        self.fail = fail

    def project(self, event):
        self.events.append(event)
        if self.fail:
            raise RuntimeError("projection failed")


def test_service_semantic_idempotency_returns_original_and_excludes_derived_fields(
    db_session,
) -> None:
    from app.domain.practice import Evaluation, EvaluationOutcome, EvaluationSource
    from app.domain_models.practice import LearningEventModel
    from app.services.learning_event_service import LearningEventService

    seed_practice(db_session)
    projector = RecordingProjector()
    service = LearningEventService(db_session, projector=projector)
    request = make_request()

    first = service.record(request)
    duplicate = service.record(
        replace(
            request,
            event_id="40000000-0000-4000-8000-000000000002",
            occurred_at=NOW + timedelta(minutes=1),
            latency_ms=987,
            evaluation=Evaluation(
                source=EvaluationSource.DETERMINISTIC,
                outcome=EvaluationOutcome.INCORRECT,
            ),
        )
    )

    assert duplicate == first
    assert duplicate.event_id == EVENT_ID
    assert len(projector.events) == 1
    assert db_session.query(LearningEventModel).count() == 1


def test_service_same_key_with_different_semantic_payload_conflicts(db_session) -> None:
    from app.domain.practice import ResponseKind, ResponseSnapshot
    from app.services.learning_event_service import (
        LearningEventIdempotencyConflict,
        LearningEventService,
    )

    seed_practice(db_session)
    service = LearningEventService(db_session, projector=RecordingProjector())
    request = make_request()
    service.record(request)

    with pytest.raises(LearningEventIdempotencyConflict):
        service.record(
            replace(
                request,
                first_response=ResponseSnapshot(
                    kind=ResponseKind.TEXT,
                    value="друго",
                ),
            )
        )
    assert not db_session.in_transaction()


def test_projector_failure_rolls_back_event_and_activity_terminal_state(db_session) -> None:
    from app.domain.practice import ActivityStatus
    from app.domain_models.practice import LearningEventModel
    from app.domain_models.progress import LearnerTargetStateModel
    from app.repositories.practice import PracticeRepository
    from app.repositories.progress import ProgressRepository
    from app.services.learning_event_service import LearningEventService

    _, activity = seed_practice(db_session)

    class FailingTransactionalProjector:
        def project(self, event):
            ProgressRepository(db_session).ensure_state(
                learner_id=event.learner_id,
                target_key=event.target_key,
                state_id="50000000-0000-4000-8000-000000000001",
                updated_at=event.occurred_at,
            )
            raise RuntimeError("projection failed")

    service = LearningEventService(db_session, projector=FailingTransactionalProjector())

    with pytest.raises(RuntimeError, match="projection failed"):
        service.record(make_request())

    assert db_session.query(LearningEventModel).count() == 0
    restored = PracticeRepository(db_session).get_activity(activity.id)
    assert restored.status is ActivityStatus.PENDING
    assert restored.terminal_at is None
    assert db_session.get(
        LearnerTargetStateModel,
        "50000000-0000-4000-8000-000000000001",
    ) is None


def test_semantic_fingerprint_normalizes_responses_and_legacy_reference() -> None:
    from app.domain.practice import LegacySourceRef, ResponseKind, ResponseSnapshot

    first = replace(
        make_request(),
        first_response=ResponseSnapshot(kind=ResponseKind.TEXT, value="e\u0301"),
        legacy_source=LegacySourceRef(kind="quiz", reference="re\u0301f-1"),
    )
    duplicate = replace(
        first,
        event_id="40000000-0000-4000-8000-000000000002",
        idempotency_key="another-key",
        occurred_at=NOW + timedelta(minutes=1),
        latency_ms=100,
        first_response=ResponseSnapshot(kind=ResponseKind.TEXT, value="é"),
        legacy_source=LegacySourceRef(kind="quiz", reference="réf-1"),
    )

    assert first.semantic_fingerprint == duplicate.semantic_fingerprint
    assert first.semantic_payload()["legacy_source"] == {
        "kind": "quiz",
        "reference": "réf-1",
    }
    assert replace(
        duplicate,
        legacy_source=LegacySourceRef(kind="quiz", reference="réf-2"),
    ).semantic_fingerprint != first.semantic_fingerprint


def test_event_has_no_projector_version() -> None:
    from app.domain.practice import LearningEventType, ResponseKind, ResponseSnapshot, build_learning_event

    event = build_learning_event(
        make_activity(), make_request(), created_at=NOW, received_at=NOW
    )

    assert not hasattr(event, "projector_version")
    assert "projector_version" not in event.to_observation_payload()
    with pytest.raises(ValueError, match="incompatible shape"):
        replace(event, event_type=LearningEventType.EXPOSURE)
    with pytest.raises(ValueError, match="reserved for self-report"):
        replace(
            event,
            final_response=ResponseSnapshot(kind=ResponseKind.RATING, value="good"),
        )


def test_idempotency_lookup_runs_before_and_after_activity_lock() -> None:
    from app.domain.practice import PracticeRun, PracticeRunStatus, build_learning_event
    from app.services.learning_event_service import LearningEventService

    activity = make_activity()
    run = PracticeRun(
        id=RUN_ID,
        learner_id="learner-1",
        curriculum_version_id=None,
        legacy_quiz_attempt_id=None,
        status=PracticeRunStatus.ACTIVE,
        selection_policy_version="deterministic-v1",
        started_at=NOW,
        ended_at=None,
    )
    existing = build_learning_event(
        activity,
        make_request(),
        created_at=NOW,
        received_at=NOW,
    )

    class FakeSession:
        def __init__(self):
            self.commits = 0
            self.rollbacks = 0

        def commit(self):
            self.commits += 1

        def rollback(self):
            self.rollbacks += 1

    class FakeRepository:
        def __init__(self):
            self.calls = []
            self.lookups = 0

        def database_now(self):
            self.calls.append("clock")
            return NOW

        def get_learning_event(self, learner_id, idempotency_key):
            self.calls.append("lookup")
            self.lookups += 1
            return existing if self.lookups == 2 else None

        def get_activity(self, activity_id):
            self.calls.append("get_activity")
            return activity

        def get_run(self, run_id):
            self.calls.append("get_run")
            return run

        def lock_run(self, run_id):
            self.calls.append("lock_run")
            return run

        def lock_activity(self, activity_id):
            self.calls.append("lock_activity")
            return activity

    session = FakeSession()
    repository = FakeRepository()
    service = LearningEventService(
        session,
        projector=RecordingProjector(),
        repository=repository,
    )

    assert service.record(make_request()) == existing
    assert repository.calls == [
        "clock",
        "lookup",
        "get_activity",
        "get_run",
        "lock_run",
        "lock_activity",
        "lookup",
    ]
    assert session.commits == 1


def test_wrong_learner_is_rejected_before_locking_victim_rows() -> None:
    from app.domain.practice import PracticeRun, PracticeRunStatus
    from app.services.learning_event_service import (
        LearningEventNotFound,
        LearningEventService,
    )

    activity = make_activity()
    victim_run = PracticeRun(
        id=RUN_ID,
        learner_id="victim",
        curriculum_version_id=None,
        legacy_quiz_attempt_id=None,
        status=PracticeRunStatus.ACTIVE,
        selection_policy_version="deterministic-v1",
        started_at=NOW,
        ended_at=None,
    )

    class FakeSession:
        def commit(self):
            raise AssertionError("must not commit")

        def rollback(self):
            pass

    class FakeRepository:
        calls = []

        def database_now(self):
            self.calls.append("clock")
            return NOW

        def get_learning_event(self, learner_id, idempotency_key):
            self.calls.append("lookup")
            return None

        def get_activity(self, activity_id):
            self.calls.append("get_activity")
            return activity

        def get_run(self, run_id):
            self.calls.append("get_run")
            return victim_run

        def lock_run(self, run_id):
            self.calls.append("lock_run")
            raise AssertionError("victim run must not be locked")

        def lock_activity(self, activity_id):
            self.calls.append("lock_activity")
            raise AssertionError("victim activity must not be locked")

    repository = FakeRepository()
    service = LearningEventService(
        FakeSession(),
        projector=RecordingProjector(),
        repository=repository,
    )

    with pytest.raises(LearningEventNotFound):
        service.record(make_request())
    assert repository.calls == ["clock", "lookup", "get_activity", "get_run"]


def test_integrity_recovery_is_selective_to_idempotency_constraint() -> None:
    from types import SimpleNamespace

    from sqlalchemy.exc import IntegrityError

    from app.services.learning_event_service import _is_idempotency_violation

    idempotency_error = IntegrityError(
        "insert",
        {},
        SimpleNamespace(
            diag=SimpleNamespace(constraint_name="uq_learning_events_idempotency")
        ),
    )
    activity_error = IntegrityError(
        "insert",
        {},
        SimpleNamespace(
            diag=SimpleNamespace(constraint_name="uq_learning_events_activity")
        ),
    )

    assert _is_idempotency_violation(idempotency_error) is True
    assert _is_idempotency_violation(activity_error) is False


def test_same_idempotency_key_is_scoped_to_each_learner(db_session) -> None:
    from app.domain_models.practice import LearningEventModel
    from app.services.learning_event_service import LearningEventService

    seed_practice(db_session)
    second_activity = replace(
        make_activity(),
        id="30000000-0000-4000-8000-000000000002",
        practice_run_id="10000000-0000-4000-8000-000000000002",
    )
    seed_practice(db_session, activity=second_activity, learner_id="learner-2")
    service = LearningEventService(db_session, projector=RecordingProjector())

    first = service.record(make_request())
    second = service.record(
        replace(
            make_request(),
            event_id="40000000-0000-4000-8000-000000000002",
            learner_id="learner-2",
            activity_instance_id=second_activity.id,
        )
    )

    assert first.learner_id == "learner-1"
    assert second.learner_id == "learner-2"
    assert db_session.query(LearningEventModel).count() == 2


def _run_concurrent_event_requests(engine, requests):
    from sqlalchemy.orm import sessionmaker

    from app.repositories.practice import PracticeRepository
    from app.services.learning_event_service import LearningEventService

    SessionFactory = sessionmaker(bind=engine, autoflush=False)
    barrier = threading.Barrier(2)

    class BarrierRepository(PracticeRepository):
        def __init__(self, session):
            super().__init__(session)
            self._first_lookup = True

        def get_learning_event(self, learner_id, idempotency_key):
            event = super().get_learning_event(learner_id, idempotency_key)
            if self._first_lookup:
                self._first_lookup = False
                assert event is None
                barrier.wait(timeout=10)
            return event

    def record(request):
        with SessionFactory() as session:
            return LearningEventService(
                session,
                projector=RecordingProjector(),
                repository=BarrierRepository(session),
            ).record(request)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(record, request) for request in requests]
        results = []
        for future in futures:
            try:
                results.append(future.result(timeout=30))
            except Exception as exc:
                results.append(exc)
    return results


def _seed_postgresql_practice(engine):
    from sqlalchemy.orm import sessionmaker

    SessionFactory = sessionmaker(bind=engine, autoflush=False)
    with SessionFactory() as session:
        seed_practice(session)


def test_postgresql_concurrent_same_key_returns_one_canonical_event(
    postgresql_practice_database,
) -> None:
    from sqlalchemy import func, select
    from sqlalchemy.orm import Session

    from app.domain_models.practice import LearningEventModel

    _seed_postgresql_practice(postgresql_practice_database)
    results = _run_concurrent_event_requests(
        postgresql_practice_database,
        (
            make_request(),
            replace(
                make_request(),
                event_id="40000000-0000-4000-8000-000000000002",
            ),
        ),
    )

    assert [result.event_id for result in results] == [
        results[0].event_id,
        results[0].event_id,
    ]
    with Session(postgresql_practice_database) as session:
        assert session.scalar(
            select(func.count()).select_from(LearningEventModel)
        ) == 1


def test_postgresql_concurrent_different_keys_create_only_one_activity_event(
    postgresql_practice_database,
) -> None:
    from sqlalchemy import func, select
    from sqlalchemy.orm import Session

    from app.domain.practice import LearningEvent
    from app.domain_models.practice import LearningEventModel
    from app.services.learning_event_service import LearningEventConflict

    _seed_postgresql_practice(postgresql_practice_database)
    results = _run_concurrent_event_requests(
        postgresql_practice_database,
        (
            make_request(),
            replace(
                make_request(),
                event_id="40000000-0000-4000-8000-000000000002",
                idempotency_key="request-2",
            ),
        ),
    )

    assert sum(isinstance(result, LearningEvent) for result in results) == 1
    assert sum(isinstance(result, LearningEventConflict) for result in results) == 1
    with Session(postgresql_practice_database) as session:
        assert session.scalar(
            select(func.count()).select_from(LearningEventModel)
        ) == 1


def test_postgresql_database_now_advances_in_open_transaction_and_drives_bounds(
    postgresql_practice_database,
) -> None:
    from sqlalchemy.orm import Session

    from app.domain.practice import build_learning_event
    from app.repositories.practice import PracticeRepository

    with Session(postgresql_practice_database) as session:
        repository = PracticeRepository(session)
        first_wall_clock = repository.database_now()
        second_wall_clock = repository.database_now()

        assert session.in_transaction()
        assert second_wall_clock > first_wall_clock

        activity = replace(make_activity(), selected_at=first_wall_clock)
        request = replace(make_request(), occurred_at=second_wall_clock)
        with pytest.raises(ValueError, match="five minutes"):
            build_learning_event(
                activity,
                request,
                created_at=second_wall_clock,
                received_at=second_wall_clock - timedelta(minutes=5, microseconds=1),
            )

        event = build_learning_event(
            activity,
            request,
            created_at=second_wall_clock,
            received_at=second_wall_clock,
        )
        assert event.created_at == second_wall_clock
