from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from hashlib import sha256
from uuid import UUID, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.catalog import ContentStatus
from app.domain.progress import LearnerTargetState, ProjectionBaseline
from app.domain.shared import Capability, Modality, TargetKind
from app.domain.target import TargetSpec
from app.domain_models.catalog import LanguageLexicalUnit, LanguageSense
from app.models import UserWordProgress
from app.repositories.progress import ProgressRepository


LEGACY_PROGRESS_NAMESPACE = UUID("63ed713d-a618-5dc0-a492-a02098d7fbb6")
BOOTSTRAP_STATUSES = ("seen", "reviewing", "learned")


@dataclass(frozen=True)
class LegacyProgressBootstrapResult:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped_missing_mapping: int = 0
    skipped_ambiguous_mapping: int = 0
    skipped_frozen: int = 0


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _timestamp(value: datetime | None) -> str | None:
    normalized = _utc(value)
    return None if normalized is None else normalized.isoformat()


def _source_fingerprint(progress: UserWordProgress) -> str:
    source = {
        "correct_count": progress.correct_count,
        "first_seen_at": _timestamp(progress.first_seen_at),
        "id": progress.id,
        "incorrect_count": progress.incorrect_count,
        "is_weak": progress.is_weak,
        "last_quizzed_at": _timestamp(progress.last_quizzed_at),
        "last_seen_at": _timestamp(progress.last_seen_at),
        "next_review_at": _timestamp(progress.next_review_at),
        "review_interval_days": progress.review_interval_days,
        "review_streak": progress.review_streak,
        "status": progress.status,
        "weak_since": _timestamp(progress.weak_since),
        "word_id": progress.word_id,
    }
    canonical = json.dumps(source, sort_keys=True, separators=(",", ":"))
    return sha256(canonical.encode("utf-8")).hexdigest()


def _legacy_due_at(
    progress: UserWordProgress,
    *,
    bootstrap_at: datetime,
) -> datetime:
    explicit_due_at = _utc(progress.next_review_at)
    if explicit_due_at is not None:
        return explicit_due_at
    if progress.is_weak:
        return bootstrap_at
    shown_at = (_utc(progress.first_seen_at), _utc(progress.last_seen_at))
    if all(value is None or value.date() < bootstrap_at.date() for value in shown_at):
        return bootstrap_at
    return datetime.combine(
        bootstrap_at.date() + timedelta(days=1),
        time.min,
        tzinfo=timezone.utc,
    )


def _legacy_state(
    progress: UserWordProgress,
    *,
    target_key: str,
    bootstrap_at: datetime,
) -> LearnerTargetState:
    due_at = _legacy_due_at(progress, bootstrap_at=bootstrap_at)
    baseline = ProjectionBaseline.legacy(
        memory_due_at=due_at,
        memory_interval_days=progress.review_interval_days,
        source_ref=f"user_word_progress:{progress.id}",
        source_fingerprint=_source_fingerprint(progress),
    )
    state_id = str(
        uuid5(
            LEGACY_PROGRESS_NAMESPACE,
            f"{progress.user_id}:{target_key}",
        )
    )
    return LearnerTargetState.legacy_bootstrap(
        state_id=state_id,
        learner_id=progress.user_id,
        target_key=target_key,
        baseline=baseline,
        updated_at=bootstrap_at,
    )


def bootstrap_legacy_progress(
    session: Session,
    *,
    bootstrap_at: datetime | None = None,
) -> LegacyProgressBootstrapResult:
    at = _utc(bootstrap_at or datetime.now(timezone.utc))
    assert at is not None
    progress_repository = ProgressRepository(session)
    counts = {
        "created": 0,
        "updated": 0,
        "unchanged": 0,
        "skipped_missing_mapping": 0,
        "skipped_ambiguous_mapping": 0,
        "skipped_frozen": 0,
    }

    rows = session.scalars(
        select(UserWordProgress)
        .where(UserWordProgress.status.in_(BOOTSTRAP_STATUSES))
        .order_by(UserWordProgress.id)
    )
    for progress in rows:
        sense_ids = tuple(
            session.scalars(
                select(LanguageSense.id)
                .join(LanguageLexicalUnit)
                .where(
                    LanguageLexicalUnit.legacy_vocabulary_item_id
                    == progress.word_id,
                    LanguageLexicalUnit.status == ContentStatus.PUBLISHED.value,
                    LanguageSense.status == ContentStatus.PUBLISHED.value,
                )
                .order_by(LanguageSense.id)
            )
        )
        if not sense_ids:
            counts["skipped_missing_mapping"] += 1
            continue
        if len(sense_ids) > 1:
            counts["skipped_ambiguous_mapping"] += 1
            continue
        target = TargetSpec(
            target_kind=TargetKind.SENSE,
            target_id=sense_ids[0],
            capability=Capability.RETRIEVE_FORM,
            modality=Modality.WRITTEN,
        )
        disposition = progress_repository.bootstrap_legacy_state(
            _legacy_state(progress, target_key=target.target_key, bootstrap_at=at)
        )
        counts[disposition] += 1

    session.commit()
    return LegacyProgressBootstrapResult(**counts)
