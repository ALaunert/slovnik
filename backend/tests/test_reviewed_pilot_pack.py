"""Reviewed file pack to transactional catalog/curriculum adapter."""

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid5

import pytest

from app.domain.curriculum import CurriculumStatus
from app.services.content_publication_service import ContentPublicationService
from app.services.reviewed_pilot_pack import PILOT_PACK_NAMESPACE, load_reviewed_pilot_bundle


ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / "content/curricula/a1-pilot/publication-v1.json"
NOW = datetime(2026, 9, 30, 12, tzinfo=timezone.utc)


def test_reviewed_pilot_pack_preflights_and_publishes_idempotently_in_disposable_db(db_session) -> None:
    bundle = load_reviewed_pilot_bundle(PACK)
    report = ContentPublicationService(db_session).preflight(bundle, published_at=NOW)
    assert report.rejected == ()
    assert len(report.changed_ids) == 5
    assert len(bundle.curriculum.nodes) == 4
    assert len(bundle.examples["examples"]) == 8
    assert all(len(construction.examples) == 1 for construction in bundle.constructions)
    assert all(item["role"] == "practice" for construction in bundle.constructions
               for example in construction.examples
               for item in bundle.examples["examples"] if item["text"] == example.serbian_text)

    published = ContentPublicationService(db_session).publish(bundle, published_at=NOW)
    assert published.status is CurriculumStatus.ACTIVE
    assert ContentPublicationService(db_session).publish(bundle, published_at=NOW).id == published.id


def test_reviewed_pack_rejects_stale_pin_before_any_database_write(tmp_path, db_session) -> None:
    import json
    manifest = json.loads(PACK.read_text(encoding="utf-8"))
    manifest["bank_digest"] = "0" * 64
    corrupt = tmp_path / "publication-v1.json"
    corrupt.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="bank digest"):
        load_reviewed_pilot_bundle(corrupt, content_root=ROOT / "content")
    assert ContentPublicationService(db_session).active("slovnik-written-a1") is None


def test_reviewed_pack_uses_only_practice_examples_in_catalog() -> None:
    bundle = load_reviewed_pilot_bundle(PACK)
    heldout_texts = {item["text"] for item in bundle.examples["examples"]
                     if item["role"] == "assessment"}
    assert all(example.serbian_text not in heldout_texts
               for construction in bundle.constructions for example in construction.examples)


def _revision_manifest(tmp_path: Path, version: int, *, corrected_catalog: bool = False) -> Path:
    import json
    manifest = json.loads(PACK.read_text(encoding="utf-8"))
    manifest["version_number"] = version
    manifest["version_id"] = str(uuid5(
        PILOT_PACK_NAMESPACE, f"version:{manifest['curriculum_code']}:{version}"
    ))
    manifest["created_at"] = f"2026-10-0{version}T12:00:00+00:00"
    for row in manifest["targets"]:
        row["node_id"] = str(uuid5(
            PILOT_PACK_NAMESPACE, f"node:{manifest['version_id']}:{row['outcome_code']}"
        ))
    if corrected_catalog:
        row = manifest["targets"][0]
        row["catalog_revision"] = 2
        row["catalog_id"] = str(uuid5(
            PILOT_PACK_NAMESPACE, f"target:{row['editorial_target_ref']}:2"
        ))
        row["catalog_code"] = f"{row['catalog_key']}-r2"
        row["description"] += " Проверенный уточнённый шаблон."
    path = tmp_path / f"publication-v{version}.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False))
    return path


def test_reviewed_pack_new_revision_and_restore_use_fresh_nodes_and_catalog_ids(
    tmp_path, db_session,
) -> None:
    from app.repositories.curriculum import CurriculumRepository

    service = ContentPublicationService(db_session)
    first = load_reviewed_pilot_bundle(PACK)
    service.publish(first, published_at=NOW)
    second = load_reviewed_pilot_bundle(
        _revision_manifest(tmp_path, 2, corrected_catalog=True), content_root=ROOT / "content"
    )
    report = service.preflight(second, published_at=datetime(2026, 10, 2, 12, tzinfo=timezone.utc))
    assert report.rejected == ()
    assert len(report.changed_ids) == 2  # one new catalog ID and one version ID
    service.publish(second, published_at=datetime(2026, 10, 2, 12, tzinfo=timezone.utc))
    assert service.active("slovnik-written-a1").id == second.curriculum.id
    assert CurriculumRepository(db_session, service.target_resolver).get(first.curriculum.id).status is CurriculumStatus.RETIRED

    restored = load_reviewed_pilot_bundle(
        _revision_manifest(tmp_path, 3), content_root=ROOT / "content"
    )
    assert service.preflight(restored, published_at=datetime(2026, 10, 3, 12, tzinfo=timezone.utc)).rejected == ()
    service.publish(restored, published_at=datetime(2026, 10, 3, 12, tzinfo=timezone.utc))
    assert service.active("slovnik-written-a1").id == restored.curriculum.id
    assert CurriculumRepository(db_session, service.target_resolver).get(second.curriculum.id).status is CurriculumStatus.RETIRED
