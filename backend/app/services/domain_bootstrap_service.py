from __future__ import annotations

import unicodedata
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.catalog import (
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
)
from app.models import VocabularyItem
from app.repositories.catalog import CatalogRepository


CATALOG_BOOTSTRAP_NAMESPACE = UUID("c139c951-f3db-5f7e-a1cf-e0f8b1dc8c52")


@dataclass(frozen=True)
class BootstrapResult:
    created: int
    existing: int


def _stable_id(legacy_id: int, entity: str) -> str:
    return str(uuid5(CATALOG_BOOTSTRAP_NAMESPACE, f"vocabulary-item:{legacy_id}:{entity}"))


def _utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _nfc(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def _classify(cyrillic: str, latin: str) -> tuple[EntryKind, bool]:
    cyrillic_parts = cyrillic.split()
    latin_parts = latin.split()
    if len(cyrillic_parts) > 1 and len(cyrillic_parts) == len(latin_parts):
        return EntryKind.MWE, False
    ambiguous_separators = "-/–—"
    ambiguous = (
        len(cyrillic_parts) > 1
        or len(latin_parts) > 1
        or any(separator in cyrillic or separator in latin for separator in ambiguous_separators)
    )
    return EntryKind.WORD, ambiguous


def _valid_structured_stress(
    payload: Any,
    cyrillic: str,
    latin: str,
) -> bool:
    if payload is None:
        return True
    if not isinstance(payload, dict):
        return False
    cyrillic_syllables = payload.get("cyrillic_syllables")
    latin_syllables = payload.get("latin_syllables")
    stressed_index = payload.get("stressed_syllable_index")
    if not isinstance(cyrillic_syllables, list) or not isinstance(latin_syllables, list):
        return False
    if not cyrillic_syllables or len(cyrillic_syllables) != len(latin_syllables):
        return False
    if type(stressed_index) is not int or not 0 <= stressed_index < len(cyrillic_syllables):
        return False
    if not all(isinstance(item, str) and item.strip() for item in cyrillic_syllables):
        return False
    if not all(isinstance(item, str) and item.strip() for item in latin_syllables):
        return False
    return _nfc("".join(cyrillic_syllables)) == _nfc(cyrillic) and _nfc(
        "".join(latin_syllables)
    ) == _nfc(latin)


def _examples(word: VocabularyItem) -> tuple[LegacyExamplePayload, ...]:
    if word.example_sentences is None and word.example_translations is None:
        return ()
    return (
        LegacyExamplePayload(
            serbian_text=word.example_sentences,
            translation=word.example_translations,
        ),
    )


def _aggregate(word: VocabularyItem) -> LexicalUnit:
    kind, needs_editor_review = _classify(word.serbian_cyrillic, word.serbian_latin)
    lexical_unit_id = _stable_id(word.id, "lexical-unit")
    stress = None
    if word.stress_pattern is not None or word.stress_marker is not None:
        structured_stress = (
            word.stress_pattern if isinstance(word.stress_pattern, dict) else None
        )
        legacy_raw_stress = (
            word.stress_pattern
            if word.stress_pattern is not None and not isinstance(word.stress_pattern, dict)
            else None
        )
        stress = StressPattern(
            structured=structured_stress,
            legacy_marker=word.stress_marker,
            legacy_raw=legacy_raw_stress,
        )
    sense = Sense(
        id=_stable_id(word.id, "sense"),
        lexical_unit_id=lexical_unit_id,
        glosses=(Gloss(language="ru", text=word.russian_translation),),
        notes=word.meaning_notes,
        examples=_examples(word),
    )
    form = Form(
        id=_stable_id(word.id, "form"),
        lexical_unit_id=lexical_unit_id,
        form_kind=FormKind.FIXED if kind is EntryKind.MWE else FormKind.CITATION,
        orthographies=(
            OrthographicForm(script=Script.CYRILLIC, text=word.serbian_cyrillic),
            OrthographicForm(script=Script.LATIN, text=word.serbian_latin),
        ),
        morph_features={
            "bootstrap": {
                "source": "vocabulary_item",
                "cefr_level": word.cefr_level,
                "theme": word.theme,
                "usage_register": word.usage_register,
                "needs_editor_review": needs_editor_review,
            }
        },
        stress_pattern=stress,
    )
    valid_content = bool(
        sense.is_publishable
        and form.has_required_serbian_scripts
        and _valid_structured_stress(
            word.stress_pattern,
            word.serbian_cyrillic,
            word.serbian_latin,
        )
    )
    status = ContentStatus.PUBLISHED if valid_content else ContentStatus.DRAFT
    sense = replace(sense, status=status)
    form = replace(form, status=status)
    return LexicalUnit(
        id=lexical_unit_id,
        kind=kind,
        legacy_vocabulary_item_id=word.id,
        status=status,
        senses=(sense,),
        forms=(form,),
        created_at=_utc(word.created_at),
        updated_at=_utc(word.updated_at),
    )


def bootstrap_catalog(session: Session) -> BootstrapResult:
    repository = CatalogRepository(session)
    created = 0
    existing = 0
    for word in session.scalars(select(VocabularyItem).order_by(VocabularyItem.id)):
        if repository.get_by_legacy_vocabulary_item_id(word.id) is not None:
            existing += 1
            continue
        repository.add(_aggregate(word))
        created += 1
    session.commit()
    return BootstrapResult(created=created, existing=existing)
