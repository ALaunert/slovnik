from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
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
    Script,
    Sense,
    StressPattern,
    UsageExample,
    plain_json,
)
from app.domain_models.catalog import (
    LanguageConstruction,
    LanguageForm,
    LanguageLexicalUnit,
    LanguageSense,
)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _example_payload(
    example: UsageExample | LegacyExamplePayload,
) -> dict[str, str | None]:
    if isinstance(example, LegacyExamplePayload):
        return {
            "payload_kind": "legacy_unparsed",
            "serbian_text": example.serbian_text,
            "translation": example.translation,
        }
    return {
        "payload_kind": "usage_example",
        "serbian_text": example.serbian_text,
        "translation": example.translation,
        "target_annotation": example.target_annotation,
    }


def _example_value(
    payload: dict[str, str | None],
) -> UsageExample | LegacyExamplePayload:
    if payload.get("payload_kind") == "legacy_unparsed":
        return LegacyExamplePayload(
            serbian_text=payload.get("serbian_text"),
            translation=payload.get("translation"),
        )
    return UsageExample(
        serbian_text=payload["serbian_text"],
        translation=payload.get("translation"),
        target_annotation=payload.get("target_annotation"),
    )


def _lexical_record(value: LexicalUnit) -> LanguageLexicalUnit:
    return LanguageLexicalUnit(
        id=value.id,
        kind=value.kind.value,
        legacy_vocabulary_item_id=value.legacy_vocabulary_item_id,
        status=value.status.value,
        revision=value.revision,
        created_at=value.created_at,
        updated_at=value.updated_at,
        senses=[
            LanguageSense(
                id=sense.id,
                lexical_unit_id=value.id,
                glosses=[{"language": gloss.language, "text": gloss.text} for gloss in sense.glosses],
                notes=sense.notes,
                examples=[_example_payload(example) for example in sense.examples],
                status=sense.status.value,
                revision=sense.revision,
            )
            for sense in value.senses
        ],
        forms=[
            LanguageForm(
                id=form.id,
                lexical_unit_id=value.id,
                form_kind=form.form_kind.value,
                orthographies=[
                    {"script": orthography.script.value, "text": orthography.text}
                    for orthography in form.orthographies
                ],
                morph_features=plain_json(form.morph_features),
                stress_pattern=(
                    form.stress_pattern.to_payload() if form.stress_pattern is not None else None
                ),
                status=form.status.value,
                revision=form.revision,
            )
            for form in value.forms
        ],
    )


def _sense_value(record: LanguageSense) -> Sense:
    return Sense(
        id=record.id,
        lexical_unit_id=record.lexical_unit_id,
        glosses=tuple(
            Gloss(language=gloss["language"], text=gloss["text"])
            for gloss in record.glosses
        ),
        notes=record.notes,
        examples=tuple(_example_value(example) for example in record.examples),
        status=ContentStatus(record.status),
        revision=record.revision,
    )


def _form_value(record: LanguageForm) -> Form:
    return Form(
        id=record.id,
        lexical_unit_id=record.lexical_unit_id,
        form_kind=FormKind(record.form_kind),
        orthographies=tuple(
            OrthographicForm(script=Script(item["script"]), text=item["text"])
            for item in record.orthographies
        ),
        morph_features=record.morph_features,
        stress_pattern=StressPattern.from_payload(record.stress_pattern),
        status=ContentStatus(record.status),
        revision=record.revision,
    )


def _lexical_value(record: LanguageLexicalUnit) -> LexicalUnit:
    return LexicalUnit(
        id=record.id,
        kind=EntryKind(record.kind),
        legacy_vocabulary_item_id=record.legacy_vocabulary_item_id,
        status=ContentStatus(record.status),
        revision=record.revision,
        created_at=_utc(record.created_at),
        updated_at=_utc(record.updated_at),
        senses=tuple(_sense_value(sense) for sense in record.senses),
        forms=tuple(_form_value(form) for form in record.forms),
    )


class CatalogRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, lexical_unit: LexicalUnit) -> None:
        self._session.add(_lexical_record(lexical_unit))

    def get(self, lexical_unit_id: str) -> LexicalUnit | None:
        record = self._session.get(LanguageLexicalUnit, lexical_unit_id)
        return _lexical_value(record) if record is not None else None

    def get_by_legacy_vocabulary_item_id(self, legacy_id: int) -> LexicalUnit | None:
        record = self._session.scalar(
            select(LanguageLexicalUnit).where(
                LanguageLexicalUnit.legacy_vocabulary_item_id == legacy_id
            )
        )
        return _lexical_value(record) if record is not None else None

    def add_construction(self, construction: Construction) -> None:
        self._session.add(
            LanguageConstruction(
                id=construction.id,
                code=construction.code,
                title=construction.title,
                description=construction.description,
                morph_features=plain_json(construction.morph_features),
                examples=[_example_payload(example) for example in construction.examples],
                status=construction.status.value,
                revision=construction.revision,
            )
        )

    def get_construction(self, construction_id: str) -> Construction | None:
        record = self._session.get(LanguageConstruction, construction_id)
        if record is None:
            return None
        return Construction(
            id=record.id,
            code=record.code,
            title=record.title,
            description=record.description,
            morph_features=record.morph_features,
            examples=tuple(_example_value(example) for example in record.examples),
            status=ContentStatus(record.status),
            revision=record.revision,
        )
