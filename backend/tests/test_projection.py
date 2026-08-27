import os
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest


TARGET_KEY = (
    "v1:sense:abcdef12-1234-5678-9234-567812345678:retrieve_form:written:"
    "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"
)
OCCURRED_AT = datetime(2026, 8, 27, 8, tzinfo=timezone.utc)


@dataclass(frozen=True)
class FakeLearningEvent:
    event_id: str
    learner_id: str = "learner-1"
    target_key: str = TARGET_KEY
    occurred_at: datetime = OCCURRED_AT
    event_type: str = "response_evaluated"
    evaluation_source: str | None = "deterministic"
    evaluation_outcome: str | None = "correct"
    first_response: object | None = None


class FakeEventSource:
    def __init__(self, events: list[FakeLearningEvent]) -> None:
        self.events = events

    def events_for_target(self, *, learner_id: str, target_key: str):
        return tuple(
            event
            for event in self.events
            if event.learner_id == learner_id and event.target_key == target_key
        )


@pytest.fixture()
def projection_session(db_session):
    from app.domain_models.progress import LearnerTargetStateModel

    LearnerTargetStateModel.__table__.create(
        bind=db_session.get_bind(),
        checkfirst=True,
    )
    return db_session


@pytest.fixture()
def postgresql_projection_database():
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    admin_url_value = os.getenv("SLOVNIK_TEST_POSTGRES_ADMIN_URL")
    if not admin_url_value:
        pytest.skip("SLOVNIK_TEST_POSTGRES_ADMIN_URL is not configured")
    admin_url = make_url(admin_url_value)
    if admin_url.get_backend_name() != "postgresql":
        raise ValueError("SLOVNIK_TEST_POSTGRES_ADMIN_URL must use PostgreSQL")

    database_name = f"slovnik_projection_test_{uuid4().hex}"
    test_database_url = admin_url.set(database=database_name)
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    database_created = False
    test_engine = None
    try:
        with admin_engine.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{database_name}"'))
        database_created = True
        test_engine = create_engine(test_database_url)

        from app.domain_models.progress import LearnerTargetStateModel
        from app.models import UserProfile

        UserProfile.__table__.create(test_engine)
        LearnerTargetStateModel.__table__.create(test_engine)
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


def _neutral_state():
    from app.domain.progress import LearnerTargetState

    return LearnerTargetState.neutral(
        state_id="11111111-1111-4111-8111-111111111111",
        learner_id="learner-1",
        target_key=TARGET_KEY,
        updated_at=datetime(2026, 8, 27, 7, tzinfo=timezone.utc),
    )


def test_deterministic_correct_increases_success_and_replayable_peak() -> None:
    from app.services.learner_projection_service import project_event

    projected = project_event(
        _neutral_state(),
        FakeLearningEvent(event_id="22222222-2222-4222-8222-222222222222"),
    )

    assert (
        projected.competence.success_weight,
        projected.competence.failure_weight,
        projected.competence.peak,
        projected.competence.uncertainty,
    ) == (1, 0, 2 / 3, 2 / 3)


def test_deterministic_incorrect_increases_failure_and_reduces_uncertainty() -> None:
    from app.services.learner_projection_service import project_event

    projected = project_event(
        _neutral_state(),
        FakeLearningEvent(
            event_id="22222222-2222-4222-8222-222222222222",
            evaluation_outcome="incorrect",
        ),
    )

    assert projected.competence == type(projected.competence)(
        success_weight=0,
        failure_weight=1,
        peak=0,
        uncertainty=2 / 3,
    )


def test_only_deterministic_terminal_outcomes_change_competence() -> None:
    from app.services.learner_projection_service import project_event

    initial = _neutral_state()
    projected = tuple(
        project_event(initial, event).competence
        for event in (
            FakeLearningEvent(
                event_id="22222222-2222-4222-8222-222222222222",
                evaluation_outcome="partial",
            ),
            FakeLearningEvent(
                event_id="33333333-3333-4333-8333-333333333333",
                event_type="exposure",
            ),
        )
    )

    assert projected == (
        initial.competence,
        initial.competence,
    )


def test_first_exposure_sets_one_day_hold_without_competence_credit() -> None:
    from app.services.learner_projection_service import project_event

    initial = _neutral_state()
    projected = project_event(
        initial,
        FakeLearningEvent(
            event_id="22222222-2222-4222-8222-222222222222",
            event_type="exposure",
            evaluation_source=None,
            evaluation_outcome=None,
        ),
    )

    assert (
        projected.memory.interval_days,
        projected.memory.due_at,
        projected.competence,
    ) == (1, OCCURRED_AT + timedelta(days=1), initial.competence)


def test_first_deterministic_success_sets_one_day_memory_interval() -> None:
    from app.services.learner_projection_service import project_event

    projected = project_event(
        _neutral_state(),
        FakeLearningEvent(event_id="22222222-2222-4222-8222-222222222222"),
    )

    assert (projected.memory.interval_days, projected.memory.due_at) == (
        1,
        OCCURRED_AT + timedelta(days=1),
    )


def test_deterministic_success_doubles_memory_interval_at_180_day_cap() -> None:
    from app.services.learner_projection_service import project_event

    first = project_event(
        _neutral_state(),
        FakeLearningEvent(event_id="22222222-2222-4222-8222-222222222222"),
    )
    second_time = OCCURRED_AT + timedelta(days=1)
    doubled = project_event(
        first,
        FakeLearningEvent(
            event_id="33333333-3333-4333-8333-333333333333",
            occurred_at=second_time,
        ),
    )
    near_cap = replace(
        first,
        memory=replace(first.memory, interval_days=100),
    )
    capped = project_event(
        near_cap,
        FakeLearningEvent(
            event_id="44444444-4444-4444-8444-444444444444",
            occurred_at=second_time,
        ),
    )

    assert (
        doubled.memory.interval_days,
        doubled.memory.due_at,
        capped.memory.interval_days,
        capped.memory.due_at,
    ) == (2, second_time + timedelta(days=2), 180, second_time + timedelta(days=180))


def test_deterministic_failure_is_due_immediately_and_increments_lapses() -> None:
    from app.services.learner_projection_service import project_event

    first = project_event(
        _neutral_state(),
        FakeLearningEvent(event_id="22222222-2222-4222-8222-222222222222"),
    )
    failed_at = OCCURRED_AT + timedelta(hours=1)
    failed = project_event(
        first,
        FakeLearningEvent(
            event_id="33333333-3333-4333-8333-333333333333",
            occurred_at=failed_at,
            evaluation_outcome="incorrect",
        ),
    )

    assert (
        failed.memory.interval_days,
        failed.memory.due_at,
        failed.memory.lapses,
    ) == (0, failed_at, 1)


def test_self_report_ratings_apply_memory_only_intervals() -> None:
    from app.services.learner_projection_service import project_event

    first = project_event(
        _neutral_state(),
        FakeLearningEvent(event_id="22222222-2222-4222-8222-222222222222"),
    )
    initial = replace(first, memory=replace(first.memory, interval_days=4, lapses=2))
    events = tuple(
        FakeLearningEvent(
            event_id=event_id,
            occurred_at=OCCURRED_AT + timedelta(hours=1),
            evaluation_source="self_report",
            evaluation_outcome="unknown",
            first_response={"kind": "rating", "value": rating, "truncated": False},
        )
        for event_id, rating in (
            ("33333333-3333-4333-8333-333333333333", "again"),
            ("44444444-4444-4444-8444-444444444444", "hard"),
            ("55555555-5555-4555-8555-555555555555", "good"),
            ("66666666-6666-4666-8666-666666666666", "easy"),
        )
    )
    projected = tuple(project_event(initial, event) for event in events)
    rating_time = OCCURRED_AT + timedelta(hours=1)

    assert tuple(
        (state.memory.interval_days, state.memory.due_at, state.memory.lapses)
        for state in projected
    ) == (
        (0, rating_time + timedelta(minutes=10), 3),
        (1, rating_time + timedelta(days=1), 2),
        (8, rating_time + timedelta(days=8), 2),
        (12, rating_time + timedelta(days=12), 2),
    )


def test_self_report_good_and_easy_respect_their_distinct_caps() -> None:
    from app.services.learner_projection_service import project_event

    first = project_event(
        _neutral_state(),
        FakeLearningEvent(event_id="22222222-2222-4222-8222-222222222222"),
    )
    rating_time = OCCURRED_AT + timedelta(hours=1)
    projected = tuple(
        project_event(
            replace(first, memory=replace(first.memory, interval_days=interval)),
            FakeLearningEvent(
                event_id=event_id,
                occurred_at=rating_time,
                evaluation_source="self_report",
                evaluation_outcome="unknown",
                first_response={
                    "kind": "rating",
                    "value": rating,
                    "truncated": False,
                },
            ),
        )
        for event_id, rating, interval in (
            ("33333333-3333-4333-8333-333333333333", "good", 100),
            ("44444444-4444-4444-8444-444444444444", "easy", 200),
        )
    )

    assert tuple(
        (state.memory.interval_days, state.memory.due_at) for state in projected
    ) == (
        (180, rating_time + timedelta(days=180)),
        (365, rating_time + timedelta(days=365)),
    )


def test_non_deterministic_evidence_is_neutral_and_failure_preserves_peak() -> None:
    from app.services.learner_projection_service import project_event

    first = project_event(
        _neutral_state(),
        FakeLearningEvent(event_id="22222222-2222-4222-8222-222222222222"),
    )
    event_time = OCCURRED_AT + timedelta(hours=1)
    self_report = project_event(
        first,
        FakeLearningEvent(
            event_id="33333333-3333-4333-8333-333333333333",
            occurred_at=event_time,
            evaluation_source="self_report",
            evaluation_outcome="unknown",
            first_response={"kind": "rating", "value": "again", "truncated": False},
        ),
    )
    model_assisted = project_event(
        first,
        FakeLearningEvent(
            event_id="44444444-4444-4444-8444-444444444444",
            occurred_at=event_time,
            evaluation_source="model_assisted",
            evaluation_outcome="correct",
        ),
    )
    incorrect = project_event(
        first,
        FakeLearningEvent(
            event_id="55555555-5555-4555-8555-555555555555",
            occurred_at=event_time,
            evaluation_outcome="incorrect",
        ),
    )

    assert (
        self_report.competence,
        model_assisted.competence,
        model_assisted.memory,
        incorrect.competence.peak,
    ) == (first.competence, first.competence, first.memory, first.competence.peak)


def test_self_report_rejects_an_unvalidated_rating_value() -> None:
    from app.services.learner_projection_service import project_event

    with pytest.raises(ValueError, match="validated rating"):
        project_event(
            _neutral_state(),
            FakeLearningEvent(
                event_id="22222222-2222-4222-8222-222222222222",
                evaluation_source="self_report",
                evaluation_outcome="unknown",
                first_response={
                    "kind": "rating",
                    "value": "invented",
                    "truncated": False,
                },
            ),
        )


def test_service_materializes_and_applies_one_event_only_once(
    projection_session,
) -> None:
    from sqlalchemy import func, select

    from app.domain_models.progress import LearnerTargetStateModel
    from app.models import UserProfile
    from app.repositories.progress import ProgressRepository
    from app.services.learner_projection_service import LearnerProjectionService

    projection_session.add(UserProfile(user_id="learner-1"))
    projection_session.commit()
    event = FakeLearningEvent(
        event_id="22222222-2222-4222-8222-222222222222"
    )
    service = LearnerProjectionService(
        ProgressRepository(projection_session),
        FakeEventSource([event]),
    )

    first = service.apply_event(event)
    second = service.apply_event(event)
    row_count = projection_session.scalar(
        select(func.count()).select_from(LearnerTargetStateModel)
    )

    assert (first.evidence.count, second, row_count) == (1, first, 1)


def test_postgresql_concurrent_absent_state_applies_one_event_once(
    postgresql_projection_database,
) -> None:
    from sqlalchemy import func, select
    from sqlalchemy.orm import sessionmaker

    from app.domain_models.progress import LearnerTargetStateModel
    from app.models import UserProfile
    from app.repositories.progress import ProgressRepository
    from app.services.learner_projection_service import LearnerProjectionService

    SessionFactory = sessionmaker(bind=postgresql_projection_database)
    with SessionFactory() as session:
        session.add(UserProfile(user_id="learner-1"))
        session.commit()

    event = FakeLearningEvent(
        event_id="22222222-2222-4222-8222-222222222222"
    )
    event_source = FakeEventSource([event])
    start = threading.Barrier(2)

    class BarrierRepository(ProgressRepository):
        def __init__(self, session) -> None:
            super().__init__(session)
            self._first_lookup = True

        def _find_state_row(self, learner_id: str, target_key: str):
            row = super()._find_state_row(learner_id, target_key)
            if self._first_lookup:
                self._first_lookup = False
                assert row is None
                start.wait(timeout=10)
            return row

    def apply() -> tuple[str, int]:
        with SessionFactory() as session:
            state = LearnerProjectionService(
                BarrierRepository(session),
                event_source,
            ).apply_event(event)
            session.commit()
            return state.state_id, state.evidence.count

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(apply) for _ in range(2)]
        results = [future.result(timeout=30) for future in futures]

    with SessionFactory() as session:
        persisted = session.scalar(select(LearnerTargetStateModel))
        row_count = session.scalar(
            select(func.count()).select_from(LearnerTargetStateModel)
        )
        assert persisted is not None

    assert (len(set(results)), results[0][1], row_count, persisted.evidence_count) == (
        1,
        1,
        1,
        1,
    )


def test_replay_matches_incremental_projection_in_canonical_event_order() -> None:
    from app.services.learner_projection_service import project_event, replay_events

    events = (
        FakeLearningEvent(
            event_id="22222222-2222-4222-8222-222222222222",
            occurred_at=OCCURRED_AT,
            evaluation_outcome="incorrect",
        ),
        FakeLearningEvent(
            event_id="33333333-3333-4333-8333-333333333333",
            occurred_at=OCCURRED_AT + timedelta(hours=1),
        ),
        FakeLearningEvent(
            event_id="44444444-4444-4444-8444-444444444444",
            occurred_at=OCCURRED_AT + timedelta(hours=2),
            evaluation_outcome="partial",
        ),
    )
    incremental = _neutral_state()
    for event in events:
        incremental = project_event(incremental, event)

    replayed = replay_events(incremental, reversed(events))

    assert replayed == incremental


def test_late_event_resets_target_projection_to_frozen_baseline(
    projection_session,
) -> None:
    from app.models import UserProfile
    from app.repositories.progress import ProgressRepository
    from app.services.learner_projection_service import LearnerProjectionService

    projection_session.add(UserProfile(user_id="learner-1"))
    projection_session.commit()
    later_time = OCCURRED_AT + timedelta(hours=1)
    later = FakeLearningEvent(
        event_id="33333333-3333-4333-8333-333333333333",
        occurred_at=later_time,
    )
    earlier = FakeLearningEvent(
        event_id="22222222-2222-4222-8222-222222222222",
        occurred_at=OCCURRED_AT,
        evaluation_outcome="incorrect",
    )
    event_source = FakeEventSource([later])
    service = LearnerProjectionService(
        ProgressRepository(projection_session),
        event_source,
    )
    service.apply_event(later)
    event_source.events.append(earlier)

    replayed = service.apply_event(earlier)

    assert (
        replayed.evidence.count,
        replayed.evidence.last_evidence_at,
        replayed.evidence.last_event_id,
        replayed.competence.success_weight,
        replayed.competence.failure_weight,
        replayed.competence.peak,
        replayed.memory.interval_days,
        replayed.memory.due_at,
        replayed.memory.lapses,
    ) == (2, later_time, later.event_id, 1, 1, 0.5, 1, later_time + timedelta(days=1), 1)


def test_reverse_event_id_at_equal_time_triggers_canonical_replay(
    projection_session,
) -> None:
    from app.models import UserProfile
    from app.repositories.progress import ProgressRepository
    from app.services.learner_projection_service import LearnerProjectionService

    projection_session.add(UserProfile(user_id="learner-1"))
    projection_session.commit()
    higher = FakeLearningEvent(
        event_id="33333333-3333-4333-8333-333333333333",
    )
    lower = FakeLearningEvent(
        event_id="22222222-2222-4222-8222-222222222222",
        evaluation_outcome="incorrect",
    )
    source = FakeEventSource([higher])
    service = LearnerProjectionService(
        ProgressRepository(projection_session),
        source,
    )
    service.apply_event(higher)
    source.events.append(lower)

    replayed = service.apply_event(lower)

    assert (
        replayed.evidence.count,
        replayed.evidence.last_event_id,
        replayed.competence.peak,
        replayed.memory.interval_days,
        replayed.memory.lapses,
    ) == (2, higher.event_id, 0.5, 1, 1)


def test_native_evidence_preserves_legacy_baseline_and_switches_policy_versions() -> None:
    from app.domain.progress import LearnerTargetState, ProjectionBaseline
    from app.services.learner_projection_service import project_event, replay_events

    baseline_due_at = OCCURRED_AT - timedelta(days=2)
    legacy = LearnerTargetState.legacy_bootstrap(
        state_id="11111111-1111-4111-8111-111111111111",
        learner_id="learner-1",
        target_key=TARGET_KEY,
        baseline=ProjectionBaseline.legacy(
            memory_due_at=baseline_due_at,
            memory_interval_days=3,
            source_ref="user_word_progress:42",
            source_fingerprint="a" * 64,
        ),
        updated_at=baseline_due_at,
    )
    event = FakeLearningEvent(
        event_id="22222222-2222-4222-8222-222222222222",
        evaluation_source="model_assisted",
    )

    replayed = replay_events(project_event(legacy, event), [event])

    assert (
        replayed.baseline,
        replayed.memory.due_at,
        replayed.memory.interval_days,
        replayed.memory.policy_version,
        replayed.projection_policy_version,
        replayed.evidence.count,
    ) == (legacy.baseline, baseline_due_at, 3, "memory-v1", "projection-v1", 1)


def test_incremental_and_replay_match_from_frozen_legacy_baseline() -> None:
    from app.domain.progress import LearnerTargetState, ProjectionBaseline
    from app.services.learner_projection_service import project_event, replay_events

    baseline_due_at = OCCURRED_AT - timedelta(days=2)
    baseline = LearnerTargetState.legacy_bootstrap(
        state_id="11111111-1111-4111-8111-111111111111",
        learner_id="learner-1",
        target_key=TARGET_KEY,
        baseline=ProjectionBaseline.legacy(
            memory_due_at=baseline_due_at,
            memory_interval_days=3,
            source_ref="user_word_progress:42",
            source_fingerprint="a" * 64,
        ),
        updated_at=baseline_due_at,
    )
    events = (
        FakeLearningEvent(
            event_id="33333333-3333-4333-8333-333333333333",
            occurred_at=OCCURRED_AT + timedelta(hours=1),
        ),
        FakeLearningEvent(
            event_id="22222222-2222-4222-8222-222222222222",
            evaluation_outcome="incorrect",
        ),
    )
    incremental = baseline
    for event in sorted(events, key=lambda item: (item.occurred_at, item.event_id)):
        incremental = project_event(incremental, event)

    replayed = replay_events(incremental, reversed(events))

    assert replayed == incremental
    assert replayed.baseline == baseline.baseline


def test_native_projection_freezes_repository_bootstrapped_legacy_baseline(
    projection_session,
) -> None:
    from app.domain.shared import Capability, Modality, TargetKind
    from app.domain.target import TargetSpec
    from app.models import UserProfile, UserWordProgress, VocabularyItem
    from app.repositories.catalog import CatalogRepository
    from app.repositories.progress import ProgressRepository
    from app.services.domain_bootstrap_service import bootstrap_catalog
    from app.services.learner_projection_service import LearnerProjectionService
    from app.services.legacy_progress_bootstrap_service import bootstrap_legacy_progress

    projection_session.add(UserProfile(user_id="learner-1"))
    word = VocabularyItem(
        serbian_cyrillic="реч",
        serbian_latin="reč",
        russian_translation="слово",
        cefr_level="A1",
        theme="daily",
    )
    projection_session.add(word)
    projection_session.flush()
    progress = UserWordProgress(
        user_id="learner-1",
        word_id=word.id,
        status="reviewing",
        first_seen_at=OCCURRED_AT - timedelta(days=5),
        last_seen_at=OCCURRED_AT - timedelta(days=2),
        next_review_at=OCCURRED_AT - timedelta(days=1),
        review_interval_days=3,
    )
    projection_session.add(progress)
    projection_session.commit()
    bootstrap_catalog(projection_session)
    bootstrap_legacy_progress(
        projection_session,
        bootstrap_at=OCCURRED_AT - timedelta(hours=1),
    )
    lexical_unit = CatalogRepository(
        projection_session
    ).get_by_legacy_vocabulary_item_id(word.id)
    assert lexical_unit is not None
    target = TargetSpec(
        target_kind=TargetKind.SENSE,
        target_id=lexical_unit.senses[0].id,
        capability=Capability.RETRIEVE_FORM,
        modality=Modality.WRITTEN,
    )
    event = FakeLearningEvent(
        event_id="22222222-2222-4222-8222-222222222222",
        target_key=target.target_key,
    )
    service = LearnerProjectionService(
        ProgressRepository(projection_session),
        FakeEventSource([event]),
    )

    projected = service.apply_event(event)
    frozen_baseline = projected.baseline
    progress.review_interval_days = 17
    progress.next_review_at = OCCURRED_AT + timedelta(days=17)
    projection_session.commit()
    rerun = bootstrap_legacy_progress(
        projection_session,
        bootstrap_at=OCCURRED_AT + timedelta(days=1),
    )
    reloaded = ProgressRepository(projection_session).get_state(
        "learner-1",
        target.target_key,
    )

    assert rerun.skipped_frozen == 1
    assert reloaded == projected
    assert reloaded is not None
    assert reloaded.baseline == frozen_baseline
