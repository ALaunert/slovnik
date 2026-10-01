"""Synthetic-only, file-based research preparation. Never writes product evidence."""

from copy import deepcopy
from hashlib import sha256
from itertools import combinations
from random import Random
from pathlib import Path
import json
import os

from app.research_export import PROTOCOL_VERSION, _participants, _utc, content_digest as digest
from app.reviewed_example_bank import bank_digest, rights_digest
from app.research_ledger import _unique

PROTOCOL_DOCUMENT = Path(__file__).resolve().parents[2] / "docs/testing/written-pilot-protocol.md"


def _cohort(registry):
    participants = _participants(registry)
    slots = set()
    result = []
    for participant in participants:
        slot = participant.get("slot")
        if type(slot) is not int or not 0 <= slot < 12 or slot in slots:
            raise ValueError("Each enrolled pseudonym needs a unique frozen slot 0..11")
        slots.add(slot)
        result.append({"pseudonym": participant["pseudonym"], "slot": slot})
    return sorted(result, key=lambda row: row["slot"])


def _example_pin(item):
    return {"id": item["id"], "revision": item["revision"], "hash": item["content_hash"],
            "context_family": item["context_family"], "answer_policy_id": item["answer_policy"]["id"],
            "answer_policy_revision": item["answer_policy"]["revision"]}


def freeze_assignment(registry, reviewed_bundle, *, seed, frozen_at, protocol_path=PROTOCOL_DOCUMENT):
    if not isinstance(seed, str) or not 1 <= len(seed) <= 100:
        raise ValueError("A retained assignment seed is required")
    frozen = _utc(frozen_at)
    targets = {}
    for node in reviewed_bundle.curriculum.nodes:
        items = [item for item in reviewed_bundle.examples["examples"] if item["outcome_id"] == node.outcome_code]
        targets[node.target.target_key] = {
            "outcome_code": node.outcome_code, "capability": node.target.capability.value,
            "modality": node.target.modality.value,
            **{role: _example_pin(next(item for item in items if item["role"] == role))
               for role in ("practice", "assessment")},
        }
    if len(targets) != 4:
        raise ValueError("Written protocol requires exactly four reviewed targets")
    keys = sorted(targets)
    pairs = list(combinations(keys, 2))*2
    Random(seed).shuffle(pairs)
    slots = [{"7": list(pair), "28": [key for key in keys if key not in pair]} for pair in pairs]
    return {"schema_version": 1, "protocol_version": PROTOCOL_VERSION, "synthetic": True,
            "frozen_at": frozen.isoformat(), "seed": seed, "cohort": _cohort(registry),
            "pins": {"curriculum_id": reviewed_bundle.curriculum.id,
                     "curriculum_revision": reviewed_bundle.curriculum.version_number,
                     "bank_digest": bank_digest(reviewed_bundle.examples), "rights_digest": rights_digest(reviewed_bundle.sources),
                     "protocol_sha256": sha256(Path(protocol_path).read_bytes()).hexdigest()},
            "targets": targets, "slots": slots}


def _source_activity(row):
    responded = row["response_at"]
    response = None
    if row["response_kind"] is not None:
        if responded is None or not isinstance(row["first_response"], str):
            raise ValueError("Invalid immutable first response")
        if row["response_kind"] == "rating":
            response = {"kind": "self_report", "at": responded, "rating": row["first_response"], "text": row["first_response"]}
        elif row["response_kind"] in {"text", "choice"}:
            response = {"kind": "scored", "at": responded, "outcome": row["outcome"], "text": row["first_response"]}
        else:
            raise ValueError("Unknown immutable response kind")
    elif row["first_response"] is not None or row["outcome"] is not None:
        raise ValueError("Invalid immutable first response")
    return {"id": row["activity_id"], "offered_at": row["issued_at"], "context_family": row["context_family"],
            "retry_of": row.get("retry_of"), "response": response,
            "probe_horizon_days": row.get("probe_horizon_days")}


def join_source_history(source, observer):
    """Reconcile retained file facts, not current DB rows. Unknownness is never upgraded."""
    rows = {row["activity_id"]: row for row in source}
    if len(rows) != len(source):
        raise ValueError("Duplicate source activity ID")
    observed = {row["id"]: row for row in _unique(observer["activities"])}
    if rows.keys() != observed.keys():
        raise ValueError("Observer coverage has missing or additional source activities")
    activities, presentations = [], deepcopy(observer.get("presentations", []))
    for activity_id, row in rows.items():
        expected, facts = _source_activity(row), observed[activity_id]
        for field in ("id", "context_family", "retry_of", "probe_horizon_days"):
            if facts.get(field) != expected[field]:
                raise ValueError("Observer conflicts with immutable source activity")
        if _utc(facts["offered_at"]) != _utc(expected["offered_at"]):
            raise ValueError("Observer conflicts with immutable source invitation")
        response, claimed = expected["response"], facts.get("response")
        if (response is None) != (claimed is None):
            raise ValueError("Observer conflicts with immutable first response")
        if response is not None:
            if _utc(claimed["at"]) != _utc(response["at"]) or any(
                claimed.get(key) != value for key, value in response.items() if key != "at"
            ):
                raise ValueError("Observer conflicts with immutable first response")
        declared = {"cue": "hint"}.get(row["support_declared"], row["support_declared"])
        support = facts.get("support", "unknown")
        if support not in {"none", "unknown", "hint", "reveal", "correction", "exposure"}:
            raise ValueError("Unknown observer support")
        if declared in {"hint", "reveal", "correction", "exposure"} and support != declared:
            raise ValueError("Observer cannot erase known source support")
        if declared == "unknown" and support == "none":
            support = "unknown"
        normalized = {**expected, **{key: facts[key] for key in ("display_status", "shown_at", "support_at") if key in facts},
                      "support": support}
        if declared == "exposure":
            presentations.append({key: value for key, value in normalized.items()
                                  if key in {"id", "offered_at", "context_family", "display_status", "shown_at"}})
        else:
            activities.append(normalized)
    return {"activities": activities, "presentations": presentations}


SOURCE_FIELDS = set("pseudonym activity_id event_id target_key capability modality context_family retry_of issued_at response_at first_response response_kind outcome evaluation_source support_declared diagnostic_category display_status delayed_eligibility independence_verified active_minutes status example_id example_revision example_hash answer_policy_id answer_policy_revision selection_policy_version workload".split())
SUPPORT_KINDS = {"none", "unknown", "hint", "reveal", "correction", "exposure"}
PRESENTATION_FIELDS = {"id", "activity_id", "offered_at", "shown_at", "context_family", "display_status", "support", "support_at"}


def _initial_display(presentation, activity):
    return (presentation.get("activity_id") == activity["id"]
            and presentation.get("display_status") == activity.get("display_status") == "shown"
            and presentation["context_family"] == activity["context_family"]
            and _utc(presentation["offered_at"]) == _utc(activity["offered_at"])
            and _utc(presentation["shown_at"]) == _utc(activity["shown_at"]))


def _check_pin(record, pin):
    fields = {"example_id": "id", "example_revision": "revision", "example_hash": "hash",
              "context_family": "context_family", "answer_policy_id": "answer_policy_id",
              "answer_policy_revision": "answer_policy_revision"}
    if any(record.get(field) != pin[name] for field, name in fields.items()):
        raise ValueError("Frozen reviewed example/answer-policy pin mismatch")


def _uuid4(value):
    from uuid import UUID
    if not isinstance(value, str) or str(UUID(value)) != value or UUID(value).version != 4:
        raise ValueError("Canonical random UUID4 required")
    return value


def _blind_rows(candidates, assignment, registry, retained_mapping):
    from random import SystemRandom
    from uuid import uuid4
    study = digest(assignment)
    required = {digest([row["pseudonym"], row["target_key"], row["probe_id"]]): row for row in candidates}
    withdrawn = {row["pseudonym"] for row in registry["participants"] if row["withdrawn"]}
    entries = []
    if retained_mapping is not None:
        if set(retained_mapping) != {"assignment_sha256", "entries"} or retained_mapping.get("assignment_sha256") != study:
            raise ValueError("Retained blind mapping belongs to another frozen assignment")
        known_keys, known_ids, orders = set(), set(), set()
        for item in retained_mapping["entries"]:
            if set(item) != {"source_key", "pseudonym", "response_sha256", "response_id", "order"}:
                raise ValueError("Unknown retained blind mapping fields")
            key, response_id, order = item["source_key"], _uuid4(item["response_id"]), item["order"]
            if key in known_keys or response_id in known_ids or type(order) is not int or order < 0 or order in orders:
                raise ValueError("Blind mapping IDs/order must be unique")
            known_keys.add(key)
            known_ids.add(response_id)
            orders.add(order)
            if item["pseudonym"] in withdrawn:
                continue
            row = required.get(key)
            if row is None or item["pseudonym"] != row["pseudonym"] or item["response_sha256"] != digest(row["blind"]):
                raise ValueError("Retained blind mapping conflicts with immutable first response")
            entries.append(deepcopy(item))
        if {item["source_key"] for item in entries} != required.keys():
            raise ValueError("Retained blind mapping has missing first responses")
    else:
        rows = list(required.items())
        SystemRandom().shuffle(rows)
        entries = [{"source_key": key, "pseudonym": row["pseudonym"], "response_sha256": digest(row["blind"]),
                    "response_id": str(uuid4()), "order": index} for index, (key, row) in enumerate(rows)]
    entries.sort(key=lambda item: item["order"])
    blind = [{"response_id": item["response_id"], **required[item["source_key"]]["blind"]} for item in entries]
    return blind, {"assignment_sha256": study, "entries": entries}


def build_dataset(export, registry, assignment, observer, reviewed_bundle, *, retained_mapping=None,
                  protocol_path=PROTOCOL_DOCUMENT):
    """Join retained synthetic inputs. File hashes attest consistency, not DB authenticity."""
    from collections import defaultdict
    from app.domain.shared import Capability
    from app.services.answer_policy import ReviewedAnswerPolicy
    from app.research_ledger import summarize_history
    participants = _participants(registry)
    active = {row["pseudonym"]: row for row in participants if not row["withdrawn"]}
    expected = freeze_assignment(registry, reviewed_bundle, seed=assignment["seed"], frozen_at=assignment["frozen_at"],
                                 protocol_path=protocol_path)
    if assignment != expected:
        raise ValueError("Frozen assignment/content/protocol pins changed")
    manifest = export["manifest"]
    if (manifest.get("export_version") != "local-research-export-v2" or manifest.get("synthetic") is not True
            or manifest.get("protocol_version") != PROTOCOL_VERSION
            or manifest.get("enrollment_sha256") != digest(registry)
            or manifest.get("records_sha256") != digest(export["records"])
            or manifest.get("records") != len(export["records"])):
        raise ValueError("Source export manifest/input digest mismatch")
    if (type(observer.get("schema_version")) is not int or observer["schema_version"] != 1 or observer.get("synthetic") is not True
            or observer.get("protocol_version") != PROTOCOL_VERSION):
        raise ValueError("Unknown or non-synthetic observer protocol")
    frozen = _utc(assignment["frozen_at"])
    sources, used_ids = defaultdict(list), set()
    for row in export["records"]:
        owner, target = row["pseudonym"], row["target_key"]
        if owner not in active or target not in assignment["targets"] or set(row)-SOURCE_FIELDS:
            raise ValueError("Unconsented owner, unknown target or extra source fields")
        activity_id = _uuid4(row["activity_id"])
        if activity_id in used_ids:
            raise ValueError("Duplicate source activity ID")
        used_ids.add(activity_id)
        pin = assignment["targets"][target]
        if row["capability"] != pin["capability"] or row["modality"] != pin["modality"]:
            raise ValueError("Source target scope mismatch")
        _check_pin(row, pin["practice"])
        if _utc(row["issued_at"]) < max(frozen, _utc(active[owner]["consent_at"])):
            raise ValueError("Source invitation predates frozen assignment or consent")
        sources[owner, target].append(row)
    observations = {}
    for row in observer["histories"]:
        key = (row["pseudonym"], row["target_key"])
        if key[0] not in active or key[1] not in assignment["targets"]:
            raise ValueError("Observer owner/target is not consented")
        if key in observations and observations[key] != row:
            raise ValueError("Duplicate observer history conflicts")
        observations[key] = row
    if not sources.keys() <= observations.keys():
        raise ValueError("Observer coverage is missing source history")
    for rows in sources.values():
        by_id = {row["activity_id"]: row for row in rows}
        for row in rows:
            if row.get("retry_of") is not None and row["retry_of"] not in by_id:
                raise ValueError("Retry parent is outside this consented owner/target history")
    items = {item["id"]: item for item in reviewed_bundle.examples["examples"]}
    histories, candidates, incidents = [], [], set()
    invited = 0
    for owner, participant in active.items():
        slot = assignment["slots"][participant["slot"]]
        for target, pin in assignment["targets"].items():
            facts = observations.get((owner, target), {"activities": [], "presentations": [], "probes": []})
            for presentation in facts.get("presentations", []):
                if set(presentation)-PRESENTATION_FIELDS or presentation.get("support", "unknown") not in SUPPORT_KINDS:
                    raise ValueError("Unknown observer presentation fields/support")
                if _utc(presentation["offered_at"]) < max(frozen, _utc(participant["consent_at"])):
                    raise ValueError("Observer display predates frozen assignment or consent")
            joined = join_source_history(sources[owner, target], facts)
            horizon = 7 if target in slot["7"] else 28
            probes = _unique(facts.get("probes", []))
            if len(probes) > 1:
                raise ValueError("Only one heldout probe per enrolled participant/target")
            for probe in probes:
                _uuid4(probe["id"])
                if probe["id"] in used_ids:
                    raise ValueError("Duplicate probe ID")
                used_ids.add(probe["id"])
                _check_pin(probe, pin["assessment"])
                if probe.get("support", "unknown") not in SUPPORT_KINDS-{"exposure"}:
                    raise ValueError("Unknown probe support")
                if type(probe.get("probe_horizon_days")) is not int or probe["probe_horizon_days"] != horizon or probe.get("retry_of") is not None:
                    raise ValueError("Probe differs from frozen horizon/first-attempt assignment")
                if _utc(probe["offered_at"]) < max(frozen, _utc(participant["consent_at"])):
                    raise ValueError("Probe invitation predates frozen assignment or consent")
                normalized = {key: deepcopy(probe[key]) for key in ("id", "offered_at", "context_family", "display_status", "shown_at", "support", "support_at") if key in probe}
                normalized["probe_horizon_days"] = horizon
                response = probe.get("response")
                if response is not None:
                    item = items[pin["assessment"]["id"]]
                    verdict = ReviewedAnswerPolicy.from_reviewed_example(item, capability=Capability(pin["capability"])).evaluate(response["text"])
                    normalized["response"] = {"kind": "scored", "at": response["at"], "text": response["text"], "outcome": verdict.verdict.value}
                    candidates.append({"pseudonym": owner, "target_key": target, "probe_id": probe["id"],
                                       "blind": {"task": {key: item["task"][key] for key in ("input", "instruction_ru", "format")},
                                                 "first_response": response["text"], "rubric": {"version": "written-task-rubric-v1", "task_success": [0, 1, 2], "target_accuracy": [0, 1, 2]}}})
                else:
                    normalized["response"] = None
                cutoff = response["at"] if response else probe.get("shown_at") or probe["offered_at"]
                if any(row["context_family"] == pin["assessment"]["context_family"] and row.get("display_status") == "shown"
                       and _utc(row["shown_at"]) < _utc(cutoff) and not _initial_display(row, normalized)
                       for row in joined["presentations"]):
                    incidents.add("heldout_previous_display")
                joined["activities"].append(normalized)
                invited += 1
            by_id = {row["id"]: row for row in joined["activities"]}
            for presentation in joined["presentations"]:
                if presentation.get("activity_id") is not None:
                    linked = by_id.get(presentation["activity_id"])
                    if linked is None or linked["context_family"] != presentation["context_family"]:
                        raise ValueError("Observer display link has unknown activity or mismatched family")
                    if not _initial_display(presentation, linked):
                        raise ValueError("A linked display must match the activity's observed initial display")
                    if presentation.get("support") in {"hint", "reveal", "correction"} and (
                            presentation["support"] != linked.get("support")
                            or presentation.get("support_at") != linked.get("support_at")):
                        raise ValueError("Linked support conflicts with the observed activity")
            history = {**joined, "history_complete": facts.get("history_complete") is True,
                       "support_capture_complete": facts.get("support_capture_complete") is True, "key_frozen": True}
            metrics = summarize_history(history)
            histories.append({"pseudonym": owner, "target_key": target, "capability": pin["capability"], "modality": pin["modality"],
                              "assigned_horizon_days": horizon, **history, "metrics": metrics,
                              "workload": [{"activity_id": row["activity_id"], "report": _workload(row.get("workload"))}
                                           for row in sources[owner, target]]})
    blind, mapping = _blind_rows(candidates, assignment, registry, retained_mapping)
    analysis = {"synthetic": True, "human_agreement": "not_measured", "protocol_status": "preparation",
                "recruitment_target": 12, "enrolled": len(active), "withdrawn": len(participants)-len(active),
                "unrecruited": 12-len(participants),
                "planned": len(active)*4, "invited": invited, "not_invited": len(active)*4-invited,
                "incidents": sorted(incidents), "active_minutes": None,
                "efficacy_or_cefr_claim": None}
    return {"manifest": {"schema_version": 1, "dataset_version": "written-research-dataset-v1", "synthetic": True,
                         "input_hashes": {"export": digest(export), "enrollment": digest(registry), "assignment": digest(assignment),
                                          "observer": digest(observer)},
                         "omissions": ["human consent review", "human rubric agreement", "verified active minutes", "DB source attestation"]},
            "histories": histories, "blind": blind, "mapping": mapping, "analysis": analysis,
            "assignment": deepcopy(assignment), "protocol": Path(protocol_path).read_bytes().decode("utf-8")}


def _workload(report):
    if report is None:
        return None
    if not isinstance(report, dict) or set(report)-{"policy_version", "timezone", "window", "issued", "limits", "remaining"}:
        raise ValueError("Unknown workload fields")
    # Workload must be structured counters/window metadata, never free-form identity fields.
    for key in ("issued", "limits", "remaining"):
        values = report.get(key, {})
        if (not isinstance(values, dict) or set(values)-{"total", "root", "new", "due", "weak", "assessment", "repair", "probe"}
                or any(type(value) is not int or value < 0 for value in values.values())):
            raise ValueError("Invalid workload counters")
    if "window" in report and (not isinstance(report["window"], dict) or set(report["window"])-{
            "start", "end", "timezone", "transition", "calendar_policy_version"}):
        raise ValueError("Unknown workload window fields")
    return deepcopy(report)


def empty_ratings(blind):
    return {"schema_version": 1, "synthetic": True, "protocol_version": PROTOCOL_VERSION,
            "blind_sha256": digest(blind), "ratings": [], "adjudications": []}


def analyze_ratings(blind, ratings):
    """Check linked synthetic rubric rows; retain disagreement and missing pairs."""
    if (type(ratings.get("schema_version")) is not int or ratings["schema_version"] != 1
            or ratings.get("synthetic") is not True or ratings.get("protocol_version") != PROTOCOL_VERSION
            or ratings.get("blind_sha256") != digest(blind)
            or set(ratings)-{"schema_version", "synthetic", "protocol_version", "blind_sha256", "ratings", "adjudications"}):
        raise ValueError("Unknown ratings protocol or blind packet digest mismatch")
    known = {_uuid4(row["response_id"]) for row in blind}
    if len(known) != len(blind):
        raise ValueError("Duplicate blinded response ID")
    by_response = {response_id: {} for response_id in known}
    adjudications = {}
    for key in ("ratings", "adjudications"):
        rows = ratings.get(key, [])
        if not isinstance(rows, list):
            raise ValueError("Expected rating rows")
        for row in rows:
            if set(row) != {"response_id", "rater_id", "task_success", "target_accuracy"}:
                raise ValueError("Unknown rating fields")
            response_id, rater_id = _uuid4(row["response_id"]), _uuid4(row["rater_id"])
            if response_id not in known or any(type(row[scale]) is not int or row[scale] not in (0, 1, 2)
                                               for scale in ("task_success", "target_accuracy")):
                raise ValueError("Unlinked response or invalid rubric score")
            previous = by_response[response_id].get(rater_id) if key == "ratings" else adjudications.get(response_id)
            if previous is not None and previous != row:
                raise ValueError("Conflicting duplicate rater/response")
            if key == "ratings":
                by_response[response_id][rater_id] = deepcopy(row)
                if len(by_response[response_id]) > 2:
                    raise ValueError("Only two distinct independent raters are allowed")
            else:
                if len(by_response[response_id]) != 2:
                    raise ValueError("Adjudication needs the two original ratings")
                adjudications[response_id] = deepcopy(row)
    scales = {scale: {"agree": 0, "disagree": 0, "extreme_disagreement": 0}
              for scale in ("task_success", "target_accuracy")}
    paired = 0
    for rows in by_response.values():
        if len(rows) != 2:
            continue
        paired += 1
        first, second = rows.values()
        for scale in scales:
            distance = abs(first[scale]-second[scale])
            scales[scale]["agree" if distance == 0 else "disagree"] += 1
            scales[scale]["extreme_disagreement"] += distance == 2
    return {"synthetic": True, "human_agreement": "not_measured", "responses": len(known), "paired": paired,
            "missing_ratings": sum(2-len(rows) for rows in by_response.values()),
            "unpaired_response_ids": sorted(key for key, rows in by_response.items() if len(rows) != 2),
            "scales": scales, "adjudications": len(adjudications)}


DATASET_FILES = ("dataset.json", "assignment.json", "protocol.md", "blinded-responses.json",
                 "blind-mapping.json", "ratings.json", "analysis.json")
MANIFEST_FILE = "dataset-manifest.json"


def _private_path(directory):
    requested = Path(directory).absolute()
    if any(path.is_symlink() for path in (requested, *requested.parents)):
        raise ValueError("Refusing research files through a symlink")
    destination = requested.resolve()
    if destination.is_relative_to(Path(__file__).resolve().parents[2]):
        raise ValueError("Research files must be outside the repository")
    return destination


def _encoded(payload):
    return json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")


def write_dataset(dataset, directory, *, ratings=None):
    """Write a new, private synthetic bundle. Input registries remain separately held."""
    manifest = deepcopy(dataset["manifest"])
    if manifest.get("dataset_version") != "written-research-dataset-v1" or manifest.get("synthetic") is not True:
        raise ValueError("Unknown or non-synthetic research dataset")
    ratings = ratings if ratings is not None else empty_ratings(dataset["blind"])
    analysis = {**dataset["analysis"], "ratings": analyze_ratings(dataset["blind"], ratings)}
    protocol = dataset["protocol"].encode("utf-8")
    if sha256(protocol).hexdigest() != dataset["assignment"]["pins"]["protocol_sha256"]:
        raise ValueError("Retained protocol digest mismatch")
    payloads = {"dataset.json": _encoded(dataset["histories"]), "assignment.json": _encoded(dataset["assignment"]),
                "protocol.md": protocol, "blinded-responses.json": _encoded(dataset["blind"]),
                "blind-mapping.json": _encoded(dataset["mapping"]), "ratings.json": _encoded(ratings),
                "analysis.json": _encoded(analysis)}
    manifest["input_hashes"]["ratings"] = digest(ratings)
    manifest["input_hashes"]["blind_mapping"] = digest(dataset["mapping"])
    manifest["files"] = list(DATASET_FILES)
    manifest["file_sha256"] = {name: sha256(value).hexdigest() for name, value in payloads.items()}
    payloads[MANIFEST_FILE] = _encoded(manifest)
    _write_private(payloads, directory)


def _write_private(payloads, directory):
    destination = _private_path(directory)
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    os.chmod(destination, 0o700)
    for name, value in payloads.items():
        with (destination / name).open("xb") as handle:
            os.chmod(destination / name, 0o600)
            handle.write(value)


def _read_manifest(destination):
    files = tuple(destination.iterdir())
    if {path.name for path in files} != {*DATASET_FILES, MANIFEST_FILE}:
        raise ValueError("Refusing research dataset with unknown files")
    if any(path.is_symlink() or not path.is_file() for path in files):
        raise ValueError("Refusing research dataset with a symlink or non-file")
    manifest = json.loads((destination / MANIFEST_FILE).read_text(encoding="utf-8"))
    if (manifest.get("dataset_version") != "written-research-dataset-v1" or manifest.get("synthetic") is not True
            or manifest.get("files") != list(DATASET_FILES)):
        raise ValueError("Unknown research dataset manifest")
    return manifest


def verify_dataset(directory):
    destination = _private_path(directory)
    manifest = _read_manifest(destination)
    if manifest.get("file_sha256") != {name: sha256((destination / name).read_bytes()).hexdigest() for name in DATASET_FILES}:
        raise ValueError("Research dataset file digest mismatch")
    return manifest


def remove_dataset(directory):
    destination = _private_path(directory)
    if not destination.exists():
        return
    _read_manifest(destination)
    for name in (*DATASET_FILES, MANIFEST_FILE):
        (destination / name).unlink()
    destination.rmdir()


def write_assignment(assignment, directory, *, protocol_path=PROTOCOL_DOCUMENT):
    protocol = Path(protocol_path).read_bytes()
    if (assignment.get("synthetic") is not True or assignment.get("protocol_version") != PROTOCOL_VERSION
            or assignment["pins"]["protocol_sha256"] != sha256(protocol).hexdigest()):
        raise ValueError("Unknown assignment or protocol digest mismatch")
    _write_private({"assignment.json": _encoded(assignment), "protocol.md": protocol}, directory)


def remove_assignment(directory):
    destination = _private_path(directory)
    if not destination.exists():
        return
    files = tuple(destination.iterdir())
    if {path.name for path in files} != {"assignment.json", "protocol.md"}:
        raise ValueError("Refusing assignment deletion with unknown files")
    if any(path.is_symlink() or not path.is_file() for path in files):
        raise ValueError("Refusing assignment deletion with a symlink or non-file")
    assignment = json.loads((destination / "assignment.json").read_text(encoding="utf-8"))
    if assignment.get("synthetic") is not True or assignment.get("protocol_version") != PROTOCOL_VERSION:
        raise ValueError("Unknown assignment")
    for path in files:
        path.unlink()
    destination.rmdir()


def main(argv=None):
    import argparse
    from app.services.reviewed_pilot_pack import load_reviewed_pilot_bundle
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("freeze", "build"):
        sub = commands.add_parser(command)
        for name in ("enrollment", "pack", "output"):
            sub.add_argument("--"+name, type=Path, required=True)
        sub.add_argument("--content-root", type=Path)
        sub.add_argument("--protocol", type=Path, default=PROTOCOL_DOCUMENT)
        if command == "freeze":
            sub.add_argument("--seed", required=True)
            sub.add_argument("--frozen-at", required=True)
        else:
            for name in ("export", "assignment", "observer"):
                sub.add_argument("--"+name, type=Path, required=True)
            for name in ("mapping", "ratings"):
                sub.add_argument("--"+name, type=Path)
    for command in ("verify", "remove", "remove-assignment"):
        commands.add_parser(command).add_argument("directory", type=Path)
    args = parser.parse_args(argv)
    if args.command == "verify":
        print(json.dumps(verify_dataset(args.directory), ensure_ascii=False, indent=2))
    elif args.command == "remove":
        remove_dataset(args.directory)
    elif args.command == "remove-assignment":
        remove_assignment(args.directory)
    else:
        def read(path):
            return json.loads(path.read_text(encoding="utf-8"))
        enrollment = read(args.enrollment)
        bundle = load_reviewed_pilot_bundle(args.pack, content_root=args.content_root)
        if args.command == "freeze":
            assignment = freeze_assignment(enrollment, bundle, seed=args.seed, frozen_at=args.frozen_at, protocol_path=args.protocol)
            write_assignment(assignment, args.output, protocol_path=args.protocol)
        else:
            source = ({"manifest": read(args.export / "export-manifest.json"), "records": read(args.export / "events.json")}
                      if args.export.is_dir() else read(args.export))
            dataset = build_dataset(source, enrollment, read(args.assignment), read(args.observer), bundle,
                                    retained_mapping=read(args.mapping) if args.mapping else None, protocol_path=args.protocol)
            write_dataset(dataset, args.output, ratings=read(args.ratings) if args.ratings else None)


if __name__ == "__main__":
    main()
