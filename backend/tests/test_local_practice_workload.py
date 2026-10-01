from dataclasses import replace
from datetime import timedelta
from uuid import uuid4

import test_local_practice_api as pilot_tests
import test_reviewed_pilot_publication as publication_tests

from app.domain_models.practice import ActivityInstanceModel
from app.services import local_practice_service

pilot_client = pilot_tests.pilot_client
postgresql_publication_engine = publication_tests.postgresql_publication_engine


def save_unknown(client, activity):
    response = client.post(f"/api/practice/pilot-test/activities/{activity['id']}/responses",
                           json={"idempotency_key": str(uuid4()), "response": "unknown"})
    assert response.status_code == 200


def test_daily_new_budget_shared_between_runs_counts_pending_and_exposure(pilot_client):
    run1, _ = pilot_tests.start(pilot_client)
    first = pilot_tests.next_activity(pilot_client, run1)["activity"]
    assert pilot_tests.next_activity(pilot_client, run1)["activity"] == first
    run2, _ = pilot_tests.start(pilot_client)
    second = pilot_tests.next_activity(pilot_client, run2, kind="exposure")["activity"]
    assert second["id"] != first["id"]
    assert second["context_family"] != first["context_family"]
    pilot_client.post(f"/api/practice/pilot-test/activities/{second['id']}/responses",
                      json={"idempotency_key": "exposure"})
    assert pilot_tests.next_activity(pilot_client, run2)["reason"] == "daily_acquire_budget_reached"
    workload = pilot_client.get(f"/api/practice/pilot-test/runs/{run1}").json()["workload"]
    assert workload["issued"]["new"] == 2
    assert workload["remaining"]["new"] == 0
    assert workload["timezone"] == "UTC"


def test_zero_root_budget_and_repair_budget_are_enforced(pilot_client, monkeypatch):
    monkeypatch.setattr(local_practice_service, "WORKLOAD", replace(local_practice_service.WORKLOAD, root_limit=0))
    run_id, _ = pilot_tests.start(pilot_client)
    assert pilot_tests.next_activity(pilot_client, run_id)["reason"] == "daily_workload_budget_reached"
    monkeypatch.setattr(local_practice_service, "WORKLOAD", replace(local_practice_service.WORKLOAD, root_limit=6, repair_limit=0))
    activity = pilot_tests.next_activity(pilot_client, run_id)["activity"]
    save_unknown(pilot_client, activity)
    response = pilot_client.post(f"/api/practice/pilot-test/activities/{activity['id']}/repair",
                                 json={"retry_id": str(uuid4()), "support": "cue"})
    assert response.status_code == 409
    assert "budget" in response.json()["detail"].lower()


def test_long_absence_restarts_bounded_budget_without_rewriting_old_activity(pilot_client, db_session):
    run_id, _ = pilot_tests.start(pilot_client)
    activity = pilot_tests.next_activity(pilot_client, run_id)["activity"]
    save_unknown(pilot_client, activity)
    old = db_session.get(ActivityInstanceModel, activity["id"])
    old.selected_at -= timedelta(days=90)
    db_session.commit()
    old_time = old.selected_at
    new_run, _ = pilot_tests.start(pilot_client)
    issued = pilot_tests.next_activity(pilot_client, new_run)["activity"]
    assert issued is not None
    assert db_session.get(ActivityInstanceModel, activity["id"]).selected_at == old_time
    workload = pilot_client.get(f"/api/practice/pilot-test/runs/{new_run}").json()["workload"]
    assert workload["issued"]["total"] == 1


def test_utc_rollover_and_prior_exposure_do_not_relabel_familiar_material_new(pilot_client, db_session, monkeypatch):
    from datetime import datetime, timezone
    from app.repositories.practice import PracticeRepository
    from app.domain_models.catalog import LanguageConstruction
    clock = datetime(2026, 10, 1, 23, 59, 59, tzinfo=timezone.utc)
    monkeypatch.setattr(PracticeRepository, "database_now", lambda self: clock)
    run_id, _ = pilot_tests.start(pilot_client)
    first = pilot_tests.next_activity(pilot_client, run_id, kind="exposure")["activity"]
    pilot_client.post(f"/api/practice/pilot-test/activities/{first['id']}/responses", json={"idempotency_key": "view"})
    target_id = db_session.get(ActivityInstanceModel, first["id"]).spec_payload["target_spec"]["target_id"]
    for construction in db_session.query(LanguageConstruction):
        if construction.id != target_id:
            construction.status = "retired"
    db_session.commit()
    clock += timedelta(seconds=2)
    new_run, resumed = pilot_tests.start(pilot_client)
    assert resumed["workload"]["issued"]["total"] == 0
    repeated = pilot_tests.next_activity(pilot_client, new_run)["activity"]
    assert repeated is not None
    assert "new_target" not in repeated["selection_reasons"]
    assert db_session.get(ActivityInstanceModel, repeated["id"]).selected_at.replace(tzinfo=timezone.utc) == clock


def test_v1_run_remains_readable_and_submittable_but_cannot_issue_again(pilot_client, db_session):
    from app.domain_models.practice import PracticeRunModel
    from app.services.local_workload import LEGACY_POLICY
    run_id, _ = pilot_tests.start(pilot_client)
    first = pilot_tests.next_activity(pilot_client, run_id)["activity"]
    run = db_session.get(PracticeRunModel, run_id)
    run.selection_policy_version = LEGACY_POLICY
    row = db_session.get(ActivityInstanceModel, first["id"])
    row.selection_policy_version = LEGACY_POLICY
    db_session.commit()
    assert pilot_tests.next_activity(pilot_client, run_id)["activity"]["id"] == first["id"]
    save_unknown(pilot_client, first)
    assert pilot_client.get(f"/api/practice/pilot-test/runs/{run_id}").status_code == 200
    assert pilot_tests.next_activity(pilot_client, run_id)["reason"] == "policy_retired"
    response = pilot_client.post(f"/api/practice/pilot-test/activities/{first['id']}/repair",
                                 json={"retry_id": str(uuid4()), "support": "reveal"})
    assert response.status_code == 409


def test_postgresql_parallel_runs_share_one_issuance_budget(postgresql_publication_engine, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from datetime import datetime, timezone
    from threading import Barrier
    from sqlalchemy.orm import Session
    from app.models import UserProfile
    from app.services.reviewed_pilot_publication_service import ContentPublicationService
    from app.services.reviewed_pilot_pack import load_reviewed_pilot_bundle
    from app.services.local_practice_service import LocalPracticeService
    monkeypatch.setattr(local_practice_service, "WORKLOAD", replace(local_practice_service.WORKLOAD, new_limit=1))
    run_ids = [str(uuid4()), str(uuid4())]
    with Session(postgresql_publication_engine) as session:
        session.add(UserProfile(user_id="parallel"))
        session.commit()
        ContentPublicationService(session).publish(load_reviewed_pilot_bundle(pilot_tests.PACK),
                                                   published_at=datetime.now(timezone.utc))
        for run_id in run_ids:
            LocalPracticeService(session).create_or_resume("parallel", run_id)
    barrier = Barrier(2)
    def issue(run_id):
        with Session(postgresql_publication_engine) as session:
            barrier.wait(timeout=5)
            return LocalPracticeService(session).next_activity("parallel", run_id)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(issue, run_ids))
    assert sum(result["activity"] is not None for result in results) == 1
    assert [result["reason"] for result in results if result["activity"] is None] == ["daily_acquire_budget_reached"]


def test_duplicate_v1_new_issuances_still_exhaust_new_budget(pilot_client, db_session):
    from app.domain_models.practice import PracticeRunModel
    from app.repositories.practice import PracticeRepository
    from app.services.local_workload import LEGACY_POLICY
    first_run, _ = pilot_tests.start(pilot_client)
    first = pilot_tests.next_activity(pilot_client, first_run)["activity"]
    second_run, _ = pilot_tests.start(pilot_client)
    row = db_session.get(PracticeRunModel, second_run)
    row.selection_policy_version = LEGACY_POLICY
    db_session.commit()
    repository = PracticeRepository(db_session)
    activity = repository.get_activity(first["id"])
    duplicate = replace(activity, id=str(uuid4()), practice_run_id=second_run,
                        selected_at=repository.database_now(),
                        selection=replace(activity.selection, policy_version=LEGACY_POLICY))
    repository.add_activity(repository.get_run(second_run), duplicate)
    db_session.commit()
    third_run, _ = pilot_tests.start(pilot_client)
    assert pilot_tests.next_activity(pilot_client, third_run)["reason"] == "daily_acquire_budget_reached"


def test_postgresql_submit_waits_for_profile_before_locking_run(postgresql_publication_engine, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from datetime import datetime, timezone
    from threading import Event
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from app.models import UserProfile
    from app.repositories.practice import PracticeRepository
    from app.services.reviewed_pilot_publication_service import ContentPublicationService
    from app.services.reviewed_pilot_pack import load_reviewed_pilot_bundle
    from app.services.local_practice_service import LocalPracticeService
    run_id = str(uuid4())
    with Session(postgresql_publication_engine) as session:
        session.add(UserProfile(user_id="lock-order"))
        session.commit()
        ContentPublicationService(session).publish(load_reviewed_pilot_bundle(pilot_tests.PACK),
                                                   published_at=datetime.now(timezone.utc))
        service = LocalPracticeService(session)
        service.create_or_resume("lock-order", run_id)
        activity = service.next_activity("lock-order", run_id)["activity"]
    acquired_run = Event()
    original = PracticeRepository.lock_run
    def lock_run(self, run_id):
        result = original(self, run_id)
        acquired_run.set()
        return result
    monkeypatch.setattr(PracticeRepository, "lock_run", lock_run)
    def submit():
        with Session(postgresql_publication_engine) as session:
            return LocalPracticeService(session).submit("lock-order", activity["id"],
                                                        idempotency_key="one", response="unknown")
    with Session(postgresql_publication_engine) as blocker, ThreadPoolExecutor(max_workers=1) as pool:
        blocker.scalar(select(UserProfile).where(UserProfile.user_id == "lock-order").with_for_update())
        future = pool.submit(submit)
        try:
            assert not acquired_run.wait(timeout=0.3), "Submission inverted profile/run lock order"
        finally:
            blocker.rollback()
        assert future.result(timeout=5)["outcome"] == "unresolved"
