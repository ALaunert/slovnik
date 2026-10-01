import copy
import json
from pathlib import Path

import pytest


def test_declared_fixture_analysis_reconciles_all_p0_truth_rows():
    from app.research_ledger import summarize_history
    fixture = json.loads((Path(__file__).parent / "fixtures/learning/p0_01_histories.json").read_text())
    for original in fixture["histories"]:
        history = {**original, "history_complete": True, "support_capture_complete": True, "key_frozen": True}
        actual = summarize_history(history)
        for metric, expected in original["expected"].items():
            assert actual[metric] == expected


def test_unknown_contact_or_support_cannot_enter_delayed_success():
    from app.research_ledger import summarize_history
    history = {"history_complete": False, "support_capture_complete": True, "key_frozen": True,
               "presentations": [], "activities": [
                   {"id": "a", "context_family": "practice", "offered_at": "2026-01-01T10:00:00+00:00", "support": "none",
                    "response": {"kind": "scored", "at": "2026-01-01T10:01:00+00:00", "outcome": "correct"}},
                   {"id": "b", "context_family": "heldout", "offered_at": "2026-01-09T10:00:00+00:00", "support": "none",
                    "probe_horizon_days": 7, "response": {"kind": "scored", "at": "2026-01-09T10:01:00+00:00", "outcome": "correct"}},
               ]}
    actual = summarize_history(history)
    assert actual["delayed_7d"][:2] == [0, 0]
    assert actual["probe_unknown"] == 1
    history["history_complete"] = True
    history["support_capture_complete"] = False
    assert summarize_history(history)["delayed_7d"][:2] == [0, 0]


@pytest.mark.parametrize("horizon, date", [(7, "2026-01-09"), (28, "2026-01-30")])
@pytest.mark.parametrize("display_status", [None, "unknown"])
def test_answer_timestamp_cannot_replace_unknown_delayed_probe_start(horizon, date, display_status):
    from app.research_ledger import summarize_history
    history = _probe_history()
    probe = history["activities"][0]
    probe.update(offered_at=f"{date}T00:00:00+00:00", probe_horizon_days=horizon)
    if display_status is not None:
        probe["display_status"] = display_status
    probe["response"]["at"] = f"{date}T00:01:00+00:00"
    original_response = copy.deepcopy(probe["response"])
    actual = summarize_history(history)
    assert actual[f"delayed_{horizon}d"] == [0, 0, 1, 0, 0]
    assert actual["probe_unknown"] == 1
    observation = actual["probe_observations"][0]
    assert observation["eligibility"] == "unknown"
    assert "probe_contact_unknown" in observation["reasons"]
    assert observation["responded"] is True and observation["resolved"] is True
    assert probe["response"] == original_response


def test_duplicate_delivery_keeps_one_invitation_and_conflicting_first_response_rejects():
    from app.research_ledger import summarize_history
    fixture = json.loads((Path(__file__).parent / "fixtures/learning/p0_01_histories.json").read_text())
    original = fixture["histories"][4]
    history = copy.deepcopy({**original, "history_complete": True, "support_capture_complete": True, "key_frozen": True})
    history["activities"].append(copy.deepcopy(history["activities"][1]))
    assert summarize_history(history)["delayed_7d"] == original["expected"]["delayed_7d"]
    history["activities"][-1]["response"]["outcome"] = "incorrect"
    with pytest.raises(ValueError, match="conflicting"):
        summarize_history(history)


def test_hint_shown_without_response_resets_latest_verified_contact():
    from app.research_ledger import summarize_history
    history = {"history_complete": True, "support_capture_complete": True, "key_frozen": True,
               "presentations": [{"id": "contact", "context_family": "initial", "offered_at": "2026-01-01T00:00:00+00:00",
                                  "shown_at": "2026-01-01T00:00:00+00:00", "display_status": "shown"}],
               "activities": [
                   {"id": "help", "context_family": "practice", "offered_at": "2026-01-07T00:00:00+00:00", "support": "hint",
                    "support_at": "2026-01-07T00:01:00+00:00", "response": None, "display_status": "not_shown"},
                   {"id": "probe", "context_family": "heldout", "offered_at": "2026-01-09T00:00:00+00:00", "support": "none",
                    "probe_horizon_days": 7, "response": {"kind": "scored", "at": "2026-01-09T00:01:00+00:00", "outcome": "correct"}},
               ]}
    assert summarize_history(history)["delayed_7d"][:2] == [0, 0]


@pytest.mark.parametrize("shown_at", ["2026-01-09T00:00:00+00:00", "2026-01-20T00:00:00+00:00"])
def test_invitation_in_window_does_not_admit_late_display_or_response(shown_at):
    from app.research_ledger import summarize_history
    history = _probe_history()
    history["activities"][0].update(display_status="shown", shown_at=shown_at)
    history["activities"][0]["response"]["at"] = "2026-01-20T00:01:00+00:00"
    actual = summarize_history(history)
    assert actual["delayed_7d"] == [0, 0, 1, 0, 0]
    assert actual["probe_excluded"] == 1


def _probe_history():
    return {"history_complete": True, "support_capture_complete": True, "key_frozen": True,
            "presentations": [{"id": "initial", "context_family": "practice", "offered_at": "2026-01-01T00:00:00+00:00",
                               "shown_at": "2026-01-01T00:00:00+00:00", "display_status": "shown"}],
            "activities": [{"id": "probe", "context_family": "heldout", "offered_at": "2026-01-09T00:00:00+00:00",
                            "support": "none", "probe_horizon_days": 7,
                            "response": {"kind": "scored", "at": "2026-01-09T00:01:00+00:00", "outcome": "correct"}}]}


@pytest.mark.parametrize("contact_kind", ["presentation", "activity"])
def test_contact_between_invitation_and_actual_probe_is_included(contact_kind):
    from app.research_ledger import summarize_history
    history = _probe_history()
    history["activities"][0].update(display_status="shown", shown_at="2026-01-09T01:00:00+00:00")
    history["activities"][0]["response"]["at"] = "2026-01-09T01:01:00+00:00"
    contact = {"id": "intervening", "context_family": "practice-two", "offered_at": "2026-01-09T00:20:00+00:00",
               "display_status": "shown", "shown_at": "2026-01-09T00:30:00+00:00"}
    if contact_kind == "presentation":
        history["presentations"].append(contact)
    else:
        history["activities"].append({**contact, "response": None, "support": "none"})
    assert summarize_history(history)["delayed_7d"][:2] == [0, 0]


def test_current_probe_display_does_not_reset_its_own_delay():
    from app.research_ledger import summarize_history
    history = _probe_history()
    history["activities"][0].update(display_status="shown", shown_at="2026-01-09T00:00:10+00:00")
    assert summarize_history(history)["delayed_7d"] == [1, 1, 1, 0, 0]


def test_probe_report_retains_exclusion_reasons_and_response_missingness():
    from app.research_ledger import summarize_history
    history = _probe_history()
    task = history["activities"][0]
    task.update(display_status="shown", shown_at="2026-01-09T00:00:10+00:00")
    task["response"]["at"] = "2026-01-20T00:01:00+00:00"
    report = summarize_history(history)["probe_observations"][0]
    assert report["eligibility"] == "excluded" and report["reasons"] == ["outside_window"]
    assert report["responded"] is True and report["resolved"] is True and report["missing"] is False
    task["response"] = None
    task.pop("shown_at")
    task["display_status"] = "unknown"
    report = summarize_history(history)["probe_observations"][0]
    assert report["missing"] is True and report["eligibility"] == "unknown"
    assert "probe_contact_unknown" in report["reasons"]


def test_linked_contact_only_exempts_the_actual_initial_display():
    from app.research_ledger import summarize_history
    history = _probe_history()
    probe = history["activities"][0]
    probe.update(display_status="shown", shown_at="2026-01-09T00:00:10+00:00")
    linked = {"id": "linked", "activity_id": "probe", "context_family": "heldout",
              "offered_at": probe["offered_at"], "display_status": "shown", "shown_at": probe["shown_at"]}
    history["presentations"].append(linked)
    assert summarize_history(history)["delayed_7d"][:2] == [1, 1]
    linked.update(support="reveal", support_at="2026-01-09T00:00:20+00:00")
    assert summarize_history(history)["delayed_7d"][:2] == [0, 0]
    linked.pop("support")
    linked.pop("support_at")
    linked["offered_at"] = linked["shown_at"] = "2026-01-02T00:00:00+00:00"
    assert summarize_history(history)["delayed_7d"][:2] == [0, 0]


@pytest.mark.parametrize("contact_kind", ["presentation", "activity"])
def test_known_family_contact_before_actual_response_is_not_independent_first(contact_kind):
    from app.research_ledger import summarize_history
    history = _probe_history()
    history["presentations"] = []
    task = history["activities"][0]
    task.pop("probe_horizon_days")
    task.update(offered_at="2026-01-01T00:00:00+00:00", display_status="shown",
                shown_at="2026-01-03T00:00:00+00:00")
    task["response"]["at"] = "2026-01-03T00:01:00+00:00"
    contact = {"id": "contact", "context_family": "heldout", "offered_at": "2026-01-02T00:00:00+00:00",
               "display_status": "shown", "shown_at": "2026-01-02T00:00:00+00:00"}
    if contact_kind == "presentation":
        history["presentations"].append(contact)
    else:
        history["activities"].append({**contact, "response": None, "support": "none"})
    actual = summarize_history(history)
    assert actual["first_unaided"] == [0, 0]
    assert actual["same_context"] == [1, 1]
