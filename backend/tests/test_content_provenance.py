"""Source rights are specific to both medium and intended use."""

from copy import deepcopy

import pytest

from app.content_provenance import attribution_lines, validate_source_manifest


@pytest.fixture
def authored() -> dict:
    permission = {"status": "approved", "uses": ["analysis", "pilot_display"],
                  "license": "author permission", "evidence": "agreement:synthetic-001",
                  "reviewer": "fixture reviewer", "reviewed_at": "2026-09-25"}
    return {"schema_version": 1, "sources": [{
        "id": "own-fixture", "source_type": "authored", "item_id": "sentence-1",
        "author": "Fixture author", "release": None, "checksum": None,
        "source_url": None, "attribution": "Fixture author; synthetic agreement",
        "rights": {"text": deepcopy(permission), "translation": deepcopy(permission),
                   "audio": {"status": "unknown", "uses": []}},
    }]}


def test_approved_authored_text_and_translation_have_stable_attribution(authored: dict) -> None:
    assert validate_source_manifest(authored, use="pilot_display", media=("text", "translation")) == []
    assert attribution_lines(authored, use="pilot_display", media=("text", "translation")) == [
        "Fixture author; synthetic agreement"
    ]


def test_unknown_web_text_blocks_publication_not_analysis(authored: dict) -> None:
    source = authored["sources"][0]
    source["source_type"] = "web_corpus"
    source["release"] = "2.0"
    source["checksum"] = "sha256:abc"
    source["rights"]["text"] = {"status": "unknown", "uses": ["analysis"]}
    assert validate_source_manifest(authored, use="pilot_display", media=("text",))
    assert validate_source_manifest(authored, use="analysis", media=("text",)) == []


def test_translation_rights_are_independent_of_text(authored: dict) -> None:
    authored["sources"][0]["rights"]["translation"]["status"] = "unknown"
    assert validate_source_manifest(authored, use="pilot_display", media=("translation",))
    assert validate_source_manifest(authored, use="pilot_display", media=("text",)) == []


def test_by_sa_adaptation_requires_attribution_and_share_alike(authored: dict) -> None:
    source = authored["sources"][0]
    source["rights"]["text"].update(license="CC BY-SA 4.0", adapted=True, share_alike=False)
    assert validate_source_manifest(authored, use="pilot_display", media=("text",))
    source["rights"]["text"]["share_alike"] = True
    assert validate_source_manifest(authored, use="pilot_display", media=("text",)) == []


def test_nc_or_missing_review_blocks_publication(authored: dict) -> None:
    permission = authored["sources"][0]["rights"]["text"]
    permission["license"] = "CC BY-NC 4.0"
    assert validate_source_manifest(authored, use="pilot_display", media=("text",))
    permission["license"] = "author permission"
    permission.pop("reviewer")
    assert validate_source_manifest(authored, use="pilot_display", media=("text",))


def test_changed_release_or_checksum_fails_pin(authored: dict) -> None:
    source = authored["sources"][0]
    source.update(source_type="corpus", release="1.3", checksum="sha256:old",
                  pinned_release="1.3", pinned_checksum="sha256:old")
    assert validate_source_manifest(authored, use="pilot_display", media=("text",)) == []
    source["checksum"] = "sha256:new"
    assert validate_source_manifest(authored, use="pilot_display", media=("text",))


def test_authored_permission_needs_agreement(authored: dict) -> None:
    authored["sources"][0]["rights"]["text"]["evidence"] = ""
    assert validate_source_manifest(authored, use="pilot_display", media=("text",))
