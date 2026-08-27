from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.domain.catalog import RetirementPolicyDecision
from app.domain.curriculum_policy import (
    CurriculumFrontierPolicy,
    FrontierAvailability,
    FrontierReason,
)
from app.domain.curriculum import (
    CurriculumNode,
    CurriculumStatus,
    CurriculumVersion,
    PrerequisiteEdge,
    PrerequisiteKind,
)
from app.domain.shared import Capability, Modality, TargetKind
from app.domain.target import TargetSpec
from app.repositories.curriculum import CurriculumRepository
from app.services import curriculum_service as curriculum_service_module
from app.services.curriculum_service import CurriculumService


NOW = datetime(2026, 8, 27, 9, 0, tzinfo=timezone.utc)
VERSION_ID = "11111111-1111-4111-8111-111111111111"
NODE_A_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
NODE_B_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
NODE_C_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
TARGET_A_ID = "10000000-0000-4000-8000-000000000001"
TARGET_B_ID = "10000000-0000-4000-8000-000000000002"
TARGET_C_ID = "10000000-0000-4000-8000-000000000003"


def _target(target_id: str = TARGET_A_ID) -> TargetSpec:
    return TargetSpec(
        target_kind=TargetKind.SENSE,
        target_id=target_id,
        capability=Capability.RECOGNIZE_MEANING,
        modality=Modality.WRITTEN,
    )


def _node(
    node_id: str = NODE_A_ID,
    target_id: str = TARGET_A_ID,
    *,
    version_id: str = VERSION_ID,
    priority: int = 50,
    outcome_code: str = "A1.core",
) -> CurriculumNode:
    return CurriculumNode(
        id=node_id,
        curriculum_version_id=version_id,
        target=_target(target_id),
        priority=priority,
        outcome_code=outcome_code,
    )


def _edge(
    edge_id: str,
    prerequisite_node_id: str,
    dependent_node_id: str,
    *,
    kind: PrerequisiteKind = PrerequisiteKind.HARD,
    version_id: str = VERSION_ID,
) -> PrerequisiteEdge:
    return PrerequisiteEdge(
        id=edge_id,
        curriculum_version_id=version_id,
        prerequisite_node_id=prerequisite_node_id,
        dependent_node_id=dependent_node_id,
        kind=kind,
    )


def _draft(
    *,
    version_id: str = VERSION_ID,
    version_number: int = 1,
    nodes: tuple[CurriculumNode, ...] | None = None,
    prerequisites: tuple[PrerequisiteEdge, ...] = (),
) -> CurriculumVersion:
    return CurriculumVersion(
        id=version_id,
        curriculum_code="serbian-core",
        version_number=version_number,
        created_at=NOW,
        nodes=nodes if nodes is not None else (_node(version_id=version_id),),
        prerequisites=prerequisites,
    )


@pytest.mark.parametrize("catalog_state", ["missing", "draft", "retired"])
def test_publication_requires_every_target_to_resolve_as_published(
    catalog_state: str,
) -> None:
    draft = _draft()

    with pytest.raises(ValueError, match="published target"):
        draft.publish(
            published_at=NOW,
            target_is_published=lambda _target: catalog_state == "published",
        )


def test_valid_draft_publishes_an_immutable_active_snapshot() -> None:
    draft = _draft()

    published = draft.publish(
        published_at=NOW,
        target_is_published=lambda _target: True,
    )

    assert published.status is CurriculumStatus.ACTIVE
    assert published.published_at == NOW
    assert published.retired_at is None
    with pytest.raises(ValueError, match="draft"):
        published.add_node(
            _node(NODE_B_ID, TARGET_B_ID, version_id=published.id)
        )


def test_publication_rejects_a_hard_prerequisite_cycle() -> None:
    nodes = (
        _node(NODE_A_ID, TARGET_A_ID),
        _node(NODE_B_ID, TARGET_B_ID),
        _node(NODE_C_ID, TARGET_C_ID),
    )
    draft = _draft(
        nodes=nodes,
        prerequisites=(
            _edge(
                "20000000-0000-4000-8000-000000000001",
                NODE_A_ID,
                NODE_B_ID,
            ),
            _edge(
                "20000000-0000-4000-8000-000000000002",
                NODE_B_ID,
                NODE_C_ID,
            ),
            _edge(
                "20000000-0000-4000-8000-000000000003",
                NODE_C_ID,
                NODE_A_ID,
            ),
        ),
    )

    with pytest.raises(ValueError, match="HARD prerequisite graph must be acyclic"):
        draft.publish(
            published_at=NOW,
            target_is_published=lambda _target: True,
        )


def test_publication_allows_a_soft_prerequisite_cycle() -> None:
    nodes = (
        _node(NODE_A_ID, TARGET_A_ID),
        _node(NODE_B_ID, TARGET_B_ID),
    )
    draft = _draft(
        nodes=nodes,
        prerequisites=(
            _edge(
                "20000000-0000-4000-8000-000000000004",
                NODE_A_ID,
                NODE_B_ID,
                kind=PrerequisiteKind.SOFT,
            ),
            _edge(
                "20000000-0000-4000-8000-000000000005",
                NODE_B_ID,
                NODE_A_ID,
                kind=PrerequisiteKind.SOFT,
            ),
        ),
    )

    published = draft.publish(
        published_at=NOW,
        target_is_published=lambda _target: True,
    )

    assert published.status is CurriculumStatus.ACTIVE


@pytest.mark.parametrize(
    "corruption",
    [
        "duplicate_node",
        "invalid_priority",
        "invalid_outcome",
        "cross_version_node",
        "self_edge",
        "double_kind_edge",
    ],
)
def test_publication_revalidates_the_complete_draft_graph(corruption: str) -> None:
    node_a = _node(NODE_A_ID, TARGET_A_ID)
    node_b = _node(NODE_B_ID, TARGET_B_ID)
    edge = _edge(
        "20000000-0000-4000-8000-000000000006",
        NODE_A_ID,
        NODE_B_ID,
    )
    draft = _draft(nodes=(node_a, node_b), prerequisites=(edge,))

    if corruption == "duplicate_node":
        object.__setattr__(node_b, "id", NODE_A_ID)
    elif corruption == "invalid_priority":
        object.__setattr__(node_b, "priority", 101)
    elif corruption == "invalid_outcome":
        object.__setattr__(node_b, "outcome_code", "A0.invalid")
    elif corruption == "cross_version_node":
        object.__setattr__(node_b, "curriculum_version_id", TARGET_C_ID)
    elif corruption == "self_edge":
        object.__setattr__(edge, "dependent_node_id", NODE_A_ID)
    else:
        duplicate_edge = _edge(
            "20000000-0000-4000-8000-000000000007",
            NODE_A_ID,
            NODE_B_ID,
            kind=PrerequisiteKind.SOFT,
        )
        object.__setattr__(draft, "prerequisites", (edge, duplicate_edge))

    with pytest.raises(ValueError):
        draft.publish(
            published_at=NOW,
            target_is_published=lambda _target: True,
        )


class _TargetResolver:
    def __init__(self, published_target_ids: set[str]) -> None:
        self.published_target_ids = published_target_ids

    def is_published(self, target: TargetSpec) -> bool:
        return target.target_id in self.published_target_ids


@pytest.fixture()
def curriculum_engine():
    from app.db import Base

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


def test_replacement_activation_retires_previous_and_keeps_history_readable(
    curriculum_engine,
) -> None:
    resolver = _TargetResolver({TARGET_A_ID, TARGET_B_ID})
    version_two_id = "22222222-2222-4222-8222-222222222222"
    first = _draft()
    second = _draft(
        version_id=version_two_id,
        version_number=2,
        nodes=(
            _node(
                NODE_B_ID,
                TARGET_B_ID,
                version_id=version_two_id,
            ),
        ),
    )
    with Session(curriculum_engine) as session:
        repository = CurriculumRepository(session, resolver)
        repository.add(first)
        repository.add(second)
        session.commit()

        service = CurriculumService(session, resolver)
        activated_first = service.publish(first.id, published_at=NOW)
        activated_second = service.publish(
            second.id,
            published_at=NOW + timedelta(hours=1),
        )

        historical_first = repository.get(first.id)
        persisted_second = repository.get(second.id)

    assert activated_first.status is CurriculumStatus.ACTIVE
    assert activated_second.status is CurriculumStatus.ACTIVE
    assert historical_first is not None
    assert historical_first.status is CurriculumStatus.RETIRED
    assert historical_first.retired_at == NOW + timedelta(hours=1)
    assert persisted_second == activated_second


def test_replacement_publication_cannot_predate_the_current_active_version(
    curriculum_engine,
) -> None:
    resolver = _TargetResolver({TARGET_A_ID, TARGET_B_ID})
    version_two_id = "22222222-2222-4222-8222-222222222222"
    created_at = NOW - timedelta(days=2)
    first = CurriculumVersion(
        id=VERSION_ID,
        curriculum_code="serbian-core",
        version_number=1,
        created_at=created_at,
        nodes=(_node(),),
    )
    second = CurriculumVersion(
        id=version_two_id,
        curriculum_code="serbian-core",
        version_number=2,
        created_at=created_at,
        nodes=(_node(NODE_B_ID, TARGET_B_ID, version_id=version_two_id),),
    )
    with Session(curriculum_engine) as session:
        repository = CurriculumRepository(session, resolver)
        repository.add(first)
        repository.add(second)
        session.commit()
        service = CurriculumService(session, resolver)
        service.publish(first.id, published_at=NOW)

        with pytest.raises(ValueError, match="current active publication"):
            service.publish(
                second.id,
                published_at=NOW - timedelta(hours=1),
            )

        assert repository.get(first.id).status is CurriculumStatus.ACTIVE
        assert repository.get(second.id).status is CurriculumStatus.DRAFT


def test_replacement_version_number_must_increase(
    curriculum_engine,
) -> None:
    resolver = _TargetResolver({TARGET_A_ID, TARGET_B_ID})
    replacement_id = "22222222-2222-4222-8222-222222222222"
    active = _draft(version_number=2)
    replacement = _draft(
        version_id=replacement_id,
        version_number=1,
        nodes=(
            _node(
                NODE_B_ID,
                TARGET_B_ID,
                version_id=replacement_id,
            ),
        ),
    )
    with Session(curriculum_engine) as session:
        repository = CurriculumRepository(session, resolver)
        repository.add(active)
        repository.add(replacement)
        session.commit()
        service = CurriculumService(session, resolver)
        service.publish(active.id, published_at=NOW)

        with pytest.raises(ValueError, match="version_number"):
            service.publish(
                replacement.id,
                published_at=NOW + timedelta(hours=1),
            )

        assert repository.get(active.id).status is CurriculumStatus.ACTIVE
        assert repository.get(replacement.id).status is CurriculumStatus.DRAFT


def test_failed_replacement_publication_is_atomic(curriculum_engine) -> None:
    resolver = _TargetResolver({TARGET_A_ID})
    version_two_id = "22222222-2222-4222-8222-222222222222"
    first = _draft()
    invalid_second = _draft(
        version_id=version_two_id,
        version_number=2,
        nodes=(
            _node(
                NODE_B_ID,
                TARGET_B_ID,
                version_id=version_two_id,
            ),
        ),
    )
    with Session(curriculum_engine) as session:
        repository = CurriculumRepository(session, resolver)
        repository.add(first)
        repository.add(invalid_second)
        session.commit()
        service = CurriculumService(session, resolver)
        service.publish(first.id, published_at=NOW)

        with pytest.raises(ValueError, match="published target"):
            service.publish(
                invalid_second.id,
                published_at=NOW + timedelta(hours=1),
            )

        assert repository.get(first.id).status is CurriculumStatus.ACTIVE
        assert repository.get(invalid_second.id).status is CurriculumStatus.DRAFT


def test_failed_activation_rolls_back_the_flushed_retirement(
    curriculum_engine,
    monkeypatch,
) -> None:
    resolver = _TargetResolver({TARGET_A_ID, TARGET_B_ID})
    replacement_id = "22222222-2222-4222-8222-222222222222"
    first = _draft()
    replacement = _draft(
        version_id=replacement_id,
        version_number=2,
        nodes=(
            _node(
                NODE_B_ID,
                TARGET_B_ID,
                version_id=replacement_id,
            ),
        ),
    )
    retirement_was_flushed = False
    rollback_was_called = False

    with Session(curriculum_engine) as session:
        repository = CurriculumRepository(session, resolver)
        repository.add(first)
        repository.add(replacement)
        session.commit()
        service = CurriculumService(session, resolver)
        service.publish(first.id, published_at=NOW)
        original_rollback = session.rollback

        def track_rollback() -> None:
            nonlocal rollback_was_called
            rollback_was_called = True
            original_rollback()

        monkeypatch.setattr(session, "rollback", track_rollback)

        def fail_activation(
            failing_repository,
            version_id: str,
            published_at: datetime,
        ) -> bool:
            nonlocal retirement_was_flushed
            del version_id, published_at
            persisted_first = failing_repository.get(first.id)
            assert persisted_first is not None
            assert persisted_first.status is CurriculumStatus.RETIRED
            retirement_was_flushed = True
            raise RuntimeError("injected activation failure")

        monkeypatch.setattr(
            CurriculumRepository,
            "activate_if_draft",
            fail_activation,
        )

        with pytest.raises(RuntimeError, match="injected activation failure"):
            service.publish(
                replacement.id,
                published_at=NOW + timedelta(hours=1),
            )

    assert retirement_was_flushed is True
    assert rollback_was_called is True
    with Session(curriculum_engine) as fresh_session:
        fresh_repository = CurriculumRepository(fresh_session, resolver)
        persisted_first = fresh_repository.get(first.id)
        persisted_replacement = fresh_repository.get(replacement.id)

        assert persisted_first is not None
        assert persisted_first.status is CurriculumStatus.ACTIVE
        assert persisted_replacement is not None
        assert persisted_replacement.status is CurriculumStatus.DRAFT


def test_repository_rejects_direct_storage_of_an_unvalidated_active_graph(
    curriculum_engine,
) -> None:
    nodes = (
        _node(NODE_A_ID, TARGET_A_ID),
        _node(NODE_B_ID, TARGET_B_ID),
    )
    manually_active = CurriculumVersion(
        id=VERSION_ID,
        curriculum_code="serbian-core",
        version_number=1,
        created_at=NOW,
        status=CurriculumStatus.ACTIVE,
        published_at=NOW,
        nodes=nodes,
        prerequisites=(
            _edge(
                "20000000-0000-4000-8000-000000000010",
                NODE_A_ID,
                NODE_B_ID,
            ),
            _edge(
                "20000000-0000-4000-8000-000000000011",
                NODE_B_ID,
                NODE_A_ID,
            ),
        ),
    )
    resolver = _TargetResolver(set())

    with Session(curriculum_engine) as session:
        repository = CurriculumRepository(session, resolver)

        with pytest.raises(ValueError, match="draft"):
            repository.add(manually_active)

        assert repository.get(manually_active.id) is None


def test_active_reference_blocks_retirement_until_replacement(curriculum_engine) -> None:
    resolver = _TargetResolver({TARGET_A_ID, TARGET_B_ID})
    version_two_id = "22222222-2222-4222-8222-222222222222"
    first = _draft()
    replacement = _draft(
        version_id=version_two_id,
        version_number=2,
        nodes=(
            _node(
                NODE_B_ID,
                TARGET_B_ID,
                version_id=version_two_id,
            ),
        ),
    )
    with Session(curriculum_engine) as session:
        repository = CurriculumRepository(session, resolver)
        repository.add(first)
        repository.add(replacement)
        session.commit()
        service = CurriculumService(session, resolver)
        service.publish(first.id, published_at=NOW)

        assert (
            service.retirement_policy_for(_target(TARGET_A_ID))
            is RetirementPolicyDecision.ACTIVE_REFERENCE
        )
        same_content_other_capability = TargetSpec(
            target_kind=TargetKind.SENSE,
            target_id=TARGET_A_ID,
            capability=Capability.RETRIEVE_FORM,
            modality=Modality.WRITTEN,
        )
        assert (
            service.retirement_policy_for(same_content_other_capability)
            is RetirementPolicyDecision.ACTIVE_REFERENCE
        )

        service.publish(
            replacement.id,
            published_at=NOW + timedelta(hours=1),
        )
        assert (
            service.retirement_policy_for(_target(TARGET_A_ID))
            is RetirementPolicyDecision.ALLOWED
        )


@pytest.fixture()
def postgresql_curriculum_engine():
    admin_url_value = os.getenv("SLOVNIK_TEST_POSTGRES_ADMIN_URL")
    if not admin_url_value:
        pytest.skip("SLOVNIK_TEST_POSTGRES_ADMIN_URL is not configured")
    admin_url = make_url(admin_url_value)
    if admin_url.get_backend_name() != "postgresql":
        raise ValueError("SLOVNIK_TEST_POSTGRES_ADMIN_URL must use PostgreSQL")

    database_name = f"slovnik_curriculum_test_{uuid4().hex}"
    test_database_url = admin_url.set(database=database_name)
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    database_created = False
    test_engine = None
    try:
        with admin_engine.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{database_name}"'))
        database_created = True
        test_engine = create_engine(test_database_url)

        from app.domain_models.curriculum import (
            CurriculumNodeRecord,
            CurriculumPrerequisiteRecord,
            CurriculumVersionRecord,
        )

        CurriculumVersionRecord.__table__.create(test_engine)
        CurriculumNodeRecord.__table__.create(test_engine)
        CurriculumPrerequisiteRecord.__table__.create(test_engine)
        yield test_engine
    finally:
        if test_engine is not None:
            test_engine.dispose()
        if database_created:
            with admin_engine.connect() as connection:
                connection.execute(
                    text(
                        """
                        SELECT pg_terminate_backend(pid)
                        FROM pg_stat_activity
                        WHERE datname = :database_name
                          AND pid <> pg_backend_pid()
                        """
                    ),
                    {"database_name": database_name},
                )
                connection.execute(text(f'DROP DATABASE "{database_name}"'))
        admin_engine.dispose()


@pytest.mark.parametrize("has_existing_active", [False, True])
def test_postgresql_concurrent_publication_has_one_winner_and_one_active(
    postgresql_curriculum_engine,
    monkeypatch,
    has_existing_active: bool,
) -> None:
    from app.domain_models.curriculum import CurriculumVersionRecord

    resolver = _TargetResolver({TARGET_A_ID, TARGET_B_ID})
    replacement_id = "22222222-2222-4222-8222-222222222222"
    candidate = _draft(
        version_id=replacement_id if has_existing_active else VERSION_ID,
        version_number=2 if has_existing_active else 1,
        nodes=(
            _node(
                NODE_B_ID if has_existing_active else NODE_A_ID,
                TARGET_B_ID if has_existing_active else TARGET_A_ID,
                version_id=replacement_id if has_existing_active else VERSION_ID,
            ),
        ),
    )
    SessionFactory = sessionmaker(bind=postgresql_curriculum_engine)
    with SessionFactory() as session:
        repository = CurriculumRepository(session, resolver)
        if has_existing_active:
            repository.add(_draft())
        repository.add(candidate)
        session.commit()
        if has_existing_active:
            CurriculumService(session, resolver).publish(VERSION_ID, published_at=NOW)

    original_get_active = CurriculumRepository.get_active_by_code
    start = threading.Barrier(2)

    def synchronized_get_active(repository, curriculum_code: str):
        active = original_get_active(repository, curriculum_code)
        start.wait(timeout=10)
        return active

    monkeypatch.setattr(
        CurriculumRepository,
        "get_active_by_code",
        synchronized_get_active,
    )

    def publish() -> str:
        with SessionFactory() as session:
            try:
                CurriculumService(session, resolver).publish(
                    candidate.id,
                    published_at=NOW + timedelta(hours=1),
                )
            except curriculum_service_module.CurriculumActivationConflict:
                return "conflict"
            return "published"

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(publish) for _ in range(2)]
        outcomes = [future.result(timeout=30) for future in futures]

    with SessionFactory() as session:
        active_ids = session.scalars(
            select(CurriculumVersionRecord.id).where(
                CurriculumVersionRecord.status == CurriculumStatus.ACTIVE.value
            )
        ).all()

    assert sorted(outcomes) == ["conflict", "published"]
    assert active_ids == [candidate.id]


@pytest.mark.parametrize("has_existing_active", [False, True])
def test_postgresql_concurrent_distinct_publications_have_one_winner(
    postgresql_curriculum_engine,
    monkeypatch,
    has_existing_active: bool,
) -> None:
    from app.domain_models.curriculum import CurriculumVersionRecord

    resolver = _TargetResolver({TARGET_A_ID, TARGET_B_ID, TARGET_C_ID})
    second_id = "22222222-2222-4222-8222-222222222222"
    third_id = "33333333-3333-4333-8333-333333333333"
    first = (
        _draft(
            version_id=second_id,
            version_number=2,
            nodes=(_node(NODE_B_ID, TARGET_B_ID, version_id=second_id),),
        )
        if has_existing_active
        else _draft()
    )
    second = _draft(
        version_id=third_id if has_existing_active else second_id,
        version_number=3 if has_existing_active else 2,
        nodes=(
            _node(
                NODE_C_ID if has_existing_active else NODE_B_ID,
                TARGET_C_ID if has_existing_active else TARGET_B_ID,
                version_id=third_id if has_existing_active else second_id,
            ),
        ),
    )
    SessionFactory = sessionmaker(bind=postgresql_curriculum_engine)
    with SessionFactory() as session:
        repository = CurriculumRepository(session, resolver)
        if has_existing_active:
            repository.add(_draft())
        repository.add(first)
        repository.add(second)
        session.commit()
        if has_existing_active:
            CurriculumService(session, resolver).publish(VERSION_ID, published_at=NOW)

    original_get_active = CurriculumRepository.get_active_by_code
    start = threading.Barrier(2)

    def synchronized_get_active(repository, curriculum_code: str):
        active = original_get_active(repository, curriculum_code)
        assert (active is not None) is has_existing_active
        start.wait(timeout=10)
        return active

    monkeypatch.setattr(
        CurriculumRepository,
        "get_active_by_code",
        synchronized_get_active,
    )

    def publish(version_id: str) -> str:
        with SessionFactory() as session:
            try:
                CurriculumService(session, resolver).publish(
                    version_id,
                    published_at=NOW,
                )
            except curriculum_service_module.CurriculumActivationConflict:
                return "conflict"
            return "published"

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(publish, version.id) for version in (first, second)]
        outcomes = [future.result(timeout=30) for future in futures]

    with SessionFactory() as session:
        active_ids = session.scalars(
            select(CurriculumVersionRecord.id).where(
                CurriculumVersionRecord.status == CurriculumStatus.ACTIVE.value
            )
        ).all()

    assert sorted(outcomes) == ["conflict", "published"]
    assert len(active_ids) == 1
    assert active_ids[0] in {first.id, second.id}


def test_frontier_marks_a_root_node_available_without_learner_state() -> None:
    curriculum = _draft().publish(
        published_at=NOW,
        target_is_published=lambda _target: True,
    )

    decisions = CurriculumFrontierPolicy().evaluate(
        curriculum,
        states_by_target_key={},
        requested_level="A1",
    )

    assert len(decisions) == 1
    assert decisions[0].node == curriculum.nodes[0]
    assert decisions[0].availability is FrontierAvailability.AVAILABLE
    assert decisions[0].reason_codes == (FrontierReason.READY,)
    assert decisions[0].policy_version == "frontier-v1"


def _state(
    *,
    evidence_count: int,
    success_weight: float,
    failure_weight: float = 0,
    peak: float,
    memory_due_at: datetime | None = None,
):
    return SimpleNamespace(
        evidence=SimpleNamespace(count=evidence_count),
        competence=SimpleNamespace(
            success_weight=success_weight,
            failure_weight=failure_weight,
            peak=peak,
        ),
        memory=SimpleNamespace(due_at=memory_due_at),
    )


def _hard_curriculum() -> CurriculumVersion:
    nodes = (
        _node(NODE_A_ID, TARGET_A_ID),
        _node(NODE_B_ID, TARGET_B_ID),
    )
    draft = _draft(
        nodes=nodes,
        prerequisites=(
            _edge(
                "20000000-0000-4000-8000-000000000008",
                NODE_A_ID,
                NODE_B_ID,
            ),
        ),
    )
    return draft.publish(
        published_at=NOW,
        target_is_published=lambda _target: True,
    )


@pytest.mark.parametrize(
    ("state", "reason"),
    [
        (None, FrontierReason.HARD_PREREQUISITE_MISSING_STATE),
        (
            _state(evidence_count=0, success_weight=0, peak=0),
            FrontierReason.HARD_PREREQUISITE_NO_NATIVE_EVIDENCE,
        ),
        (
            _state(evidence_count=1, success_weight=0, peak=0.5),
            FrontierReason.HARD_PREREQUISITE_NO_DETERMINISTIC_SUCCESS,
        ),
        (
            _state(evidence_count=1, success_weight=1, peak=0.59),
            FrontierReason.HARD_PREREQUISITE_BELOW_PEAK,
        ),
    ],
)
def test_frontier_blocks_unready_hard_prerequisites(state, reason) -> None:
    curriculum = _hard_curriculum()
    states = {} if state is None else {curriculum.nodes[0].target.target_key: state}

    decisions = CurriculumFrontierPolicy().evaluate(
        curriculum,
        states_by_target_key=states,
        requested_level="A1",
    )
    dependent = next(decision for decision in decisions if decision.node.id == NODE_B_ID)

    assert dependent.availability is FrontierAvailability.NOT_YET_READY
    assert dependent.reason_codes == (reason,)


def test_frontier_uses_peak_and_ignores_later_failure_or_overdue_memory() -> None:
    curriculum = _hard_curriculum()
    prerequisite = curriculum.nodes[0]
    state = _state(
        evidence_count=2,
        success_weight=1,
        failure_weight=1,
        peak=0.6,
        memory_due_at=NOW - timedelta(days=1),
    )

    decisions = CurriculumFrontierPolicy().evaluate(
        curriculum,
        states_by_target_key={prerequisite.target.target_key: state},
        requested_level="A1",
    )
    dependent = next(decision for decision in decisions if decision.node.id == NODE_B_ID)

    assert dependent.availability is FrontierAvailability.AVAILABLE
    assert dependent.reason_codes == (FrontierReason.READY,)


def test_frontier_consumes_projected_high_water_state_after_later_failure() -> None:
    from app.domain.progress import LearnerTargetState
    from app.services.learner_projection_service import project_event

    curriculum = _hard_curriculum()
    prerequisite = curriculum.nodes[0]
    state = LearnerTargetState.neutral(
        state_id="50000000-0000-4000-8000-000000000001",
        learner_id="learner-1",
        target_key=prerequisite.target.target_key,
        updated_at=NOW - timedelta(hours=3),
    )
    success = SimpleNamespace(
        event_id="60000000-0000-4000-8000-000000000001",
        learner_id="learner-1",
        target_key=prerequisite.target.target_key,
        occurred_at=NOW - timedelta(hours=2),
        event_type="response_evaluated",
        evaluation_source="deterministic",
        evaluation_outcome="correct",
        first_response=None,
    )
    failure = SimpleNamespace(
        event_id="60000000-0000-4000-8000-000000000002",
        learner_id="learner-1",
        target_key=prerequisite.target.target_key,
        occurred_at=NOW - timedelta(hours=1),
        event_type="response_evaluated",
        evaluation_source="deterministic",
        evaluation_outcome="incorrect",
        first_response=None,
    )
    projected = project_event(project_event(state, success), failure)

    decisions = CurriculumFrontierPolicy().evaluate(
        curriculum,
        states_by_target_key={prerequisite.target.target_key: projected},
        requested_level="A1",
    )
    dependent = next(
        decision for decision in decisions if decision.node.id == NODE_B_ID
    )

    assert projected.competence.peak == 2 / 3
    assert projected.competence.failure_weight == 1
    assert projected.memory.due_at == failure.occurred_at
    assert dependent.availability is FrontierAvailability.AVAILABLE
    assert dependent.reason_codes == (FrontierReason.READY,)
    assert dependent.policy_version == "frontier-v1"


@pytest.mark.parametrize("prerequisite_ready", [False, True])
def test_soft_prerequisite_only_contributes_readiness_metadata(
    prerequisite_ready: bool,
) -> None:
    nodes = (
        _node(NODE_A_ID, TARGET_A_ID),
        _node(NODE_B_ID, TARGET_B_ID),
    )
    curriculum = _draft(
        nodes=nodes,
        prerequisites=(
            _edge(
                "20000000-0000-4000-8000-000000000009",
                NODE_A_ID,
                NODE_B_ID,
                kind=PrerequisiteKind.SOFT,
            ),
        ),
    ).publish(
        published_at=NOW,
        target_is_published=lambda _target: True,
    )
    states = (
        {
            curriculum.nodes[0].target.target_key: _state(
                evidence_count=1,
                success_weight=1,
                peak=0.6,
            )
        }
        if prerequisite_ready
        else {}
    )

    decisions = CurriculumFrontierPolicy().evaluate(
        curriculum,
        states_by_target_key=states,
        requested_level="A1",
    )
    dependent = next(decision for decision in decisions if decision.node.id == NODE_B_ID)

    assert dependent.availability is FrontierAvailability.AVAILABLE
    assert dependent.soft_ready_count == int(prerequisite_ready)


def test_frontier_applies_cumulative_cefr_outcome_envelope() -> None:
    curriculum = _draft(
        nodes=(
            _node(NODE_A_ID, TARGET_A_ID, outcome_code="A1.root"),
            _node(NODE_B_ID, TARGET_B_ID, outcome_code="A2.next"),
            _node(NODE_C_ID, TARGET_C_ID, outcome_code="B1.future"),
        )
    ).publish(
        published_at=NOW,
        target_is_published=lambda _target: True,
    )

    decisions = CurriculumFrontierPolicy().evaluate(
        curriculum,
        states_by_target_key={},
        requested_level="A2",
    )
    by_node_id = {decision.node.id: decision for decision in decisions}

    assert by_node_id[NODE_A_ID].availability is FrontierAvailability.AVAILABLE
    assert by_node_id[NODE_B_ID].availability is FrontierAvailability.AVAILABLE
    assert (
        by_node_id[NODE_C_ID].availability
        is FrontierAvailability.NOT_YET_READY
    )
    assert by_node_id[NODE_C_ID].reason_codes == (
        FrontierReason.ABOVE_CEFR_ENVELOPE,
    )


@pytest.mark.parametrize("status", [CurriculumStatus.DRAFT, CurriculumStatus.RETIRED])
def test_frontier_requires_the_current_active_snapshot(status: CurriculumStatus) -> None:
    curriculum = _draft()
    if status is CurriculumStatus.RETIRED:
        curriculum = curriculum.publish(
            published_at=NOW,
            target_is_published=lambda _target: True,
        ).retire(NOW + timedelta(hours=1))

    with pytest.raises(ValueError, match="active curriculum"):
        CurriculumFrontierPolicy().evaluate(
            curriculum,
            states_by_target_key={},
            requested_level="A1",
        )


def test_frontier_rejects_unknown_cefr_envelope() -> None:
    curriculum = _draft().publish(
        published_at=NOW,
        target_is_published=lambda _target: True,
    )

    with pytest.raises(ValueError, match="requested_level"):
        CurriculumFrontierPolicy().evaluate(
            curriculum,
            states_by_target_key={},
            requested_level="A0",
        )
