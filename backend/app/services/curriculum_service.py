from __future__ import annotations

from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.catalog import RetirementPolicyDecision
from app.domain.curriculum import CurriculumVersion
from app.domain.target import TargetSpec
from app.repositories.curriculum import CurriculumRepository, TargetResolver


class CurriculumActivationConflict(RuntimeError):
    pass


def _is_one_active_conflict(error: IntegrityError) -> bool:
    diagnostics = getattr(error.orig, "diag", None)
    constraint_name = getattr(diagnostics, "constraint_name", None)
    if constraint_name is None:
        constraint_name = getattr(error.orig, "constraint_name", None)
    if constraint_name is not None:
        return constraint_name == "uq_curriculum_versions_one_active"
    return str(error.orig) == (
        "UNIQUE constraint failed: curriculum_versions.curriculum_code"
    )


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
