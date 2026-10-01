from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
import test_local_practice_api as pilot_tests
import test_content_publication as publication_tests

UTC = timezone.utc
pilot_client = pilot_tests.pilot_client
postgresql_publication_engine = publication_tests.postgresql_publication_engine


def profile():
    return SimpleNamespace(timezone="UTC", previous_timezone="UTC", timezone_change_at=None,
                           timezone_window_start=None)


@pytest.mark.parametrize("instant,hours", [("2026-03-29T10:00:00+00:00", 23), ("2026-10-25T10:00:00+00:00", 25)])
def test_local_day_spans_actual_dst_hours(instant, hours):
    from app.learner_time import day_window
    window = day_window(datetime.fromisoformat(instant), "Europe/Belgrade")
    assert window.end-window.start == timedelta(hours=hours)
    assert window.start <= datetime.fromisoformat(instant) < window.end
    assert window.start.tzinfo == UTC and window.end.tzinfo == UTC


@pytest.mark.parametrize("day,zone,expected", [
    (date(2018, 11, 4), "America/Sao_Paulo", "2018-11-04T03:00:00+00:00"),
    (date(2024, 11, 3), "America/Havana", "2024-11-03T04:00:00+00:00"),
    (date(2011, 12, 30), "Pacific/Apia", "2011-12-30T10:00:00+00:00"),
    (date(1919, 3, 31), "America/Toronto", "1919-03-31T04:30:00+00:00"),
])
def test_first_existing_day_boundary_handles_gap_fold_and_skipped_date(day, zone, expected):
    from app.learner_time import first_day_instant
    assert first_day_instant(day, zone) == datetime.fromisoformat(expected)


def test_zone_request_preserves_window_until_exact_new_boundary():
    from app.learner_time import allocation_window, request_timezone
    owner = profile()
    now = datetime(2026, 10, 1, 12, tzinfo=UTC)
    original = allocation_window(owner, now)
    request_timezone(owner, "Europe/Belgrade", now)
    pending = allocation_window(owner, now)
    assert pending.start == original.start
    assert pending.end == datetime(2026, 10, 2, 22, tzinfo=UTC)
    assert pending.zone == "UTC" and pending.transition is True
    active = allocation_window(owner, pending.end)
    assert active.zone == "Europe/Belgrade" and active.transition is False
    assert active.start == pending.end


def test_repeat_is_idempotent_and_pending_replacement_never_shortens_quota_period():
    from app.learner_time import allocation_window, request_timezone
    owner = profile()
    now = datetime(2026, 10, 1, 12, tzinfo=UTC)
    request_timezone(owner, "Pacific/Kiritimati", now)
    first = allocation_window(owner, now)
    facts = vars(owner).copy()
    request_timezone(owner, "Pacific/Kiritimati", now + timedelta(hours=1))
    assert vars(owner) == facts
    request_timezone(owner, "Pacific/Honolulu", now + timedelta(hours=1))
    second = allocation_window(owner, now)
    assert second.start == first.start and second.end >= first.end and second.zone == "UTC"
    request_timezone(owner, "UTC", now + timedelta(hours=2))
    third = allocation_window(owner, now)
    assert third.start == first.start and third.end >= second.end


def test_profile_api_adds_utc_fallback_and_rejects_invalid_zone(client):
    data = client.post("/api/profiles", json={"user_id": "calendar"}).json()
    assert data["timezone"] == data["effective_timezone"] == "UTC"
    assert data["allocation_window"]["transition"] is False
    bad = client.patch("/api/profiles/calendar", json={"timezone": "Mars/Olympus"})
    assert bad.status_code == 422
    changed = client.patch("/api/profiles/calendar", json={"timezone": "Europe/Belgrade"})
    assert changed.status_code == 200
    assert changed.json()["timezone"] == "Europe/Belgrade"
    assert changed.json()["effective_timezone"] == "UTC"
    assert changed.json()["allocation_window"]["transition"] is True


def test_legacy_review_list_status_and_grade_share_local_day(client, db_session, monkeypatch):
    from app.models import UserProfile, UserWordProgress, VocabularyItem
    from app.services import learning_service
    from app.learner_time import day_window
    now = datetime(2026, 10, 2, 1, tzinfo=UTC)
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return now
    monkeypatch.setattr(learning_service, "datetime", Clock)
    zone = "Pacific/Honolulu"
    local = day_window(now, zone)
    touched = local.start + timedelta(seconds=1)
    owner = UserProfile(user_id="local-review", timezone=zone)
    word = VocabularyItem(serbian_cyrillic="дан", serbian_latin="dan", russian_translation="день",
                          cefr_level="A1", theme="time")
    db_session.add_all([owner, word])
    db_session.flush()
    progress = UserWordProgress(user_id=owner.user_id, word_id=word.id, status="seen", first_seen_at=touched,
                                last_seen_at=touched, next_review_at=None, is_weak=False)
    db_session.add(progress)
    db_session.commit()
    assert learning_service.get_review_words(db_session, owner.user_id) == []
    assert learning_service.get_review_status(db_session, owner.user_id, word.id) is False
    with pytest.raises(ValueError, match="not currently due"):
        learning_service.grade_review(db_session, owner.user_id, word.id, "good")


def test_written_issuance_report_rolls_over_at_local_midnight(pilot_client, db_session, monkeypatch):
    import test_local_practice_api as pilot_tests
    from app.models import UserProfile
    from app.repositories.practice import PracticeRepository
    clock = datetime(2026, 10, 1, 21, 59, 59, tzinfo=UTC)
    monkeypatch.setattr(PracticeRepository, "database_now", lambda self: clock)
    owner = db_session.get(UserProfile, "pilot-test")
    # A directly constructed profile models a zone that already became effective.
    owner.timezone = "Europe/Belgrade"
    db_session.commit()
    run_id, _ = pilot_tests.start(pilot_client)
    first = pilot_tests.next_activity(pilot_client, run_id)["activity"]
    pilot_client.post(f"/api/practice/pilot-test/activities/{first['id']}/responses",
                      json={"idempotency_key": "one", "response": "unknown"})
    before = pilot_client.get(f"/api/practice/pilot-test/runs/{run_id}").json()["workload"]
    assert before["timezone"] == "Europe/Belgrade"
    assert before["issued"]["total"] == 1
    assert before["window"]["end"] == "2026-10-01T22:00:00+00:00"
    clock += timedelta(seconds=1)
    after = pilot_client.get(f"/api/practice/pilot-test/runs/{run_id}").json()["workload"]
    assert after["issued"]["total"] == 0


def test_timezone_change_does_not_reset_consumed_written_quota(pilot_client, db_session, monkeypatch):
    import test_local_practice_api as pilot_tests
    from app.repositories.practice import PracticeRepository
    clock = datetime(2026, 10, 1, 12, tzinfo=UTC)
    monkeypatch.setattr(PracticeRepository, "database_now", lambda self: clock)
    run1, _ = pilot_tests.start(pilot_client)
    run2, _ = pilot_tests.start(pilot_client)
    for run in (run1, run2):
        activity = pilot_tests.next_activity(pilot_client, run)["activity"]
        pilot_client.post(f"/api/practice/pilot-test/activities/{activity['id']}/responses",
                          json={"idempotency_key": str(run), "response": "unknown"})
    before = pilot_client.get(f"/api/practice/pilot-test/runs/{run1}").json()["workload"]
    changed = pilot_client.patch("/api/profiles/pilot-test", json={"timezone": "Pacific/Honolulu"})
    assert changed.status_code == 200
    clock = datetime(2026, 10, 2, 0, 1, tzinfo=UTC)
    after = pilot_client.get(f"/api/practice/pilot-test/runs/{run1}").json()["workload"]
    assert after["issued"] == before["issued"]
    assert after["remaining"]["new"] == 0 and after["window"]["transition"] is True
    assert pilot_tests.next_activity(pilot_client, run1)["reason"] == "daily_acquire_budget_reached"


def test_daily_quiz_prioritizes_touches_in_local_day_and_week_starts_locally(db_session, monkeypatch):
    from app.models import UserProfile, UserWordProgress, VocabularyItem
    from app.services import quiz_service
    now = datetime(2026, 10, 5, 1, tzinfo=UTC)  # Sunday locally in Honolulu; Monday in UTC.
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return now
    monkeypatch.setattr(quiz_service, "datetime", Clock)
    owner = UserProfile(user_id="local-quiz", timezone="Pacific/Honolulu")
    db_session.add(owner)
    for index, touched in enumerate([now-timedelta(days=2), now-timedelta(hours=3)]):
        word = VocabularyItem(serbian_cyrillic=f"дан{index}", serbian_latin=f"dan{index}",
                              russian_translation=f"день{index}", cefr_level="A1", theme="time")
        db_session.add(word)
        db_session.flush()
        db_session.add(UserWordProgress(user_id=owner.user_id, word_id=word.id, status="seen", first_seen_at=touched,
                                        last_seen_at=touched, is_weak=False))
    db_session.commit()
    daily = quiz_service._source_progress(db_session, owner.user_id, "daily")
    assert daily[0].first_seen_at.replace(tzinfo=UTC) == now-timedelta(hours=3)
    assert len(quiz_service._source_progress(db_session, owner.user_id, "weekly")) == 2


def test_timezone_upgrade_preserves_legacy_rows_and_downgrades(tmp_path, monkeypatch):
    from alembic import command
    from sqlalchemy import create_engine, text
    from test_migrations import build_alembic_config, seed_legacy_vocabulary, seed_legacy_progress, LEGACY_USER_ID
    url = f"sqlite:///{tmp_path / 'timezone.db'}"
    config = build_alembic_config(url, monkeypatch)
    command.upgrade(config, "20260826_0005")
    engine = create_engine(url)
    seed_legacy_vocabulary(engine)
    seed_legacy_progress(engine)
    with engine.connect() as connection:
        before = connection.execute(text("SELECT * FROM user_word_progress")).mappings().all()
    command.upgrade(config, "head")
    with engine.connect() as connection:
        owner = connection.execute(text("SELECT * FROM user_profiles WHERE user_id=:id"), {"id": LEGACY_USER_ID}).mappings().one()
        assert owner["timezone"] == owner["previous_timezone"] == "UTC"
        assert owner["timezone_change_at"] is None and owner["timezone_window_start"] is None
        assert connection.execute(text("SELECT * FROM user_word_progress")).mappings().all() == before
    command.downgrade(config, "20260826_0005")
    with engine.connect() as connection:
        assert connection.execute(text("SELECT * FROM user_word_progress")).mappings().all() == before
    engine.dispose()


def test_new_repair_pins_its_own_window_without_rewriting_parent(pilot_client, db_session, monkeypatch):
    from uuid import uuid4
    from app.domain_models.practice import ActivityInstanceModel
    from app.repositories.practice import PracticeRepository
    clock = datetime(2026, 10, 1, 12, tzinfo=UTC)
    monkeypatch.setattr(PracticeRepository, "database_now", lambda self: clock)
    run, _ = pilot_tests.start(pilot_client)
    parent = pilot_tests.next_activity(pilot_client, run)["activity"]
    pilot_client.post(f"/api/practice/pilot-test/activities/{parent['id']}/responses",
                      json={"idempotency_key": "parent", "response": "unknown"})
    original = db_session.get(ActivityInstanceModel, parent["id"]).spec_payload.copy()
    pilot_client.patch("/api/profiles/pilot-test", json={"timezone": "Europe/Belgrade"})
    response = pilot_client.post(f"/api/practice/pilot-test/activities/{parent['id']}/repair",
                                 json={"retry_id": str(uuid4()), "support": "cue"})
    assert response.status_code == 200
    child = db_session.get(ActivityInstanceModel, response.json()["id"])
    assert child.spec_payload["snapshot"]["workload_policy"]["window"]["transition"] is True
    assert db_session.get(ActivityInstanceModel, parent["id"]).spec_payload == original


@pytest.mark.parametrize("operation", ["next", "repair"])
def test_postgresql_timezone_change_serializes_with_issuance(postgresql_publication_engine, monkeypatch, operation):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from uuid import uuid4
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from app.models import UserProfile
    from app.repositories.practice import PracticeRepository
    from app.services.content_publication_service import ContentPublicationService
    from app.services.reviewed_pilot_pack import load_reviewed_pilot_bundle
    from app.services.local_practice_service import LocalPracticeService
    from app.domain_models.practice import ActivityInstanceModel
    from app.learner_time import request_timezone
    run = str(uuid4())
    with Session(postgresql_publication_engine) as session:
        session.add(UserProfile(user_id="zone-race"))
        session.commit()
        ContentPublicationService(session).publish(load_reviewed_pilot_bundle(pilot_tests.PACK), published_at=datetime.now(UTC))
        service = LocalPracticeService(session)
        service.create_or_resume("zone-race", run)
        first = service.next_activity("zone-race", run)["activity"]
        service.submit("zone-race", first["id"], idempotency_key="first", response="unknown")
    sampled_clock = Event()
    original = PracticeRepository.database_now
    def clock(self):
        sampled_clock.set()
        return original(self)
    monkeypatch.setattr(PracticeRepository, "database_now", clock)
    def issue():
        with Session(postgresql_publication_engine) as session:
            service = LocalPracticeService(session)
            result = (service.next_activity("zone-race", run)["activity"] if operation == "next" else
                      service.repair("zone-race", first["id"], retry_id=str(uuid4()), support="cue"))
            return session.get(ActivityInstanceModel, result["id"]).spec_payload["snapshot"]["workload_policy"]
    with Session(postgresql_publication_engine) as blocker, ThreadPoolExecutor(max_workers=1) as pool:
        owner = blocker.scalar(select(UserProfile).where(UserProfile.user_id == "zone-race").with_for_update())
        request_timezone(owner, "Europe/Belgrade", original(PracticeRepository(blocker)))
        future = pool.submit(issue)
        try:
            assert not sampled_clock.wait(timeout=0.3), "Issuance sampled time before acquiring the profile lock"
        finally:
            blocker.commit()
        report = future.result(timeout=5)
        assert report["window"]["transition"] is True
        assert report["issued"]["total"] == 1

