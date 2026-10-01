"""Structural checks for the unpublished written pilot brief."""

import json
from pathlib import Path


MANIFEST = Path(__file__).parents[2] / "content/curricula/a1-pilot/manifest.json"


def test_four_draft_outcomes_have_separate_practice_and_holdout_families() -> None:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    assert data["status"] == "draft"
    outcomes = data["outcomes"]
    ids = [item["id"] for item in outcomes]
    assert ids == [
        "A1.PERSONAL_DETAILS", "A1.SIMPLE_REQUEST", "A1.PRICE_INFO", "A1.LOCATION_INFO"
    ]
    assert len(set(ids)) == len(ids)
    families = []
    for item in outcomes:
        assert item["cefr"]["edition"] == "Companion Volume 2020"
        assert item["cefr"]["scale"] and item["cefr"]["page"]
        assert item["written_task"] and item["input"] and item["rubric"]
        assert item["primary_target"]["id"] and item["primary_target"]["capability"]
        assert item["script_conditions"] and item["hypothesis"]
        assert item["practice_families"] and item["assessment_family"]
        families.extend(item["practice_families"] + [item["assessment_family"]])
    assert len(set(families)) == len(families)
    assert all(edge["kind"] == "soft" for edge in data["proposed_edges"])
    assert all(edge["from"] in ids and edge["to"] in ids for edge in data["proposed_edges"])
    assert data["proposed_hard_edges"] == []
