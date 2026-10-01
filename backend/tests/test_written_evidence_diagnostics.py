import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from app.domain.evidence_diagnostics import EvidenceFact, classify_history
from app.services.evidence_diagnostic_service import diagnose_events


FIXTURE = Path(__file__).parent / "fixtures/learning/p0_01_histories.json"


def test_p0_01_fixture_categories_reconcile_without_promoting_retry() -> None:
    histories = json.loads(FIXTURE.read_text(encoding="utf-8"))["histories"]
    totals = {name: [0, 0] for name in (
        "independent_first", "assisted", "repair", "self_report", "repeated_context", "unresolved"
    )}
    for history in histories:
        facts = []
        for activity in history["activities"]:
            response = activity["response"]
            if response is None:
                continue
            facts.append(EvidenceFact(
                event_id=f"{history['id']}:{activity['id']}",
                occurred_at=datetime.fromisoformat(response["at"]),
                event_type="response_evaluated",
                evaluation_source="self_report" if response["kind"] == "self_report" else "deterministic",
                evaluation_outcome="unknown" if response["kind"] == "self_report" else response["outcome"],
                response_present=True,
                retry_of=f"{history['id']}:{activity['retry_of']}" if activity.get("retry_of") else None,
                support=activity["support"], support_capture_complete=True,
                context_family=activity["context_family"], context_history_complete=True,
                rating=response.get("rating"),
            ))
        categories = classify_history(facts)
        for result in categories:
            if result.category in totals:
                totals[result.category][1] += result.outcome in {"correct", "incorrect"} or result.category == "self_report"
                totals[result.category][0] += result.outcome == "correct" or (
                    result.category == "self_report" and result.rating in {"good", "easy"}
                )
            if result.category not in {"self_report", "exposure"}:
                totals["unresolved"][1] += 1
            if result.outcome == "unresolved":
                totals["unresolved"][0] += 1
    assert totals["independent_first"] == [3, 4]
    assert totals["assisted"] == [1, 1]
    assert totals["repair"] == [1, 1]
    assert totals["self_report"] == [1, 1]
    assert totals["repeated_context"] == [1, 1]
    assert totals["unresolved"] == [1, 8]


def test_missing_lineage_and_support_never_become_independent_success() -> None:
    at = datetime.fromisoformat("2026-01-01T00:00:00+00:00")
    fact = EvidenceFact("a", at, "response_evaluated", "deterministic", "correct", True)
    result = classify_history([fact])[0]
    assert result.category == "unknown"
    assert result.context_status == "unknown"


def test_late_event_and_duplicate_id_are_sorted_and_deduplicated() -> None:
    at = datetime.fromisoformat("2026-01-01T00:00:00+00:00")
    first = EvidenceFact("a", at, "response_evaluated", "deterministic", "incorrect", True,
                         support="none", support_capture_complete=True,
                         context_family="f", context_history_complete=True)
    retry = EvidenceFact("b", at.replace(day=2), "response_evaluated", "deterministic", "correct", True,
                         retry_of="a", support="none", support_capture_complete=True,
                         context_family="f", context_history_complete=True)
    results = classify_history([retry, first, retry])
    assert [result.category for result in results] == ["independent_first", "repair"]


def test_stored_shadow_snapshot_keeps_missing_support_and_context_unknown() -> None:
    at = datetime.fromisoformat("2026-01-01T00:00:00+00:00")
    event = SimpleNamespace(event_id="e1", activity_instance_id="a1", occurred_at=at,
                            event_type="response_evaluated", evaluation_source="deterministic",
                            evaluation_outcome="correct", first_response=object(), hints=())
    activity = SimpleNamespace(id="a1", retry_of_activity_instance_id=None,
                               spec=SimpleNamespace(snapshot={"legacy_question_type": "ru_to_sr_typing"}))
    assert diagnose_events([(event, activity)])[0].category == "unknown"
    assert diagnose_events([(event, activity)])[0].context_status == "unknown"


def test_stored_hint_without_timing_is_supported_but_not_assisted_first() -> None:
    at = datetime.fromisoformat("2026-01-01T00:00:00+00:00")
    event = SimpleNamespace(event_id="e1", activity_instance_id="a1", occurred_at=at,
                            event_type="response_evaluated", evaluation_source="deterministic",
                            evaluation_outcome="correct", first_response=object(),
                            hints=(SimpleNamespace(kind="reveal"),))
    activity = SimpleNamespace(id="a1", retry_of_activity_instance_id=None,
                               spec=SimpleNamespace(snapshot={}))
    assert diagnose_events([(event, activity)])[0].category == "supported_timing_unknown"


def test_stored_retry_remains_retry_when_parent_event_not_loaded() -> None:
    at = datetime.fromisoformat("2026-01-01T00:00:00+00:00")
    event = SimpleNamespace(event_id="e2", activity_instance_id="a2", occurred_at=at,
                            event_type="response_evaluated", evaluation_source="deterministic",
                            evaluation_outcome="correct", first_response=object(), hints=())
    activity = SimpleNamespace(id="a2", retry_of_activity_instance_id="a1",
                               spec=SimpleNamespace(snapshot={}))
    assert diagnose_events([(event, activity)])[0].category == "retry"


def test_exposure_and_model_only_verdict_are_not_objective_successes() -> None:
    at = datetime.fromisoformat("2026-01-01T00:00:00+00:00")
    exposure = EvidenceFact("shown", at, "exposure", None, None, False)
    model = EvidenceFact("model", at.replace(day=2), "response_evaluated",
                         "model_assisted", "correct", True,
                         support="none", support_capture_complete=True,
                         context_family="new", context_history_complete=True)
    assert [result.category for result in classify_history([exposure, model])] == [
        "exposure", "unknown"
    ]


def test_model_retry_and_other_learner_context_do_not_create_false_evidence() -> None:
    at = datetime.fromisoformat("2026-01-01T00:00:00+00:00")
    first = EvidenceFact("a", at, "response_evaluated", "deterministic", "incorrect", True,
                         support="none", support_capture_complete=True,
                         context_family="f", context_history_complete=True, lineage_key="learner-a")
    other = EvidenceFact("b", at.replace(day=2), "response_evaluated", "deterministic", "correct", True,
                         support="none", support_capture_complete=True,
                         context_family="f", context_history_complete=True, lineage_key="learner-b")
    model_retry = EvidenceFact("c", at.replace(day=3), "response_evaluated", "model_assisted", "correct", True,
                               retry_of="a", context_family="f", context_history_complete=True,
                               lineage_key="learner-a")
    results = classify_history([model_retry, other, first])
    assert [result.category for result in results] == ["independent_first", "independent_first", "unknown"]
