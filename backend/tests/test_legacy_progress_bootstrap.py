import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, text


BOOTSTRAP_AT = datetime(2026, 8, 27, 10, tzinfo=timezone.utc)


def _seed_progress_rows(db_session, statuses=("seen", "reviewing", "learned")):
    from app.models import UserProfile, UserWordProgress, VocabularyItem

    db_session.add(UserProfile(user_id="learner-1"))
    words = [
        VocabularyItem(
            serbian_cyrillic=f"реч{index}",
            serbian_latin=f"rec{index}",
            russian_translation=f"слово {index}",
            cefr_level="A1",
            theme="daily",
        )
        for index, _status in enumerate(statuses, start=1)
    ]
    db_session.add_all(words)
    db_session.flush()
    rows = [
        UserWordProgress(
            user_id="learner-1",
            word_id=word.id,
            status=status,
            first_seen_at=BOOTSTRAP_AT - timedelta(days=2),
            last_seen_at=BOOTSTRAP_AT - timedelta(days=1),
            next_review_at=BOOTSTRAP_AT + timedelta(days=index),
            review_interval_days=index,
        )
        for index, (word, status) in enumerate(zip(words, statuses), start=1)
    ]
    db_session.add_all(rows)
    db_session.commit()
    return words, rows


def test_maps_seen_reviewing_and_learned_to_low_confidence_sense_retrieval(
    db_session,
) -> None:
    from app.domain.progress import BaselineKind
    from app.domain.shared import Capability, Modality, TargetKind
    from app.domain.target import TargetSpec
    from app.domain_models.practice import LearningEventModel
    from app.repositories.catalog import CatalogRepository
    from app.repositories.progress import ProgressRepository
    from app.services.domain_bootstrap_service import bootstrap_catalog
    from app.services.legacy_progress_bootstrap_service import bootstrap_legacy_progress

    words, rows = _seed_progress_rows(db_session)
    bootstrap_catalog(db_session)

    result = bootstrap_legacy_progress(db_session, bootstrap_at=BOOTSTRAP_AT)

    repository = ProgressRepository(db_session)
    catalog = CatalogRepository(db_session)
    states = []
    for word in words:
        lexical_unit = catalog.get_by_legacy_vocabulary_item_id(word.id)
        assert lexical_unit is not None
        assert len(lexical_unit.senses) == 1
        target = TargetSpec(
            target_kind=TargetKind.SENSE,
            target_id=lexical_unit.senses[0].id,
            capability=Capability.RETRIEVE_FORM,
            modality=Modality.WRITTEN,
        )
        state = repository.get_state("learner-1", target.target_key)
        assert state is not None
        states.append(state)

    assert result.created == 3
    assert all(
        (
            state.competence.success_weight,
            state.competence.failure_weight,
            state.competence.peak,
            state.competence.uncertainty,
            state.evidence.count,
        )
        == (0, 0, 0, 1, 0)
        for state in states
    )
    assert all(state.baseline.kind is BaselineKind.LEGACY_BOOTSTRAP for state in states)
    assert all(
        state.memory.policy_version == "legacy-bootstrap-v1"
        and state.projection_policy_version == "legacy-bootstrap-v1"
        for state in states
    )
    assert [state.baseline.payload["source_ref"] for state in states] == [
        f"user_word_progress:{row.id}" for row in rows
    ]
    assert all(len(state.baseline.payload["source_fingerprint"]) == 64 for state in states)
    assert db_session.scalar(select(func.count()).select_from(LearningEventModel)) == 0


def test_adapts_explicit_due_weak_old_and_same_day_null_schedules(db_session) -> None:
    from app.domain.shared import Capability, Modality, TargetKind
    from app.domain.target import TargetSpec
    from app.repositories.catalog import CatalogRepository
    from app.repositories.progress import ProgressRepository
    from app.services.domain_bootstrap_service import bootstrap_catalog
    from app.services.legacy_progress_bootstrap_service import bootstrap_legacy_progress

    words, rows = _seed_progress_rows(
        db_session,
        statuses=("reviewing", "reviewing", "learned", "seen"),
    )
    explicit_due = BOOTSTRAP_AT + timedelta(days=8)
    rows[0].next_review_at = explicit_due
    rows[0].review_interval_days = 7
    rows[1].next_review_at = None
    rows[1].is_weak = True
    rows[1].first_seen_at = BOOTSTRAP_AT
    rows[1].last_seen_at = BOOTSTRAP_AT
    rows[2].next_review_at = None
    rows[2].first_seen_at = BOOTSTRAP_AT - timedelta(days=2)
    rows[2].last_seen_at = BOOTSTRAP_AT - timedelta(days=1)
    rows[3].next_review_at = None
    rows[3].first_seen_at = BOOTSTRAP_AT
    rows[3].last_seen_at = BOOTSTRAP_AT
    db_session.commit()
    bootstrap_catalog(db_session)

    bootstrap_legacy_progress(db_session, bootstrap_at=BOOTSTRAP_AT)

    repository = ProgressRepository(db_session)
    catalog = CatalogRepository(db_session)
    states = []
    for word in words:
        lexical_unit = catalog.get_by_legacy_vocabulary_item_id(word.id)
        assert lexical_unit is not None
        target = TargetSpec(
            target_kind=TargetKind.SENSE,
            target_id=lexical_unit.senses[0].id,
            capability=Capability.RETRIEVE_FORM,
            modality=Modality.WRITTEN,
        )
        state = repository.get_state("learner-1", target.target_key)
        assert state is not None
        states.append(state)

    assert [state.memory.due_at for state in states] == [
        explicit_due,
        BOOTSTRAP_AT,
        BOOTSTRAP_AT,
        datetime(2026, 8, 28, tzinfo=timezone.utc),
    ]
    assert states[0].memory.interval_days == 7
    assert states[3].memory.due_at > BOOTSTRAP_AT


def test_rerun_is_byte_stable_and_changed_source_resnapshots_zero_evidence(
    db_session,
) -> None:
    from app.domain.shared import Capability, Modality, TargetKind
    from app.domain.target import TargetSpec
    from app.repositories.catalog import CatalogRepository
    from app.repositories.progress import ProgressRepository
    from app.services.domain_bootstrap_service import bootstrap_catalog
    from app.services.legacy_progress_bootstrap_service import bootstrap_legacy_progress

    words, rows = _seed_progress_rows(db_session, statuses=("reviewing",))
    bootstrap_catalog(db_session)
    first_result = bootstrap_legacy_progress(db_session, bootstrap_at=BOOTSTRAP_AT)
    first_bytes = tuple(
        db_session.execute(
            text(
                "SELECT id, learner_id, target_key, baseline_kind, "
                "baseline_memory_due_at, baseline_memory_interval_days, "
                "baseline_payload, memory_due_at, memory_interval_days, "
                "memory_policy_version, projection_policy_version, updated_at "
                "FROM learner_target_states"
            )
        ).one()
    )

    unchanged_result = bootstrap_legacy_progress(
        db_session,
        bootstrap_at=BOOTSTRAP_AT + timedelta(days=30),
    )
    unchanged_bytes = tuple(
        db_session.execute(
            text(
                "SELECT id, learner_id, target_key, baseline_kind, "
                "baseline_memory_due_at, baseline_memory_interval_days, "
                "baseline_payload, memory_due_at, memory_interval_days, "
                "memory_policy_version, projection_policy_version, updated_at "
                "FROM learner_target_states"
            )
        ).one()
    )

    assert first_result.created == 1
    assert unchanged_result.unchanged == 1
    assert unchanged_bytes == first_bytes

    rows[0].next_review_at = BOOTSTRAP_AT + timedelta(days=12)
    rows[0].review_interval_days = 12
    db_session.commit()
    changed_result = bootstrap_legacy_progress(
        db_session,
        bootstrap_at=BOOTSTRAP_AT + timedelta(hours=1),
    )

    lexical_unit = CatalogRepository(db_session).get_by_legacy_vocabulary_item_id(
        words[0].id
    )
    assert lexical_unit is not None
    target = TargetSpec(
        target_kind=TargetKind.SENSE,
        target_id=lexical_unit.senses[0].id,
        capability=Capability.RETRIEVE_FORM,
        modality=Modality.WRITTEN,
    )
    changed = ProgressRepository(db_session).get_state("learner-1", target.target_key)
    assert changed is not None
    assert changed_result.updated == 1
    assert changed.state_id == first_bytes[0]
    first_payload = json.loads(first_bytes[6])
    assert (
        changed.baseline.payload["source_fingerprint"]
        != first_payload["source_fingerprint"]
    )
    assert (changed.memory.due_at, changed.memory.interval_days) == (
        BOOTSTRAP_AT + timedelta(days=12),
        12,
    )


def test_neutral_and_native_states_are_frozen_against_legacy_updates(db_session) -> None:
    from app.domain.shared import Capability, Modality, TargetKind
    from app.domain.target import TargetSpec
    from app.repositories.catalog import CatalogRepository
    from app.repositories.progress import ProgressRepository
    from app.services.domain_bootstrap_service import bootstrap_catalog
    from app.services.learner_projection_service import project_event
    from app.services.legacy_progress_bootstrap_service import bootstrap_legacy_progress

    words, rows = _seed_progress_rows(
        db_session,
        statuses=("seen", "reviewing"),
    )
    bootstrap_catalog(db_session)
    catalog = CatalogRepository(db_session)
    targets = []
    for word in words:
        lexical_unit = catalog.get_by_legacy_vocabulary_item_id(word.id)
        assert lexical_unit is not None
        targets.append(
            TargetSpec(
                target_kind=TargetKind.SENSE,
                target_id=lexical_unit.senses[0].id,
                capability=Capability.RETRIEVE_FORM,
                modality=Modality.WRITTEN,
            )
        )

    repository = ProgressRepository(db_session)
    neutral = repository.ensure_state(
        learner_id="learner-1",
        target_key=targets[0].target_key,
        state_id="11111111-1111-4111-8111-111111111111",
        updated_at=BOOTSTRAP_AT - timedelta(days=1),
    )
    first_result = bootstrap_legacy_progress(db_session, bootstrap_at=BOOTSTRAP_AT)
    legacy = repository.get_state("learner-1", targets[1].target_key)
    assert legacy is not None

    @dataclass(frozen=True)
    class Event:
        event_id: str = "22222222-2222-4222-8222-222222222222"
        learner_id: str = "learner-1"
        target_key: str = targets[1].target_key
        occurred_at: datetime = BOOTSTRAP_AT + timedelta(minutes=1)
        event_type: str = "response_evaluated"
        evaluation_source: str = "deterministic"
        evaluation_outcome: str = "correct"
        first_response: object | None = None

    native = project_event(legacy, Event())
    repository.save_projection(native)
    db_session.commit()
    rows[0].review_interval_days = 9
    rows[1].review_interval_days = 9
    db_session.commit()

    result = bootstrap_legacy_progress(
        db_session,
        bootstrap_at=BOOTSTRAP_AT + timedelta(days=1),
    )

    assert first_result.created == 1
    assert result.skipped_frozen == 2
    assert repository.get_state("learner-1", targets[0].target_key) == neutral
    assert repository.get_state("learner-1", targets[1].target_key) == native


def test_missing_and_ambiguous_sense_mappings_are_skipped_without_private_logs(
    db_session,
    caplog,
) -> None:
    from uuid import uuid4

    from sqlalchemy import select

    from app.domain_models.catalog import LanguageLexicalUnit, LanguageSense
    from app.models import UserWordProgress, VocabularyItem
    from app.services.domain_bootstrap_service import bootstrap_catalog
    from app.services.legacy_progress_bootstrap_service import bootstrap_legacy_progress

    words, _rows = _seed_progress_rows(
        db_session,
        statuses=("seen", "reviewing"),
    )
    bootstrap_catalog(db_session)
    lexical_units = [
        db_session.scalar(
            select(LanguageLexicalUnit).where(
                LanguageLexicalUnit.legacy_vocabulary_item_id == word.id
            )
        )
        for word in words
    ]
    assert all(lexical_unit is not None for lexical_unit in lexical_units)
    ambiguous = lexical_units[0]
    empty = lexical_units[1]
    assert ambiguous is not None and empty is not None
    ambiguous.senses.append(
        LanguageSense(
            id=str(uuid4()),
            lexical_unit_id=ambiguous.id,
            glosses=[{"language": "ru", "text": "другое значение"}],
            notes=None,
            examples=[],
            status=ambiguous.status,
            revision=1,
        )
    )
    for sense in tuple(empty.senses):
        db_session.delete(sense)
    missing_word = VocabularyItem(
        serbian_cyrillic="без маппинга",
        serbian_latin="bez mapinga",
        russian_translation="private raw answer sentinel",
        cefr_level="A1",
        theme="private",
    )
    db_session.add(missing_word)
    db_session.flush()
    db_session.add(
        UserWordProgress(
            user_id="learner-1",
            word_id=missing_word.id,
            status="seen",
            first_seen_at=BOOTSTRAP_AT,
            last_seen_at=BOOTSTRAP_AT,
        )
    )
    db_session.commit()
    db_session.expire_all()

    result = bootstrap_legacy_progress(db_session, bootstrap_at=BOOTSTRAP_AT)

    assert result.skipped_ambiguous_mapping == 1
    assert result.skipped_missing_mapping == 2
    assert result.created == 0
    assert "learner-1" not in caplog.text
    assert "private raw answer sentinel" not in caplog.text


def test_mapping_uses_only_one_published_sense_and_ignores_draft_alternatives(
    db_session,
) -> None:
    from uuid import uuid4

    from sqlalchemy import func, select

    from app.domain.shared import Capability, Modality, TargetKind
    from app.domain.target import TargetSpec
    from app.domain_models.catalog import LanguageLexicalUnit, LanguageSense
    from app.domain_models.progress import LearnerTargetStateModel
    from app.repositories.progress import ProgressRepository
    from app.services.domain_bootstrap_service import bootstrap_catalog
    from app.services.legacy_progress_bootstrap_service import bootstrap_legacy_progress

    words, _rows = _seed_progress_rows(
        db_session,
        statuses=("seen", "reviewing"),
    )
    bootstrap_catalog(db_session)
    lexical_units = [
        db_session.scalar(
            select(LanguageLexicalUnit).where(
                LanguageLexicalUnit.legacy_vocabulary_item_id == word.id
            )
        )
        for word in words
    ]
    assert all(lexical_unit is not None for lexical_unit in lexical_units)
    draft_lexical = lexical_units[0]
    published_lexical = lexical_units[1]
    assert draft_lexical is not None and published_lexical is not None
    draft_lexical.status = "draft"
    for sense in draft_lexical.senses:
        sense.status = "draft"
    for form in draft_lexical.forms:
        form.status = "draft"
    published_sense_id = published_lexical.senses[0].id
    published_lexical.senses.append(
        LanguageSense(
            id=str(uuid4()),
            lexical_unit_id=published_lexical.id,
            glosses=[{"language": "ru", "text": "черновая альтернатива"}],
            notes=None,
            examples=[],
            status="draft",
            revision=1,
        )
    )
    db_session.commit()
    db_session.expire_all()

    result = bootstrap_legacy_progress(db_session, bootstrap_at=BOOTSTRAP_AT)

    expected_target = TargetSpec(
        target_kind=TargetKind.SENSE,
        target_id=published_sense_id,
        capability=Capability.RETRIEVE_FORM,
        modality=Modality.WRITTEN,
    )
    assert result.created == 1
    assert result.skipped_missing_mapping == 1
    assert result.skipped_ambiguous_mapping == 0
    assert db_session.scalar(
        select(func.count()).select_from(LearnerTargetStateModel)
    ) == 1
    assert ProgressRepository(db_session).get_state(
        "learner-1",
        expected_target.target_key,
    ) is not None
