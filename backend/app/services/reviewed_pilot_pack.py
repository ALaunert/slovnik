"""Load the approved file-backed written pilot into the atomic publication boundary."""

from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
from uuid import UUID, uuid5

from app.domain.catalog import Construction, ContentStatus, UsageExample
from app.domain.curriculum import CurriculumNode, CurriculumVersion, PrerequisiteEdge, PrerequisiteKind
from app.domain.shared import Capability, Modality, TargetKind
from app.domain.target import TargetSpec
from app.pilot_examples import validate_pilot_examples
from app.reviewed_example_bank import bank_digest, rights_digest
from app.services.reviewed_pilot_publication_service import PublicationBundle


PILOT_PACK_NAMESPACE = UUID("c8432996-5ae3-4cb3-a089-780ae5cf8d3b")


def _pinned_json(root: Path, name: str) -> dict:
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError(f"invalid reviewed pack file: {name}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"reviewed pack file must be an object: {name}")
    return value


def _id(kind: str, name: str) -> str:
    return str(uuid5(PILOT_PACK_NAMESPACE, f"{kind}:{name}"))


def load_reviewed_pilot_bundle(
    manifest_path: Path, *, content_root: Path | None = None,
) -> PublicationBundle:
    """Read pinned approved files without changing catalog, curriculum or learner state."""
    root = (content_root or manifest_path.resolve().parents[2]).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1 or manifest.get("status") != "prepared_for_local":
        raise ValueError("unsupported or unapproved reviewed publication manifest")
    pilot = _pinned_json(root, manifest["pilot_file"])
    bank = _pinned_json(root, manifest["bank_file"])
    sources = _pinned_json(root, manifest["sources_file"])
    if manifest.get("bank_digest") != bank_digest(bank):
        raise ValueError("reviewed bank digest changed")
    pilot_digest = sha256(json.dumps(pilot, sort_keys=True, ensure_ascii=False,
                                   separators=(",", ":")).encode("utf-8")).hexdigest()
    if manifest.get("pilot_digest") != pilot_digest:
        raise ValueError("reviewed pilot brief digest changed")
    if manifest.get("rights_digest") != rights_digest(sources):
        raise ValueError("reviewed rights digest changed")
    errors = validate_pilot_examples(bank, pilot, sources, publication=True)
    if errors:
        raise ValueError("reviewed example bank rejected: " + "; ".join(errors))
    if manifest.get("version_id") != _id("version", f"{manifest['curriculum_code']}:{manifest['version_number']}"):
        raise ValueError("curriculum revision identity changed")

    outcomes = {item["id"]: item for item in pilot["outcomes"]}
    rows = manifest.get("targets")
    if (not isinstance(rows, list) or len(rows) != len(outcomes)
            or {row.get("outcome_code") for row in rows} != set(outcomes)):
        raise ValueError("reviewed outcome coverage missing or duplicated")
    by_outcome: dict[str, CurriculumNode] = {}
    constructions: list[Construction] = []
    mapping: dict[str, str] = {}
    source_by_id = {item["id"]: item for item in sources["sources"]}
    for row in rows:
        code = row["outcome_code"]
        outcome = outcomes[code]
        editorial_ref = outcome["primary_target"]["id"]
        if (row.get("editorial_target_ref") != editorial_ref
                or row.get("catalog_id") != _id("target", f"{editorial_ref}:{row.get('catalog_revision')}")
                or row.get("catalog_code") != f"{row.get('catalog_key')}-r{row.get('catalog_revision')}"
                or row.get("node_id") != _id("node", f"{manifest['version_id']}:{code}")
                or row.get("target_kind") != "construction"
                or row.get("capability") != "apply_construction"
                or row.get("cefr") != outcome["cefr"]
                or row.get("practice_families") != outcome["practice_families"]
                or row.get("assessment_family") != outcome["assessment_family"]):
            raise ValueError(f"{code}: stale target/outcome pin")
        items = [item for item in bank["examples"] if item["outcome_id"] == code]
        practice = [item for item in items if item["role"] == "practice"]
        assessment = [item for item in items if item["role"] == "assessment"]
        if (len(practice) != 1 or len(assessment) != 1
                or row.get("practice_example_id") != practice[0]["id"]
                or row.get("assessment_example_id") != assessment[0]["id"]):
            raise ValueError(f"{code}: reviewed practice/assessment identity mismatch")
        expected_policies = [
            {"id": item["answer_policy"]["id"], "revision": item["answer_policy"]["revision"]}
            for item in items
        ]
        if row.get("answer_policies") != expected_policies:
            raise ValueError(f"{code}: reviewed answer-policy revision changed")
        if any(
            row.get("source") != {
                "id": item["source_id"],
                "release": source_by_id[item["source_id"]]["release"],
                "checksum": source_by_id[item["source_id"]]["checksum"],
            }
            for item in items
        ):
            raise ValueError(f"{code}: reviewed source revision changed")
        mapping[editorial_ref] = row["catalog_id"]
        construction = Construction(
            id=row["catalog_id"], code=row["catalog_code"], title=row["title"],
            description=row["description"],
            morph_features={"pilot_outcome": code, "written_task_pattern": True},
            examples=(UsageExample(
                serbian_text=practice[0]["text"], translation=practice[0]["translation"],
            ),),
            status=ContentStatus.PUBLISHED, revision=row["catalog_revision"],
        )
        constructions.append(construction)
        by_outcome[code] = CurriculumNode(
            id=row["node_id"], curriculum_version_id=manifest["version_id"],
            target=TargetSpec(
                target_kind=TargetKind.CONSTRUCTION, target_id=row["catalog_id"],
                capability=Capability.APPLY_CONSTRUCTION, modality=Modality.WRITTEN,
            ),
            priority=row["priority"], outcome_code=code,
        )
    if len(set(mapping.values())) != len(mapping):
        raise ValueError("reviewed target mapping merges outcomes")
    if manifest.get("edges") != pilot.get("proposed_edges") or pilot.get("proposed_hard_edges"):
        raise ValueError("reviewed prerequisite proposal changed")
    edges = tuple(PrerequisiteEdge(
        id=_id("edge", f"{manifest['version_id']}:{item['from']}:{item['to']}"),
        curriculum_version_id=manifest["version_id"],
        prerequisite_node_id=by_outcome[item["from"]].id,
        dependent_node_id=by_outcome[item["to"]].id,
        kind=PrerequisiteKind(item["kind"]),
    ) for item in manifest["edges"])
    curriculum = CurriculumVersion(
        id=manifest["version_id"], curriculum_code=manifest["curriculum_code"],
        version_number=manifest["version_number"],
        created_at=datetime.fromisoformat(manifest["created_at"]),
        nodes=tuple(by_outcome.values()), prerequisites=edges,
    )
    return PublicationBundle(
        curriculum=curriculum, sources=sources, pilot=pilot, examples=bank,
        constructions=tuple(constructions), target_mapping=mapping,
    )
