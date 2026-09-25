from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, update
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
from app.domain.shared import TargetKind
from app.domain.target import TargetSpec
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
        record = _lexical_record(lexical_unit)
        if lexical_unit.status is ContentStatus.PUBLISHED:
            # Bootstrap can create an already published aggregate. Insert its
            # children while the new parent is draft, then expose the complete
            # aggregate as published in the same transaction.
            record.status = ContentStatus.DRAFT.value
            self._session.add(record)
            self._session.flush()
            record.status = ContentStatus.PUBLISHED.value
        else:
            self._session.add(record)

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

    def is_published(self, target: TargetSpec) -> bool:
        record_type = {
            TargetKind.SENSE: LanguageSense,
            TargetKind.FORM: LanguageForm,
            TargetKind.CONSTRUCTION: LanguageConstruction,
        }[target.target_kind]
        record = self._session.get(record_type, target.target_id)
        if record is None or record.status != ContentStatus.PUBLISHED.value:
            return False
        if target.target_kind is TargetKind.CONSTRUCTION:
            return True
        parent = self._session.get(LanguageLexicalUnit, record.lexical_unit_id)
        return parent is not None and parent.status == ContentStatus.PUBLISHED.value

    def publish_construction_if_draft(self, construction_id: str) -> Construction:
        draft = self.get_construction(construction_id)
        if draft is None:
            raise ValueError(f"construction missing: {construction_id}")
        published = draft.publish()
        changed = self._session.execute(
            update(LanguageConstruction)
            .where(LanguageConstruction.id == construction_id,
                   LanguageConstruction.status == ContentStatus.DRAFT.value,
                   LanguageConstruction.revision == draft.revision)
            .values(status=ContentStatus.PUBLISHED.value, revision=published.revision)
        )
        if changed.rowcount != 1:
            raise ValueError(f"construction changed before publication: {construction_id}")
        return published

    def publish_lexical_unit_if_draft(self, lexical_unit_id: str) -> LexicalUnit:
        # The FK check in a child INSERT takes a key-share lock in PostgreSQL.
        # A full parent lock makes publication and guarded child insertion serialize.
        self._session.scalar(
            select(LanguageLexicalUnit)
            .where(LanguageLexicalUnit.id == lexical_unit_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        draft = self.get(lexical_unit_id)
        if draft is None:
            raise ValueError(f"lexical unit missing: {lexical_unit_id}")
        published = draft.publish()
        changed = self._session.execute(
            update(LanguageLexicalUnit)
            .where(LanguageLexicalUnit.id == lexical_unit_id,
                   LanguageLexicalUnit.status == ContentStatus.DRAFT.value,
                   LanguageLexicalUnit.revision == draft.revision)
            .values(status=ContentStatus.PUBLISHED.value, revision=published.revision,
                    updated_at=published.updated_at)
        )
        if changed.rowcount != 1:
            raise ValueError(f"lexical unit changed before publication: {lexical_unit_id}")
        for sense in draft.senses:
            changed = self._session.execute(
                update(LanguageSense)
                .where(LanguageSense.id == sense.id,
                       LanguageSense.lexical_unit_id == lexical_unit_id,
                       LanguageSense.status == ContentStatus.DRAFT.value,
                       LanguageSense.revision == sense.revision)
                .values(status=ContentStatus.PUBLISHED.value, revision=sense.revision + 1)
            )
            if changed.rowcount != 1:
                raise ValueError(f"sense changed before publication: {sense.id}")
        for form in draft.forms:
            changed = self._session.execute(
                update(LanguageForm)
                .where(LanguageForm.id == form.id,
                       LanguageForm.lexical_unit_id == lexical_unit_id,
                       LanguageForm.status == ContentStatus.DRAFT.value,
                       LanguageForm.revision == form.revision)
                .values(status=ContentStatus.PUBLISHED.value, revision=form.revision + 1)
            )
            if changed.rowcount != 1:
                raise ValueError(f"form changed before publication: {form.id}")
        current_senses = set(self._session.scalars(
            select(LanguageSense.id).where(LanguageSense.lexical_unit_id == lexical_unit_id)
        ))
        current_forms = set(self._session.scalars(
            select(LanguageForm.id).where(LanguageForm.lexical_unit_id == lexical_unit_id)
        ))
        if (current_senses != {sense.id for sense in draft.senses}
                or current_forms != {form.id for form in draft.forms}):
            raise ValueError(f"child set changed before publication: {lexical_unit_id}")
        return published
