from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.curriculum import (
    CurriculumNode,
    CurriculumStatus,
    CurriculumVersion,
    PrerequisiteEdge,
    PrerequisiteKind,
)
from app.domain.target import TargetSpec
from app.domain_models.curriculum import (
    CurriculumNodeRecord,
    CurriculumPrerequisiteRecord,
    CurriculumVersionRecord,
)


class TargetResolver(Protocol):
    def is_published(self, target: TargetSpec) -> bool: ...


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _node_record(node: CurriculumNode) -> CurriculumNodeRecord:
    payload = node.target.to_payload()
    return CurriculumNodeRecord(
        id=node.id,
        curriculum_version_id=node.curriculum_version_id,
        target_key=node.target.target_key,
        target_kind=node.target.target_kind.value,
        target_id=node.target.target_id,
        capability=node.target.capability.value,
        modality=node.target.modality.value,
        condition_payload=payload["condition"],
        priority=node.priority,
        outcome_code=node.outcome_code,
    )


def _edge_record(edge: PrerequisiteEdge) -> CurriculumPrerequisiteRecord:
    return CurriculumPrerequisiteRecord(
        id=edge.id,
        curriculum_version_id=edge.curriculum_version_id,
        prerequisite_node_id=edge.prerequisite_node_id,
        dependent_node_id=edge.dependent_node_id,
        kind=edge.kind.value,
    )


def _version_record(value: CurriculumVersion) -> CurriculumVersionRecord:
    return CurriculumVersionRecord(
        id=value.id,
        curriculum_code=value.curriculum_code,
        version_number=value.version_number,
        status=value.status.value,
        created_at=value.created_at,
        published_at=value.published_at,
        retired_at=value.retired_at,
        nodes=[_node_record(node) for node in value.nodes],
        prerequisites=[_edge_record(edge) for edge in value.prerequisites],
    )


def _target_value(record: CurriculumNodeRecord) -> TargetSpec:
    return TargetSpec.from_payload(
        {
            "schema_version": 1,
            "target_kind": record.target_kind,
            "target_id": record.target_id,
            "capability": record.capability,
            "modality": record.modality,
            "condition": record.condition_payload,
            "target_key": record.target_key,
        }
    )


def _node_value(record: CurriculumNodeRecord) -> CurriculumNode:
    return CurriculumNode(
        id=record.id,
        curriculum_version_id=record.curriculum_version_id,
        target=_target_value(record),
        priority=record.priority,
        outcome_code=record.outcome_code,
    )


def _edge_value(record: CurriculumPrerequisiteRecord) -> PrerequisiteEdge:
    return PrerequisiteEdge(
        id=record.id,
        curriculum_version_id=record.curriculum_version_id,
        prerequisite_node_id=record.prerequisite_node_id,
        dependent_node_id=record.dependent_node_id,
        kind=PrerequisiteKind(record.kind),
    )


def _version_value(record: CurriculumVersionRecord) -> CurriculumVersion:
    return CurriculumVersion(
        id=record.id,
        curriculum_code=record.curriculum_code,
        version_number=record.version_number,
        status=CurriculumStatus(record.status),
        created_at=_utc(record.created_at),
        published_at=_utc(record.published_at) if record.published_at is not None else None,
        retired_at=_utc(record.retired_at) if record.retired_at is not None else None,
        nodes=tuple(_node_value(node) for node in record.nodes),
        prerequisites=tuple(_edge_value(edge) for edge in record.prerequisites),
    )


class CurriculumRepository:
    def __init__(self, session: Session, target_resolver: TargetResolver) -> None:
        self._session = session
        self._target_resolver = target_resolver

    def add(self, version: CurriculumVersion) -> None:
        self._session.add(_version_record(version))

    def get(self, version_id: str) -> CurriculumVersion | None:
        record = self._session.get(CurriculumVersionRecord, version_id)
        return _version_value(record) if record is not None else None

    def get_by_code_version(
        self, curriculum_code: str, version_number: int
    ) -> CurriculumVersion | None:
        record = self._session.scalar(
            select(CurriculumVersionRecord).where(
                CurriculumVersionRecord.curriculum_code == curriculum_code,
                CurriculumVersionRecord.version_number == version_number,
            )
        )
        return _version_value(record) if record is not None else None

    def target_is_published(self, target: TargetSpec) -> bool:
        return self._target_resolver.is_published(target)
