import copy
from pathlib import Path
import json

import pytest

from test_research_export import registry
import test_local_practice_api as pilot_tests

pilot_client = pilot_tests.pilot_client


def inputs():
    from app.services.reviewed_pilot_pack import load_reviewed_pilot_bundle
    enrollment = registry()
    enrollment["participants"][0]["slot"] = 0
    bundle = load_reviewed_pilot_bundle(pilot_tests.PACK)
    return enrollment, bundle


def test_assignment_balances_twelve_slots_and_pins_reviewed_content():
    from app.research_dataset import freeze_assignment
    enrollment, bundle = inputs()
    assignment = freeze_assignment(enrollment, bundle, seed="fixture-1", frozen_at="2026-09-01T00:00:00+00:00")
    assert assignment == freeze_assignment(enrollment, bundle, seed="fixture-1", frozen_at="2026-09-01T00:00:00+00:00")
    assert len(assignment["slots"]) == 12
    targets = set(assignment["targets"])
    for slot in assignment["slots"]:
        assert set(slot["7"]) | set(slot["28"]) == targets
        assert len(slot["7"]) == len(slot["28"]) == 2
        assert not set(slot["7"]) & set(slot["28"])
    for target in targets:
        assert sum(target in slot["7"] for slot in assignment["slots"]) == 6
    assert assignment["cohort"] == [{"pseudonym": enrollment["participants"][0]["pseudonym"], "slot": 0}]
    assert "bank_digest" in assignment["pins"] and "rights_digest" in assignment["pins"]
    assert all(row["assessment"]["context_family"] != row["practice"]["context_family"]
               for row in assignment["targets"].values())


def test_record_digest_matches_actual_export(pilot_client, db_session):
    from app.research_dataset import digest
    from app.research_export import export_local_events
    run, _ = pilot_tests.start(pilot_client)
    pilot_tests.next_activity(pilot_client, run)
    exported = export_local_events(db_session, registry())
    assert exported["manifest"]["records_sha256"] == digest(exported["records"])
    assert "response_kind" in exported["records"][0]


def source_rows(history):
    """Explicit synthetic responses for a join test, never historical backfill."""
    rows = []
    for activity in history["activities"]:
        response = activity.get("response")
        rows.append({"activity_id": activity["id"], "issued_at": activity["offered_at"],
                     "context_family": activity["context_family"], "retry_of": activity.get("retry_of"),
                     "support_declared": activity["support"], "response_at": response["at"] if response else None,
                     "response_kind": "rating" if response and response["kind"] == "self_report" else "text" if response else None,
                     "first_response": response.get("rating", "synthetic answer") if response else None,
                     "outcome": response.get("outcome") if response else None,
                     "probe_horizon_days": activity.get("probe_horizon_days")})
    return rows


def test_joint_source_observer_reconciliation_preserves_all_six_p0_truths():
    from app.research_dataset import join_source_history
    from app.research_ledger import summarize_history
    fixture = json.loads((Path(__file__).parent / "fixtures/learning/p0_01_histories.json").read_text())
    for original in fixture["histories"]:
        source = source_rows(original)
        observer = copy.deepcopy(original)
        for activity, row in zip(observer["activities"], source):
            if activity.get("response"):
                activity["response"]["text"] = row["first_response"]
        joined = join_source_history(source, observer)
        history = {**joined, "history_complete": True, "support_capture_complete": True, "key_frozen": True}
        actual = summarize_history(history)
        for metric, expected in original["expected"].items():
            assert actual[metric] == expected


def test_observer_cannot_omit_or_rewrite_source_first_response():
    from app.research_dataset import join_source_history
    history = {"presentations": [], "activities": [
        {"id": "a", "context_family": "practice", "offered_at": "2026-10-01T00:00:00+00:00", "support": "reveal",
         "support_at": "2026-10-01T00:00:01+00:00",
         "response": {"kind": "scored", "at": "2026-10-01T00:01:00+00:00", "outcome": "incorrect", "text": "synthetic answer"}}]}
    rows = source_rows(history)
    assert join_source_history(rows, history)["activities"][0]["response"]["outcome"] == "incorrect"
    with pytest.raises(ValueError, match="missing|coverage"):
        join_source_history(rows, {"activities": [], "presentations": []})
    for field, value in [("text", "changed"), ("outcome", "correct"), ("at", "2026-10-02T00:01:00+00:00")]:
        altered = copy.deepcopy(history)
        altered["activities"][0]["response"][field] = value
        with pytest.raises(ValueError, match="immutable|first response"):
            join_source_history(rows, altered)
    altered = copy.deepcopy(history)
    altered["activities"][0]["support"] = "none"
    with pytest.raises(ValueError, match="support"):
        join_source_history(rows, altered)


def prepared_data():
    from uuid import uuid4
    from app.research_dataset import freeze_assignment, digest, _source_activity
    enrollment, bundle = inputs()
    participant = enrollment["participants"][0]
    participant["consent_at"] = "2026-09-01T00:00:00+00:00"
    assignment = freeze_assignment(enrollment, bundle, seed="joined-fixture", frozen_at="2026-09-02T00:00:00+00:00")
    key = assignment["slots"][0]["7"][0]
    target = assignment["targets"][key]
    items = {item["id"]: item for item in bundle.examples["examples"]}
    practice = items[target["practice"]["id"]]
    heldout = items[target["assessment"]["id"]]
    source = {"pseudonym": participant["pseudonym"], "activity_id": str(uuid4()), "event_id": str(uuid4()),
              "target_key": key, "capability": target["capability"], "modality": target["modality"],
              "context_family": practice["context_family"], "retry_of": None, "support_declared": "none",
              "issued_at": "2026-10-01T10:00:00+00:00", "response_at": "2026-10-01T10:01:00+00:00",
              "first_response": practice["accepted_answers"][0], "response_kind": "text", "outcome": "correct",
              "example_id": practice["id"], "example_revision": practice["revision"], "example_hash": practice["content_hash"],
              "answer_policy_id": practice["answer_policy"]["id"], "answer_policy_revision": practice["answer_policy"]["revision"],
              "workload": {"policy_version": "fixture-budget", "issued": {"total": 0}}, "active_minutes": None}
    export = {"manifest": {"export_version": "local-research-export-v2", "protocol_version": assignment["protocol_version"],
                           "synthetic": True, "enrollment_sha256": digest(enrollment), "records_sha256": digest([source]),
                           "records": 1}, "records": [source]}
    activity = {**_source_activity(source), "display_status": "shown", "shown_at": "2026-10-01T10:00:01+00:00", "support": "none"}
    probe = {"id": str(uuid4()), "offered_at": "2026-10-09T10:00:00+00:00", "display_status": "shown",
             "shown_at": "2026-10-09T10:00:01+00:00", "support": "none", "probe_horizon_days": 7,
             "context_family": heldout["context_family"], "example_id": heldout["id"],
             "example_revision": heldout["revision"], "example_hash": heldout["content_hash"],
             "answer_policy_id": heldout["answer_policy"]["id"], "answer_policy_revision": heldout["answer_policy"]["revision"],
             "response": {"at": "2026-10-09T10:00:20+00:00", "text": heldout["accepted_answers"][0]}}
    observer = {"schema_version": 1, "protocol_version": assignment["protocol_version"], "synthetic": True,
                "histories": [{"pseudonym": participant["pseudonym"], "target_key": key,
                               "history_complete": True, "support_capture_complete": True,
                               "activities": [activity], "presentations": [], "probes": [probe]}]}
    return export, enrollment, assignment, observer, bundle


def test_joint_dataset_has_planned_missing_counts_and_minimized_blind_packet():
    from app.research_dataset import build_dataset
    args = prepared_data()
    output = build_dataset(*args)
    assert output["analysis"]["planned"] == 4
    assert output["analysis"]["invited"] == 1 and output["analysis"]["not_invited"] == 3
    history = next(row for row in output["histories"] if row["activities"])
    assert history["metrics"]["delayed_7d"] == [1, 1, 1, 0, 0]
    assert len(output["blind"]) == 1
    row = output["blind"][0]
    assert set(row) == {"response_id", "task", "first_response", "rubric"}
    assert row["first_response"] == args[3]["histories"][0]["probes"][0]["response"]["text"]
    assert not {"pseudonym", "horizon", "target_key", "outcome", "accepted_answers"} & row.keys()


def test_dataset_preserves_answer_without_inventing_delayed_probe_display():
    from app.research_dataset import build_dataset
    args = prepared_data()
    probe = args[3]["histories"][0]["probes"][0]
    probe.pop("shown_at")
    probe["display_status"] = "unknown"
    output = build_dataset(*args)
    history = next(row for row in output["histories"] if row["activities"])
    assert history["metrics"]["delayed_7d"] == [0, 0, 1, 0, 0]
    assert history["metrics"]["probe_observations"][0]["eligibility"] == "unknown"
    assert output["blind"][0]["first_response"] == probe["response"]["text"]
    again = build_dataset(*args, retained_mapping=output["mapping"])
    assert again["blind"] == output["blind"] and again["analysis"] == output["analysis"]


@pytest.mark.parametrize("problem", ["digest", "consent", "owner", "pin", "late_freeze", "duplicate_probe", "changed_first"])
def test_joint_dataset_rejects_integrity_and_assignment_conflicts(problem):
    from app.research_dataset import build_dataset, digest
    args = list(prepared_data())
    export, enrollment, assignment, observer, _ = args
    if problem == "digest":
        export["records"][0]["first_response"] = "edited export"
    elif problem == "consent":
        enrollment["participants"][0]["scopes"] = []
    elif problem == "owner":
        export["records"][0]["pseudonym"] = "unconsented"
        export["manifest"]["records_sha256"] = digest(export["records"])
    elif problem == "pin":
        assignment["pins"]["bank_digest"] = "0"*64
    elif problem == "late_freeze":
        assignment["frozen_at"] = "2026-10-02T00:00:00+00:00"
    elif problem == "duplicate_probe":
        from uuid import uuid4
        duplicate = copy.deepcopy(observer["histories"][0]["probes"][0])
        duplicate["id"] = str(uuid4())
        observer["histories"][0]["probes"].append(duplicate)
    else:
        observer["histories"][0]["activities"][0]["response"]["text"] = "edited observer"
    with pytest.raises(ValueError):
        build_dataset(*args)


@pytest.mark.parametrize("mode,expected", [("missing", [0, 0, 1, 1, 0]), ("empty", [0, 1, 1, 0, 0]), ("unlisted", [0, 0, 1, 0, 1])])
def test_probe_missing_empty_and_unresolved_stay_distinct(mode, expected):
    from app.research_dataset import build_dataset
    args = prepared_data()
    probe = args[3]["histories"][0]["probes"][0]
    if mode == "missing":
        probe["response"] = None
    else:
        probe["response"]["text"] = "" if mode == "empty" else "unlisted synthetic variant"
    output = build_dataset(*args)
    history = next(row for row in output["histories"] if row["activities"])
    assert history["metrics"]["delayed_7d"] == expected
    assert len(output["blind"]) == (0 if mode == "missing" else 1)


def test_prior_heldout_display_excludes_independence_and_is_reported_as_incident():
    from app.research_dataset import build_dataset
    args = prepared_data()
    history = args[3]["histories"][0]
    family = history["probes"][0]["context_family"]
    history["presentations"].append({"id": "leak", "context_family": family, "offered_at": "2026-10-02T10:00:00+00:00",
                                     "shown_at": "2026-10-02T10:00:00+00:00", "display_status": "shown"})
    output = build_dataset(*args)
    analysis = next(row for row in output["histories"] if row["activities"])
    assert analysis["metrics"]["delayed_7d"][:2] == [0, 0]
    assert output["analysis"]["incidents"] == ["heldout_previous_display"]


def rating_input(blind):
    from uuid import uuid4
    from app.research_dataset import digest
    return {"schema_version": 1, "synthetic": True, "protocol_version": "written-feasibility-protocol-v1",
            "blind_sha256": digest(blind), "ratings": [
                {"response_id": blind[0]["response_id"], "rater_id": str(uuid4()), "task_success": 2, "target_accuracy": 2},
                {"response_id": blind[0]["response_id"], "rater_id": str(uuid4()), "task_success": 2, "target_accuracy": 1}],
            "adjudications": []}


def test_ratings_preserve_disagreement_missingness_and_never_claim_human_agreement():
    from app.research_dataset import build_dataset, analyze_ratings
    output = build_dataset(*prepared_data())
    ratings = rating_input(output["blind"])
    before = copy.deepcopy(output)
    actual = analyze_ratings(output["blind"], ratings)
    assert actual["human_agreement"] == "not_measured"
    assert actual["paired"] == 1 and actual["missing_ratings"] == 0
    assert actual["scales"]["task_success"] == {"agree": 1, "disagree": 0, "extreme_disagreement": 0}
    assert actual["scales"]["target_accuracy"] == {"agree": 0, "disagree": 1, "extreme_disagreement": 0}
    assert output == before
    ratings["ratings"].pop()
    missing = analyze_ratings(output["blind"], ratings)
    assert missing["paired"] == 0 and missing["missing_ratings"] == 1
    assert missing["unpaired_response_ids"] == [output["blind"][0]["response_id"]]


@pytest.mark.parametrize("problem", ["unknown_id", "duplicate_rater", "bool_score", "third_rater", "changed_packet", "human", "conflicting_duplicate", "adjudication_without_pair"])
def test_ratings_reject_unlinked_or_invalid_scores(problem):
    from uuid import uuid4
    from app.research_dataset import build_dataset, analyze_ratings
    output = build_dataset(*prepared_data())
    ratings = rating_input(output["blind"])
    if problem == "unknown_id":
        ratings["ratings"][0]["response_id"] = str(uuid4())
    elif problem == "duplicate_rater":
        ratings["ratings"][1]["rater_id"] = ratings["ratings"][0]["rater_id"]
    elif problem == "bool_score":
        ratings["ratings"][0]["task_success"] = True
    elif problem == "third_rater":
        ratings["ratings"].append({**ratings["ratings"][0], "rater_id": str(uuid4())})
    elif problem == "changed_packet":
        ratings["blind_sha256"] = "0"*64
    elif problem == "human":
        ratings["synthetic"] = False
    elif problem == "conflicting_duplicate":
        ratings["ratings"].append({**ratings["ratings"][0], "task_success": 0})
    else:
        ratings["ratings"].pop()
        ratings["adjudications"] = [{**ratings["ratings"][0], "rater_id": str(uuid4())}]
    with pytest.raises(ValueError):
        analyze_ratings(output["blind"], ratings)


def test_dataset_private_files_have_verified_digests_and_bounded_removal(tmp_path):
    from app.research_dataset import build_dataset, write_dataset, remove_dataset, verify_dataset
    output = build_dataset(*prepared_data())
    ratings = rating_input(output["blind"])
    directory = tmp_path / "restricted"
    write_dataset(output, directory, ratings=ratings)
    assert directory.stat().st_mode & 0o777 == 0o700
    assert all(path.stat().st_mode & 0o777 == 0o600 for path in directory.iterdir())
    manifest = verify_dataset(directory)
    assert {"ratings.json", "analysis.json", "blind-mapping.json", "blinded-responses.json"} <= set(manifest["files"])
    assert json.loads((directory / "analysis.json").read_text())["ratings"]["paired"] == 1
    (directory / "unrelated.txt").write_text("user file")
    with pytest.raises(ValueError, match="unknown files"):
        remove_dataset(directory)
    (directory / "unrelated.txt").unlink()
    (directory / "ratings.json").write_text("{}")
    with pytest.raises(ValueError, match="digest"):
        verify_dataset(directory)
    # Recognized files may be erased even when an interrupted edit invalidates their hash.
    remove_dataset(directory)
    remove_dataset(directory)
    assert not directory.exists()


def test_dataset_writer_and_remover_refuse_symlinks_and_existing_directories(tmp_path):
    from app.research_dataset import build_dataset, write_dataset, remove_dataset
    output = build_dataset(*prepared_data())
    destination = tmp_path / "private"
    write_dataset(output, destination)
    with pytest.raises(FileExistsError):
        write_dataset(output, destination)
    alias = tmp_path / "alias"
    alias.symlink_to(destination, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        remove_dataset(alias)
    with pytest.raises(ValueError, match="symlink"):
        write_dataset(output, alias / "child")
    outside = tmp_path / "outside.json"
    outside.write_text("unrelated")
    (destination / "ratings.json").unlink()
    (destination / "ratings.json").symlink_to(outside)
    with pytest.raises(ValueError, match="symlink"):
        remove_dataset(destination)
    assert outside.read_text() == "unrelated"


def test_retained_protocol_is_checked_and_workload_is_preserved(tmp_path):
    from app.research_dataset import build_dataset, PROTOCOL_DOCUMENT
    args = prepared_data()
    protocol = tmp_path / "protocol.md"
    protocol.write_bytes(PROTOCOL_DOCUMENT.read_bytes())
    output = build_dataset(*args, protocol_path=protocol)
    history = next(row for row in output["histories"] if row["activities"])
    assert history["workload"] == [{"activity_id": args[0]["records"][0]["activity_id"],
                                     "report": args[0]["records"][0]["workload"]}]
    assert output["analysis"]["unrecruited"] == 11
    protocol.write_text("altered protocol")
    with pytest.raises(ValueError, match="protocol|pins"):
        build_dataset(*args, protocol_path=protocol)


def test_actual_source_export_join_and_write_do_not_mutate_product(pilot_client, db_session, tmp_path):
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import select
    from app.domain_models.practice import LearningEventModel
    from app.domain_models.progress import LearnerTargetStateModel
    from app.research_dataset import freeze_assignment, build_dataset, _source_activity, write_dataset, verify_dataset
    from app.research_export import export_local_events, write_export
    enrollment, bundle = inputs()
    assignment = freeze_assignment(enrollment, bundle, seed="actual-db-fixture",
                                   frozen_at=(datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat())
    run, _ = pilot_tests.start(pilot_client)
    first = pilot_tests.next_activity(pilot_client, run)["activity"]
    pilot_client.post(f"/api/practice/pilot-test/activities/{first['id']}/responses",
                      json={"idempotency_key": "dataset-first", "response": "unknown"}).raise_for_status()
    state = db_session.scalar(select(LearnerTargetStateModel))
    before = (state.evidence_count, state.last_event_id, state.memory_due_at)
    exported = export_local_events(db_session, enrollment)
    write_export(exported, tmp_path / "raw")
    # Read the actual serialized source, not a hand-constructed export surrogate.
    exported = {"manifest": json.loads((tmp_path / "raw/export-manifest.json").read_text()),
                "records": json.loads((tmp_path / "raw/events.json").read_text())}
    row = exported["records"][0]
    observer = {"schema_version": 1, "protocol_version": assignment["protocol_version"], "synthetic": True,
                "histories": [{"pseudonym": row["pseudonym"], "target_key": row["target_key"],
                               "activities": [_source_activity(row)], "presentations": [], "probes": []}]}
    output = build_dataset(exported, enrollment, assignment, observer, bundle)
    write_dataset(output, tmp_path / "joint")
    verify_dataset(tmp_path / "joint")
    assert (state.evidence_count, state.last_event_id, state.memory_due_at) == before
    assert len(list(db_session.scalars(select(LearningEventModel)))) == 1
    history = next(row for row in output["histories"] if row["activities"])
    assert history["metrics"]["unresolved"] == [1, 1]
    assert history["workload"][0]["report"] == exported["records"][0]["workload"]
    assert "pilot-test" not in json.dumps(output)


@pytest.mark.parametrize("problem", ["presentation_identity", "workload_identity", "preconsent_display", "unknown_probe_support", "cross_target_retry"])
def test_joint_dataset_rejects_unminimized_or_inconsistent_observations(problem):
    from app.research_dataset import build_dataset, digest
    args = prepared_data()
    history = args[3]["histories"][0]
    if problem in {"presentation_identity", "preconsent_display"}:
        display = {"id": "contact", "context_family": history["activities"][0]["context_family"],
                   "offered_at": "2026-10-01T12:00:00+00:00", "shown_at": "2026-10-01T12:00:01+00:00",
                   "display_status": "shown"}
        if problem == "presentation_identity":
            display["learner_id"] = "private-identity"
        else:
            display["offered_at"] = display["shown_at"] = "2026-08-01T12:00:00+00:00"
        history["presentations"].append(display)
    elif problem == "workload_identity":
        args[0]["records"][0]["workload"]["learner_id"] = "private-identity"
        args[0]["manifest"]["records_sha256"] = digest(args[0]["records"])
    elif problem == "unknown_probe_support":
        history["probes"][0]["support"] = "invented-support"
    else:
        from uuid import uuid4
        parent = str(uuid4())
        args[0]["records"][0]["retry_of"] = parent
        history["activities"][0]["retry_of"] = parent
        args[0]["manifest"]["records_sha256"] = digest(args[0]["records"])
    with pytest.raises(ValueError):
        build_dataset(*args)


def test_file_cli_freezes_builds_verifies_and_removes_synthetic_bundle(tmp_path, capsys):
    from app.research_dataset import main
    from app.research_export import write_export
    args = prepared_data()
    names = ("export", "enrollment", "assignment", "observer")
    for name, value in zip(names, args[:4]):
        (tmp_path / f"{name}.json").write_text(json.dumps(value))
    frozen = tmp_path / "frozen"
    main(["freeze", "--enrollment", str(tmp_path / "enrollment.json"), "--pack", str(pilot_tests.PACK),
          "--seed", args[2]["seed"], "--frozen-at", args[2]["frozen_at"], "--output", str(frozen)])
    assert json.loads((frozen / "assignment.json").read_text()) == args[2]
    output = tmp_path / "built"
    write_export(args[0], tmp_path / "source-export")
    main(["build", "--export", str(tmp_path / "source-export"), "--enrollment", str(tmp_path / "enrollment.json"),
          "--assignment", str(frozen / "assignment.json"), "--protocol", str(frozen / "protocol.md"),
          "--observer", str(tmp_path / "observer.json"), "--pack", str(pilot_tests.PACK), "--output", str(output)])
    main(["verify", str(output)])
    assert '"synthetic": true' in capsys.readouterr().out
    main(["remove", str(output)])
    main(["remove-assignment", str(frozen)])
    assert not output.exists() and not frozen.exists()


def test_withdrawal_rejects_old_export_and_removes_linked_blind_rows_on_rebuild():
    from app.research_dataset import build_dataset, digest
    args = prepared_data()
    first = build_dataset(*args)
    args[1]["participants"][0]["withdrawn"] = True
    with pytest.raises(ValueError, match="digest"):
        build_dataset(*args, retained_mapping=first["mapping"])
    args[0]["records"] = []
    args[0]["manifest"].update(enrollment_sha256=digest(args[1]), records_sha256=digest([]), records=0)
    args[3]["histories"] = []
    output = build_dataset(*args, retained_mapping=first["mapping"])
    assert output["histories"] == output["blind"] == output["mapping"]["entries"] == []
    assert output["analysis"]["withdrawn"] == 1
    assert output["assignment"] == first["assignment"]


@pytest.mark.parametrize("problem", ["identity", "order", "response_id", "changed_text"])
def test_retained_blind_mapping_rejects_extra_fields_and_changed_correspondence(problem):
    from app.research_dataset import build_dataset
    args = prepared_data()
    first = build_dataset(*args)
    mapping = first["mapping"]
    if problem == "identity":
        mapping["entries"][0]["learner_id"] = "direct-identity"
    elif problem == "order":
        mapping["entries"][0]["order"] = True
    elif problem == "response_id":
        mapping["entries"][0]["response_id"] = "not-random"
    else:
        args[3]["histories"][0]["probes"][0]["response"]["text"] = "edited first response"
    with pytest.raises(ValueError):
        build_dataset(*args, retained_mapping=mapping)


@pytest.mark.parametrize("problem", ["early_display", "hidden_reveal"])
def test_linked_probe_display_cannot_hide_prior_exposure_or_help(problem):
    from app.research_dataset import build_dataset
    args = prepared_data()
    history = args[3]["histories"][0]
    probe = history["probes"][0]
    display = {"id": "linked", "activity_id": probe["id"], "context_family": probe["context_family"],
               "offered_at": probe["offered_at"], "shown_at": probe["shown_at"], "display_status": "shown"}
    if problem == "early_display":
        display["offered_at"] = display["shown_at"] = "2026-10-02T10:00:00+00:00"
    else:
        display.update(support="reveal", support_at="2026-10-09T10:00:10+00:00")
    history["presentations"].append(display)
    with pytest.raises(ValueError, match="linked|display|support"):
        build_dataset(*args)


def test_known_holdout_display_before_first_response_is_an_incident_even_if_start_unknown():
    from app.research_dataset import build_dataset
    args = prepared_data()
    history = args[3]["histories"][0]
    probe = history["probes"][0]
    probe.pop("shown_at")
    probe["display_status"] = "unknown"
    history["presentations"].append({"id": "known-leak", "context_family": probe["context_family"],
                                     "offered_at": probe["offered_at"], "shown_at": "2026-10-09T10:00:10+00:00",
                                     "display_status": "shown"})
    output = build_dataset(*args)
    assert output["analysis"]["incidents"] == ["heldout_previous_display"]
