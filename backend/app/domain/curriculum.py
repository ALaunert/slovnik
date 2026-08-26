from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID

from .target import TargetSpec


class CurriculumStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    RETIRED = "retired"


class PrerequisiteKind(str, Enum):
    HARD = "hard"
    SOFT = "soft"


_OUTCOME_CODE = re.compile(r"^(?:A1|A2|B1|B2|C1|C2)\..+$")


def _canonical_id(value: str, field_name: str = "id") -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a UUID string")
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"{field_name} must be a UUID string") from exc
    if str(parsed) != value:
        raise ValueError(f"{field_name} must be a canonical lowercase UUID")
    return value


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError("timestamps must be datetime values")
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _required_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must not be empty")
    return value


def _typed_tuple(value: Any, item_type: type[Any], field_name: str) -> tuple[Any, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name} must be a sequence")
    items = tuple(value)
    if not all(isinstance(item, item_type) for item in items):
        raise ValueError(f"{field_name} contains an invalid value")
    return items


def _lifecycle_timestamps(
    status: CurriculumStatus,
    created_at: datetime,
    published_at: datetime | None,
    retired_at: datetime | None,
) -> tuple[datetime | None, datetime | None]:
    published = _utc(published_at) if published_at is not None else None
    retired = _utc(retired_at) if retired_at is not None else None
    valid_shape = (
        status is CurriculumStatus.DRAFT and published is None and retired is None
    ) or (
        status is CurriculumStatus.ACTIVE and published is not None and retired is None
    ) or (
        status is CurriculumStatus.RETIRED
        and published is not None
        and retired is not None
    )
    if not valid_shape:
        raise ValueError("invalid curriculum lifecycle timestamp shape")
    if published is not None and published < created_at:
        raise ValueError("invalid curriculum lifecycle timestamp order")
    if retired is not None and published is not None and retired < published:
        raise ValueError("invalid curriculum lifecycle timestamp order")
    return published, retired


@dataclass(frozen=True)
class CurriculumNode:
    id: str
    curriculum_version_id: str
    target: TargetSpec
    priority: int
    outcome_code: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _canonical_id(self.id))
        object.__setattr__(
            self,
            "curriculum_version_id",
            _canonical_id(self.curriculum_version_id, "curriculum_version_id"),
        )
        if not isinstance(self.target, TargetSpec):
            raise ValueError("target must be a TargetSpec")
        if type(self.priority) is not int or not 0 <= self.priority <= 100:
            raise ValueError("priority must be an integer from 0 through 100")
        if not isinstance(self.outcome_code, str) or not _OUTCOME_CODE.fullmatch(
            self.outcome_code
        ):
            raise ValueError("outcome_code must have the format <CEFR>.<stable-code>")


@dataclass(frozen=True)
class PrerequisiteEdge:
    id: str
    curriculum_version_id: str
    prerequisite_node_id: str
    dependent_node_id: str
    kind: PrerequisiteKind

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _canonical_id(self.id))
        object.__setattr__(
            self,
            "curriculum_version_id",
            _canonical_id(self.curriculum_version_id, "curriculum_version_id"),
        )
        object.__setattr__(
            self,
            "prerequisite_node_id",
            _canonical_id(self.prerequisite_node_id, "prerequisite_node_id"),
        )
        object.__setattr__(
            self,
            "dependent_node_id",
            _canonical_id(self.dependent_node_id, "dependent_node_id"),
        )
        if not isinstance(self.kind, PrerequisiteKind):
            raise ValueError("kind must be a PrerequisiteKind")
        if self.prerequisite_node_id == self.dependent_node_id:
            raise ValueError("a curriculum node cannot be a prerequisite of itself")


@dataclass(frozen=True)
class CurriculumVersion:
    id: str
    curriculum_code: str
    version_number: int
    created_at: datetime
    status: CurriculumStatus = CurriculumStatus.DRAFT
    published_at: datetime | None = None
    retired_at: datetime | None = None
    nodes: tuple[CurriculumNode, ...] = field(default_factory=tuple)
    prerequisites: tuple[PrerequisiteEdge, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _canonical_id(self.id))
        object.__setattr__(
            self,
            "curriculum_code",
            _required_text(self.curriculum_code, "curriculum_code"),
        )
        if type(self.version_number) is not int or self.version_number < 1:
            raise ValueError("version_number must be an integer greater than or equal to 1")
        if not isinstance(self.status, CurriculumStatus):
            raise ValueError("status must be a CurriculumStatus")
        object.__setattr__(self, "created_at", _utc(self.created_at))
        published_at, retired_at = _lifecycle_timestamps(
            self.status,
            self.created_at,
            self.published_at,
            self.retired_at,
        )
        object.__setattr__(self, "published_at", published_at)
        object.__setattr__(self, "retired_at", retired_at)
        nodes = tuple(
            sorted(_typed_tuple(self.nodes, CurriculumNode, "nodes"), key=lambda node: node.id)
        )
        if any(node.curriculum_version_id != self.id for node in nodes):
            raise ValueError("every node must belong to its curriculum version")
        if len({node.id for node in nodes}) != len(nodes):
            raise ValueError("curriculum node id must be unique within a version")
        if len({node.target.target_key for node in nodes}) != len(nodes):
            raise ValueError("curriculum target_key must be unique within a version")
        object.__setattr__(self, "nodes", nodes)
        prerequisites = tuple(
            sorted(
                _typed_tuple(
                    self.prerequisites, PrerequisiteEdge, "prerequisites"
                ),
                key=lambda edge: edge.id,
            )
        )
        if any(edge.curriculum_version_id != self.id for edge in prerequisites):
            raise ValueError("every prerequisite edge must belong to its curriculum version")
        node_ids = {node.id for node in nodes}
        if any(
            edge.prerequisite_node_id not in node_ids
            or edge.dependent_node_id not in node_ids
            for edge in prerequisites
        ):
            raise ValueError("every prerequisite endpoint must belong to the version")
        if len({edge.id for edge in prerequisites}) != len(prerequisites):
            raise ValueError("prerequisite edge id must be unique within a version")
        pairs = {
            (edge.prerequisite_node_id, edge.dependent_node_id)
            for edge in prerequisites
        }
        if len(pairs) != len(prerequisites):
            raise ValueError("a directed node pair can have only one prerequisite edge")
        object.__setattr__(self, "prerequisites", prerequisites)

    def add_node(self, node: CurriculumNode) -> CurriculumVersion:
        self._require_draft()
        return replace(self, nodes=(*self.nodes, node))

    def add_prerequisite(self, edge: PrerequisiteEdge) -> CurriculumVersion:
        self._require_draft()
        return replace(self, prerequisites=(*self.prerequisites, edge))

    def _require_draft(self) -> None:
        if self.status is not CurriculumStatus.DRAFT:
            raise ValueError("only a draft curriculum can be edited")

    def retire(self, retired_at: datetime) -> CurriculumVersion:
        if self.status is not CurriculumStatus.ACTIVE:
            raise ValueError("only an active curriculum can be retired")
        return replace(
            self,
            status=CurriculumStatus.RETIRED,
            retired_at=_utc(retired_at),
        )
