from datetime import datetime, timezone
from math import inf, nan
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, text, update
from sqlalchemy.orm import Session

from app.domain.catalog import (
    Construction,
    ContentStatus,
    EntryKind,
    Form,
    FormKind,
    Gloss,
    LegacyExamplePayload,
    LexicalUnit,
    OrthographicForm,
    RetirementPolicyDecision,
    Script,
    Sense,
    StressPattern,
    UsageExample,
)
from app.domain_models.catalog import LanguageForm, LanguageLexicalUnit, LanguageSense
from app.repositories.catalog import CatalogRepository
from app.services.domain_bootstrap_service import bootstrap_catalog


def _id() -> str:
    return str(uuid4())


def test_published_lexical_unit_requires_a_sense_and_written_form():
    sense = Sense(
        id=_id(),
        lexical_unit_id="00000000-0000-0000-0000-000000000001",
        glosses=(Gloss(language="ru", text="слово"),),
        status=ContentStatus.PUBLISHED,
    )

    with pytest.raises(ValueError, match="written Form"):
        LexicalUnit(
            id="00000000-0000-0000-0000-000000000001",
            kind=EntryKind.WORD,
            status=ContentStatus.PUBLISHED,
            senses=(sense,),
        )

    form = Form(
        id=_id(),
        lexical_unit_id="00000000-0000-0000-0000-000000000001",
        form_kind=FormKind.CITATION,
        orthographies=(
            OrthographicForm(Script.CYRILLIC, "реч"),
            OrthographicForm(Script.LATIN, "reč"),
        ),
        status=ContentStatus.PUBLISHED,
    )
    published = LexicalUnit(
        id="00000000-0000-0000-0000-000000000001",
        kind=EntryKind.WORD,
        status=ContentStatus.PUBLISHED,
        senses=(sense,),
        forms=(form,),
    )

    assert published.status is ContentStatus.PUBLISHED


def test_publication_rejects_an_empty_sense_among_valid_children():
    lexical_unit_id = _id()
    draft = LexicalUnit(
        id=lexical_unit_id,
        kind=EntryKind.WORD,
        senses=(
            Sense(_id(), lexical_unit_id, (Gloss("ru", "дом"),)),
            Sense(_id(), lexical_unit_id, ()),
        ),
        forms=(
            Form(
                _id(),
                lexical_unit_id,
                FormKind.CITATION,
                (
                    OrthographicForm(Script.CYRILLIC, "дом"),
                    OrthographicForm(Script.LATIN, "dom"),
                ),
            ),
            Form(
                _id(),
                lexical_unit_id,
                FormKind.INFLECTED,
                (
                    OrthographicForm(Script.CYRILLIC, "дома"),
                    OrthographicForm(Script.LATIN, "doma"),
                ),
                morph_features={
                    "grammar": {
                        "cases": ["genitive", {"number": "singular"}],
                        "confidence": 0.5,
                        "nullable": None,
                    }
                },
                stress_pattern=StressPattern(
                    structured={
                        "cyrillic_syllables": ["до", "ма"],
                        "latin_syllables": ["do", "ma"],
                        "stressed_syllable_index": 0,
                    }
                ),
            ),
        ),
    )

    with pytest.raises(ValueError, match="every Sense"):
        draft.publish()


def test_publication_rejects_an_invalid_form_among_valid_children():
    lexical_unit_id = _id()
    draft = LexicalUnit(
        id=lexical_unit_id,
        kind=EntryKind.WORD,
        senses=(Sense(_id(), lexical_unit_id, (Gloss("ru", "дом"),)),),
        forms=(
            Form(
                _id(),
                lexical_unit_id,
                FormKind.CITATION,
                (
                    OrthographicForm(Script.CYRILLIC, "дом"),
                    OrthographicForm(Script.LATIN, "dom"),
                ),
            ),
            Form(
                _id(),
                lexical_unit_id,
                FormKind.INFLECTED,
                (OrthographicForm(Script.CYRILLIC, "дома"),),
            ),
        ),
    )

    with pytest.raises(ValueError, match="every Form"):
        draft.publish()


@pytest.mark.parametrize(
    ("kind", "form_kind"),
    [
        (EntryKind.MWE, FormKind.CITATION),
        (EntryKind.WORD, FormKind.FIXED),
    ],
)
def test_publication_rejects_form_kind_incompatible_with_entry_kind(kind, form_kind):
    lexical_unit_id = _id()
    draft = LexicalUnit(
        id=lexical_unit_id,
        kind=kind,
        senses=(Sense(_id(), lexical_unit_id, (Gloss("ru", "значение"),)),),
        forms=(
            Form(
                _id(),
                lexical_unit_id,
                form_kind,
                (
                    OrthographicForm(Script.CYRILLIC, "добар дан"),
                    OrthographicForm(Script.LATIN, "dobar dan"),
                ),
            ),
        ),
    )

    with pytest.raises(ValueError, match="EntryKind"):
        draft.publish()


def test_aggregate_and_child_lifecycle_statuses_must_match():
    lexical_unit_id = _id()
    published_sense = Sense(
        _id(),
        lexical_unit_id,
        (Gloss("ru", "дом"),),
        status=ContentStatus.PUBLISHED,
    )
    draft_sense = Sense(_id(), lexical_unit_id, (Gloss("ru", "жилище"),))
    published_form = Form(
        _id(),
        lexical_unit_id,
        FormKind.CITATION,
        (
            OrthographicForm(Script.CYRILLIC, "дом"),
            OrthographicForm(Script.LATIN, "dom"),
        ),
        status=ContentStatus.PUBLISHED,
    )

    with pytest.raises(ValueError, match="child statuses"):
        LexicalUnit(
            id=lexical_unit_id,
            kind=EntryKind.WORD,
            status=ContentStatus.PUBLISHED,
            senses=(published_sense, draft_sense),
            forms=(published_form,),
        )


def test_retired_aggregate_cannot_be_empty():
    with pytest.raises(ValueError, match="retired LexicalUnit requires valid Senses"):
        LexicalUnit(
            id=_id(),
            kind=EntryKind.WORD,
            status=ContentStatus.RETIRED,
        )


def test_sequence_fields_are_defensively_copied_from_callers():
    lexical_unit_id = _id()
    glosses = [Gloss("ru", "дом")]
    examples = [UsageExample("Ово је дом.")]
    orthographies = [
        OrthographicForm(Script.CYRILLIC, "дом"),
        OrthographicForm(Script.LATIN, "dom"),
    ]
    sense = Sense(_id(), lexical_unit_id, glosses, examples=examples)
    form = Form(_id(), lexical_unit_id, FormKind.CITATION, orthographies)
    senses = [sense]
    forms = [form]
    lexical_unit = LexicalUnit(
        id=lexical_unit_id,
        kind=EntryKind.WORD,
        senses=senses,
        forms=forms,
    )
    construction_examples = [UsageExample("Књига је на столу.")]
    construction = Construction(
        id=_id(),
        code="location-on",
        title="Location",
        description="Location construction",
        examples=construction_examples,
    )
    stress_parts = ["ra", "diti"]
    stress_pattern = StressPattern(structured={"parts": stress_parts})

    glosses.append(Gloss("ru", "жилище"))
    examples.clear()
    orthographies.clear()
    senses.clear()
    forms.clear()
    construction_examples.clear()
    stress_parts.clear()

    assert isinstance(sense.glosses, tuple) and len(sense.glosses) == 1
    assert isinstance(sense.examples, tuple) and len(sense.examples) == 1
    assert isinstance(form.orthographies, tuple) and len(form.orthographies) == 2
    assert isinstance(lexical_unit.senses, tuple) and len(lexical_unit.senses) == 1
    assert isinstance(lexical_unit.forms, tuple) and len(lexical_unit.forms) == 1
    assert isinstance(construction.examples, tuple) and len(construction.examples) == 1
    assert stress_pattern.structured["parts"] == ["ra", "diti"]


def test_sequence_fields_reject_invalid_nested_children():
    lexical_unit_id = _id()
    with pytest.raises(ValueError, match="glosses"):
        Sense(_id(), lexical_unit_id, ["not-a-gloss"])
    with pytest.raises(ValueError, match="examples"):
        Sense(_id(), lexical_unit_id, [Gloss("ru", "дом")], examples=[object()])
    with pytest.raises(ValueError, match="orthographies"):
        Form(_id(), lexical_unit_id, FormKind.CITATION, ["not-an-orthography"])
    with pytest.raises(ValueError, match="senses"):
        LexicalUnit(id=lexical_unit_id, kind=EntryKind.WORD, senses=[object()])
    with pytest.raises(ValueError, match="forms"):
        LexicalUnit(id=lexical_unit_id, kind=EntryKind.WORD, forms=[object()])


def test_form_and_construction_reject_invalid_value_object_types():
    lexical_unit_id = _id()
    orthographies = (
        OrthographicForm(Script.CYRILLIC, "дом"),
        OrthographicForm(Script.LATIN, "dom"),
    )
    with pytest.raises(ValueError, match="morph_features must be a Mapping"):
        Form(
            _id(),
            lexical_unit_id,
            FormKind.CITATION,
            orthographies,
            morph_features=[],
        )
    with pytest.raises(ValueError, match="stress_pattern must be a StressPattern"):
        Form(
            _id(),
            lexical_unit_id,
            FormKind.CITATION,
            orthographies,
            stress_pattern={"legacy_marker": "до́м"},
        )
    with pytest.raises(ValueError, match="morph_features must be a Mapping"):
        Construction(
            id=_id(),
            code="invalid-features",
            title="Invalid features",
            description="Invalid feature container",
            morph_features=[],
        )


@pytest.mark.parametrize(
    "payload",
    [
        {1: "non-string-key"},
        {"nested": {"unsupported": object()}},
        {"number": nan},
        {"number": inf},
        {"tuple": ("not", "json")},
    ],
)
def test_recursive_json_values_reject_non_portable_payloads(payload):
    with pytest.raises(ValueError, match="JSON"):
        Construction(
            id=_id(),
            code="invalid-json",
            title="Invalid JSON",
            description="Invalid JSON payload",
            morph_features=payload,
        )


def test_catalog_ids_and_revisions_are_canonical():
    with pytest.raises(ValueError, match="canonical lowercase UUID"):
        LexicalUnit(id=str(uuid4()).upper(), kind=EntryKind.WORD)

    with pytest.raises(ValueError, match="revision"):
        LexicalUnit(id=_id(), kind=EntryKind.WORD, revision=0)


def test_draft_publication_and_retirement_advance_revision():
    lexical_unit_id = _id()
    draft = LexicalUnit(
        id=lexical_unit_id,
        kind=EntryKind.WORD,
        senses=(
            Sense(
                id=_id(),
                lexical_unit_id=lexical_unit_id,
                glosses=(Gloss("ru", "дом"),),
            ),
        ),
        forms=(
            Form(
                id=_id(),
                lexical_unit_id=lexical_unit_id,
                form_kind=FormKind.CITATION,
                orthographies=(
                    OrthographicForm(Script.CYRILLIC, "дом"),
                    OrthographicForm(Script.LATIN, "dom"),
                ),
            ),
        ),
    )

    published = draft.publish()
    retired = published.retire(policy_decision=RetirementPolicyDecision.ALLOWED)

    assert published.revision == 2
    assert all(item.status is ContentStatus.PUBLISHED for item in published.senses + published.forms)
    assert retired.status is ContentStatus.RETIRED
    assert retired.revision == 3
    assert all(item.status is ContentStatus.RETIRED for item in retired.senses + retired.forms)
    with pytest.raises(ValueError, match="active curriculum"):
        published.retire(policy_decision=RetirementPolicyDecision.ACTIVE_REFERENCE)
    with pytest.raises(ValueError, match="only draft"):
        published.publish()


def test_retirement_requires_an_explicit_policy_decision():
    lexical_unit_id = _id()
    published = LexicalUnit(
        id=lexical_unit_id,
        kind=EntryKind.WORD,
        status=ContentStatus.PUBLISHED,
        senses=(
            Sense(
                _id(),
                lexical_unit_id,
                (Gloss("ru", "дом"),),
                status=ContentStatus.PUBLISHED,
            ),
        ),
        forms=(
            Form(
                _id(),
                lexical_unit_id,
                FormKind.CITATION,
                (
                    OrthographicForm(Script.CYRILLIC, "дом"),
                    OrthographicForm(Script.LATIN, "dom"),
                ),
                status=ContentStatus.PUBLISHED,
            ),
        ),
    )

    with pytest.raises(TypeError, match="policy_decision"):
        published.retire()


def test_serbian_written_form_validates_cyrillic_and_latin_representations():
    lexical_unit_id = _id()
    invalid_form = Form(
        id=_id(),
        lexical_unit_id=lexical_unit_id,
        form_kind=FormKind.CITATION,
        orthographies=(
            OrthographicForm(Script.CYRILLIC, "dom"),
            OrthographicForm(Script.LATIN, "дом"),
        ),
    )
    draft = LexicalUnit(
        id=lexical_unit_id,
        kind=EntryKind.WORD,
        senses=(Sense(_id(), lexical_unit_id, (Gloss("ru", "дом"),)),),
        forms=(invalid_form,),
    )

    with pytest.raises(ValueError, match="Serbian Cyrillic and Latin"):
        draft.publish()


def test_construction_publication_requires_curated_example():
    draft = Construction(
        id=_id(),
        code="location-u-locative",
        title="Location with u",
        description="Basic location construction",
    )

    with pytest.raises(ValueError, match="example"):
        draft.publish()

    publishable = Construction(
        id=_id(),
        code="location-na-locative",
        title="Location with na",
        description="Basic location construction",
        examples=(UsageExample("Књига је на столу.", "Книга на столе."),),
    )
    published = publishable.publish()
    assert published.status is ContentStatus.PUBLISHED
    with pytest.raises(ValueError, match="active curriculum"):
        published.retire(policy_decision=RetirementPolicyDecision.ACTIVE_REFERENCE)


def test_retired_construction_requires_a_valid_usage_example():
    with pytest.raises(ValueError, match="valid UsageExample"):
        Construction(
            id=_id(),
            code="invalid-retired",
            title="Invalid retired construction",
            description="Missing curated example",
            status=ContentStatus.RETIRED,
        )
    with pytest.raises(ValueError, match="construction examples"):
        Construction(
            id=_id(),
            code="legacy-example",
            title="Legacy example",
            description="Legacy payload is not curated content",
            examples=(LegacyExamplePayload("Пример.", "Пример."),),
        )
    with pytest.raises(ValueError, match="construction examples"):
        Construction(
            id=_id(),
            code="arbitrary-example",
            title="Arbitrary example",
            description="Arbitrary values are not curated content",
            examples=(object(),),
        )


def test_usage_example_rejects_empty_serbian_text():
    with pytest.raises(ValueError, match="Serbian text"):
        UsageExample("", "Только перевод")


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("translation", 42),
        ("target_annotation", ["invalid"]),
        ("translation", " "),
        ("target_annotation", ""),
    ],
)
def test_usage_example_rejects_invalid_optional_fields(field_name, value):
    with pytest.raises(ValueError, match=field_name):
        UsageExample("Валидан пример.", **{field_name: value})


def test_catalog_orm_matches_sql_01_and_repository_returns_detached_values():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    from app.db import Base

    Base.metadata.create_all(engine)
    expected_columns = {
        "language_lexical_units": {
            "id",
            "kind",
            "legacy_vocabulary_item_id",
            "status",
            "revision",
            "created_at",
            "updated_at",
        },
        "language_senses": {
            "id",
            "lexical_unit_id",
            "glosses",
            "notes",
            "examples",
            "status",
            "revision",
        },
        "language_forms": {
            "id",
            "lexical_unit_id",
            "form_kind",
            "orthographies",
            "morph_features",
            "stress_pattern",
            "status",
            "revision",
        },
        "language_constructions": {
            "id",
            "code",
            "title",
            "description",
            "morph_features",
            "examples",
            "status",
            "revision",
        },
    }
    inspector = inspect(engine)
    assert {
        table: {column["name"] for column in inspector.get_columns(table)}
        for table in expected_columns
    } == expected_columns
    assert {
        constraint["name"]
        for constraint in inspector.get_check_constraints("language_forms")
    } == {
        "ck_language_forms_form_kind",
        "ck_language_forms_revision",
        "ck_language_forms_status",
    }

    lexical_unit_id = _id()
    aggregate = LexicalUnit(
        id=lexical_unit_id,
        kind=EntryKind.WORD,
        legacy_vocabulary_item_id=None,
        senses=(Sense(_id(), lexical_unit_id, (Gloss("ru", "дом"),)),),
        forms=(
            Form(
                _id(),
                lexical_unit_id,
                FormKind.CITATION,
                (
                    OrthographicForm(Script.CYRILLIC, "дом"),
                    OrthographicForm(Script.LATIN, "dom"),
                ),
            ),
        ),
    )
    with Session(engine) as session:
        repository = CatalogRepository(session)
        repository.add(aggregate)
        session.commit()
        returned = repository.get(lexical_unit_id)

        assert returned == aggregate
        assert not isinstance(returned, LanguageLexicalUnit)
        assert session.scalar(
            text("SELECT count(*) FROM language_forms WHERE stress_pattern IS NULL")
        ) == 1
        assert isinstance(session.get(LanguageForm, aggregate.forms[0].id), LanguageForm)

        construction = Construction(
            id=_id(),
            code="nested-roundtrip",
            title="Nested roundtrip",
            description="Portable nested JSON",
            morph_features={
                "constraints": [{"case": "locative", "required": True}],
                "weight": 0.75,
            },
            examples=(UsageExample("Књига је на столу.", "Книга на столе."),),
        )
        repository.add_construction(construction)
        session.commit()
        assert repository.get_construction(construction.id) == construction

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    assert set(expected_columns).issubset(inspect(engine).get_table_names())


@pytest.mark.parametrize("status", [ContentStatus.PUBLISHED, ContentStatus.RETIRED])
def test_repository_rehydration_rejects_entry_and_form_kind_mismatch(status):
    from app.db import Base

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    lexical_unit_id = _id()
    now = datetime.now(timezone.utc)
    with Session(engine) as session:
        session.add(
            LanguageLexicalUnit(
                id=lexical_unit_id,
                kind=EntryKind.MWE.value,
                status=status.value,
                revision=1,
                created_at=now,
                updated_at=now,
                senses=[
                    LanguageSense(
                        id=_id(),
                        lexical_unit_id=lexical_unit_id,
                        glosses=[{"language": "ru", "text": "добрый день"}],
                        notes=None,
                        examples=[],
                        status=status.value,
                        revision=1,
                    )
                ],
                forms=[
                    LanguageForm(
                        id=_id(),
                        lexical_unit_id=lexical_unit_id,
                        form_kind=FormKind.CITATION.value,
                        orthographies=[
                            {"script": Script.CYRILLIC.value, "text": "добар дан"},
                            {"script": Script.LATIN.value, "text": "dobar dan"},
                        ],
                        morph_features={},
                        stress_pattern=None,
                        status=status.value,
                        revision=1,
                    )
                ],
            )
        )
        session.commit()

        with pytest.raises(ValueError, match="EntryKind"):
            CatalogRepository(session).get(lexical_unit_id)


def test_vocabulary_bootstrap_is_idempotent_and_preserves_legacy_content():
    from app.db import Base
    from app.models import VocabularyItem

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    if not inspect(engine).has_table("learning_events"):
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE learning_events (id TEXT PRIMARY KEY)"))

    stress = {
        "cyrillic_syllables": ["ра", "ди", "ти"],
        "latin_syllables": ["ra", "di", "ti"],
        "stressed_syllable_index": 0,
    }
    with Session(engine) as session:
        words = [
            VocabularyItem(
                serbian_cyrillic="кућа",
                serbian_latin="kuća",
                russian_translation="дом",
                cefr_level="A1",
                theme="home",
                meaning_notes="жилище",
                example_sentences="Ово је кућа.\nКућа је велика.",
                example_translations="Это дом.\nДом большой.",
            ),
            VocabularyItem(
                serbian_cyrillic="радити",
                serbian_latin="raditi",
                russian_translation="работать",
                cefr_level="A1",
                theme="actions",
                stress_pattern=stress,
            ),
            VocabularyItem(
                serbian_cyrillic="хвала",
                serbian_latin="hvala",
                russian_translation="спасибо",
                cefr_level="A1",
                theme="greetings",
                stress_marker="хва́ла",
            ),
            VocabularyItem(
                serbian_cyrillic="добар дан",
                serbian_latin="dobar dan",
                russian_translation="добрый день",
                cefr_level="A1",
                theme="greetings",
            ),
            VocabularyItem(
                serbian_cyrillic="до виђења",
                serbian_latin="doviđenja",
                russian_translation="до свидания",
                cefr_level="A1",
                theme="greetings",
            ),
            VocabularyItem(
                serbian_cyrillic="",
                serbian_latin="partial",
                russian_translation="",
                cefr_level="A1",
                theme="editorial",
            ),
            VocabularyItem(
                serbian_cyrillic="превод",
                serbian_latin="prevod",
                russian_translation="перевод",
                cefr_level="A1",
                theme="editorial",
                example_translations="Только перевод примера.",
            ),
            VocabularyItem(
                serbian_cyrillic="invalid",
                serbian_latin="невалидно",
                russian_translation="ошибка",
                cefr_level="A1",
                theme="editorial",
            ),
            VocabularyItem(
                serbian_cyrillic="писати",
                serbian_latin="pisati",
                russian_translation="писать",
                cefr_level="A1",
                theme="actions",
                stress_pattern={**stress, "latin_syllables": ["pog", "re", "šno"]},
            ),
            VocabularyItem(
                serbian_cyrillic="листа",
                serbian_latin="lista",
                russian_translation="список",
                cefr_level="A1",
                theme="editorial",
                stress_pattern=["malformed", "stress"],
            ),
            VocabularyItem(
                serbian_cyrillic="скалар",
                serbian_latin="skalar",
                russian_translation="скаляр",
                cefr_level="A1",
                theme="editorial",
                stress_pattern="malformed-stress",
            ),
            VocabularyItem(
                serbian_cyrillic="ауто-пут",
                serbian_latin="auto-put",
                russian_translation="автомагистраль",
                cefr_level="A1",
                theme="travel",
            ),
        ]
        session.add_all(words)
        session.commit()
        legacy_ids = [word.id for word in words]

        first = bootstrap_catalog(session)
        snapshot = tuple(
            session.execute(
                text(
                    "SELECT id, kind, legacy_vocabulary_item_id, status, revision, "
                    "created_at, updated_at FROM language_lexical_units ORDER BY "
                    "legacy_vocabulary_item_id"
                )
            ).all()
        ) + tuple(
            session.execute(
                text(
                    "SELECT id, lexical_unit_id, glosses, notes, examples, status, revision "
                    "FROM language_senses ORDER BY lexical_unit_id"
                )
            ).all()
        ) + tuple(
            session.execute(
                text(
                    "SELECT id, lexical_unit_id, form_kind, orthographies, morph_features, "
                    "stress_pattern, status, revision FROM language_forms ORDER BY lexical_unit_id"
                )
            ).all()
        )
        second = bootstrap_catalog(session)
        second_snapshot = tuple(
            session.execute(
                text(
                    "SELECT id, kind, legacy_vocabulary_item_id, status, revision, "
                    "created_at, updated_at FROM language_lexical_units ORDER BY "
                    "legacy_vocabulary_item_id"
                )
            ).all()
        ) + tuple(
            session.execute(
                text(
                    "SELECT id, lexical_unit_id, glosses, notes, examples, status, revision "
                    "FROM language_senses ORDER BY lexical_unit_id"
                )
            ).all()
        ) + tuple(
            session.execute(
                text(
                    "SELECT id, lexical_unit_id, form_kind, orthographies, morph_features, "
                    "stress_pattern, status, revision FROM language_forms ORDER BY lexical_unit_id"
                )
            ).all()
        )

        assert first.created == 12
        assert second.created == 0
        assert snapshot == second_snapshot

        catalog = [
            CatalogRepository(session).get_by_legacy_vocabulary_item_id(legacy_id)
            for legacy_id in legacy_ids
        ]
        assert all(item is not None for item in catalog)
        (
            house,
            structured,
            legacy,
            mwe,
            ambiguous,
            partial,
            translation_only,
            invalid_scripts,
            invalid_stress,
            malformed_list_stress,
            malformed_scalar_stress,
            ambiguous_hyphen,
        ) = catalog
        assert house.forms[0].orthographies == (
            OrthographicForm(Script.CYRILLIC, "кућа"),
            OrthographicForm(Script.LATIN, "kuća"),
        )
        assert house.senses[0].notes == "жилище"
        assert house.senses[0].examples[0].serbian_text == words[0].example_sentences
        assert house.senses[0].examples[0].translation == words[0].example_translations
        assert structured.forms[0].stress_pattern.structured == stress
        assert legacy.forms[0].stress_pattern.legacy_marker == "хва́ла"
        assert structured.forms[0].morph_features["bootstrap"]["cefr_level"] == "A1"
        assert structured.forms[0].morph_features["bootstrap"]["theme"] == "actions"
        assert len(
            structured.forms[0].morph_features["bootstrap"]["source_fingerprint"]
        ) == 64
        assert mwe.kind is EntryKind.MWE
        assert mwe.forms[0].form_kind is FormKind.FIXED
        assert ambiguous.kind is EntryKind.WORD
        assert ambiguous.forms[0].morph_features["bootstrap"]["needs_editor_review"] is True
        assert partial.status is ContentStatus.DRAFT
        assert translation_only.status is ContentStatus.DRAFT
        assert translation_only.senses[0].examples[0].serbian_text is None
        assert (
            translation_only.senses[0].examples[0].translation
            == "Только перевод примера."
        )
        assert invalid_scripts.status is ContentStatus.DRAFT
        assert invalid_stress.status is ContentStatus.DRAFT
        assert malformed_list_stress.status is ContentStatus.DRAFT
        assert malformed_list_stress.forms[0].stress_pattern.legacy_raw == [
            "malformed",
            "stress",
        ]
        assert malformed_scalar_stress.status is ContentStatus.DRAFT
        assert (
            malformed_scalar_stress.forms[0].stress_pattern.legacy_raw
            == "malformed-stress"
        )
        assert ambiguous_hyphen.kind is EntryKind.WORD
        assert (
            ambiguous_hyphen.forms[0].morph_features["bootstrap"]["needs_editor_review"]
            is True
        )
        assert all(item.status is ContentStatus.PUBLISHED for item in catalog[:4])
        assert session.scalar(text("SELECT count(*) FROM learning_events")) == 0


def test_catalog_mapping_audit_reports_stale_source_without_mutation(db_session) -> None:
    from app.models import VocabularyItem
    from app.services.catalog_mapping_service import audit_catalog_mappings

    word = VocabularyItem(
        serbian_cyrillic="кућа",
        serbian_latin="kuća",
        russian_translation="дом",
        cefr_level="A1",
        theme="home",
    )
    db_session.add(word)
    db_session.commit()
    bootstrap_catalog(db_session)

    word.russian_translation = "здание"
    db_session.commit()

    audit = audit_catalog_mappings(db_session)

    assert audit.stale == (word.id,)
    assert audit.missing == ()
    assert audit.ambiguous == ()


def test_locking_mapping_refreshes_stale_identity_map_before_fingerprint_check(
    db_session,
) -> None:
    from app.domain.shared import Capability
    from app.models import VocabularyItem
    from app.services.catalog_mapping_service import (
        CatalogMappingError,
        resolve_catalog_mapping,
    )

    word = VocabularyItem(
        serbian_cyrillic="реч",
        serbian_latin="reč",
        russian_translation="слово",
        cefr_level="A1",
        theme="identity-map",
    )
    db_session.add(word)
    db_session.commit()
    bootstrap_catalog(db_session)
    loaded = db_session.get(VocabularyItem, word.id)
    db_session.execute(
        update(VocabularyItem)
        .where(VocabularyItem.id == word.id)
        .values(russian_translation="изменено")
        .execution_options(synchronize_session=False)
    )
    assert loaded is not None
    assert loaded.russian_translation == "слово"

    with pytest.raises(CatalogMappingError) as error:
        resolve_catalog_mapping(
            db_session,
            word.id,
            capability=Capability.RETRIEVE_FORM,
        )

    assert error.value.reason == "stale"
