from __future__ import annotations

import hashlib
import json
import unicodedata
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.catalog import ContentStatus, FormKind
from app.domain.shared import Capability, Modality, TargetKind
from app.domain.target import TargetSpec
from app.domain_models.catalog import LanguageForm, LanguageLexicalUnit, LanguageSense
from app.models import VocabularyItem


class CatalogMappingError(RuntimeError):
    def __init__(self, reason: str) -> None:
        super().__init__("Legacy word has no unique published lexical mapping")
        self.reason = reason


@dataclass(frozen=True)
class CatalogLexicalMapping:
    target: TargetSpec
    citation_form_snapshot: dict[str, object]


@dataclass(frozen=True)
class CatalogMappingAudit:
    missing: tuple[int, ...]
    stale: tuple[int, ...]
    ambiguous: tuple[int, ...]


def _normalized(value: Any) -> Any:
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, list):
        return [_normalized(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _normalized(item) for key, item in value.items()}
    return value


def vocabulary_source_fingerprint(word: VocabularyItem) -> str:
    payload = _normalized(
        {
            "schema_version": 1,
            "serbian_cyrillic": word.serbian_cyrillic,
            "serbian_latin": word.serbian_latin,
            "russian_translation": word.russian_translation,
            "cefr_level": word.cefr_level,
            "theme": word.theme,
            "usage_register": word.usage_register,
            "stress_marker": word.stress_marker,
            "stress_pattern": word.stress_pattern,
            "meaning_notes": word.meaning_notes,
            "example_sentences": word.example_sentences,
            "example_translations": word.example_translations,
        }
    )
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _mapping_rows(
    session: Session,
    word_id: int,
    *,
    lock_source: bool = False,
) -> tuple[VocabularyItem | None, tuple[str, ...], tuple[LanguageForm, ...]]:
    word_statement = select(VocabularyItem).where(VocabularyItem.id == word_id)
    if lock_source:
        word_statement = word_statement.with_for_update().execution_options(
            populate_existing=True
        )
    word = session.scalar(word_statement)
    sense_ids = tuple(
        session.scalars(
            select(LanguageSense.id)
            .join(LanguageLexicalUnit)
            .where(
                LanguageLexicalUnit.legacy_vocabulary_item_id == word_id,
                LanguageLexicalUnit.status == ContentStatus.PUBLISHED.value,
                LanguageSense.status == ContentStatus.PUBLISHED.value,
            )
            .order_by(LanguageSense.id)
        )
    )
    forms = tuple(
        session.scalars(
            select(LanguageForm)
            .join(LanguageLexicalUnit)
            .where(
                LanguageLexicalUnit.legacy_vocabulary_item_id == word_id,
                LanguageLexicalUnit.status == ContentStatus.PUBLISHED.value,
                LanguageForm.status == ContentStatus.PUBLISHED.value,
                LanguageForm.form_kind.in_(
                    (FormKind.CITATION.value, FormKind.FIXED.value)
                ),
            )
            .order_by(LanguageForm.id)
        )
    )
    return word, sense_ids, forms


def _mapping_reason(
    word: VocabularyItem | None,
    sense_ids: tuple[str, ...],
    forms: tuple[LanguageForm, ...],
) -> str | None:
    if word is None or not sense_ids or not forms:
        return "missing"
    if len(sense_ids) != 1 or len(forms) != 1:
        return "ambiguous"
    bootstrap = forms[0].morph_features.get("bootstrap")
    stored = bootstrap.get("source_fingerprint") if isinstance(bootstrap, dict) else None
    if stored != vocabulary_source_fingerprint(word):
        return "stale"
    return None


def resolve_catalog_mapping(
    session: Session,
    word_id: int,
    *,
    capability: Capability,
    lock_source: bool = True,
) -> CatalogLexicalMapping:
    word, sense_ids, forms = _mapping_rows(
        session,
        word_id,
        lock_source=lock_source,
    )
    reason = _mapping_reason(word, sense_ids, forms)
    if reason is not None:
        raise CatalogMappingError(reason)
    form = forms[0]
    return CatalogLexicalMapping(
        target=TargetSpec(
            target_kind=TargetKind.SENSE,
            target_id=sense_ids[0],
            capability=capability,
            modality=Modality.WRITTEN,
        ),
        citation_form_snapshot={
            "id": form.id,
            "form_kind": form.form_kind,
            "orthographies": form.orthographies,
        },
    )


def audit_catalog_mappings(session: Session) -> CatalogMappingAudit:
    grouped: dict[str, list[int]] = {"missing": [], "stale": [], "ambiguous": []}
    word_ids = tuple(session.scalars(select(VocabularyItem.id).order_by(VocabularyItem.id)))
    for word_id in word_ids:
        reason = _mapping_reason(*_mapping_rows(session, word_id))
        if reason is not None:
            grouped[reason].append(word_id)
    return CatalogMappingAudit(
        missing=tuple(grouped["missing"]),
        stale=tuple(grouped["stale"]),
        ambiguous=tuple(grouped["ambiguous"]),
    )
