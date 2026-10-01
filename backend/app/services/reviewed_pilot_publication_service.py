"""Preflight and atomically publish a reviewed file-backed content bundle."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from datetime import datetime
from hashlib import sha256
import json
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.catalog import (
    Construction,
    ContentStatus,
    FormKind,
    LexicalUnit,
    UsageExample,
)
from app.domain.curriculum import CurriculumStatus, CurriculumVersion
from app.domain.shared import TargetKind
from app.domain.target import TargetSpec
from app.domain_models.catalog import (
    LanguageConstruction,
    LanguageForm,
    LanguageLexicalUnit,
    LanguageSense,
)
from app.domain_models.curriculum import CurriculumVersionRecord
from app.models import VocabularyItem
from app.pilot_examples import validate_pilot_examples
from app.repositories.catalog import CatalogRepository
from app.repositories.curriculum import CurriculumRepository
from app.services.catalog_mapping_service import (
    CatalogMappingError,
    resolve_catalog_mapping,
    vocabulary_source_fingerprint,
)
from app.services.curriculum_service import (
    CurriculumActivationConflict,
    CurriculumService,
    _replacement_retired_at,
)


@dataclass
class PublicationBundle:
    curriculum: CurriculumVersion
    sources: dict[str, Any]
    pilot: dict[str, Any]
    examples: dict[str, Any]
    lexical_units: tuple[LexicalUnit, ...] = ()
    constructions: tuple[Construction, ...] = ()
    target_mapping: dict[str, str] = dataclass_field(default_factory=dict)


def _bundle_fingerprint(bundle: PublicationBundle) -> str:
    # The catalog and curriculum definitions are compared separately by preflight.
    # Bind the editorial/rights request too, using a different namespace from
    # the draft-catalog PublicationRequest interface.
    payload = {
        "schema": "reviewed-pilot-bundle-v1",
        "curriculum_version_id": bundle.curriculum.id,
        "sources": bundle.sources,
        "pilot": bundle.pilot,
        "examples": bundle.examples,
        "target_mapping": bundle.target_mapping,
        "lexical_unit_ids": sorted(item.id for item in bundle.lexical_units),
        "construction_ids": sorted(item.id for item in bundle.constructions),
    }
    return sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                             separators=(",", ":")).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PublicationPreflightReport:
    changed_ids: tuple[str, ...]
    rejected: tuple[str, ...]


class PublicationPreflightError(ValueError):
    def __init__(self, report: PublicationPreflightReport) -> None:
        self.report = report
        super().__init__("; ".join(report.rejected))


def _same_definition(existing: CurriculumVersion, proposed: CurriculumVersion) -> bool:
    return (
        existing.id == proposed.id
        and existing.curriculum_code == proposed.curriculum_code
        and existing.version_number == proposed.version_number
        and existing.created_at == proposed.created_at
        and existing.nodes == proposed.nodes
        and existing.prerequisites == proposed.prerequisites
    )


def _catalog_example_errors(
    target_id: str,
    examples: tuple[object, ...],
    reviewed: set[tuple[str, str, str]],
) -> list[str]:
    return [
        f"{target_id}: catalog example has no matching reviewed text, translation and rights"
        for example in examples
        if not isinstance(example, UsageExample)
        or (target_id, example.serbian_text, example.translation) not in reviewed
    ]


class _PublicationTargetResolver:
    def __init__(
        self,
        session: Session,
        lexical_units: tuple[LexicalUnit, ...] = (),
        constructions: tuple[Construction, ...] = (),
    ) -> None:
        self._session = session
        self._senses = {
            sense.id: (unit, sense.status)
            for unit in lexical_units
            for sense in unit.senses
        }
        self._forms = {
            form.id: (unit, form)
            for unit in lexical_units
            for form in unit.forms
        }
        self._constructions = {item.id: item for item in constructions}

    def is_published(self, target: TargetSpec) -> bool:
        return self.reason(target) is None

    def reason(self, target: TargetSpec) -> str | None:
        if target.target_kind is TargetKind.CONSTRUCTION:
            candidate = self._constructions.get(target.target_id)
            if candidate is not None:
                status = candidate.status
            else:
                record = self._session.get(LanguageConstruction, target.target_id)
                status = ContentStatus(record.status) if record else None
            return None if status is ContentStatus.PUBLISHED else f"{target.target_id}: missing or retired construction"

        if target.target_kind not in {TargetKind.SENSE, TargetKind.FORM}:
            return f"{target.target_id}: unsupported target kind"
        candidate = (
            self._senses.get(target.target_id)
            if target.target_kind is TargetKind.SENSE
            else self._forms.get(target.target_id)
        )
        if candidate is not None:
            unit, content = candidate
            content_status = (
                content if target.target_kind is TargetKind.SENSE else content.status
            )
            if unit.status is not ContentStatus.PUBLISHED or content_status is not ContentStatus.PUBLISHED:
                return f"{target.target_id}: unpublished or retired target"
            if (
                target.target_kind is TargetKind.FORM
                and target.condition.get("form_kind") != content.form_kind.value
            ):
                return f"{target.target_id}: form kind mismatch"
            legacy_id = unit.legacy_vocabulary_item_id
            if legacy_id is None:
                return None
            word = self._session.get(VocabularyItem, legacy_id)
            if word is None:
                return f"{target.target_id}: missing legacy source"
            published_senses = [
                sense for sense in unit.senses
                if sense.status is ContentStatus.PUBLISHED
            ]
            citation_forms = [
                form for form in unit.forms
                if form.status is ContentStatus.PUBLISHED
                and form.form_kind in {FormKind.CITATION, FormKind.FIXED}
            ]
            if len(published_senses) != 1 or len(citation_forms) != 1:
                return f"{target.target_id}: ambiguous legacy mapping"
            if (
                target.target_kind is TargetKind.SENSE
                and published_senses[0].id != target.target_id
            ):
                return f"{target.target_id}: ambiguous legacy mapping"
            fingerprint = citation_forms[0].morph_features.get("bootstrap", {}).get("source_fingerprint")
            if fingerprint != vocabulary_source_fingerprint(word):
                return f"{target.target_id}: stale legacy mapping"
            return None

        record_type = (
            LanguageSense if target.target_kind is TargetKind.SENSE else LanguageForm
        )
        record = self._session.get(record_type, target.target_id)
        if record is None or record.status != ContentStatus.PUBLISHED.value:
            return f"{target.target_id}: missing or retired target"
        if (
            target.target_kind is TargetKind.FORM
            and target.condition.get("form_kind") != record.form_kind
        ):
            return f"{target.target_id}: form kind mismatch"
        unit = self._session.get(LanguageLexicalUnit, record.lexical_unit_id)
        if unit is None or unit.status != ContentStatus.PUBLISHED.value:
            return f"{target.target_id}: missing or retired lexical unit"
        if unit.legacy_vocabulary_item_id is None:
            return None
        try:
            mapping = resolve_catalog_mapping(
                self._session,
                unit.legacy_vocabulary_item_id,
                capability=target.capability,
            )
        except CatalogMappingError as exc:
            return f"{target.target_id}: {exc.reason} legacy mapping"
        if (
            target.target_kind is TargetKind.SENSE
            and mapping.target.target_id != target.target_id
        ):
            return f"{target.target_id}: ambiguous legacy mapping"
        return None


class ContentPublicationService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._catalog = CatalogRepository(session)
        self.target_resolver = _PublicationTargetResolver(session)

    def active(self, curriculum_code: str) -> CurriculumVersion | None:
        return CurriculumRepository(self._session, self.target_resolver).get_active_by_code(
            curriculum_code
        )

    def preflight(
        self, bundle: PublicationBundle, *, published_at: datetime
    ) -> PublicationPreflightReport:
        errors = validate_pilot_examples(
            bundle.examples, bundle.pilot, bundle.sources, publication=True
        )
        if not bundle.examples.get("examples"):
            errors.append("reviewed examples missing")
        curriculum = bundle.curriculum
        if curriculum.status is not CurriculumStatus.DRAFT:
            errors.append("proposed curriculum must be a draft")
        targets = {node.target.target_id for node in curriculum.nodes}
        editorial_targets = {
            outcome.get("primary_target", {}).get("id")
            for outcome in bundle.pilot.get("outcomes", [])
        }
        if set(bundle.target_mapping) - editorial_targets:
            errors.append("target mapping contains an unused editorial key")
        if len(set(bundle.target_mapping.values())) != len(bundle.target_mapping):
            errors.append("target mapping merges distinct editorial targets")
        for outcome in bundle.pilot.get("outcomes", []):
            target_id = outcome.get("primary_target", {}).get("id")
            if bundle.target_mapping.get(target_id, target_id) not in targets:
                errors.append(f"{outcome.get('id')}: primary target absent from curriculum")
        for example in bundle.examples.get("examples", []):
            target_ref = example.get("target_ref")
            if bundle.target_mapping.get(target_ref, target_ref) not in targets:
                errors.append(f"{example.get('id')}: example target absent from curriculum")
            for field in ("translation_status", "answer_policy_status"):
                if example.get(field) != "internally_checked":
                    errors.append(f"{example.get('id')}: {field} is not internally checked")
        reviewed = {
            (bundle.target_mapping.get(item["target_ref"], item["target_ref"]),
             item["text"], item["translation"])
            for item in bundle.examples.get("examples", [])
            if item.get("role") == "practice"
            and item.get("review", {}).get("status") == "internally_checked"
            and item.get("translation_status") == "internally_checked"
            and item.get("answer_policy_status") == "internally_checked"
            and all(key in item for key in ("target_ref", "text", "translation"))
        }

        changed: list[str] = []
        for unit in bundle.lexical_units:
            if unit.status is not ContentStatus.PUBLISHED:
                errors.append(f"{unit.id}: catalog unit is not published")
            existing = self._catalog.get(unit.id)
            if existing is None:
                changed.append(unit.id)
            elif existing != unit:
                errors.append(f"{unit.id}: existing catalog ID has different content")
            for sense in unit.senses:
                errors.extend(_catalog_example_errors(sense.id, sense.examples, reviewed))
        proposed_codes: set[str] = set()
        for construction in bundle.constructions:
            if construction.status is not ContentStatus.PUBLISHED:
                errors.append(f"{construction.id}: construction is not published")
            if construction.code in proposed_codes:
                errors.append(f"{construction.id}: duplicate proposed construction code")
            proposed_codes.add(construction.code)
            code_owner = self._session.scalar(select(LanguageConstruction.id).where(
                LanguageConstruction.code == construction.code
            ))
            if code_owner is not None and code_owner != construction.id:
                errors.append(f"{construction.id}: construction code already belongs to {code_owner}")
            existing = self._catalog.get_construction(construction.id)
            if existing is None:
                changed.append(construction.id)
            elif existing != construction:
                errors.append(f"{construction.id}: existing construction ID has different content")
            errors.extend(_catalog_example_errors(construction.id, construction.examples, reviewed))

        resolver = _PublicationTargetResolver(
            self._session, bundle.lexical_units, bundle.constructions
        )
        for node in curriculum.nodes:
            reason = resolver.reason(node.target)
            if reason is not None:
                errors.append(reason)
            if node.target.target_kind is TargetKind.CONSTRUCTION and not any(
                item.id == node.target.target_id for item in bundle.constructions
            ):
                existing_construction = self._catalog.get_construction(node.target.target_id)
                if existing_construction is not None:
                    errors.extend(_catalog_example_errors(
                        existing_construction.id, existing_construction.examples, reviewed
                    ))
            if node.target.target_kind in {TargetKind.SENSE, TargetKind.FORM} and not any(
                node.target.target_id == target.id
                for unit in bundle.lexical_units
                for target in (
                    unit.senses if node.target.target_kind is TargetKind.SENSE else unit.forms
                )
            ):
                record_type = (
                    LanguageSense if node.target.target_kind is TargetKind.SENSE
                    else LanguageForm
                )
                target_record = self._session.get(record_type, node.target.target_id)
                if target_record is not None:
                    existing_unit = self._catalog.get(target_record.lexical_unit_id)
                    if existing_unit is not None:
                        linked_senses = (
                            tuple(sense for sense in existing_unit.senses if sense.id == node.target.target_id)
                            if node.target.target_kind is TargetKind.SENSE
                            else existing_unit.senses
                        )
                        for sense in linked_senses:
                            errors.extend(_catalog_example_errors(
                                node.target.target_id, sense.examples, reviewed
                            ))
        if curriculum.status is CurriculumStatus.DRAFT:
            try:
                published = curriculum.publish(
                    published_at=published_at,
                    target_is_published=resolver.is_published,
                )
            except ValueError as exc:
                errors.append(str(exc))
            else:
                active = self.active(curriculum.curriculum_code)
                if active is not None and active.id != curriculum.id:
                    try:
                        _replacement_retired_at(active, published)
                    except ValueError as exc:
                        errors.append(str(exc))

        repository = CurriculumRepository(self._session, resolver)
        existing_version = repository.get(curriculum.id)
        if existing_version is not None and existing_version.status is CurriculumStatus.ACTIVE:
            record = self._session.get(CurriculumVersionRecord, curriculum.id)
            if (record.publication_request_fingerprint is not None
                    and record.publication_request_fingerprint != _bundle_fingerprint(bundle)):
                errors.append(f"{curriculum.id}: publication bundle differs from active version")
        if existing_version is None:
            changed.append(curriculum.id)
        elif not _same_definition(existing_version, curriculum):
            errors.append(f"{curriculum.id}: existing curriculum ID has different content")
        elif existing_version.status is CurriculumStatus.RETIRED:
            errors.append(f"{curriculum.id}: retired version cannot be republished")
        elif existing_version.status is CurriculumStatus.DRAFT:
            changed.append(curriculum.id)
        elif changed:
            # Under READ COMMITTED another publisher can commit its complete
            # atomic bundle between the catalog reads and this version read.
            # Recheck actual rows before treating an earlier absence as a new ID.
            current_missing = []
            for unit in bundle.lexical_units:
                current = self._catalog.get(unit.id)
                if current is None:
                    current_missing.append(unit.id)
                elif current != unit:
                    errors.append(f"{unit.id}: existing catalog ID has different content")
            for construction in bundle.constructions:
                current = self._catalog.get_construction(construction.id)
                if current is None:
                    current_missing.append(construction.id)
                elif current != construction:
                    errors.append(f"{construction.id}: existing construction ID has different content")
            changed = current_missing
            if changed:
                errors.append(f"{curriculum.id}: active version cannot accept new catalog IDs")

        return PublicationPreflightReport(tuple(sorted(set(changed))), tuple(sorted(set(errors))))

    def publish(self, bundle: PublicationBundle, *, published_at: datetime) -> CurriculumVersion:
        report = self.preflight(bundle, published_at=published_at)
        if report.rejected:
            raise PublicationPreflightError(report)
        curriculum = bundle.curriculum
        repository = CurriculumRepository(self._session, self.target_resolver)
        existing = repository.get(curriculum.id)
        if existing is not None and existing.status is CurriculumStatus.ACTIVE:
            # Local revisions published before the integrity migration have no
            # fingerprint. Adopt only after the full exact-content preflight.
            record = self._session.scalar(select(CurriculumVersionRecord).where(
                CurriculumVersionRecord.id == curriculum.id,
            ).with_for_update().execution_options(populate_existing=True))
            fingerprint = _bundle_fingerprint(bundle)
            if record.publication_request_fingerprint not in (None, fingerprint):
                self._session.rollback()
                raise PublicationPreflightError(PublicationPreflightReport(
                    (), (f"{curriculum.id}: publication bundle differs from active version",),
                ))
            record.publication_request_fingerprint = fingerprint
            self._session.commit()
            return existing
        try:
            for unit in bundle.lexical_units:
                if self._catalog.get(unit.id) is None:
                    self._catalog.add(unit)
            for construction in bundle.constructions:
                if self._catalog.get_construction(construction.id) is None:
                    self._catalog.add_construction(construction)
            self._session.flush()
            if existing is None:
                repository.add(curriculum)
                self._session.flush()
            published = CurriculumService(
                self._session, self.target_resolver
            ).publish_in_transaction(curriculum.id, published_at=published_at)
            record = self._session.get(CurriculumVersionRecord, curriculum.id)
            record.publication_request_fingerprint = _bundle_fingerprint(bundle)
            self._session.commit()
            return published
        except (IntegrityError, CurriculumActivationConflict):
            self._session.rollback()
            retry_report = self.preflight(bundle, published_at=published_at)
            winner = self.active(curriculum.curriculum_code)
            if (
                not retry_report.rejected
                and winner is not None
                and winner.id == curriculum.id
                and _same_definition(winner, curriculum)
                and all(
                    self._catalog.get(unit.id) == unit
                    for unit in bundle.lexical_units
                )
                and all(
                    self._catalog.get_construction(item.id) == item
                    for item in bundle.constructions
                )
            ):
                return winner
            raise
        except Exception:
            self._session.rollback()
            raise
