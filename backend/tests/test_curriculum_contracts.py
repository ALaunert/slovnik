from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from uuid import UUID

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from app.domain.curriculum import (
    CurriculumNode,
    CurriculumStatus,
    CurriculumVersion,
    PrerequisiteEdge,
    PrerequisiteKind,
)
from app.domain.shared import Capability, Modality, TargetKind
from app.domain.target import TargetSpec
from app.domain_models.curriculum import CurriculumVersionRecord
from app.repositories.curriculum import CurriculumRepository


VERSION_ID = "26de741a-e1d9-4cc2-84d0-ea8e935b19bc"
NODE_ID = "f2534952-ed61-40c3-a3f5-b2217b24ab58"
OTHER_NODE_ID = "cf0d3b45-1383-4538-87a8-dcd4727b7a12"
TARGET_ID = "e44ed2cf-f691-4acc-bd6c-34510a55a976"
EDGE_ID = "59cba753-9e44-445b-87df-c34f3d0513c1"
OTHER_EDGE_ID = "4d625af6-19ce-4cb6-96ad-5e4179f25395"
OTHER_VERSION_ID = "5754a99e-c569-4724-980a-1a23e49b9b59"
NOW = datetime(2026, 8, 26, 10, 0, tzinfo=timezone.utc)
PUBLISHED_AT = datetime(2026, 8, 26, 11, 0, tzinfo=timezone.utc)
RETIRED_AT = datetime(2026, 8, 27, 11, 0, tzinfo=timezone.utc)


def _target(*, condition: dict[str, object] | None = None) -> TargetSpec:
    return TargetSpec(
        target_kind=TargetKind.SENSE,
        target_id=TARGET_ID,
        capability=Capability.RECOGNIZE_MEANING,
        modality=Modality.WRITTEN,
        condition=condition or {},
    )


def _node(
    *,
    node_id: str = NODE_ID,
    version_id: str = VERSION_ID,
    target: TargetSpec | None = None,
    priority: int = 50,
    outcome_code: str = "A1.location.basic",
) -> CurriculumNode:
    return CurriculumNode(
        id=node_id,
        curriculum_version_id=version_id,
        target=target or _target(),
        priority=priority,
        outcome_code=outcome_code,
    )


def _edge(
    *,
    edge_id: str = EDGE_ID,
    version_id: str = VERSION_ID,
    prerequisite_node_id: str = NODE_ID,
    dependent_node_id: str = OTHER_NODE_ID,
    kind: PrerequisiteKind = PrerequisiteKind.HARD,
) -> PrerequisiteEdge:
    return PrerequisiteEdge(
        id=edge_id,
        curriculum_version_id=version_id,
        prerequisite_node_id=prerequisite_node_id,
        dependent_node_id=dependent_node_id,
        kind=kind,
    )


def test_draft_version_has_stable_identity_code_and_version() -> None:
    version = CurriculumVersion(
        id=VERSION_ID,
        curriculum_code="serbian-core",
        version_number=1,
        created_at=NOW,
    )

    assert str(UUID(version.id)) == version.id
    assert version.curriculum_code == "serbian-core"
    assert version.version_number == 1
    assert version.status is CurriculumStatus.DRAFT
    assert version.nodes == ()
    assert version.prerequisites == ()


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("id", "not-a-uuid"),
        ("curriculum_code", ""),
        ("version_number", 0),
    ],
)
def test_draft_version_rejects_invalid_identity_fields(
    field_name: str, value: object
) -> None:
    values: dict[str, object] = {
        "id": VERSION_ID,
        "curriculum_code": "serbian-core",
        "version_number": 1,
        "created_at": NOW,
    }
    values[field_name] = value

    with pytest.raises(ValueError):
        CurriculumVersion(**values)


@pytest.mark.parametrize("priority", [-1, 101, True])
def test_node_rejects_priority_outside_integer_range(priority: object) -> None:
    with pytest.raises(ValueError, match="priority"):
        _node(priority=priority)


@pytest.mark.parametrize(
    "outcome_code",
    ["A0.location", "A1", "A1.", "a1.location"],
)
def test_node_rejects_invalid_outcome_code(outcome_code: str) -> None:
    with pytest.raises(ValueError, match="outcome_code"):
        _node(outcome_code=outcome_code)


def test_version_rejects_duplicate_target_key() -> None:
    first = _node()
    duplicate = _node(node_id=OTHER_NODE_ID)

    with pytest.raises(ValueError, match="target_key"):
        CurriculumVersion(
            id=VERSION_ID,
            curriculum_code="serbian-core",
            version_number=1,
            created_at=NOW,
            nodes=(first, duplicate),
        )


def test_version_rejects_duplicate_node_id_even_for_distinct_targets() -> None:
    first = _node()
    duplicate_id = _node(target=_target(condition={"sense": 2}))

    with pytest.raises(ValueError, match="node id"):
        CurriculumVersion(
            id=VERSION_ID,
            curriculum_code="serbian-core",
            version_number=1,
            created_at=NOW,
            nodes=(first, duplicate_id),
        )


def test_edge_rejects_self_reference() -> None:
    with pytest.raises(ValueError, match="itself"):
        _edge(dependent_node_id=NODE_ID)


@pytest.mark.parametrize(
    "edge",
    [
        _edge(version_id=OTHER_VERSION_ID),
        _edge(dependent_node_id="2935b225-9de1-4d2b-83e7-aa1f248e5ca0"),
    ],
)
def test_version_rejects_edge_outside_its_owned_nodes(edge: PrerequisiteEdge) -> None:
    nodes = (
        _node(),
        _node(node_id=OTHER_NODE_ID, target=_target(condition={"sense": 2})),
    )

    with pytest.raises(ValueError, match="belong|endpoint"):
        CurriculumVersion(
            id=VERSION_ID,
            curriculum_code="serbian-core",
            version_number=1,
            created_at=NOW,
            nodes=nodes,
            prerequisites=(edge,),
        )


def test_version_rejects_two_edge_kinds_for_same_directed_pair() -> None:
    nodes = (
        _node(),
        _node(node_id=OTHER_NODE_ID, target=_target(condition={"sense": 2})),
    )

    with pytest.raises(ValueError, match="one prerequisite edge"):
        CurriculumVersion(
            id=VERSION_ID,
            curriculum_code="serbian-core",
            version_number=1,
            created_at=NOW,
            nodes=nodes,
            prerequisites=(
                _edge(),
                _edge(edge_id=OTHER_EDGE_ID, kind=PrerequisiteKind.SOFT),
            ),
        )


@pytest.mark.parametrize(
    ("status", "published_at", "retired_at"),
    [
        (CurriculumStatus.DRAFT, PUBLISHED_AT, None),
        (CurriculumStatus.DRAFT, None, RETIRED_AT),
        (CurriculumStatus.ACTIVE, None, None),
        (CurriculumStatus.ACTIVE, PUBLISHED_AT, RETIRED_AT),
        (CurriculumStatus.RETIRED, None, RETIRED_AT),
        (CurriculumStatus.RETIRED, PUBLISHED_AT, None),
        (
            CurriculumStatus.ACTIVE,
            datetime(2026, 8, 26, 9, 0, tzinfo=timezone.utc),
            None,
        ),
        (
            CurriculumStatus.RETIRED,
            PUBLISHED_AT,
            datetime(2026, 8, 26, 10, 30, tzinfo=timezone.utc),
        ),
    ],
)
def test_version_rejects_lifecycle_timestamp_masquerades(
    status: CurriculumStatus,
    published_at: datetime | None,
    retired_at: datetime | None,
) -> None:
    with pytest.raises(ValueError, match="lifecycle"):
        CurriculumVersion(
            id=VERSION_ID,
            curriculum_code="serbian-core",
            version_number=1,
            created_at=NOW,
            status=status,
            published_at=published_at,
            retired_at=retired_at,
        )


def test_draft_edit_returns_a_new_graph_and_defensively_copies_sequences() -> None:
    caller_nodes: list[CurriculumNode] = []
    draft = CurriculumVersion(
        id=VERSION_ID,
        curriculum_code="serbian-core",
        version_number=1,
        created_at=NOW,
        nodes=caller_nodes,
    )

    caller_nodes.append(_node())
    edited = draft.add_node(_node())

    assert draft.nodes == ()
    assert edited.nodes == (_node(),)


def test_draft_can_add_a_valid_prerequisite_without_mutating_original() -> None:
    nodes = (
        _node(),
        _node(node_id=OTHER_NODE_ID, target=_target(condition={"sense": 2})),
    )
    draft = CurriculumVersion(
        id=VERSION_ID,
        curriculum_code="serbian-core",
        version_number=1,
        created_at=NOW,
        nodes=nodes,
    )

    edited = draft.add_prerequisite(_edge())

    assert draft.prerequisites == ()
    assert edited.prerequisites == (_edge(),)


def test_active_and_retired_snapshots_reject_graph_or_content_mutation() -> None:
    active = CurriculumVersion(
        id=VERSION_ID,
        curriculum_code="serbian-core",
        version_number=1,
        created_at=NOW,
        status=CurriculumStatus.ACTIVE,
        published_at=PUBLISHED_AT,
        nodes=(_node(),),
    )

    with pytest.raises(ValueError, match="draft"):
        active.add_node(
            _node(node_id=OTHER_NODE_ID, target=_target(condition={"sense": 2}))
        )
    with pytest.raises(FrozenInstanceError):
        active.nodes[0].priority = 99  # type: ignore[misc]

    retired = active.retire(RETIRED_AT)
    assert retired.status is CurriculumStatus.RETIRED
    assert retired.published_at == PUBLISHED_AT
    assert retired.retired_at == RETIRED_AT
    with pytest.raises(ValueError, match="active"):
        retired.retire(RETIRED_AT)


def test_draft_cannot_transition_directly_to_retired() -> None:
    draft = CurriculumVersion(
        id=VERSION_ID,
        curriculum_code="serbian-core",
        version_number=1,
        created_at=NOW,
    )

    with pytest.raises(ValueError, match="active"):
        draft.retire(RETIRED_AT)


class _FailingTargetResolver:
    def __init__(self) -> None:
        self.calls = 0

    def is_published(self, target: TargetSpec) -> bool:
        self.calls += 1
        raise AssertionError(f"draft storage must not resolve {target.target_key}")


class _PublishedTargetResolver:
    def __init__(self) -> None:
        self.resolved: list[str] = []

    def is_published(self, target: TargetSpec) -> bool:
        self.resolved.append(target.target_key)
        return True


def test_repository_exposes_only_the_fake_target_resolver_contract() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    resolver = _PublishedTargetResolver()
    target = _target()

    with Session(engine) as session:
        repository = CurriculumRepository(session, resolver)
        assert repository.target_is_published(target) is True

    assert resolver.resolved == [target.target_key]


def test_curriculum_orm_matches_sql_01_and_round_trips_a_draft_graph() -> None:
    from app.db import Base

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    expected_columns = {
        "curriculum_versions": {
            "id",
            "curriculum_code",
            "version_number",
            "status",
            "created_at",
            "published_at",
            "retired_at",
        },
        "curriculum_nodes": {
            "id",
            "curriculum_version_id",
            "target_key",
            "target_kind",
            "target_id",
            "capability",
            "modality",
            "condition_payload",
            "priority",
            "outcome_code",
        },
        "curriculum_prerequisites": {
            "id",
            "curriculum_version_id",
            "prerequisite_node_id",
            "dependent_node_id",
            "kind",
        },
    }
    inspector = inspect(engine)
    assert {
        table: {column["name"] for column in inspector.get_columns(table)}
        for table in expected_columns
    } == expected_columns
    prerequisite_fks = inspector.get_foreign_keys("curriculum_prerequisites")
    assert {
        (tuple(fk["constrained_columns"]), tuple(fk["referred_columns"]))
        for fk in prerequisite_fks
    } >= {
        (("curriculum_version_id",), ("id",)),
        (
            ("curriculum_version_id", "prerequisite_node_id"),
            ("curriculum_version_id", "id"),
        ),
        (
            ("curriculum_version_id", "dependent_node_id"),
            ("curriculum_version_id", "id"),
        ),
    }

    nodes = (
        _node(target=_target(condition={"register": ["neutral", {"case": "nom"}]})),
        _node(node_id=OTHER_NODE_ID, target=_target(condition={"sense": 2})),
    )
    draft = CurriculumVersion(
        id=VERSION_ID,
        curriculum_code="serbian-core",
        version_number=1,
        created_at=NOW,
        nodes=nodes,
        prerequisites=(_edge(),),
    )
    resolver = _FailingTargetResolver()
    with Session(engine) as session:
        repository = CurriculumRepository(session, resolver)
        repository.add(draft)
        session.commit()
        session.expunge_all()
        returned = repository.get(VERSION_ID)

        assert returned == draft
        assert returned is not None
        assert returned.status is CurriculumStatus.DRAFT
        assert returned.published_at is None
        assert returned.retired_at is None
        returned_nested_node = next(node for node in returned.nodes if node.id == NODE_ID)
        assert returned_nested_node.target.to_payload()["condition"] == {
            "register": ["neutral", {"case": "nom"}]
        }
        assert not isinstance(returned, CurriculumVersionRecord)
        assert isinstance(session.get(CurriculumVersionRecord, VERSION_ID), CurriculumVersionRecord)
        assert repository.get_by_code_version("serbian-core", 1) == draft
        assert resolver.calls == 0
