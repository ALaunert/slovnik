"""Validate the P2-01a route inventory and sanitized rehearsal data.

Run from any directory: python docs/testing/identity/check_matrix.py
This checks design artifacts only; it does not assert that auth is implemented.
"""

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
ROUTERS = ROOT / "backend" / "app" / "routers"
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def source_routes() -> set[tuple[str, str]]:
    found = set()
    for source in ROUTERS.glob("*.py"):
        tree = ast.parse(source.read_text())
        prefix = ""
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            if not any(isinstance(target, ast.Name) and target.id == "router" for target in node.targets):
                continue
            if isinstance(node.value, ast.Call):
                for keyword in node.value.keywords:
                    if keyword.arg == "prefix":
                        prefix = ast.literal_eval(keyword.value)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                    continue
                if not isinstance(decorator.func.value, ast.Name) or decorator.func.value.id != "router":
                    continue
                if decorator.func.attr in HTTP_METHODS:
                    found.add((decorator.func.attr.upper(), prefix + ast.literal_eval(decorator.args[0])))
    return found


def main() -> None:
    matrix = json.loads((HERE / "route-ownership-matrix.json").read_text())
    fixtures = json.loads((HERE / "legacy-linking-rehearsal.json").read_text())
    listed = [(row["method"], row["path"]) for row in matrix["routes"]]
    assert len(listed) == len(set(listed)), "duplicate route in matrix"
    actual = source_routes()
    assert set(listed) == actual, f"route coverage mismatch: missing={actual - set(listed)}, stale={set(listed) - actual}"
    known_cases = set(matrix["cases"])
    for row in matrix["routes"]:
        assert set(row["cases"]) <= known_cases, row
        if row["scope"] in {"profile", "progress", "quiz"}:
            assert {"owner", "anonymous", "foreign", "expired", "revoked"} <= set(row["cases"]), row
        if row["scope"] == "editor":
            assert {"learner-editor", "forged-role", "expired", "revoked"} <= set(row["cases"]), row
    assert fixtures["synthetic"] is True
    assert len({p["user_id"] for p in fixtures["profiles"]}) == len(fixtures["profiles"])
    assert len({s["id"] for s in fixtures["scenarios"]}) == len(fixtures["scenarios"])
    assert {"unclaimed", "verified-opt-in", "claimed-collision", "claim-race", "idempotent-retry", "interrupted-claim", "logout"} <= {s["id"] for s in fixtures["scenarios"]}
    print(f"identity design inventory valid: {len(actual)} routes; {len(fixtures['scenarios'])} rehearsal scenarios")


if __name__ == "__main__":
    main()
