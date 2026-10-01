"""Atomic pilot publication uses synthetic approved material only."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.domain.catalog import Construction, ContentStatus, UsageExample
from app.domain.curriculum import (
    CurriculumNode,
    CurriculumStatus,
    CurriculumVersion,
    PrerequisiteEdge,
    PrerequisiteKind,
)
from app.domain.shared import Capability, Modality, TargetKind
from app.domain.target import TargetSpec
from app.domain_models.catalog import LanguageConstruction
from app.db import Base
from app.models import VocabularyItem
from app.repositories.catalog import CatalogRepository
from app.repositories.curriculum import CurriculumRepository
from app.services.content_publication_service import (
    ContentPublicationService,
    PublicationBundle,
    PublicationPreflightError,
)
from app.services.domain_bootstrap_service import _aggregate, bootstrap_catalog


NOW = datetime(2026, 9, 25, 12, tzinfo=timezone.utc)
CONSTRUCTION_ID = "40000000-0000-4000-8000-000000000001"
VERSION_ID = "50000000-0000-4000-8000-000000000001"
NODE_ID = "60000000-0000-4000-8000-000000000001"


def _bundle(
    *, version_number: int = 1, version_id: str = VERSION_ID,
    construction_id: str = CONSTRUCTION_ID,
) -> PublicationBundle:
    construction = Construction(
        id=construction_id,
        code=f"synthetic-request-{construction_id[-1]}",
        title="Synthetic request",
        description="Test-only constructed content",
        examples=(UsageExample(serbian_text="Molim vodu.", translation="Воду, пожалуйста."),),
        status=ContentStatus.PUBLISHED,
        revision=2,
    )
    target = TargetSpec(
        target_kind=TargetKind.CONSTRUCTION,
        target_id=construction.id,
        capability=Capability.APPLY_CONSTRUCTION,
        modality=Modality.WRITTEN,
    )
    curriculum = CurriculumVersion(
        id=version_id,
        curriculum_code="synthetic-written",
        version_number=version_number,
        created_at=NOW,
        nodes=(CurriculumNode(
            id=NODE_ID if version_number == 1 else "60000000-0000-4000-8000-000000000002",
            curriculum_version_id=version_id,
            target=target,
            priority=50,
            outcome_code="A1.synthetic",
        ),),
    )
    right = {
        "status": "approved", "uses": ["analysis", "pilot_display"],
        "license": "author permission", "evidence": "agreement:synthetic-test",
        "reviewer": "fixture", "reviewed_at": "2026-09-25",
    }
    sources = {"schema_version": 1, "sources": [{
        "id": "synthetic-source", "source_type": "authored", "item_id": "synthetic-1",
        "release": None, "checksum": None, "attribution": "Synthetic test fixture",
        "rights": {"text": deepcopy(right), "translation": deepcopy(right)},
    }]}
    pilot = {"outcomes": [{
        "id": "A1.synthetic", "practice_families": ["practice"],
        "assessment_family": "holdout", "primary_target": {"id": construction.id},
    }]}
    examples = {"schema_version": 1, "examples": [{
        "id": "synthetic-practice", "outcome_id": "A1.synthetic", "role": "practice",
        "context_family": "practice", "source_id": "synthetic-source",
        "text": "Molim vodu.", "translation": "Воду, пожалуйста.",
        "script": "latin", "target_ref": construction.id, "target_span": [0, 5],
        "accepted_answers": ["Molim vodu."],
        "translation_status": "internally_checked",
        "answer_policy_status": "internally_checked",
        "review": {"status": "internally_checked", "reviewer": "fixture",
                   "date": "2026-09-25", "source_locators": ["synthetic:1"]},
    }]}
    return PublicationBundle(
        curriculum=curriculum,
        constructions=(construction,),
        sources=sources,
        pilot=pilot,
        examples=examples,
    )


def test_atomic_publication_persists_catalog_and_curriculum_together(db_session) -> None:
    bundle = _bundle()
    service = ContentPublicationService(db_session)
    report = service.preflight(bundle, published_at=NOW)
    assert report.rejected == ()
    assert CONSTRUCTION_ID in report.changed_ids
    assert VERSION_ID in report.changed_ids

    result = service.publish(bundle, published_at=NOW)
    assert result.status is CurriculumStatus.ACTIVE
    assert CatalogRepository(db_session).get_construction(CONSTRUCTION_ID) == bundle.constructions[0]
    assert service.publish(bundle, published_at=NOW).id == VERSION_ID
    assert db_session.scalars(select(LanguageConstruction.id)).all() == [CONSTRUCTION_ID]


def test_preflight_rejects_unknown_rights_before_writing(db_session) -> None:
    bundle = _bundle()
    bundle.sources["sources"][0]["rights"]["text"]["status"] = "unknown"
    service = ContentPublicationService(db_session)
    report = service.preflight(bundle, published_at=NOW)
    assert any("permission" in reason for reason in report.rejected)

    with pytest.raises(PublicationPreflightError):
        service.publish(bundle, published_at=NOW)
    assert db_session.scalars(select(LanguageConstruction.id)).all() == []


def test_publication_maps_reviewed_editorial_target_to_catalog_uuid(db_session) -> None:
    bundle = _bundle()
    bundle.pilot["outcomes"][0]["primary_target"]["id"] = "request-written"
    bundle.examples["examples"][0]["target_ref"] = "request-written"
    assert any("primary target absent" in reason for reason in
               ContentPublicationService(db_session).preflight(bundle, published_at=NOW).rejected)

    bundle.target_mapping = {"request-written": CONSTRUCTION_ID}
    assert ContentPublicationService(db_session).preflight(bundle, published_at=NOW).rejected == ()
    assert ContentPublicationService(db_session).publish(bundle, published_at=NOW).status is CurriculumStatus.ACTIVE


def test_publication_rejects_stale_editorial_target_mapping(db_session) -> None:
    bundle = _bundle()
    bundle.target_mapping = {"unused-editorial-key": CONSTRUCTION_ID}
    assert any("target mapping" in reason for reason in
               ContentPublicationService(db_session).preflight(bundle, published_at=NOW).rejected)


def test_preflight_rejects_existing_construction_code_under_new_id(db_session) -> None:
    first = _bundle()
    ContentPublicationService(db_session).publish(first, published_at=NOW)
    second = _bundle(
        version_number=2,
        version_id="50000000-0000-4000-8000-000000000002",
        construction_id="40000000-0000-4000-8000-000000000002",
    )
    second.constructions = (replace(
        second.constructions[0], code=first.constructions[0].code,
    ),)
    report = ContentPublicationService(db_session).preflight(second, published_at=NOW)
    assert any("construction code" in reason for reason in report.rejected)


def test_preflight_rejects_unreviewed_catalog_example(db_session) -> None:
    bundle = _bundle()
    bundle.constructions = (replace(
        bundle.constructions[0],
        examples=(UsageExample(
            serbian_text="Unreviewed replacement.",
            translation="Непроверенная замена.",
        ),),
    ),)
    report = ContentPublicationService(db_session).preflight(bundle, published_at=NOW)
    assert any("catalog example" in reason for reason in report.rejected)


def test_preflight_keeps_reviewed_assessment_examples_out_of_catalog(db_session) -> None:
    bundle = _bundle()
    heldout = deepcopy(bundle.examples["examples"][0])
    heldout.update({"id": "synthetic-holdout", "role": "assessment", "context_family": "holdout",
                    "text": "Molim čaj.", "translation": "Чай, пожалуйста.",
                    "accepted_answers": ["Molim čaj."]})
    bundle.examples["examples"].append(heldout)
    bundle.constructions = (replace(bundle.constructions[0], examples=(
        UsageExample(serbian_text="Molim čaj.", translation="Чай, пожалуйста."),
    )),)
    report = ContentPublicationService(db_session).preflight(bundle, published_at=NOW)
    assert any("catalog example" in reason for reason in report.rejected)


def test_preflight_rejects_unreviewed_existing_target_example(db_session) -> None:
    bundle = _bundle()
    unreviewed = replace(
        bundle.constructions[0],
        examples=(UsageExample(
            serbian_text="Other catalog text.",
            translation="Другой текст.",
        ),),
    )
    CatalogRepository(db_session).add_construction(unreviewed)
    db_session.commit()
    bundle.constructions = ()
    report = ContentPublicationService(db_session).preflight(bundle, published_at=NOW)
    assert any("catalog example" in reason for reason in report.rejected)


@pytest.mark.parametrize("field", ["translation_status", "answer_policy_status"])
def test_preflight_rejects_draft_translation_or_answer_key(db_session, field: str) -> None:
    bundle = _bundle()
    bundle.examples["examples"][0][field] = "draft"
    report = ContentPublicationService(db_session).preflight(bundle, published_at=NOW)
    assert any(field in reason for reason in report.rejected)


def test_active_repeat_rejects_new_catalog_ids(db_session) -> None:
    bundle = _bundle()
    service = ContentPublicationService(db_session)
    service.publish(bundle, published_at=NOW)
    extra = _bundle(construction_id="40000000-0000-4000-8000-000000000002")
    bundle.constructions += extra.constructions
    report = service.preflight(bundle, published_at=NOW)
    assert extra.constructions[0].id in report.changed_ids
    with pytest.raises(PublicationPreflightError):
        service.publish(bundle, published_at=NOW)
    assert CatalogRepository(db_session).get_construction(extra.constructions[0].id) is None


def test_preflight_rejects_missing_target_and_hard_cycle(db_session) -> None:
    service = ContentPublicationService(db_session)
    missing = _bundle()
    missing.constructions = ()
    assert any("missing" in reason for reason in service.preflight(missing, published_at=NOW).rejected)

    cyclic = _bundle()
    other = _bundle(construction_id="40000000-0000-4000-8000-000000000002")
    cyclic.constructions += other.constructions
    second_node = CurriculumNode(
        id="60000000-0000-4000-8000-000000000002",
        curriculum_version_id=VERSION_ID,
        target=TargetSpec(
            target_kind=TargetKind.CONSTRUCTION,
            target_id=other.constructions[0].id,
            capability=Capability.APPLY_CONSTRUCTION,
            modality=Modality.WRITTEN,
        ),
        priority=50,
        outcome_code="A1.synthetic",
    )
    cyclic.curriculum = CurriculumVersion(
        id=VERSION_ID, curriculum_code="synthetic-written", version_number=1,
        created_at=NOW, nodes=(*cyclic.curriculum.nodes, second_node),
        prerequisites=(
            PrerequisiteEdge(
                id="70000000-0000-4000-8000-000000000001",
                curriculum_version_id=VERSION_ID,
                prerequisite_node_id=NODE_ID,
                dependent_node_id=second_node.id,
                kind=PrerequisiteKind.HARD,
            ),
            PrerequisiteEdge(
                id="70000000-0000-4000-8000-000000000002",
                curriculum_version_id=VERSION_ID,
                prerequisite_node_id=second_node.id,
                dependent_node_id=NODE_ID,
                kind=PrerequisiteKind.HARD,
            ),
        ),
    )
    assert any("acyclic" in reason for reason in service.preflight(cyclic, published_at=NOW).rejected)
    assert db_session.scalars(select(LanguageConstruction.id)).all() == []


def test_failure_before_catalog_write_leaves_no_partial_rows(db_session, monkeypatch) -> None:
    def fail_add(*_args):
        raise RuntimeError("injected catalog failure")

    monkeypatch.setattr(CatalogRepository, "add_construction", fail_add)
    with pytest.raises(RuntimeError, match="injected catalog failure"):
        ContentPublicationService(db_session).publish(_bundle(), published_at=NOW)
    assert db_session.scalars(select(LanguageConstruction.id)).all() == []
    assert ContentPublicationService(db_session).active("synthetic-written") is None


def test_activation_failure_rolls_back_catalog_and_keeps_old_active(db_session, monkeypatch) -> None:
    word = VocabularyItem(
        serbian_cyrillic="кућа", serbian_latin="kuća", russian_translation="дом",
        cefr_level="A1", theme="home",
    )
    db_session.add(word)
    db_session.commit()
    bootstrap_catalog(db_session)
    mapping_before = CatalogRepository(db_session).get_by_legacy_vocabulary_item_id(word.id)
    first = _bundle()
    service = ContentPublicationService(db_session)
    service.publish(first, published_at=NOW)
    replacement = _bundle(
        version_number=2,
        version_id="50000000-0000-4000-8000-000000000002",
        construction_id="40000000-0000-4000-8000-000000000002",
    )

    def fail_activation(*_args, **_kwargs):
        assert set(db_session.scalars(select(LanguageConstruction.id)).all()) == {
            CONSTRUCTION_ID, replacement.constructions[0].id,
        }
        raise RuntimeError("injected activation failure")

    monkeypatch.setattr(CurriculumRepository, "activate_if_draft", fail_activation)
    with pytest.raises(RuntimeError, match="injected activation failure"):
        service.publish(replacement, published_at=NOW + timedelta(hours=1))

    assert service.active("synthetic-written").id == VERSION_ID
    assert CurriculumRepository(db_session, service.target_resolver).get(replacement.curriculum.id) is None
    assert db_session.scalars(select(LanguageConstruction.id)).all() == [CONSTRUCTION_ID]
    assert CatalogRepository(db_session).get_by_legacy_vocabulary_item_id(word.id) == mapping_before


def test_preflight_rejects_retired_content_and_keeps_active(db_session) -> None:
    first = _bundle()
    service = ContentPublicationService(db_session)
    service.publish(first, published_at=NOW)
    record = db_session.get(LanguageConstruction, CONSTRUCTION_ID)
    record.status = "retired"
    db_session.commit()
    replacement = _bundle(
        version_number=2,
        version_id="50000000-0000-4000-8000-000000000002",
    )
    replacement.constructions = ()
    report = service.preflight(replacement, published_at=NOW + timedelta(hours=1))
    assert any("retired" in reason for reason in report.rejected)
    with pytest.raises(PublicationPreflightError):
        service.publish(replacement, published_at=NOW + timedelta(hours=1))
    assert service.active("synthetic-written").id == VERSION_ID


def test_preflight_rejects_stale_legacy_mapping(db_session) -> None:
    word = VocabularyItem(
        serbian_cyrillic="кућа", serbian_latin="kuća", russian_translation="дом",
        cefr_level="A1", theme="home",
    )
    db_session.add(word)
    db_session.commit()
    bootstrap_catalog(db_session)
    lexical = CatalogRepository(db_session).get_by_legacy_vocabulary_item_id(word.id)
    assert lexical is not None
    word.russian_translation = "здание"
    db_session.commit()

    bundle = _bundle()
    bundle.constructions = ()
    bundle.curriculum = CurriculumVersion(
        id=VERSION_ID, curriculum_code="synthetic-written", version_number=1,
        created_at=NOW,
        nodes=(CurriculumNode(
            id=NODE_ID, curriculum_version_id=VERSION_ID,
            target=TargetSpec(
                target_kind=TargetKind.SENSE, target_id=lexical.senses[0].id,
                capability=Capability.RECOGNIZE_MEANING, modality=Modality.WRITTEN,
            ), priority=50, outcome_code="A1.synthetic",
        ),),
    )
    bundle.pilot["outcomes"][0]["primary_target"]["id"] = lexical.senses[0].id
    bundle.examples["examples"][0]["target_ref"] = lexical.senses[0].id

    report = ContentPublicationService(db_session).preflight(bundle, published_at=NOW)
    assert any("stale" in reason for reason in report.rejected)


def test_preflight_rejects_ambiguous_proposed_legacy_mapping(db_session) -> None:
    word = VocabularyItem(
        serbian_cyrillic="кућа", serbian_latin="kuća", russian_translation="дом",
        cefr_level="A1", theme="home",
    )
    db_session.add(word)
    db_session.commit()
    lexical = _aggregate(word)
    extra_sense = replace(
        lexical.senses[0], id="80000000-0000-4000-8000-000000000001"
    )
    ambiguous = replace(lexical, senses=(*lexical.senses, extra_sense))
    sense_id = lexical.senses[0].id
    bundle = _bundle()
    bundle.constructions = ()
    bundle.lexical_units = (ambiguous,)
    bundle.curriculum = CurriculumVersion(
        id=VERSION_ID, curriculum_code="synthetic-written", version_number=1,
        created_at=NOW,
        nodes=(CurriculumNode(
            id=NODE_ID, curriculum_version_id=VERSION_ID,
            target=TargetSpec(
                target_kind=TargetKind.SENSE, target_id=sense_id,
                capability=Capability.RECOGNIZE_MEANING, modality=Modality.WRITTEN,
            ), priority=50, outcome_code="A1.synthetic",
        ),),
    )
    bundle.pilot["outcomes"][0]["primary_target"]["id"] = sense_id
    bundle.examples["examples"][0]["target_ref"] = sense_id
    report = ContentPublicationService(db_session).preflight(bundle, published_at=NOW)
    assert any("ambiguous" in reason for reason in report.rejected)


def test_preflight_accepts_fresh_published_form_target(db_session) -> None:
    word = VocabularyItem(
        serbian_cyrillic="кућа", serbian_latin="kuća", russian_translation="дом",
        cefr_level="A1", theme="home",
    )
    db_session.add(word)
    db_session.commit()
    bootstrap_catalog(db_session)
    lexical = CatalogRepository(db_session).get_by_legacy_vocabulary_item_id(word.id)
    assert lexical is not None
    form_id = lexical.forms[0].id
    bundle = _bundle()
    bundle.constructions = ()
    bundle.curriculum = CurriculumVersion(
        id=VERSION_ID, curriculum_code="synthetic-written", version_number=1,
        created_at=NOW,
        nodes=(CurriculumNode(
            id=NODE_ID, curriculum_version_id=VERSION_ID,
            target=TargetSpec(
                target_kind=TargetKind.FORM, target_id=form_id,
                capability=Capability.RETRIEVE_FORM, modality=Modality.WRITTEN,
                condition={"form_kind": "citation"},
            ), priority=50, outcome_code="A1.synthetic",
        ),),
    )
    bundle.pilot["outcomes"][0]["primary_target"]["id"] = form_id
    bundle.examples["examples"][0]["target_ref"] = form_id
    assert ContentPublicationService(db_session).preflight(bundle, published_at=NOW).rejected == ()

    mismatched = TargetSpec(
        target_kind=TargetKind.FORM, target_id=form_id,
        capability=Capability.RETRIEVE_FORM, modality=Modality.WRITTEN,
        condition={"form_kind": "inflected"},
    )
    bundle.curriculum = CurriculumVersion(
        id=VERSION_ID, curriculum_code="synthetic-written", version_number=1,
        created_at=NOW,
        nodes=(CurriculumNode(
            id=NODE_ID, curriculum_version_id=VERSION_ID,
            target=mismatched, priority=50, outcome_code="A1.synthetic",
        ),),
    )
    assert any(
        "form kind" in reason
        for reason in ContentPublicationService(db_session).preflight(bundle, published_at=NOW).rejected
    )


def test_preflight_rejects_unreviewed_examples_linked_to_existing_form(db_session) -> None:
    word = VocabularyItem(
        serbian_cyrillic="кућа", serbian_latin="kuća", russian_translation="дом",
        cefr_level="A1", theme="home",
        example_sentences="Legacy unreviewed.",
        example_translations="Старый непроверенный пример.",
    )
    db_session.add(word)
    db_session.commit()
    bootstrap_catalog(db_session)
    lexical = CatalogRepository(db_session).get_by_legacy_vocabulary_item_id(word.id)
    assert lexical is not None
    form_id = lexical.forms[0].id
    bundle = _bundle()
    bundle.constructions = ()
    bundle.curriculum = CurriculumVersion(
        id=VERSION_ID, curriculum_code="synthetic-written", version_number=1,
        created_at=NOW,
        nodes=(CurriculumNode(
            id=NODE_ID, curriculum_version_id=VERSION_ID,
            target=TargetSpec(
                target_kind=TargetKind.FORM, target_id=form_id,
                capability=Capability.RETRIEVE_FORM, modality=Modality.WRITTEN,
                condition={"form_kind": "citation"},
            ), priority=50, outcome_code="A1.synthetic",
        ),),
    )
    bundle.pilot["outcomes"][0]["primary_target"]["id"] = form_id
    bundle.examples["examples"][0]["target_ref"] = form_id

    report = ContentPublicationService(db_session).preflight(bundle, published_at=NOW)
    assert any("catalog example" in reason for reason in report.rejected)


@pytest.fixture()
def postgresql_publication_engine():
    admin_url_value = os.getenv("SLOVNIK_TEST_POSTGRES_ADMIN_URL")
    if not admin_url_value:
        pytest.skip("SLOVNIK_TEST_POSTGRES_ADMIN_URL is not configured")
    admin_url = make_url(admin_url_value)
    if admin_url.get_backend_name() != "postgresql":
        raise ValueError("SLOVNIK_TEST_POSTGRES_ADMIN_URL must use PostgreSQL")
    database_name = f"slovnik_publication_test_{uuid4().hex}"
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    test_engine = None
    created = False
    try:
        with admin_engine.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{database_name}"'))
        created = True
        test_engine = create_engine(admin_url.set(database=database_name))
        Base.metadata.create_all(test_engine)
        yield test_engine
    finally:
        if test_engine is not None:
            test_engine.dispose()
        if created:
            with admin_engine.connect() as connection:
                connection.execute(text(f'DROP DATABASE "{database_name}" WITH (FORCE)'))
        admin_engine.dispose()


def test_postgresql_concurrent_identical_publication_is_idempotent(
    postgresql_publication_engine,
) -> None:
    SessionFactory = sessionmaker(bind=postgresql_publication_engine)
    barrier = threading.Barrier(2)

    def publish() -> str:
        with SessionFactory() as session:
            barrier.wait(timeout=10)
            return ContentPublicationService(session).publish(_bundle(), published_at=NOW).id

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(publish) for _ in range(2)]
        results = [future.result(timeout=30) for future in futures]
    assert results == [VERSION_ID, VERSION_ID]

    with SessionFactory() as session:
        assert ContentPublicationService(session).active("synthetic-written").id == VERSION_ID
        assert session.scalars(select(LanguageConstruction.id)).all() == [CONSTRUCTION_ID]


def test_postgresql_identical_winner_commits_between_preflight_catalog_and_version_reads(
    postgresql_publication_engine, monkeypatch,
) -> None:
    factory = sessionmaker(bind=postgresql_publication_engine)
    original = CatalogRepository.get_construction
    with factory() as delayed:
        committed = False

        def read_and_publish(repository, construction_id):
            nonlocal committed
            value = original(repository, construction_id)
            if repository._session is delayed and value is None and not committed:
                committed = True
                with factory() as winner:
                    ContentPublicationService(winner).publish(_bundle(), published_at=NOW)
            return value

        monkeypatch.setattr(CatalogRepository, "get_construction", read_and_publish)
        assert ContentPublicationService(delayed).publish(_bundle(), published_at=NOW).id == VERSION_ID
        assert committed


def test_postgresql_concurrent_activation_of_same_draft_is_idempotent(
    postgresql_publication_engine, monkeypatch,
) -> None:
    SessionFactory = sessionmaker(bind=postgresql_publication_engine)
    bundle = _bundle()
    with SessionFactory() as session:
        catalog = CatalogRepository(session)
        catalog.add_construction(bundle.constructions[0])
        service = ContentPublicationService(session)
        CurriculumRepository(session, service.target_resolver).add(bundle.curriculum)
        session.commit()

    original_activate = CurriculumRepository.activate_if_draft
    barrier = threading.Barrier(2)

    def synchronized_activate(repository, version_id, published_at):
        barrier.wait(timeout=10)
        return original_activate(repository, version_id, published_at)

    monkeypatch.setattr(CurriculumRepository, "activate_if_draft", synchronized_activate)

    def publish() -> str:
        with SessionFactory() as session:
            return ContentPublicationService(session).publish(_bundle(), published_at=NOW).id

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(publish) for _ in range(2)]
        results = [future.result(timeout=30) for future in futures]
    assert results == [VERSION_ID, VERSION_ID]

    with SessionFactory() as session:
        assert ContentPublicationService(session).active("synthetic-written").id == VERSION_ID
