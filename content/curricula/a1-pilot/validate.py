"""Validate the provisional written pilot contract; does not publish content."""

import json
import sys
from pathlib import Path


REQUIRED_OUTCOMES = {
    "A1.PERSONAL_DETAILS", "A1.SIMPLE_REQUEST", "A1.PRICE_INFO", "A1.LOCATION_INFO"
}
CAPABILITIES = {
    "sense": {"recognize_meaning", "retrieve_form"},
    "form": {"retrieve_form"},
    "construction": {"apply_construction"},
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique_ids(items, label):
    ids = [item["id"] for item in items]
    require(all(isinstance(item, str) and item for item in ids), f"empty {label} id")
    require(len(ids) == len(set(ids)), f"duplicate {label} id")
    return set(ids)


def validate(manifest):
    require(manifest["schema_version"] == 1, "unsupported schema version")
    require(manifest["status"] == "provisional_editorial_draft", "draft status required")
    source = manifest["cefr_source"]
    require(source["edition"] == "Council of Europe 2020", "CEFR edition required")
    require(source["locator_basis"] == "printed page", "printed CEFR locator required")
    targets = manifest["targets"]
    target_ids = unique_ids(targets, "target")
    for target in targets:
        require(target["capability"] in CAPABILITIES.get(target["kind"], set()),
                f"invalid capability for {target['id']}")
        require(bool(target["function"].strip()), f"target function missing: {target['id']}")

    outcomes = manifest["outcomes"]
    outcome_ids = unique_ids(outcomes, "outcome")
    require(outcome_ids == REQUIRED_OUTCOMES, "pilot must contain exactly four specified outcomes")
    inputs, practice, assessment = set(), set(), set()
    for outcome in outcomes:
        ids = outcome["target_ids"]
        require(ids and len(ids) == len(set(ids)), f"empty/duplicate target set: {outcome['id']}")
        require(set(ids) <= target_ids, f"unknown target: {outcome['id']}")
        require(outcome["primary_target_id"] in ids, f"primary target missing: {outcome['id']}")
        require(outcome["stage"] in {0, 1, 2}, f"pilot stage outside 0–2: {outcome['id']}")
        cefr = outcome["cefr"]
        require(cefr["level"] == "A1" and cefr["scale"] and
                type(cefr["printed_page"]) is int and cefr["printed_page"] > 0,
                f"CEFR locator missing: {outcome['id']}")
        for field in ("function", "written_task", "scope_note"):
            require(bool(outcome[field].strip()), f"{field} missing: {outcome['id']}")
        for field in ("communicative_success", "target_accuracy", "support"):
            require(bool(outcome["rubric"][field].strip()),
                    f"rubric {field} missing: {outcome['id']}")
        require(set(outcome["script_conditions"]) ==
                {"serbian_latin", "serbian_cyrillic"},
                f"both script conditions required: {outcome['id']}")
        families = outcome["families"]
        for role in ("input", "practice", "assessment"):
            values = families[role]
            require(values and len(values) == len(set(values)) and
                    all(isinstance(value, str) and value for value in values),
                    f"empty/duplicate {role} family: {outcome['id']}")
        inputs.update(families["input"])
        practice.update(families["practice"])
        assessment.update(families["assessment"])
    require(not (practice & assessment), "practice/assessment family overlap")
    require(not ((inputs & practice) or (inputs & assessment)),
            "input family overlaps practice/assessment")

    edges = manifest["edges"]
    unique_ids(edges, "edge")
    graph = {outcome_id: [] for outcome_id in outcome_ids}
    pairs = set()
    for edge in edges:
        start, end = edge["from"], edge["to"]
        require(start in outcome_ids and end in outcome_ids, f"unresolved edge: {edge['id']}")
        require(start != end, f"self edge: {edge['id']}")
        require(edge["kind"] in {"soft", "hard"}, f"invalid edge kind: {edge['id']}")
        require((start, end) not in pairs, f"duplicate edge pair: {edge['id']}")
        pairs.add((start, end))
        if edge["kind"] == "hard":
            graph[start].append(end)
    visiting, visited = set(), set()

    def visit(node):
        require(node not in visiting, "hard edge cycle")
        if node in visited:
            return
        visiting.add(node)
        for successor in graph[node]:
            visit(successor)
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        visit(node)


if __name__ == "__main__":
    try:
        path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("manifest.json")
        validate(json.loads(path.read_text(encoding="utf-8")))
    except (ValueError, KeyError, TypeError, IndexError, OSError) as error:
        print(f"pilot manifest invalid: {error}", file=sys.stderr)
        sys.exit(1)
    print("pilot manifest valid (editorial approval still required)")
