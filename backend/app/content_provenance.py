"""File-backed, unpublished source-rights contract for the proposed pilot."""

from __future__ import annotations

from typing import Any


def validate_source_manifest(
    manifest: dict[str, Any], *, use: str, media: tuple[str, ...]
) -> list[str]:
    """Return actionable reasons a requested use is not recorded as permitted."""
    errors: list[str] = []
    if manifest.get("schema_version") != 1 or not isinstance(manifest.get("sources"), list):
        return ["unsupported source manifest"]
    ids: set[str] = set()
    for source in manifest["sources"]:
        source_id = source.get("id")
        if not source_id or source_id in ids or not source.get("item_id"):
            errors.append(f"{source_id}: missing or duplicate source/item ID")
        ids.add(source_id)
        if source.get("pinned_release", source.get("release")) != source.get("release"):
            errors.append(f"{source_id}: release changed")
        if source.get("pinned_checksum", source.get("checksum")) != source.get("checksum"):
            errors.append(f"{source_id}: checksum changed")
        if source.get("source_type") != "authored" and (
            not source.get("release") or not source.get("checksum")
        ):
            errors.append(f"{source_id}: external release/checksum missing")
        for medium in media:
            if medium not in {"text", "translation", "audio"}:
                errors.append(f"{source_id}: unsupported medium {medium}")
                continue
            right = source.get("rights", {}).get(medium, {})
            if use == "analysis":
                if "analysis" not in right.get("uses", []):
                    errors.append(f"{source_id}/{medium}: analysis not recorded")
                continue
            if right.get("status") != "approved" or use not in right.get("uses", []):
                errors.append(f"{source_id}/{medium}: permission unknown or use not approved")
                continue
            if not all(right.get(field) for field in ("license", "evidence", "reviewer", "reviewed_at")):
                errors.append(f"{source_id}/{medium}: license, evidence or review missing")
            if not source.get("attribution"):
                errors.append(f"{source_id}/{medium}: attribution missing")
            if source.get("source_type") == "authored" and not str(right.get("evidence", "")).startswith("agreement:"):
                errors.append(f"{source_id}/{medium}: author agreement missing")
            license_name = str(right.get("license", "")).upper()
            if "-NC" in license_name:
                errors.append(f"{source_id}/{medium}: NC use excluded from publication")
            if "BY-SA" in license_name and right.get("adapted") and not right.get("share_alike"):
                errors.append(f"{source_id}/{medium}: adapted BY-SA needs share-alike")
    return errors


def attribution_lines(
    manifest: dict[str, Any], *, use: str, media: tuple[str, ...]
) -> list[str]:
    errors = validate_source_manifest(manifest, use=use, media=media)
    if errors:
        raise ValueError("; ".join(errors))
    return sorted({source["attribution"] for source in manifest["sources"]})
