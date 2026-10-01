from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import settings
from app.db import get_db
from app.domain_models.catalog import LanguageConstruction
from app.domain_models.practice import ActivityInstanceModel, LearningEventModel
from app.domain_models.progress import LearnerTargetStateModel
from app.main import app
from app.models import UserProfile
from app.services.content_publication_service import ContentPublicationService
from app.services.reviewed_pilot_pack import load_reviewed_pilot_bundle


PACK = Path(__file__).resolve().parents[2] / "content/curricula/a1-pilot/publication-v1.json"


@pytest.fixture()
def pilot_client(db_session, monkeypatch):
    # A genuine listener is supplied by the launcher; unit HTTP tests exercise
    # that dependency separately rather than pretending TestClient is a socket.
    monkeypatch.setattr(settings, "local_pilot_enabled", True)
    db_session.add(UserProfile(user_id="pilot-test"))
    db_session.commit()
    bundle = load_reviewed_pilot_bundle(PACK)
    from datetime import datetime, timezone
    ContentPublicationService(db_session).publish(bundle, published_at=datetime.now(timezone.utc))
    app.dependency_overrides[get_db] = lambda: db_session
    from app.local_pilot import require_local_pilot
    app.dependency_overrides[require_local_pilot] = lambda: None
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def start(client):
    run_id = str(uuid4())
    response = client.put(f"/api/practice/pilot-test/runs/{run_id}")
    assert response.status_code == 200, response.text
    return run_id, response.json()


def next_activity(client, run_id, **body):
    response = client.post(f"/api/practice/pilot-test/runs/{run_id}/next", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def test_run_creation_resume_and_pending_next_are_idempotent(pilot_client):
    run_id, first = start(pilot_client)
    assert first["activities"] == []
    assert pilot_client.put(f"/api/practice/pilot-test/runs/{run_id}").json() == first
    activity = next_activity(pilot_client, run_id)["activity"]
    assert next_activity(pilot_client, run_id)["activity"] == activity
    resumed = pilot_client.get(f"/api/practice/pilot-test/runs/{run_id}")
    assert resumed.json()["activities"] == [activity]
    assert pilot_client.get(f"/api/practice/other/runs/{run_id}").status_code == 404


def test_public_activity_has_no_unrevealed_keys_or_holdout(pilot_client):
    run_id, _ = start(pilot_client)
    activity = next_activity(pilot_client, run_id)["activity"]
    assert set(activity) == {
        "id", "kind", "operation", "cue_level", "status", "sequence_number",
        "capability", "context_family", "task", "response_contract", "presentation",
        "selection_reasons", "result", "retry_of", "support",
    }
    assert activity["presentation"] is None
    assert activity["result"] is None
    assert "expected" not in activity["task"]
    assert activity["context_family"].endswith("-practice")


def test_unresolved_first_response_is_saved_once_without_credit(pilot_client, db_session):
    run_id, _ = start(pilot_client)
    activity = next_activity(pilot_client, run_id)["activity"]
    url = f"/api/practice/pilot-test/activities/{activity['id']}/responses"
    body = {"idempotency_key": "submit-once", "response": "Неизвестная формулировка"}
    first = pilot_client.post(url, json=body)
    assert first.status_code == 200, first.text
    assert first.json()["outcome"] == "unresolved"
    assert pilot_client.post(url, json=body).json() == first.json()
    assert pilot_client.post(url, json={**body, "response": "другой ответ"}).status_code == 409
    rows = db_session.scalars(select(LearningEventModel)).all()
    assert len(rows) == 1
    assert rows[0].observation_payload["first_response"]["value"] == body["response"]
    state = db_session.scalar(select(LearnerTargetStateModel))
    assert state.evidence_count == 1
    assert state.deterministic_evidence_count == 0
    assert state.competence_success_weight == state.competence_failure_weight == 0
    assert state.memory_due_at is None
    resumed = pilot_client.get(f"/api/practice/pilot-test/runs/{run_id}").json()
    assert resumed["activities"][0]["result"] == first.json()


def test_exposure_is_an_immutable_non_scored_presentation(pilot_client, db_session):
    run_id, _ = start(pilot_client)
    activity = next_activity(pilot_client, run_id, kind="exposure")["activity"]
    assert activity["kind"] == "exposure" and activity["operation"] is None
    assert activity["presentation"]["serbian"]
    url = f"/api/practice/pilot-test/activities/{activity['id']}/responses"
    assert pilot_client.post(url, json={"idempotency_key": "exposure", "response": "fake"}).status_code == 422
    result = pilot_client.post(url, json={"idempotency_key": "exposure"})
    assert result.status_code == 200, result.text
    assert result.json()["outcome"] is None
    event = db_session.scalar(select(LearningEventModel))
    assert event.event_type == "exposure" and event.observation_payload["first_response"] is None


def test_retired_target_cannot_be_issued_but_issued_key_survives(pilot_client, db_session):
    run_id, _ = start(pilot_client)
    activity = next_activity(pilot_client, run_id)["activity"]
    # Preserve the issued key even if future catalog status changes.
    for row in db_session.scalars(select(LanguageConstruction)):
        row.status = "retired"
    db_session.commit()
    result = pilot_client.post(
        f"/api/practice/pilot-test/activities/{activity['id']}/responses",
        json={"idempotency_key": "pinned", "response": "unknown"},
    )
    assert result.status_code == 200, result.text
    stopped = next_activity(pilot_client, run_id)
    assert stopped["activity"] is None
    assert stopped["reason"] == "empty_frontier"


def test_default_practice_gate_fails_closed(client):
    assert client.get("/api/practice/availability").status_code == 404
    assert client.put(f"/api/practice/pilot-test/runs/{uuid4()}").status_code == 404
    assert client.get("/api/health").status_code == 200


def test_issued_snapshot_pins_source_and_grades_without_current_files(pilot_client, db_session, monkeypatch):
    from app.services import local_practice_service
    run_id, _ = start(pilot_client)
    activity = next_activity(pilot_client, run_id)["activity"]
    row = db_session.get(ActivityInstanceModel, activity["id"])
    snapshot = row.spec_payload["snapshot"]
    assert snapshot["snapshot_version"] == 2
    assert snapshot["pack"]["bank_digest"]
    assert snapshot["source"]["release"]
    assert snapshot["source"]["checksum"]
    assert snapshot["answer_policy_revision"] == 1
    assert snapshot["primary_capability"] == "apply_construction"
    assert snapshot["target_span"] == snapshot["private_reviewed_example"]["target_span"]
    answer = snapshot["private_reviewed_example"]["accepted_answers"][0]
    monkeypatch.setattr(local_practice_service, "PACK", Path("/missing/file"))
    result = pilot_client.post(
        f"/api/practice/pilot-test/activities/{activity['id']}/responses",
        json={"idempotency_key": "correct-pinned", "response": answer},
    )
    assert result.status_code == 200, result.text
    assert result.json()["outcome"] == "correct"


def test_all_four_practice_items_issue_once_and_holdouts_stay_private(pilot_client, db_session, monkeypatch):
    from dataclasses import replace
    from app.services import local_practice_service
    # Content coverage independently of the smaller default daily new allocation.
    monkeypatch.setattr(local_practice_service, "WORKLOAD", replace(local_practice_service.WORKLOAD, new_limit=4))
    run_id, _ = start(pilot_client)
    issued = []
    for index in range(4):
        activity = next_activity(pilot_client, run_id)["activity"]
        assert activity is not None
        issued.append(activity)
        assert pilot_client.post(
            f"/api/practice/pilot-test/activities/{activity['id']}/responses",
            json={"idempotency_key": f"unresolved-{index}", "response": "unknown"},
        ).status_code == 200
    assert len({item["context_family"] for item in issued}) == 4
    assert {item["operation"] for item in issued} == {"complete", "transform"}
    assert next_activity(pilot_client, run_id)["activity"] is None
