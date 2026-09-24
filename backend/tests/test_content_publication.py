"""Transaction and preflight checks for catalog/curriculum publication composition."""

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base
from app.domain.catalog import (
    Construction, ContentStatus, EntryKind, Form, FormKind, Gloss, LexicalUnit,
    OrthographicForm, RetirementPolicyDecision, Script, Sense, UsageExample,
)
from app.domain.curriculum import CurriculumNode, CurriculumStatus, CurriculumVersion
from app.domain.curriculum import PrerequisiteEdge, PrerequisiteKind
from app.domain.shared import Capability, Modality, TargetKind
from app.domain.target import TargetSpec
from app.models import VocabularyItem
from app.repositories.catalog import CatalogRepository
from app.repositories.curriculum import CurriculumRepository
from app.domain_models.curriculum import CurriculumVersionRecord
from app.domain_models.catalog import LanguageForm
from app.services.content_publication_service import (
    ContentPublicationService,
    PublicationPreflightError,
    PublicationRequest,
)
from app.services.catalog_mapping_service import vocabulary_source_fingerprint
from app.services.curriculum_service import CurriculumService


NOW = datetime(2026, 9, 24, 12, tzinfo=timezone.utc)


@pytest.fixture()
def engine():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


def source_manifest(decision="allowed"):
    material = {
        "rights": {"analysis": "allowed", "redistribution": decision, "adaptation": decision},
        "license": "fictional test agreement", "evidence_url": "https://example.test/fictional",
        "reviewer": "test-only", "reviewed_on": "2026-09-24",
        "attribution_required": False, "share_alike_required": False,
    }
    return {"schema_version": 1, "sources": [{
        "source_id": "test-author", "kind": "authored", "release_id": "test-only",
        "review": {"reviewer": "test-only", "reviewed_on": "2026-09-24",
                   "evidence_url": "https://example.test/fictional"},
        "items": [{"item_id": "example-1", "materials": {
            "text": material, "translation": dict(material),
        }}],
    }]}


def draft_pair(version_number=1, code="test-pack"):
    construction_id = str(uuid4())
    version_id = str(uuid4())
    construction = Construction(
        id=construction_id, code=f"test-{construction_id}", title="Test construction",
        description="A synthetic construction", examples=(UsageExample("Здраво.", "Привет."),),
    )
    target = TargetSpec(TargetKind.CONSTRUCTION, construction_id,
                        Capability.APPLY_CONSTRUCTION, Modality.WRITTEN)
    curriculum = CurriculumVersion(
        id=version_id, curriculum_code=code, version_number=version_number,
        created_at=NOW - timedelta(days=1),
        nodes=(CurriculumNode(id=str(uuid4()), curriculum_version_id=version_id,
                              target=target, priority=50, outcome_code="A1.test"),),
    )
    return construction, curriculum


def request(construction, curriculum, sources=None):
    return PublicationRequest(
        curriculum_version_id=curriculum.id,
        construction_ids=(construction.id,),
        source_item_ids_by_catalog_id={construction.id: ("example-1",)},
        source_manifest=sources or source_manifest(),
    )


def stage(session, construction, curriculum):
    catalog = CatalogRepository(session)
    catalog.add_construction(construction)
    CurriculumRepository(session, catalog).add(curriculum)
    session.commit()


def test_catalog_and_curriculum_publish_together(engine):
    construction, curriculum = draft_pair()
    with Session(engine) as session:
        stage(session, construction, curriculum)
        result = ContentPublicationService(session).publish(
            request(construction, curriculum), published_at=NOW)
        assert result.changed_ids == (construction.id, curriculum.id)
    with Session(engine) as session:
        assert CatalogRepository(session).get_construction(construction.id).status is ContentStatus.PUBLISHED
        assert CurriculumRepository(session, CatalogRepository(session)).get(curriculum.id).status is CurriculumStatus.ACTIVE


def test_repeat_publication_is_idempotent(engine):
    construction, curriculum = draft_pair()
    with Session(engine) as session:
        stage(session, construction, curriculum)
        publisher = ContentPublicationService(session)
        publisher.publish(request(construction, curriculum), published_at=NOW)
        repeat = publisher.publish(request(construction, curriculum), published_at=NOW + timedelta(hours=1))
        assert repeat.changed_ids == ()
        assert CatalogRepository(session).get_construction(construction.id).revision == 2
        assert CurriculumRepository(session, CatalogRepository(session)).get(curriculum.id).published_at == NOW


def test_active_repeat_rejects_different_published_catalog_ids(engine):
    construction, curriculum = draft_pair()
    unrelated, unrelated_curriculum = draft_pair(code="other-pack")
    with Session(engine) as session:
        stage(session, construction, curriculum)
        stage(session, unrelated, unrelated_curriculum)
        publisher = ContentPublicationService(session)
        publisher.publish(request(construction, curriculum), published_at=NOW)
        publisher.publish(request(unrelated, unrelated_curriculum), published_at=NOW)
        wrong = PublicationRequest(
            curriculum_version_id=curriculum.id, construction_ids=(unrelated.id,),
            source_item_ids_by_catalog_id={unrelated.id: ("example-1",)},
            source_manifest=source_manifest(),
        )
        with pytest.raises(PublicationPreflightError, match="unrelated catalog id"):
            publisher.publish(wrong, published_at=NOW + timedelta(hours=1))
        assert CurriculumRepository(session, CatalogRepository(session)).get(curriculum.id).published_at == NOW


def test_unresolved_rights_preflight_changes_nothing(engine):
    construction, curriculum = draft_pair()
    with Session(engine) as session:
        stage(session, construction, curriculum)
        with pytest.raises(PublicationPreflightError, match="redistribution"):
            ContentPublicationService(session).publish(
                request(construction, curriculum, source_manifest("unknown")), published_at=NOW)
    with Session(engine) as session:
        assert CatalogRepository(session).get_construction(construction.id).status is ContentStatus.DRAFT
        assert CurriculumRepository(session, CatalogRepository(session)).get(curriculum.id).status is CurriculumStatus.DRAFT


def test_replacement_using_published_target_still_requires_source_rights(engine):
    construction, first = draft_pair()
    replacement_id = str(uuid4())
    replacement = CurriculumVersion(
        id=replacement_id, curriculum_code=first.curriculum_code, version_number=2,
        created_at=first.created_at,
        nodes=(CurriculumNode(id=str(uuid4()), curriculum_version_id=replacement_id,
                              target=first.nodes[0].target, priority=50, outcome_code="A1.test"),),
    )
    with Session(engine) as session:
        stage(session, construction, first)
        ContentPublicationService(session).publish(request(construction, first), published_at=NOW)
        CurriculumRepository(session, CatalogRepository(session)).add(replacement)
        session.commit()
        packet = PublicationRequest(
            curriculum_version_id=replacement.id, source_manifest={"schema_version": 1, "sources": []},
            source_item_ids_by_catalog_id={},
        )
        with pytest.raises(PublicationPreflightError, match="source item missing"):
            ContentPublicationService(session).publish(packet, published_at=NOW + timedelta(hours=1))
        assert CurriculumRepository(session, CatalogRepository(session)).get(first.id).status is CurriculumStatus.ACTIVE
        denied = PublicationRequest(
            curriculum_version_id=replacement.id, source_manifest=source_manifest("denied"),
            source_item_ids_by_catalog_id={construction.id: ("example-1",)},
        )
        with pytest.raises(PublicationPreflightError, match="redistribution is denied"):
            ContentPublicationService(session).publish(denied, published_at=NOW + timedelta(hours=1))
        approved = PublicationRequest(
            curriculum_version_id=replacement.id, source_manifest=source_manifest(),
            source_item_ids_by_catalog_id={construction.id: ("example-1",)},
        )
        ContentPublicationService(session).publish(approved, published_at=NOW + timedelta(hours=1))
        assert CurriculumRepository(session, CatalogRepository(session)).get(replacement.id).status is CurriculumStatus.ACTIVE


def test_unrelated_catalog_id_cannot_be_published_with_a_draft(engine):
    referenced, curriculum = draft_pair()
    unrelated, _ = draft_pair()
    with Session(engine) as session:
        stage(session, referenced, curriculum)
        CatalogRepository(session).add_construction(unrelated)
        session.commit()
        packet = PublicationRequest(
            curriculum_version_id=curriculum.id, construction_ids=(referenced.id, unrelated.id),
            source_item_ids_by_catalog_id={referenced.id: ("example-1",), unrelated.id: ("example-1",)},
            source_manifest=source_manifest(),
        )
        with pytest.raises(PublicationPreflightError, match="unrelated catalog id"):
            ContentPublicationService(session).publish(packet, published_at=NOW)
        assert CatalogRepository(session).get_construction(unrelated.id).status is ContentStatus.DRAFT


def test_unused_audio_rights_do_not_block_written_publication(engine):
    construction, curriculum = draft_pair()
    sources = source_manifest()
    audio = dict(sources["sources"][0]["items"][0]["materials"]["text"])
    audio["asset_id"] = "unused-audio"
    audio["rights"] = {"analysis": "allowed", "redistribution": "denied", "adaptation": "denied"}
    sources["sources"][0]["items"][0]["materials"]["audio"] = [audio]
    with Session(engine) as session:
        stage(session, construction, curriculum)
        ContentPublicationService(session).publish(
            request(construction, curriculum, sources), published_at=NOW)
        assert CatalogRepository(session).get_construction(construction.id).status is ContentStatus.PUBLISHED


def test_failure_after_catalog_write_rolls_everything_back(engine, monkeypatch):
    first_construction, first_curriculum = draft_pair()
    second_construction, second_curriculum = draft_pair(2)
    with Session(engine) as session:
        stage(session, first_construction, first_curriculum)
        ContentPublicationService(session).publish(request(first_construction, first_curriculum), published_at=NOW)
        stage(session, second_construction, second_curriculum)

        def fail_activation(*args, **kwargs):
            assert CatalogRepository(session).get_construction(second_construction.id).status is ContentStatus.PUBLISHED
            raise RuntimeError("injected activation failure")

        monkeypatch.setattr(CurriculumService, "publish_in_transaction", fail_activation)
        with pytest.raises(RuntimeError, match="injected activation failure"):
            ContentPublicationService(session).publish(
                request(second_construction, second_curriculum), published_at=NOW + timedelta(hours=1))
    with Session(engine) as session:
        catalog = CatalogRepository(session)
        repository = CurriculumRepository(session, catalog)
        assert catalog.get_construction(second_construction.id).status is ContentStatus.DRAFT
        assert repository.get(first_curriculum.id).status is CurriculumStatus.ACTIVE
        assert repository.get(second_curriculum.id).status is CurriculumStatus.DRAFT


def test_activation_failure_after_retirement_rolls_back_catalog_and_active(engine, monkeypatch):
    first_construction, first_curriculum = draft_pair()
    second_construction, second_curriculum = draft_pair(2)
    with Session(engine) as session:
        stage(session, first_construction, first_curriculum)
        ContentPublicationService(session).publish(request(first_construction, first_curriculum), published_at=NOW)
        stage(session, second_construction, second_curriculum)

        def fail_after_retirement(repository, version_id, published_at):
            del repository, version_id, published_at
            catalog = CatalogRepository(session)
            versions = CurriculumRepository(session, catalog)
            assert catalog.get_construction(second_construction.id).status is ContentStatus.PUBLISHED
            assert versions.get(first_curriculum.id).status is CurriculumStatus.RETIRED
            raise RuntimeError("activation failed after retirement")

        monkeypatch.setattr(CurriculumRepository, "activate_if_draft", fail_after_retirement)
        with pytest.raises(RuntimeError, match="activation failed after retirement"):
            ContentPublicationService(session).publish(
                request(second_construction, second_curriculum), published_at=NOW + timedelta(hours=1))
    with Session(engine) as session:
        catalog = CatalogRepository(session)
        versions = CurriculumRepository(session, catalog)
        assert catalog.get_construction(second_construction.id).status is ContentStatus.DRAFT
        assert versions.get(first_curriculum.id).status is CurriculumStatus.ACTIVE
        assert versions.get(second_curriculum.id).status is CurriculumStatus.DRAFT


def test_hard_edge_cycle_preflight_rejects_before_catalog_write(engine):
    first, curriculum = draft_pair()
    second, _ = draft_pair()
    second_target = TargetSpec(TargetKind.CONSTRUCTION, second.id,
                               Capability.APPLY_CONSTRUCTION, Modality.WRITTEN)
    first_node = curriculum.nodes[0]
    second_node = CurriculumNode(id=str(uuid4()), curriculum_version_id=curriculum.id,
                                 target=second_target, priority=50, outcome_code="A1.test")
    cycle = CurriculumVersion(
        id=curriculum.id, curriculum_code=curriculum.curriculum_code,
        version_number=curriculum.version_number, created_at=curriculum.created_at,
        nodes=(first_node, second_node), prerequisites=(
            PrerequisiteEdge(str(uuid4()), curriculum.id, first_node.id,
                             second_node.id, PrerequisiteKind.HARD),
            PrerequisiteEdge(str(uuid4()), curriculum.id, second_node.id,
                             first_node.id, PrerequisiteKind.HARD),
        ),
    )
    with Session(engine) as session:
        catalog = CatalogRepository(session)
        catalog.add_construction(first)
        catalog.add_construction(second)
        CurriculumRepository(session, catalog).add(cycle)
        session.commit()
        packet = PublicationRequest(
            curriculum_version_id=cycle.id, construction_ids=(first.id, second.id),
            source_item_ids_by_catalog_id={first.id: ("example-1",), second.id: ("example-1",)},
            source_manifest=source_manifest(),
        )
        with pytest.raises(PublicationPreflightError, match="acyclic"):
            ContentPublicationService(session).publish(packet, published_at=NOW)
        assert catalog.get_construction(first.id).status is ContentStatus.DRAFT
        assert catalog.get_construction(second.id).status is ContentStatus.DRAFT


def test_retired_catalog_content_cannot_be_revived(engine):
    construction, curriculum = draft_pair()
    retired = construction.publish().retire(policy_decision=RetirementPolicyDecision.ALLOWED)
    with Session(engine) as session:
        catalog = CatalogRepository(session)
        catalog.add_construction(retired)
        CurriculumRepository(session, catalog).add(curriculum)
        session.commit()
        with pytest.raises(PublicationPreflightError, match="only draft content"):
            ContentPublicationService(session).publish(request(construction, curriculum), published_at=NOW)
        assert catalog.get_construction(construction.id).status is ContentStatus.RETIRED


def test_stale_legacy_fingerprint_blocks_lexical_publication(engine):
    unit_id, sense_id, form_id, version_id = (str(uuid4()) for _ in range(4))
    word = VocabularyItem(
        serbian_cyrillic="вода", serbian_latin="voda", russian_translation="вода",
        cefr_level="A1", theme="daily-life",
    )
    with Session(engine) as session:
        session.add(word)
        session.flush()
        unit = LexicalUnit(
            id=unit_id, kind=EntryKind.WORD, legacy_vocabulary_item_id=word.id,
            senses=(Sense(sense_id, unit_id, (Gloss("ru", "вода"),)),),
            forms=(Form(form_id, unit_id, FormKind.CITATION,
                        (OrthographicForm(Script.CYRILLIC, "вода"),
                         OrthographicForm(Script.LATIN, "voda"))),),
        )
        target = TargetSpec(TargetKind.SENSE, sense_id, Capability.RECOGNIZE_MEANING,
                            Modality.WRITTEN)
        draft = CurriculumVersion(
            id=version_id, curriculum_code="lexical-test", version_number=1,
            created_at=NOW - timedelta(days=1),
            nodes=(CurriculumNode(id=str(uuid4()), curriculum_version_id=version_id,
                                  target=target, priority=50, outcome_code="A1.test"),),
        )
        catalog = CatalogRepository(session)
        catalog.add(unit)
        CurriculumRepository(session, catalog).add(draft)
        session.commit()
        packet = PublicationRequest(
            curriculum_version_id=version_id, lexical_unit_ids=(unit_id,),
            source_item_ids_by_catalog_id={unit_id: ("example-1",)},
            source_manifest=source_manifest(), expected_legacy_fingerprints={word.id: "stale"},
        )
        with pytest.raises(PublicationPreflightError, match="stale legacy mapping"):
            ContentPublicationService(session).publish(packet, published_at=NOW)
        assert catalog.get(unit_id).status is ContentStatus.DRAFT
        approved_packet = PublicationRequest(
            curriculum_version_id=version_id, lexical_unit_ids=(unit_id,),
            source_item_ids_by_catalog_id={unit_id: ("example-1",)},
            source_manifest=source_manifest(),
            expected_legacy_fingerprints={word.id: vocabulary_source_fingerprint(word)},
        )
        with pytest.raises(PublicationPreflightError, match="stale legacy mapping"):
            ContentPublicationService(session).publish(approved_packet, published_at=NOW)
        session.execute(update(LanguageForm).where(LanguageForm.id == form_id).values(
            morph_features={"bootstrap": {"source_fingerprint": vocabulary_source_fingerprint(word)}}
        ))
        session.commit()
        ContentPublicationService(session).publish(approved_packet, published_at=NOW)
        published_unit = catalog.get(unit_id)
        assert published_unit.status is ContentStatus.PUBLISHED
        assert published_unit.senses[0].status is ContentStatus.PUBLISHED
        assert published_unit.forms[0].status is ContentStatus.PUBLISHED
        assert CurriculumRepository(session, catalog).get(version_id).status is CurriculumStatus.ACTIVE
        replacement_id = str(uuid4())
        replacement = CurriculumVersion(
            id=replacement_id, curriculum_code="lexical-test", version_number=2,
            created_at=NOW - timedelta(days=1),
            nodes=(CurriculumNode(id=str(uuid4()), curriculum_version_id=replacement_id,
                                  target=target, priority=50, outcome_code="A1.test"),),
        )
        CurriculumRepository(session, catalog).add(replacement)
        word.russian_translation = "вода (изменено)"
        session.commit()
        existing_packet = PublicationRequest(
            curriculum_version_id=replacement_id,
            source_item_ids_by_catalog_id={unit_id: ("example-1",)},
            source_manifest=source_manifest(),
            expected_legacy_fingerprints={word.id: vocabulary_source_fingerprint(word)},
        )
        with pytest.raises(PublicationPreflightError, match="stale legacy mapping"):
            ContentPublicationService(session).publish(existing_packet, published_at=NOW + timedelta(hours=1))
        assert CurriculumRepository(session, catalog).get(version_id).status is CurriculumStatus.ACTIVE


@pytest.fixture()
def postgresql_publication_engine():
    admin_url_value = os.getenv("SLOVNIK_TEST_POSTGRES_ADMIN_URL")
    if not admin_url_value:
        pytest.skip("SLOVNIK_TEST_POSTGRES_ADMIN_URL is not configured")
    admin_url = make_url(admin_url_value)
    if admin_url.get_backend_name() != "postgresql":
        raise ValueError("SLOVNIK_TEST_POSTGRES_ADMIN_URL must use PostgreSQL")
    database_name = f"slovnik_publication_test_{uuid4().hex}"
    test_url = admin_url.set(database=database_name)
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    test_engine = None
    created = False
    try:
        with admin_engine.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{database_name}"'))
        created = True
        test_engine = create_engine(test_url)
        Base.metadata.create_all(test_engine)
        yield test_engine
    finally:
        if test_engine is not None:
            test_engine.dispose()
        if created:
            with admin_engine.connect() as connection:
                connection.execute(text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :name AND pid <> pg_backend_pid()"
                ), {"name": database_name})
                connection.execute(text(f'DROP DATABASE "{database_name}"'))
        admin_engine.dispose()


def test_postgresql_concurrent_publish_has_one_commit_and_retry_is_idempotent(
    postgresql_publication_engine, monkeypatch,
):
    construction, curriculum = draft_pair()
    packet = request(construction, curriculum)
    SessionFactory = sessionmaker(bind=postgresql_publication_engine)
    with SessionFactory() as session:
        stage(session, construction, curriculum)

    barrier = threading.Barrier(2)
    original_preflight = ContentPublicationService.preflight

    def synchronized_preflight(publisher, request, *, published_at):
        result = original_preflight(publisher, request, published_at=published_at)
        barrier.wait(timeout=10)
        return result

    monkeypatch.setattr(ContentPublicationService, "preflight", synchronized_preflight)

    def attempt():
        with SessionFactory() as session:
            try:
                ContentPublicationService(session).publish(packet, published_at=NOW)
            except ValueError:
                return "conflict"
            return "published"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = [future.result(timeout=30) for future in (pool.submit(attempt), pool.submit(attempt))]
    monkeypatch.setattr(ContentPublicationService, "preflight", original_preflight)
    assert sorted(outcomes) == ["conflict", "published"]

    with SessionFactory() as session:
        active_ids = session.scalars(select(CurriculumVersionRecord.id).where(
            CurriculumVersionRecord.status == CurriculumStatus.ACTIVE.value
        )).all()
        assert active_ids == [curriculum.id]
        assert CatalogRepository(session).get_construction(construction.id).revision == 2
        assert ContentPublicationService(session).publish(packet, published_at=NOW).changed_ids == ()


def test_child_revision_change_during_lexical_publish_fails_closed(engine, monkeypatch):
    unit_id, sense_id, form_id = (str(uuid4()) for _ in range(3))
    unit = LexicalUnit(
        id=unit_id, kind=EntryKind.WORD,
        senses=(Sense(sense_id, unit_id, (Gloss("ru", "вода"),)),),
        forms=(Form(form_id, unit_id, FormKind.CITATION,
                    (OrthographicForm(Script.CYRILLIC, "вода"),
                     OrthographicForm(Script.LATIN, "voda"))),),
    )
    with Session(engine) as session:
        catalog = CatalogRepository(session)
        catalog.add(unit)
        session.commit()
        original_get = catalog.get

        def concurrent_child_change(item_id):
            stale = original_get(item_id)
            session.execute(update(LanguageForm).where(LanguageForm.id == form_id).values(revision=2))
            return stale

        monkeypatch.setattr(catalog, "get", concurrent_child_change)
        with pytest.raises(ValueError, match="form changed before publication"):
            catalog.publish_lexical_unit_if_draft(unit_id)
        session.rollback()
    with Session(engine) as session:
        assert CatalogRepository(session).get(unit_id).status is ContentStatus.DRAFT
