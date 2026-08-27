from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid5

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.catalog import RetirementPolicyDecision
from app.domain.curriculum import (
    CurriculumNode,
    CurriculumStatus,
    CurriculumVersion,
    PrerequisiteEdge,
    PrerequisiteKind,
)
from app.domain.target import TargetSpec
from app.repositories.curriculum import CurriculumRepository, TargetResolver


PILOT_CURRICULUM_CODE = "serbian-from-russian"
PILOT_CURRICULUM_VERSION = 1
PILOT_NAMESPACE = UUID("557369ab-183e-5e79-b81d-d40c74173445")


@dataclass(frozen=True)
class PilotPrerequisite:
    prerequisite: TargetSpec
    dependent: TargetSpec
    kind: PrerequisiteKind


class CurriculumActivationConflict(RuntimeError):
    pass


def _constraint_name(error: IntegrityError) -> str | None:
    diagnostics = getattr(error.orig, "diag", None)
    constraint_name = getattr(diagnostics, "constraint_name", None)
    if constraint_name is None:
        constraint_name = getattr(error.orig, "constraint_name", None)
    return constraint_name


def _is_one_active_conflict(error: IntegrityError) -> bool:
    constraint_name = _constraint_name(error)
    if constraint_name is not None:
        return constraint_name == "uq_curriculum_versions_one_active"
    return str(error.orig) == (
        "UNIQUE constraint failed: curriculum_versions.curriculum_code"
    )


def _is_pilot_creation_conflict(error: IntegrityError) -> bool:
    constraint_name = _constraint_name(error)
    if constraint_name is not None:
        return constraint_name in {
            "curriculum_versions_pkey",
            "uq_curriculum_versions_code_number",
        }
    message = str(error.orig)
    return message in {
        "UNIQUE constraint failed: curriculum_versions.id",
        "UNIQUE constraint failed: curriculum_versions.curriculum_code, "
        "curriculum_versions.version_number",
    }


def _replacement_retired_at(
    active: CurriculumVersion,
    replacement: CurriculumVersion,
) -> datetime:
    if replacement.version_number <= active.version_number:
        raise ValueError(
            "replacement version_number must exceed the current active version"
        )
    active_published_at = active.published_at
    replacement_published_at = replacement.published_at
    if active_published_at is None or replacement_published_at is None:
        raise ValueError("replacement lifecycle must be published")
    if replacement_published_at < active_published_at:
        raise ValueError(
            "replacement cannot precede the current active publication"
        )
    retired_at = active.retire(replacement_published_at).retired_at
    assert retired_at is not None
    return retired_at


class CurriculumService:
    def __init__(self, session: Session, target_resolver: TargetResolver) -> None:
        self._session = session
        self._repository = CurriculumRepository(session, target_resolver)

    def bootstrap_technical_a1_pilot(
        self,
        *,
        bootstrap_at: datetime,
        targets: tuple[TargetSpec, ...] = (),
        prerequisites: tuple[PilotPrerequisite, ...] = (),
    ) -> CurriculumVersion:
        existing = self._repository.get_by_code_version(
            PILOT_CURRICULUM_CODE,
            PILOT_CURRICULUM_VERSION,
        )
        if existing is not None:
            return self._publish_pilot_if_ready(existing, bootstrap_at)
        version_id = str(
            uuid5(
                PILOT_NAMESPACE,
                f"{PILOT_CURRICULUM_CODE}:{PILOT_CURRICULUM_VERSION}",
            )
        )
        nodes = tuple(
            CurriculumNode(
                id=str(uuid5(PILOT_NAMESPACE, f"node:{target.target_key}")),
                curriculum_version_id=version_id,
                target=target,
                priority=50,
                outcome_code="A1.technical-pilot",
            )
            for target in targets
        )
        node_ids = {node.target.target_key: node.id for node in nodes}
        version = CurriculumVersion(
            id=version_id,
            curriculum_code=PILOT_CURRICULUM_CODE,
            version_number=PILOT_CURRICULUM_VERSION,
            created_at=bootstrap_at,
            nodes=nodes,
            prerequisites=tuple(
                PrerequisiteEdge(
                    id=str(
                        uuid5(
                            PILOT_NAMESPACE,
                            "edge:"
                            f"{prerequisite.kind.value}:"
                            f"{prerequisite.prerequisite.target_key}:"
                            f"{prerequisite.dependent.target_key}",
                        )
                    ),
                    curriculum_version_id=version_id,
                    prerequisite_node_id=node_ids[
                        prerequisite.prerequisite.target_key
                    ],
                    dependent_node_id=node_ids[prerequisite.dependent.target_key],
                    kind=prerequisite.kind,
                )
                for prerequisite in prerequisites
            ),
        )
        try:
            self._repository.add(version)
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            if not _is_pilot_creation_conflict(exc):
                raise
            existing = self._repository.get_by_code_version(
                PILOT_CURRICULUM_CODE,
                PILOT_CURRICULUM_VERSION,
            )
            if existing is None or existing.id != version.id:
                raise
            version = existing
        return self._publish_pilot_if_ready(version, bootstrap_at)

    def _publish_pilot_if_ready(
        self,
        version: CurriculumVersion,
        bootstrap_at: datetime,
    ) -> CurriculumVersion:
        if version.status is not CurriculumStatus.DRAFT:
            return version
        if any(
            not self._repository.target_is_published(node.target)
            for node in version.nodes
        ):
            return version
        try:
            return self.publish(version.id, published_at=bootstrap_at)
        except CurriculumActivationConflict:
            recovered = self._repository.get_by_code_version(
                PILOT_CURRICULUM_CODE,
                PILOT_CURRICULUM_VERSION,
            )
            if (
                recovered is not None
                and recovered.id == version.id
                and recovered.status is CurriculumStatus.ACTIVE
            ):
                return recovered
            raise

    def publish(
        self,
        version_id: str,
        *,
        published_at: datetime,
    ) -> CurriculumVersion:
        try:
            draft, published = self._validated_publication(
                version_id, published_at
            )
            active = self._repository.get_active_by_code(draft.curriculum_code)
            if active is not None and active.id != draft.id:
                retired_at = _replacement_retired_at(active, published)
                if not self._repository.retire_if_active(active.id, retired_at):
                    raise CurriculumActivationConflict(
                        "curriculum active version changed during publication"
                    )
                self._session.flush()
            if not self._repository.activate_if_draft(
                published.id, published.published_at
            ):
                raise CurriculumActivationConflict(
                    "curriculum draft was already published"
                )
            self._session.commit()
            return published
        except IntegrityError as exc:
            self._session.rollback()
            if _is_one_active_conflict(exc):
                raise CurriculumActivationConflict(
                    "another curriculum version became active"
                ) from exc
            raise
        except Exception:
            self._session.rollback()
            raise

    def _validated_publication(
        self, version_id: str, published_at: datetime
    ) -> tuple[CurriculumVersion, CurriculumVersion]:
        draft = self._repository.get(version_id)
        if draft is None:
            raise ValueError("curriculum version does not exist")
        if draft.status is not CurriculumStatus.DRAFT:
            raise CurriculumActivationConflict(
                "curriculum version is no longer a draft"
            )
        return draft, draft.publish(
            published_at=published_at,
            target_is_published=self._repository.target_is_published,
        )

    def retirement_policy_for(
        self, target: TargetSpec
    ) -> RetirementPolicyDecision:
        if self._repository.active_references_target(target):
            return RetirementPolicyDecision.ACTIVE_REFERENCE
        return RetirementPolicyDecision.ALLOWED
