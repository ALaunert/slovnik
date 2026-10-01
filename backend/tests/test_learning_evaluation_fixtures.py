"""Hand-checked P0-01 examples; no production metric implementation exists yet."""

import json
from datetime import datetime, timedelta
from pathlib import Path


FIXTURE = Path(__file__).parent / "fixtures/learning/p0_01_histories.json"
WIDTHS = {
    "presentations": 2,  # shown / offered
    "first_unaided": 2,  # correct / resolved independent first responses
    "assisted": 2,  # correct / resolved hinted first responses
    "retry": 2,  # correct / resolved retry responses
    "self_report": 2,  # good-or-easy / submitted ratings
    "same_context": 2,  # correct / resolved repeated-context first responses
    "delayed_7d": 5,  # correct / resolved / invited / missing / unresolved
    "unresolved": 2,  # unresolved / submitted scored response candidates
}


def _time(value: str) -> datetime:
    result = datetime.fromisoformat(value)
    assert result.tzinfo is not None and result.utcoffset() is not None
    return result


def _summarize(history: dict) -> dict[str, list[int]]:
    counts = {name: [0] * width for name, width in WIDTHS.items()}
    contacts: list[datetime] = []
    shown_contexts: list[tuple[datetime, str]] = []
    for presentation in history["presentations"]:
        offered = _time(presentation["offered_at"])
        assert presentation["context_family"]
        assert presentation["display_status"] in {"shown", "not_shown"}
        assert (presentation["shown_at"] is not None) == (
            presentation["display_status"] == "shown"
        )
        counts["presentations"][1] += 1
        if presentation["shown_at"] is not None:
            shown = _time(presentation["shown_at"])
            assert shown >= offered
            counts["presentations"][0] += 1
            contacts.append(shown)
            shown_contexts.append((shown, presentation["context_family"]))

    activities = history["activities"]
    assert len({activity["id"] for activity in activities}) == len(activities)
    assert [_time(a["offered_at"]) for a in activities] == sorted(
        _time(a["offered_at"]) for a in activities
    )
    earlier: dict[str, dict] = {}
    seen_contexts: set[str] = set()
    for activity in activities:
        offered = _time(activity["offered_at"])
        context = activity["context_family"]
        assert context and activity["support"] in {"none", "hint", "reveal"}
        prior_same_context = context in seen_contexts or any(
            family == context and shown < offered
            for shown, family in shown_contexts
        )
        retry_of = activity.get("retry_of")
        if retry_of is not None:
            parent = earlier[retry_of]
            assert parent["context_family"] == context
            assert parent["response"]["outcome"] == "incorrect"
            assert offered > _time(parent["response"]["at"])

        horizon = activity.get("probe_horizon_days")
        if horizon is not None:
            prior_contacts = [at for at in contacts if at < offered]
            assert horizon == 7 and prior_contacts
            assert offered - max(prior_contacts) >= timedelta(days=horizon)
            assert not prior_same_context and retry_of is None
            assert activity["support"] == "none"
            counts["delayed_7d"][2] += 1

        response = activity["response"]
        if response is None:
            assert horizon is not None
            counts["delayed_7d"][3] += 1
            earlier[activity["id"]] = activity
            continue

        responded = _time(response["at"])
        assert responded >= offered
        if activity["support"] == "none":
            assert "support_at" not in activity
        else:
            assert offered <= _time(activity["support_at"]) < responded
        if response["kind"] == "self_report":
            assert horizon is None and retry_of is None
            assert response["rating"] in {"again", "hard", "good", "easy"}
            counts["self_report"][1] += 1
            counts["self_report"][0] += response["rating"] in {"good", "easy"}
        else:
            assert response["kind"] == "scored"
            outcome = response["outcome"]
            assert outcome in {"correct", "incorrect", "unresolved"}
            counts["unresolved"][1] += 1
            if outcome == "unresolved":
                assert response["reason"]
                counts["unresolved"][0] += 1
                if horizon is not None:
                    counts["delayed_7d"][4] += 1
            else:
                if retry_of is not None:
                    bucket = "retry"
                elif activity["support"] != "none":
                    bucket = "assisted"
                elif prior_same_context:
                    bucket = "same_context"
                else:
                    bucket = "first_unaided"
                counts[bucket][1] += 1
                counts[bucket][0] += outcome == "correct"
                if horizon is not None:
                    counts["delayed_7d"][1] += 1
                    counts["delayed_7d"][0] += outcome == "correct"
        contacts.append(responded)
        seen_contexts.add(context)
        earlier[activity["id"]] = activity
    return counts


def test_p0_01_histories_match_hand_reconciled_truth_table() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert fixture["schema_version"] == 1
    histories = fixture["histories"]
    assert {history["id"] for history in histories} == {
        "wrong_then_correct_retry",
        "hint_then_correct",
        "self_rating_after_reveal",
        "same_context_again",
        "delayed_new_context_with_missing_probe",
        "ambiguous_answer",
    }
    assert len({history["learner_id"] for history in histories}) == len(histories)

    totals = {name: [0] * width for name, width in WIDTHS.items()}
    for history in histories:
        actual = _summarize(history)
        expected = {
            name: history["expected"].get(name, [0] * width)
            for name, width in WIDTHS.items()
        }
        assert actual == expected, history["id"]
        for name in WIDTHS:
            totals[name] = [a + b for a, b in zip(totals[name], actual[name])]

    assert totals == {
        "presentations": [2, 3],
        "first_unaided": [3, 4],
        "assisted": [1, 1],
        "retry": [1, 1],
        "self_report": [1, 1],
        "same_context": [1, 1],
        "delayed_7d": [1, 1, 2, 1, 0],
        "unresolved": [1, 8],
    }
    # The repaired answer is a retry success; its original first response stays wrong.
    assert _summarize(histories[0])["first_unaided"] == [0, 1]
