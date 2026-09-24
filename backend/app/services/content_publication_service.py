"""Caller-owned transaction for catalog publication and curriculum activation.

This is an infrastructure seam for a future reviewed pack. It does not publish the
file-backed synthetic pilot fixtures or infer editorial approval from database state.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.catalog import ContentStatus, FormKind
from app.domain.curriculum import CurriculumStatus
from app.domain.shared import TargetKind
from app.domain_models.catalog import LanguageForm, LanguageSense
from app.models import VocabularyItem
from app.repositories.catalog import CatalogRepository
from app.repositories.curriculum import CurriculumRepository
from app.services.catalog_mapping_service import vocabulary_source_fingerprint
from app.services.curriculum_service import (
    CurriculumActivationConflict,
    CurriculumService,
    _is_one_active_conflict,
)
from app.source_manifest import validate_manifest


@dataclass(frozen=True)
class PublicationRequest:
    curriculum_version_id: str
    source_manifest: dict[str, Any]
    source_item_ids_by_catalog_id: dict[str, tuple[str, ...]]
    lexical_unit_ids: tuple[str, ...] = ()
    construction_ids: tuple[str, ...] = ()
    expected_legacy_fingerprints: dict[int, str] = field(default_factory=dict)


@dataclass(frozen=True)
class PublicationPreflight:
    changed_ids: tuple[str, ...]
    rejected: tuple[str, ...]


class PublicationPreflightError(ValueError):
    def __init__(self, report: PublicationPreflight) -> None:
        self.report = report
        super().__init__("publication preflight rejected: " + "; ".join(report.rejected))


class ContentPublicationService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._catalog = CatalogRepository(session)
        self._curriculum = CurriculumRepository(session, self._catalog)

    def preflight(self, request: PublicationRequest, *, published_at: datetime) -> PublicationPreflight:
        rejected: list[str] = []
        draft = self._curriculum.get(request.curriculum_version_id)
        catalog_ids = (*request.lexical_unit_ids, *request.construction_ids)
        if len(catalog_ids) != len(set(catalog_ids)):
            rejected.append("duplicate catalog id in request")
        if draft is None:
            rejected.append(f"curriculum missing: {request.curriculum_version_id}")
        elif draft.status is CurriculumStatus.RETIRED:
            rejected.append("retired curriculum cannot be reactivated")

        referenced_lexical: set[str] = set()
        referenced_construction: set[str] = set()
        if draft is not None:
            for node in draft.nodes:
                target = node.target
                if target.target_kind is TargetKind.CONSTRUCTION:
                    referenced_construction.add(target.target_id)
                else:
                    record_type = (LanguageSense if target.target_kind is TargetKind.SENSE
                                   else LanguageForm)
                    record = self._session.get(record_type, target.target_id)
                    if record is None:
                        rejected.append(f"unresolved target owner: {target.target_id}")
                    else:
                        referenced_lexical.add(record.lexical_unit_id)
        if set(request.lexical_unit_ids) - referenced_lexical:
            rejected.append("unrelated catalog id in lexical publication request")
        if set(request.construction_ids) - referenced_construction:
            rejected.append("unrelated catalog id in construction publication request")
        referenced_ids = referenced_lexical | referenced_construction
        if set(request.source_item_ids_by_catalog_id) - referenced_ids:
            rejected.append("unrelated catalog id in source mapping")
        if draft is not None and draft.status is CurriculumStatus.ACTIVE:
            if (set(request.lexical_unit_ids) != referenced_lexical
                    or set(request.construction_ids) != referenced_construction):
                rejected.append("active curriculum repeat must name its referenced catalog owners")
            for node in draft.nodes:
                if not self._catalog.is_published(node.target):
                    rejected.append(f"active curriculum target is not published: {node.target.target_id}")

        candidate_targets: set[tuple[TargetKind, str]] = set()
        for item_id in sorted(referenced_lexical):
            unit = self._catalog.get(item_id)
            if unit is None:
                rejected.append(f"lexical unit missing: {item_id}")
                continue
            should_publish = item_id in request.lexical_unit_ids and draft is not None and draft.status is CurriculumStatus.DRAFT
            if should_publish:
                try:
                    unit.publish()
                except ValueError as error:
                    rejected.append(f"lexical unit {item_id}: {error}")
                else:
                    candidate_targets.update((TargetKind.SENSE, sense.id) for sense in unit.senses)
                    candidate_targets.update((TargetKind.FORM, form.id) for form in unit.forms)
            elif unit.status is not ContentStatus.PUBLISHED:
                rejected.append(f"referenced lexical unit is not published: {item_id}")
            legacy_id = unit.legacy_vocabulary_item_id
            if legacy_id is not None:
                expected = request.expected_legacy_fingerprints.get(legacy_id)
                word = self._session.scalar(select(VocabularyItem).where(VocabularyItem.id == legacy_id))
                citation_forms = tuple(form for form in unit.forms if form.form_kind in
                                       (FormKind.CITATION, FormKind.FIXED))
                bootstrap = (citation_forms[0].morph_features.get("bootstrap")
                             if len(citation_forms) == 1 else None)
                stored = bootstrap.get("source_fingerprint") if isinstance(bootstrap, Mapping) else None
                if (expected is None or word is None or len(unit.senses) != 1
                        or stored != expected or vocabulary_source_fingerprint(word) != expected):
                    rejected.append(f"stale legacy mapping: {item_id}")
        for item_id in sorted(referenced_construction):
            construction = self._catalog.get_construction(item_id)
            if construction is None:
                rejected.append(f"construction missing: {item_id}")
                continue
            should_publish = item_id in request.construction_ids and draft is not None and draft.status is CurriculumStatus.DRAFT
            if should_publish:
                try:
                    construction.publish()
                except ValueError as error:
                    rejected.append(f"construction {item_id}: {error}")
                else:
                    candidate_targets.add((TargetKind.CONSTRUCTION, item_id))
            elif construction.status is not ContentStatus.PUBLISHED:
                rejected.append(f"referenced construction is not published: {item_id}")

        source_ids = set()
        for item_id in sorted(referenced_ids):
            linked = request.source_item_ids_by_catalog_id.get(item_id, ())
            if not linked:
                rejected.append(f"source item missing for catalog content: {item_id}")
            source_ids.update(linked)
        rejected.extend(validate_manifest(
            request.source_manifest,
            requested_uses={"redistribution", "adaptation"},
            requested_item_ids=source_ids,
            requested_materials={"text", "translation"},
        ))
        for source in request.source_manifest.get("sources", []):
            for source_item in source.get("items", []):
                if source_item.get("item_id") in source_ids:
                    for material in ("text", "translation"):
                        if material not in source_item.get("materials", {}):
                            rejected.append(f"source {material} rights missing: {source_item['item_id']}")

        if draft is not None and draft.status is CurriculumStatus.DRAFT:
            try:
                draft.publish(
                    published_at=published_at,
                    target_is_published=lambda target: self._catalog.is_published(target)
                    or (target.target_kind, target.target_id) in candidate_targets,
                )
                active = self._curriculum.get_active_by_code(draft.curriculum_code)
                if active is not None:
                    if draft.version_number <= active.version_number:
                        rejected.append("replacement version_number must increase")
                    if active.published_at is not None and published_at < active.published_at:
                        rejected.append("replacement cannot predate active publication")
            except ValueError as error:
                rejected.append(f"curriculum {draft.id}: {error}")
        changed = (() if draft is not None and draft.status is CurriculumStatus.ACTIVE else
                   (*sorted(request.lexical_unit_ids), *sorted(request.construction_ids),
                    request.curriculum_version_id))
        return PublicationPreflight(changed_ids=changed, rejected=tuple(rejected))

    def publish(self, request: PublicationRequest, *, published_at: datetime) -> PublicationPreflight:
        report = self.preflight(request, published_at=published_at)
        if report.rejected:
            raise PublicationPreflightError(report)
        if not report.changed_ids:
            return report
        try:
            for item_id in request.lexical_unit_ids:
                self._catalog.publish_lexical_unit_if_draft(item_id)
            for item_id in request.construction_ids:
                self._catalog.publish_construction_if_draft(item_id)
            self._session.flush()
            CurriculumService(self._session, self._catalog).publish_in_transaction(
                request.curriculum_version_id, published_at=published_at,
            )
            self._session.commit()
            return report
        except IntegrityError as error:
            self._session.rollback()
            if _is_one_active_conflict(error):
                raise CurriculumActivationConflict("another curriculum version became active") from error
            raise
        except Exception:
            self._session.rollback()
            raise
