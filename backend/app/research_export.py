"""P1-09b engineering export preparation; human collection/export is still gated."""

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from uuid import UUID

from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.domain_models.practice import ActivityInstanceModel, PracticeRunModel
from app.repositories.practice import PracticeRepository
from app.services.evidence_diagnostic_service import diagnose_events
from app.services.local_workload import LOCAL_POLICIES

PROTOCOL_VERSION = "written-feasibility-protocol-v1"


def content_digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _utc(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
        if value.tzinfo is None:
            raise ValueError("Consent time must have a timezone")
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _participants(registry):
    if type(registry.get("schema_version")) is not int or registry.get("schema_version") != 1 or registry.get("protocol_version") != PROTOCOL_VERSION:
        raise ValueError("Unknown enrollment/protocol version")
    if registry.get("synthetic") is not True:
        raise ValueError("Human consent review and protocol are not frozen; human export is unavailable")
    review = registry.get("review", {})
    if review.get("status") != "fixture" or not review.get("reference"):
        raise ValueError("Synthetic review reference required")
    participants = registry.get("participants")
    if not isinstance(participants, list) or len(participants) > 12:
        raise ValueError("Expected at most twelve participant records")
    seen_owners, seen_pseudonyms = set(), set()
    for participant in participants:
        owner, pseudonym = participant.get("learner_id"), participant.get("pseudonym")
        if not isinstance(owner, str) or not 1 <= len(owner) <= 80:
            raise ValueError("Valid local profile ID required")
        if not isinstance(pseudonym, str) or UUID(pseudonym).version != 4 or str(UUID(pseudonym)) != pseudonym:
            raise ValueError("A random UUID4 study pseudonym is required")
        if owner in seen_owners or pseudonym in seen_pseudonyms:
            raise ValueError("Enrollment mapping must be unique")
        seen_owners.add(owner)
        seen_pseudonyms.add(pseudonym)
        if participant.get("consent_version") != "written-feasibility-consent-v1":
            raise ValueError("Known consent version required")
        digest = participant.get("consent_evidence_sha256", "")
        if not isinstance(digest, str) or len(digest) != 64 or set(digest) - set("0123456789abcdef"):
            raise ValueError("Consent evidence reference hash required")
        if type(participant.get("withdrawn")) is not bool:
            raise ValueError("Explicit withdrawal state required")
        scopes = participant.get("scopes", [])
        if not isinstance(scopes, list) or not all(isinstance(scope, str) for scope in scopes):
            raise ValueError("Consent scopes must be strings")
        if not {"local_practice", "research_export", "blinded_rating"}.issubset(scopes):
            raise ValueError("Required consent scope is absent")
        _utc(participant["consent_at"])
    return participants


def export_local_events(session, registry):
    if not settings.local_pilot_enabled or settings.environment.strip().casefold() not in {"local", "development", "test"}:
        raise ValueError("Explicit local pilot environment required")
    participants = _participants(registry)
    repository = PracticeRepository(session)
    records = []
    for participant in participants:
        if participant["withdrawn"]:
            continue
        consent_at = _utc(participant["consent_at"])
        rows = tuple(session.scalars(select(ActivityInstanceModel).join(PracticeRunModel).where(
            PracticeRunModel.learner_id == participant["learner_id"],
            PracticeRunModel.selection_policy_version.in_(LOCAL_POLICIES),
            PracticeRunModel.legacy_quiz_attempt_id.is_(None),
            ActivityInstanceModel.selected_at >= consent_at,
        ).order_by(ActivityInstanceModel.selected_at, ActivityInstanceModel.id)))
        pairs = []
        loaded = []
        from app.domain_models.practice import LearningEventModel
        for row in rows:
            event_row = session.scalar(select(LearningEventModel).where(LearningEventModel.activity_instance_id == row.id))
            event = repository.get_learning_event(participant["learner_id"], event_row.idempotency_key) if event_row else None
            activity = repository.get_activity(row.id)
            loaded.append((activity, event))
            if event:
                pairs.append((event, activity))
        classifications = {item.event_id: item for item in diagnose_events(pairs)}
        for activity, event in loaded:
            snapshot = activity.spec.to_payload()["snapshot"]
            classification = classifications.get(event.event_id) if event else None
            records.append({
                "pseudonym": participant["pseudonym"], "activity_id": activity.id,
                "event_id": event.event_id if event else None,
                "target_key": activity.target_key, "capability": activity.target_spec.capability.value,
                "modality": activity.target_spec.modality.value,
                "context_family": snapshot.get("context_family_id"), "retry_of": activity.retry_of_activity_instance_id,
                "issued_at": _utc(activity.selected_at).isoformat(),
                "response_at": _utc(event.occurred_at).isoformat() if event else None,
                "first_response": event.first_response.value if event and event.first_response else None,
                "response_kind": event.first_response.kind.value if event and event.first_response else None,
                "outcome": event.evaluation_outcome.value if event and event.evaluation_outcome else None,
                "evaluation_source": event.evaluation_source.value if event and event.evaluation_source else None,
                "support_declared": snapshot.get("repair_support") or (
                    "exposure" if activity.spec.activity_kind.value == "exposure" else
                    "none" if snapshot.get("support_capture_complete") is True else "unknown"),
                "diagnostic_category": classification.category if classification else None,
                "display_status": "unknown", "delayed_eligibility": "unknown", "independence_verified": False,
                "active_minutes": None, "status": activity.status.value,
                "example_id": snapshot.get("example_id"), "example_revision": snapshot.get("example_revision"),
                "example_hash": snapshot.get("example_hash"), "answer_policy_id": snapshot.get("answer_policy_id"),
                "answer_policy_revision": snapshot.get("answer_policy_revision"),
                "selection_policy_version": activity.selection.policy_version,
                "workload": snapshot.get("workload_policy"),
            })
    return {"manifest": {"schema_version": 1, "export_version": "local-research-export-v2",
                         "protocol_version": PROTOCOL_VERSION, "protocol_status": "draft", "synthetic": True,
                         "generated_at": datetime.now(timezone.utc).isoformat(),
                         "enrollment_sha256": content_digest(registry), "records_sha256": content_digest(records),
                         "records": len(records),
                         "omissions": ["verified displays/latest contacts", "delayed probes", "human ratings", "active minutes"],
                         "files": ["events.json", "export-manifest.json"]}, "records": records}


def write_export(export, directory):
    destination = Path(directory).resolve()
    repository = Path(__file__).resolve().parents[2]
    if destination.is_relative_to(repository):
        raise ValueError("Research exports must be outside the repository")
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    os.chmod(destination, 0o700)
    for name, payload in (("events.json", export["records"]), ("export-manifest.json", export["manifest"])):
        path = destination / name
        with path.open("x", encoding="utf-8") as handle:
            os.chmod(path, 0o600)
            json.dump(payload, handle, ensure_ascii=False, indent=2)


def remove_export(directory):
    requested = Path(directory).absolute()
    if any(path.is_symlink() for path in (requested, *requested.parents)):
        raise ValueError("Refusing export deletion through a symlink")
    destination = requested.resolve()
    if destination.is_relative_to(Path(__file__).resolve().parents[2]):
        raise ValueError("Research exports must be outside the repository")
    if not destination.exists():
        return
    files = tuple(destination.iterdir())
    if {path.name for path in files} != {"events.json", "export-manifest.json"}:
        raise ValueError("Refusing export deletion with unknown files")
    if any(path.is_symlink() or not path.is_file() for path in files):
        raise ValueError("Refusing export deletion with a symlink or non-file")
    manifest = json.loads((destination / "export-manifest.json").read_text())
    if manifest.get("export_version") not in {"local-research-export-v1", "local-research-export-v2"} or manifest.get("files") != ["events.json", "export-manifest.json"]:
        raise ValueError("Unknown export manifest")
    for name in manifest["files"]:
        (destination / name).unlink()
    destination.rmdir()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("enrollment", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    with SessionLocal() as session:
        write_export(export_local_events(session, json.loads(args.enrollment.read_text())), args.output)


if __name__ == "__main__":
    main()
