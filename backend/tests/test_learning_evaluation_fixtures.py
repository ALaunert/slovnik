"""Freeze hand-reconciled learning observations before changing reporting."""

import json
from datetime import datetime, timedelta
from pathlib import Path


FIXTURE = Path(__file__).parent / "fixtures" / "learning" / "baseline-v1.json"
METRICS = (
    "first_eligible",
    "first_correct",
    "recovered",
    "assisted_correct",
    "self_reports",
    "unresolved",
    "distinct_contexts",
    "delayed_new_context_eligible",
    "delayed_new_context_correct",
)


def _counts(events):
    counts = dict.fromkeys(METRICS, 0)
    first_seen_at = {}
    seen_contexts = set()
    first_by_activity = {}
    for event in events:
        if event["kind"] == "exposure":
            continue
        source = event["source"]
        outcome = event["outcome"]
        if source == "self_report":
            counts["self_reports"] += 1
            continue
        if outcome == "unknown":
            counts["unresolved"] += 1
            continue
        if source != "deterministic":
            continue
        if event["support"] != "none":
            assert event.get("support_timing") == "before_first"
            if outcome == "correct":
                counts["assisted_correct"] += 1
            continue
        if event["ordinal"] > 1:
            if outcome == "correct" and event.get("repair_of"):
                parent = first_by_activity.get(event["repair_of"])
                assert parent is not None and parent["target"] == event["target"]
                assert parent["outcome"] == "incorrect"
                counts["recovered"] += 1
            continue
        counts["first_eligible"] += 1
        first_by_activity[event["activity_id"]] = event
        counts["first_correct"] += int(outcome == "correct")
        target = event["target"]
        context = event.get("context_family")
        when = datetime.fromisoformat(event["at"])
        first_seen_at.setdefault(target, when)
        if context and (target, context) not in seen_contexts:
            has_prior_context = any(key[0] == target for key in seen_contexts)
            seen_contexts.add((target, context))
            counts["distinct_contexts"] += 1
            if has_prior_context and event.get("held_out") is True and when - first_seen_at[target] >= timedelta(days=7):
                counts["delayed_new_context_eligible"] += 1
                counts["delayed_new_context_correct"] += int(outcome == "correct")
    return counts


def test_frozen_histories_reconcile_with_hand_checked_totals():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert fixture["schema_version"] == 1
    assert {case["id"] for case in fixture["cases"]} == {
        "wrong_then_repair",
        "hint_then_correct",
        "self_rating",
        "repeated_context",
        "delayed_new_context",
        "ambiguous_answer",
    }
    aggregate = dict.fromkeys(METRICS, 0)
    for case in fixture["cases"]:
        actual = _counts(case["events"])
        assert actual == case["expected"], case["id"]
        for metric in METRICS:
            aggregate[metric] += actual[metric]
    assert aggregate == {
        "first_eligible": 5,
        "first_correct": 4,
        "recovered": 1,
        "assisted_correct": 1,
        "self_reports": 1,
        "unresolved": 1,
        "distinct_contexts": 4,
        "delayed_new_context_eligible": 1,
        "delayed_new_context_correct": 1,
    }
