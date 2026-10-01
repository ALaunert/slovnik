from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

import test_local_practice_api as pilot_tests
from app.domain_models.practice import LearningEventModel
from app.domain_models.progress import LearnerTargetStateModel

pilot_client = pilot_tests.pilot_client


def registry(**changes):
    return {"schema_version": 1, "protocol_version": "written-feasibility-protocol-v1", "synthetic": True,
            "review": {"status": "fixture", "reference": "synthetic engineering check"},
            "participants": [{"learner_id": "pilot-test", "pseudonym": str(uuid4()),
                              "consent_at": (datetime.now(timezone.utc)-timedelta(hours=1)).isoformat(),
                              "consent_version": "written-feasibility-consent-v1",
                              "consent_evidence_sha256": "a"*64, "withdrawn": False,
                              "scopes": ["local_practice", "research_export", "blinded_rating"]}], **changes}


def test_export_is_pseudonymous_minimized_and_never_mutates_projection(pilot_client, db_session):
    from app.research_export import export_local_events
    run_id, _ = pilot_tests.start(pilot_client)
    first = pilot_tests.next_activity(pilot_client, run_id)["activity"]
    pilot_client.post(f"/api/practice/pilot-test/activities/{first['id']}/responses",
                      json={"idempotency_key": "first", "response": "unknown"})
    state = db_session.scalar(select(LearnerTargetStateModel))
    before = (state.evidence_count, state.last_event_id, state.memory_due_at)
    enrollment = registry()
    exported = export_local_events(db_session, enrollment)
    assert exported["manifest"]["synthetic"] is True
    assert len(exported["records"]) == 1
    record = exported["records"][0]
    assert record["pseudonym"] == enrollment["participants"][0]["pseudonym"]
    assert record["first_response"] == "unknown"
    assert record["outcome"] == "unresolved"
    assert record["active_minutes"] is None
    assert record["delayed_eligibility"] == "unknown"
    assert not {"learner_id", "snapshot", "private_reviewed_example", "idempotency_key", "accepted_answers"} & record.keys()
    assert (state.evidence_count, state.last_event_id, state.memory_due_at) == before
    assert len(list(db_session.scalars(select(LearningEventModel)))) == 1


def test_export_excludes_withdrawn_and_preconsent_history(pilot_client, db_session):
    from app.research_export import export_local_events
    run_id, _ = pilot_tests.start(pilot_client)
    first = pilot_tests.next_activity(pilot_client, run_id)["activity"]
    pilot_client.post(f"/api/practice/pilot-test/activities/{first['id']}/responses",
                      json={"idempotency_key": "first", "response": ""})
    enrollment = registry()
    enrollment["participants"][0]["withdrawn"] = True
    assert export_local_events(db_session, enrollment)["records"] == []
    enrollment["participants"][0]["withdrawn"] = False
    enrollment["participants"][0]["consent_at"] = (datetime.now(timezone.utc)+timedelta(days=1)).isoformat()
    assert export_local_events(db_session, enrollment)["records"] == []


def test_export_requires_scope_unique_mapping_and_human_review(pilot_client, db_session):
    from app.research_export import export_local_events
    enrollment = registry()
    enrollment["participants"][0]["scopes"] = ["local_practice"]
    with pytest.raises(ValueError, match="scope"):
        export_local_events(db_session, enrollment)
    enrollment = registry()
    enrollment["participants"].append(enrollment["participants"][0].copy())
    with pytest.raises(ValueError, match="unique"):
        export_local_events(db_session, enrollment)
    with pytest.raises(ValueError, match="human|review|frozen"):
        export_local_events(db_session, registry(synthetic=False))


def test_export_writes_private_files_and_deletes_only_known_export(tmp_path):
    from app.research_export import write_export, remove_export
    enrollment = registry()
    export = {"records": [], "manifest": {"export_version": "local-research-export-v1",
              "files": ["events.json", "export-manifest.json"], "synthetic": True}}
    destination = tmp_path / "export"
    write_export(export, destination)
    assert destination.stat().st_mode & 0o777 == 0o700
    assert (destination / "events.json").stat().st_mode & 0o777 == 0o600
    (destination / "unrelated.txt").write_text(enrollment["protocol_version"])
    with pytest.raises(ValueError, match="unknown files"):
        remove_export(destination)
    assert (destination / "events.json").exists()
    (destination / "unrelated.txt").unlink()
    remove_export(destination)
    remove_export(destination)
    assert not destination.exists()


def test_pending_reveal_export_is_support_not_success(pilot_client, db_session):
    from app.research_export import export_local_events
    run_id, _ = pilot_tests.start(pilot_client)
    parent = pilot_tests.next_activity(pilot_client, run_id)["activity"]
    pilot_client.post(f"/api/practice/pilot-test/activities/{parent['id']}/responses",
                      json={"idempotency_key": "parent", "response": ""})
    pilot_client.post(f"/api/practice/pilot-test/activities/{parent['id']}/repair",
                      json={"retry_id": str(uuid4()), "support": "reveal"})
    exported = export_local_events(db_session, registry())
    child = next(record for record in exported["records"] if record["retry_of"])
    assert child["support_declared"] == "reveal"
    assert child["outcome"] is None and child["first_response"] is None
    assert child["independence_verified"] is False


def test_export_deletion_refuses_symlink_directory_or_files(tmp_path):
    from app.research_export import write_export, remove_export
    export = {"records": [], "manifest": {"export_version": "local-research-export-v1",
              "files": ["events.json", "export-manifest.json"], "synthetic": True}}
    destination = tmp_path / "export"
    write_export(export, destination)
    alias = tmp_path / "alias"
    alias.symlink_to(destination, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        remove_export(alias)
    assert destination.exists()
    raw = destination / "events.json"
    raw.unlink()
    outside = tmp_path / "outside.json"
    outside.write_text("[]")
    raw.symlink_to(outside)
    with pytest.raises(ValueError, match="symlink"):
        remove_export(destination)
    assert outside.exists() and raw.is_symlink()
