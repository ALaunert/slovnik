from uuid import uuid4

from sqlalchemy import select

from app.domain_models.practice import ActivityInstanceModel, LearningEventModel
from app.domain_models.catalog import LanguageConstruction
from app.domain_models.progress import LearnerTargetStateModel
from app.repositories.practice import PracticeRepository
from app.services.evidence_diagnostic_service import diagnose_events
import test_local_practice_api as pilot_tests
from test_local_practice_api import start, next_activity

pilot_client = pilot_tests.pilot_client


def submit(client, activity_id, response, token):
    return client.post(f"/api/practice/pilot-test/activities/{activity_id}/responses",
                       json={"idempotency_key": token, "response": response})


def test_wrong_first_answer_survives_hint_and_one_linked_repair(pilot_client, db_session):
    run_id, _ = start(pilot_client)
    first = next_activity(pilot_client, run_id)["activity"]
    original = submit(pilot_client, first["id"], "", "first")
    assert original.json()["outcome"] == "incorrect"
    retry_id = str(uuid4())
    url = f"/api/practice/pilot-test/activities/{first['id']}/repair"
    body = {"retry_id": retry_id, "support": "cue"}
    response = pilot_client.post(url, json=body)
    assert response.status_code == 200, response.text
    child = response.json()
    assert child["id"] == retry_id and child["retry_of"] == first["id"]
    assert child["support"]["kind"] == "cue"
    assert pilot_client.post(url, json=body).json() == child
    assert pilot_client.post(url, json={**body, "support": "reveal"}).status_code == 409
    assert pilot_client.post(url, json={**body, "retry_id": str(uuid4())}).status_code == 409
    row = db_session.get(ActivityInstanceModel, retry_id)
    answer = row.spec_payload["snapshot"]["private_reviewed_example"]["accepted_answers"][0]
    repaired = submit(pilot_client, retry_id, answer, "repair-once")
    assert repaired.status_code == 200, repaired.text
    assert repaired.json()["outcome"] == "correct"
    assert repaired.json()["evidence_kind"] == "repair"
    assert submit(pilot_client, retry_id, answer, "repair-once").json() == repaired.json()
    assert pilot_client.get(f"/api/practice/pilot-test/activities/{first['id']}/feedback").json()["can_repair"] is False
    assert pilot_client.post(f"/api/practice/pilot-test/activities/{retry_id}/repair",
                             json={"retry_id": str(uuid4()), "support": "cue"}).status_code == 409
    repository = PracticeRepository(db_session)
    events = [repository.get_learning_event("pilot-test", row.idempotency_key)
              for row in db_session.scalars(select(LearningEventModel).order_by(LearningEventModel.occurred_at))]
    assert len(events) == 2
    assert events[0].evaluation_outcome.value == "incorrect"
    assert events[0].first_response.value == ""
    assert events[1].repair_outcome.value == "repaired"
    assert events[1].hints[0].kind.value == "cue"
    assert repository.get_activity(first["id"]).spec.snapshot["support_before_first"] is False
    assert repository.get_activity(retry_id).spec.snapshot["support_before_first"] is True
    classified = diagnose_events((event, repository.get_activity(event.activity_instance_id)) for event in events)
    assert [item.category for item in classified] == ["independent_first", "repair"]
    state = db_session.scalar(select(LearnerTargetStateModel))
    assert state.competence_failure_weight == 1  # v1 keeps the original failure.
    assert state.memory_due_at is not None  # v1 schedules the later opportunity.


def test_revealed_repair_without_submission_has_no_second_scored_event(pilot_client, db_session):
    run_id, _ = start(pilot_client)
    first = next_activity(pilot_client, run_id)["activity"]
    submit(pilot_client, first["id"], "", "first")
    response = pilot_client.post(f"/api/practice/pilot-test/activities/{first['id']}/repair",
                                json={"retry_id": str(uuid4()), "support": "reveal"})
    assert response.status_code == 200, response.text
    assert response.json()["support"]["example"]["serbian"]
    assert len(db_session.scalars(select(LearningEventModel)).all()) == 1
    assert db_session.scalar(select(LearnerTargetStateModel)).competence_success_weight == 0


def test_correct_first_answer_has_feedback_but_no_repair(pilot_client, db_session):
    run_id, _ = start(pilot_client)
    first = next_activity(pilot_client, run_id)["activity"]
    feedback_url = f"/api/practice/pilot-test/activities/{first['id']}/feedback"
    assert pilot_client.get(feedback_url).status_code == 409
    row = db_session.get(ActivityInstanceModel, first["id"])
    answer = row.spec_payload["snapshot"]["private_reviewed_example"]["accepted_answers"][0]
    submit(pilot_client, first["id"], answer, "correct")
    feedback = pilot_client.get(feedback_url)
    assert feedback.status_code == 200, feedback.text
    assert feedback.json()["first_result"]["outcome"] == "correct"
    assert feedback.json()["example"]["answer"] == answer
    assert pilot_client.post(f"/api/practice/pilot-test/activities/{first['id']}/repair",
                             json={"retry_id": str(uuid4()), "support": "cue"}).status_code == 409


def test_unresolved_first_answer_is_not_reclassified_by_correct_fallback(pilot_client, db_session):
    run_id, _ = start(pilot_client)
    first = next_activity(pilot_client, run_id)["activity"]
    submit(pilot_client, first["id"], "unlisted", "unresolved")
    child = pilot_client.post(f"/api/practice/pilot-test/activities/{first['id']}/repair",
                             json={"retry_id": str(uuid4()), "support": "correction"})
    assert child.status_code == 200, child.text
    row = db_session.get(ActivityInstanceModel, child.json()["id"])
    answer = row.spec_payload["snapshot"]["private_reviewed_example"]["accepted_answers"][0]
    corrected = submit(pilot_client, child.json()["id"], answer, "fallback")
    assert corrected.json()["evidence_kind"] == "supported_retry"
    repository = PracticeRepository(db_session)
    assert repository.get_learning_event("pilot-test", "unresolved").evaluation_outcome.value == "unresolved"
    assert repository.get_learning_event("pilot-test", "fallback").repair_outcome is None


def test_repair_is_owned_and_cannot_issue_retired_content(pilot_client, db_session):
    run_id, _ = start(pilot_client)
    first = next_activity(pilot_client, run_id)["activity"]
    submit(pilot_client, first["id"], "", "first")
    body = {"retry_id": str(uuid4()), "support": "correction"}
    assert pilot_client.post(f"/api/practice/other/activities/{first['id']}/repair", json=body).status_code == 404
    assert pilot_client.get(f"/api/practice/other/activities/{first['id']}/feedback").status_code == 404
    activity = db_session.get(ActivityInstanceModel, first["id"])
    db_session.get(LanguageConstruction, activity.spec_payload["target_spec"]["target_id"]).status = "retired"
    db_session.commit()
    assert pilot_client.post(f"/api/practice/pilot-test/activities/{first['id']}/repair", json=body).status_code == 409


def test_repeated_root_context_is_not_an_independent_recurrence(pilot_client, db_session, monkeypatch):
    from datetime import timedelta
    run_id, _ = start(pilot_client)
    first = next_activity(pilot_client, run_id)["activity"]
    submit(pilot_client, first["id"], "", "first")
    clock = PracticeRepository(db_session).database_now() + timedelta(days=1)
    monkeypatch.setattr(PracticeRepository, "database_now", lambda self: clock)
    first_target = db_session.get(ActivityInstanceModel, first["id"]).spec_payload["target_spec"]["target_id"]
    for construction in db_session.query(LanguageConstruction):
        if construction.id != first_target:
            construction.status = "retired"
    db_session.commit()
    second_run, _ = start(pilot_client)
    second = next_activity(pilot_client, second_run)["activity"]
    assert second["context_family"] == first["context_family"]
    row = db_session.get(ActivityInstanceModel, second["id"])
    answer = row.spec_payload["snapshot"]["private_reviewed_example"]["accepted_answers"][0]
    submit(pilot_client, second["id"], answer, "repeated")
    repository = PracticeRepository(db_session)
    events = [repository.get_learning_event("pilot-test", token) for token in ("first", "repeated")]
    categories = diagnose_events((event, repository.get_activity(event.activity_instance_id)) for event in events)
    assert [item.category for item in categories] == ["independent_first", "repeated_context"]


def test_answer_feedback_is_withheld_before_and_during_cue_repair(pilot_client):
    run_id, _ = start(pilot_client)
    first = next_activity(pilot_client, run_id)["activity"]
    submit(pilot_client, first["id"], "", "first")
    feedback_url = f"/api/practice/pilot-test/activities/{first['id']}/feedback"
    assert pilot_client.get(feedback_url).status_code == 409
    child = pilot_client.post(f"/api/practice/pilot-test/activities/{first['id']}/repair",
                             json={"retry_id": str(uuid4()), "support": "cue"})
    assert child.status_code == 200
    assert pilot_client.get(feedback_url).status_code == 409
    assert pilot_client.get(f"/api/practice/pilot-test/activities/{child.json()['id']}/feedback").status_code == 409


def test_reserved_reveal_repair_makes_disclosure_immutable(pilot_client):
    run_id, _ = start(pilot_client)
    first = next_activity(pilot_client, run_id)["activity"]
    submit(pilot_client, first["id"], "", "first")
    child = pilot_client.post(f"/api/practice/pilot-test/activities/{first['id']}/repair",
                             json={"retry_id": str(uuid4()), "support": "reveal"})
    assert child.status_code == 200
    assert child.json()["support"]["kind"] == "reveal"
    feedback = pilot_client.get(f"/api/practice/pilot-test/activities/{first['id']}/feedback")
    assert feedback.status_code == 200
    assert feedback.json()["can_repair"] is False
