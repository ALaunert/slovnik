"""Small, deterministic validation helpers for file-backed source rights manifests.

This module checks recorded decisions. It does not determine whether a license or
agreement legally permits a use.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


USES = {"analysis", "redistribution", "adaptation"}
DECISIONS = {"allowed", "denied", "unknown"}
MATERIALS = {"text", "translation"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ManifestError(ValueError):
    """Raised when a manifest file cannot be parsed as JSON."""


def load_manifest(path: str | Path) -> dict[str, Any]:
    """Load a JSON manifest without interpreting its rights decisions."""
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ManifestError(f"could not read source manifest: {exc}") from exc
    if not isinstance(value, dict):
        raise ManifestError("source manifest must be a JSON object")
    return value


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _validate_material(
    errors: list[str],
    source_id: str,
    item_id: str,
    label: str,
    material: Any,
    requested_uses: set[str],
) -> None:
    prefix = f"source {source_id} item {item_id} {label}"
    if not isinstance(material, dict):
        errors.append(f"{prefix}: must be an object")
        return
    rights = material.get("rights")
    if not isinstance(rights, dict):
        errors.append(f"{prefix}: rights must be an object")
        rights = {}
    for use in sorted(USES):
        decision = rights.get(use)
        if decision not in DECISIONS:
            errors.append(f"{prefix}: rights.{use} must be allowed, denied, or unknown")
        elif use in requested_uses and decision != "allowed":
            errors.append(f"{prefix}: {use} is {decision}")

    if not _nonempty(material.get("license")):
        errors.append(f"{prefix}: license is required")
    if not _nonempty(material.get("evidence_url")):
        errors.append(f"{prefix}: evidence_url is required")
    if not _nonempty(material.get("reviewer")):
        errors.append(f"{prefix}: reviewer is required")
    if not _nonempty(material.get("reviewed_on")):
        errors.append(f"{prefix}: reviewed_on is required")

    attribution_required = material.get("attribution_required", False)
    share_alike_required = material.get("share_alike_required", False)
    if not isinstance(attribution_required, bool) or not isinstance(share_alike_required, bool):
        errors.append(f"{prefix}: attribution and share-alike flags must be booleans")
        return
    if requested_uses and attribution_required and not _nonempty(material.get("attribution")):
        errors.append(f"{prefix}: attribution is required")
    if "adaptation" in requested_uses and share_alike_required and not _nonempty(
        material.get("share_alike_notice")
    ):
        errors.append(f"{prefix}: share-alike notice is required")


def validate_manifest(
    manifest: dict[str, Any],
    requested_uses: set[str] | None = None,
    requested_item_ids: set[str] | None = None,
    requested_materials: set[str] | None = None,
) -> list[str]:
    """Return stable validation errors; unknown rights block only requested uses.

    ``requested_uses`` represents a publication preflight. When item IDs and material
    kinds are supplied, permission decisions are checked only for those items/materials;
    schema and evidence are still checked throughout the manifest. The default includes
    every present material for compatibility with existing callers.
    """
    errors: list[str] = []
    uses = set(requested_uses or ())
    unknown_uses = uses - USES
    for use in sorted(unknown_uses):
        errors.append(f"unknown requested use: {use}")
    material_scope = set(requested_materials) if requested_materials is not None else MATERIALS | {"audio"}
    for material in sorted(material_scope - MATERIALS - {"audio"}):
        errors.append(f"unknown requested material: {material}")
    if not isinstance(manifest, dict):
        return ["manifest must be an object"]
    if manifest.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    sources = manifest.get("sources")
    if not isinstance(sources, list):
        return errors + ["sources must be an array"]

    source_ids: set[str] = set()
    item_ids: set[str] = set()
    for source in sources:
        if not isinstance(source, dict):
            errors.append("source entry must be an object")
            continue
        source_id = source.get("source_id")
        if not _nonempty(source_id):
            errors.append("source_id is required")
            source_id = "<missing>"
        elif source_id in source_ids:
            errors.append(f"duplicate source_id: {source_id}")
        source_ids.add(source_id)
        if source.get("kind") not in {"authored", "corpus", "dictionary", "community", "other"}:
            errors.append(f"source {source_id}: unsupported kind")
        if not _nonempty(source.get("release_id")):
            errors.append(f"source {source_id}: release_id is required")

        review = source.get("review")
        if not isinstance(review, dict):
            errors.append(f"source {source_id}: review must be an object")
        else:
            for field in ("reviewer", "reviewed_on", "evidence_url"):
                if not _nonempty(review.get(field)):
                    errors.append(f"source {source_id}: source review {field} is required")

        artifact = source.get("artifact")
        if artifact is not None:
            if not isinstance(artifact, dict):
                errors.append(f"source {source_id}: artifact must be an object or null")
            else:
                if not _nonempty(artifact.get("path")):
                    errors.append(f"source {source_id}: artifact path is required")
                if not isinstance(artifact.get("sha256"), str) or not SHA256_RE.fullmatch(
                    artifact["sha256"]
                ):
                    errors.append(f"source {source_id}: artifact sha256 must be lowercase hex")

        items = source.get("items")
        if not isinstance(items, list):
            errors.append(f"source {source_id}: items must be an array")
            continue
        for item in items:
            if not isinstance(item, dict):
                errors.append(f"source {source_id}: item must be an object")
                continue
            item_id = item.get("item_id")
            if not _nonempty(item_id):
                errors.append(f"source {source_id}: item_id is required")
                item_id = "<missing>"
            if item_id in item_ids:
                errors.append(f"duplicate item_id: {item_id}")
            item_ids.add(item_id)
            materials = item.get("materials")
            if not isinstance(materials, dict) or not materials:
                errors.append(
                    f"source {source_id} item {item_id}: materials must be a non-empty object"
                )
                continue
            item_uses = uses
            if requested_item_ids is not None and item_id not in requested_item_ids:
                item_uses = set()
            for material_name in sorted(MATERIALS & materials.keys()):
                _validate_material(
                    errors,
                    source_id,
                    item_id,
                    material_name,
                    materials[material_name],
                    item_uses if material_name in material_scope else set(),
                )
            audio = materials.get("audio", [])
            if not isinstance(audio, list):
                errors.append(f"source {source_id} item {item_id} audio must be an array")
                continue
            audio_ids: set[str] = set()
            for recording in audio:
                if not isinstance(recording, dict):
                    errors.append(f"source {source_id} item {item_id} audio entry must be an object")
                    continue
                asset_id = recording.get("asset_id")
                if not _nonempty(asset_id):
                    errors.append(f"source {source_id} item {item_id} audio asset_id is required")
                    asset_id = "<missing>"
                if asset_id in audio_ids:
                    errors.append(
                        f"source {source_id} item {item_id}: duplicate audio asset_id {asset_id}"
                    )
                audio_ids.add(asset_id)
                _validate_material(
                    errors, source_id, item_id, f"audio {asset_id}", recording,
                    item_uses if "audio" in material_scope else set(),
                )
            for unknown_material in sorted(set(materials) - MATERIALS - {"audio"}):
                errors.append(f"source {source_id} item {item_id}: unsupported material {unknown_material}")
    if requested_item_ids is not None:
        for missing_item_id in sorted(requested_item_ids - item_ids):
            errors.append(f"requested item_id not found: {missing_item_id}")
    return errors


def attribution_lines(manifest: dict[str, Any], item_ids: list[str]) -> list[str]:
    """Render stable attribution lines for approved material in the requested items."""
    errors = validate_manifest(
        manifest,
        requested_uses={"redistribution"},
        requested_item_ids=set(item_ids),
    )
    if errors:
        raise ValueError("cannot render attribution for an unapproved manifest: " + "; ".join(errors))
    requested = set(item_ids)
    rows: list[tuple[str, str, str, str, str]] = []
    for source in manifest.get("sources", []):
        source_id = source.get("source_id", "")
        for item in source.get("items", []):
            if item.get("item_id") not in requested:
                continue
            materials = item.get("materials", {})
            for name in sorted(MATERIALS & materials.keys()):
                material = materials[name]
                if material.get("attribution_required") and material.get("attribution"):
                    rows.append(
                        (
                            source_id,
                            item["item_id"],
                            name,
                            material["attribution"],
                            material.get("license", ""),
                        )
                    )
            for recording in materials.get("audio", []):
                if recording.get("attribution_required") and recording.get("attribution"):
                    rows.append(
                        (
                            source_id,
                            item["item_id"],
                            recording["asset_id"],
                            recording["attribution"],
                            recording.get("license", ""),
                        )
                    )
    return [
        f"{attribution} — {item_id} [{material_id}] ({license_name})"
        for _, item_id, material_id, attribution, license_name in sorted(rows)
    ]


def verify_source_artifact(source: dict[str, Any], root: str | Path) -> str | None:
    """Check a pinned artifact's bytes; return a stable error or None."""
    artifact = source.get("artifact")
    if artifact is None:
        return None
    relative_path = Path(artifact["path"])
    if relative_path.is_absolute() or ".." in relative_path.parts:
        return "artifact path must stay within the manifest directory"
    root_path = Path(root).resolve()
    try:
        path = (root_path / relative_path).resolve(strict=True)
        path.relative_to(root_path)
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
    except ValueError:
        return "artifact path must stay within the manifest directory"
    except OSError:
        return "artifact file is missing or unreadable"
    if actual != artifact.get("sha256"):
        return "artifact checksum mismatch"
    return None
