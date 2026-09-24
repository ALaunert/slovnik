from copy import deepcopy
import hashlib
from pathlib import Path

import pytest

from app.source_manifest import (
    ManifestError,
    attribution_lines,
    load_manifest,
    validate_manifest,
    verify_source_artifact,
)


def approved_authored_manifest():
    return {
        "schema_version": 1,
        "sources": [
            {
                "source_id": "author-demo",
                "kind": "authored",
                "release_id": "agreement-2026-09",
                "artifact": None,
                "review": {
                    "reviewer": "editor@example.test",
                    "reviewed_on": "2026-09-24",
                    "evidence_url": "https://example.test/agreement",
                },
                "items": [
                    {
                        "item_id": "sentence-1",
                        "document_id": "lesson-1",
                        "materials": {
                            "text": {
                                "rights": {"analysis": "allowed", "redistribution": "allowed", "adaptation": "allowed"},
                                "license": "author agreement",
                                "attribution": "Slovnik editorial team",
                                "attribution_required": True,
                                "share_alike_required": False,
                                "evidence_url": "https://example.test/agreement",
                                "reviewer": "editor@example.test",
                                "reviewed_on": "2026-09-24",
                            }
                        },
                    }
                ],
            }
        ],
    }


def test_approved_authored_example_has_deterministic_attribution():
    manifest = approved_authored_manifest()
    validate_manifest(manifest)

    assert attribution_lines(manifest, ["sentence-1"]) == [
        "Slovnik editorial team — sentence-1 [text] (author agreement)"
    ]


def test_checked_in_source_manifest_is_valid():
    path = Path(__file__).parents[2] / "content" / "sources" / "manifest.json"
    assert validate_manifest(load_manifest(path)) == []


def test_unknown_text_rights_do_not_block_analysis_but_block_redistribution():
    manifest = approved_authored_manifest()
    material = manifest["sources"][0]["items"][0]["materials"]["text"]
    material["rights"]["redistribution"] = "unknown"
    material["rights"]["adaptation"] = "unknown"

    validate_manifest(manifest)
    assert validate_manifest(manifest, requested_uses={"analysis"}) == []
    assert "source author-demo item sentence-1 text: redistribution is unknown" in validate_manifest(
        manifest, requested_uses={"redistribution"}
    )
    with pytest.raises(ValueError, match="unapproved manifest"):
        attribution_lines(manifest, ["sentence-1"])


def test_text_only_permission_check_does_not_request_unused_audio_rights():
    manifest = approved_authored_manifest()
    audio = deepcopy(manifest["sources"][0]["items"][0]["materials"]["text"])
    audio["asset_id"] = "unused-recording"
    audio["rights"]["redistribution"] = "denied"
    manifest["sources"][0]["items"][0]["materials"]["audio"] = [audio]

    assert any("audio unused-recording: redistribution is denied" in error for error in
               validate_manifest(manifest, requested_uses={"redistribution"}))
    assert validate_manifest(
        manifest,
        requested_uses={"redistribution"},
        requested_item_ids={"sentence-1"},
        requested_materials={"text"},
    ) == []


def test_attribution_ignores_unrequested_analysis_only_item():
    manifest = approved_authored_manifest()
    unrelated = deepcopy(manifest["sources"][0]["items"][0])
    unrelated["item_id"] = "analysis-only"
    unrelated["materials"]["text"]["rights"]["redistribution"] = "unknown"
    manifest["sources"][0]["items"].append(unrelated)

    assert attribution_lines(manifest, ["sentence-1"]) == [
        "Slovnik editorial team — sentence-1 [text] (author agreement)"
    ]


def test_corpus_cc0_does_not_clear_underlying_web_text_rights():
    manifest = approved_authored_manifest()
    source = manifest["sources"][0]
    source.update(kind="corpus", release_id="corpus-1")
    material = source["items"][0]["materials"]["text"]
    material["license"] = "CC0 1.0 (corpus container)"
    material["rights"]["redistribution"] = "unknown"

    assert "source author-demo item sentence-1 text: redistribution is unknown" in validate_manifest(
        manifest, requested_uses={"redistribution"}
    )


def test_share_alike_adaptation_requires_attribution_and_share_alike_notice():
    manifest = approved_authored_manifest()
    material = manifest["sources"][0]["items"][0]["materials"]["text"]
    material.update(license="CC BY-SA 4.0", attribution_required=True, share_alike_required=True)
    material["rights"]["adaptation"] = "allowed"
    material["attribution"] = ""

    errors = validate_manifest(manifest, requested_uses={"adaptation"})
    assert any("attribution is required" in error for error in errors)
    assert any("share-alike" in error for error in errors)


def test_noncommercial_material_is_rejected_for_commercial_redistribution():
    manifest = approved_authored_manifest()
    material = manifest["sources"][0]["items"][0]["materials"]["text"]
    material["rights"]["redistribution"] = "denied"
    material["license"] = "CC BY-NC 4.0"

    assert "source author-demo item sentence-1 text: redistribution is denied" in validate_manifest(
        manifest, requested_uses={"redistribution"}
    )


def test_translation_and_audio_rights_are_independent():
    manifest = approved_authored_manifest()
    materials = manifest["sources"][0]["items"][0]["materials"]
    materials["translation"] = deepcopy(materials["text"])
    materials["translation"]["rights"]["redistribution"] = "unknown"
    materials["audio"] = [
        {
            "asset_id": "audio-1",
            **deepcopy(materials["text"]),
        }
    ]
    materials["audio"][0]["rights"]["redistribution"] = "denied"

    assert any("translation: redistribution is unknown" in e for e in validate_manifest(manifest, requested_uses={"redistribution"}))
    assert any("audio audio-1: redistribution is denied" in e for e in validate_manifest(manifest, requested_uses={"redistribution"}))


def test_missing_license_or_review_evidence_is_rejected():
    manifest = approved_authored_manifest()
    material = manifest["sources"][0]["items"][0]["materials"]["text"]
    material["license"] = ""
    material["evidence_url"] = ""
    material["reviewer"] = ""
    material["reviewed_on"] = ""

    errors = validate_manifest(manifest)
    assert any("license is required" in error for error in errors)
    assert any("evidence_url is required" in error for error in errors)
    assert any("reviewer is required" in error for error in errors)


def test_changed_release_artifact_checksum_is_detected(tmp_path):
    manifest = approved_authored_manifest()
    artifact = tmp_path / "source.txt"
    artifact.write_text("original", encoding="utf-8")
    manifest["sources"][0]["artifact"] = {
        "path": "source.txt",
        "sha256": hashlib.sha256(b"original").hexdigest(),
    }
    validate_manifest(manifest)
    assert verify_source_artifact(manifest["sources"][0], tmp_path) is None
    artifact.write_text("changed", encoding="utf-8")
    assert "checksum mismatch" in verify_source_artifact(manifest["sources"][0], tmp_path)


def test_source_artifact_symlink_cannot_escape_manifest_root(tmp_path):
    root = tmp_path / "manifest-root"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("payload", encoding="utf-8")
    (root / "linked.txt").symlink_to(outside)
    source = {"artifact": {"path": "linked.txt", "sha256": hashlib.sha256(b"payload").hexdigest()}}

    assert verify_source_artifact(source, root) == "artifact path must stay within the manifest directory"


def test_duplicate_ids_and_missing_reviewer_are_rejected():
    manifest = approved_authored_manifest()
    manifest["sources"].append(deepcopy(manifest["sources"][0]))
    errors = validate_manifest(manifest)
    assert any("duplicate source_id" in error for error in errors)

    manifest = approved_authored_manifest()
    manifest["sources"][0]["review"]["reviewer"] = ""
    assert any("source review reviewer is required" in error for error in validate_manifest(manifest))


def test_manifest_loader_rejects_invalid_json(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text("{", encoding="utf-8")
    with pytest.raises(ManifestError):
        load_manifest(path)
