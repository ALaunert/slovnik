from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import UserWordProgress, VocabularyItem
from app.services.profile_service import get_or_create_profile


def get_daily_new_words(db: Session, user_id: str) -> list[VocabularyItem]:
    profile = get_or_create_profile(db, user_id)
    seen_word_ids = select(UserWordProgress.word_id).where(UserWordProgress.user_id == user_id)
    return list(
        db.scalars(
            select(VocabularyItem)
            .where(VocabularyItem.cefr_level == profile.preferred_level)
            .where(VocabularyItem.id.not_in(seen_word_ids))
            .order_by(VocabularyItem.id)
            .limit(profile.daily_new_word_count)
        )
    )


def complete_new_words(db: Session, user_id: str, word_ids: list[int]) -> list[UserWordProgress]:
    get_or_create_profile(db, user_id)
    now = datetime.now(timezone.utc)
    progress_rows: list[UserWordProgress] = []
    for word_id in word_ids:
        progress = db.scalar(
            select(UserWordProgress).where(
                UserWordProgress.user_id == user_id, UserWordProgress.word_id == word_id
            )
        )
        if progress is None:
            progress = UserWordProgress(user_id=user_id, word_id=word_id)
            db.add(progress)
        progress.status = "seen"
        if progress.first_seen_at is None:
            progress.first_seen_at = now
        progress.last_seen_at = now
        progress_rows.append(progress)
    db.commit()
    for progress in progress_rows:
        db.refresh(progress)
    return progress_rows


def get_review_words(db: Session, user_id: str) -> list[VocabularyItem]:
    get_or_create_profile(db, user_id)
    today = datetime.now(timezone.utc).date()
    rows = list(
        db.scalars(
            select(UserWordProgress)
            .where(UserWordProgress.user_id == user_id)
            .where(UserWordProgress.status.in_(["seen", "reviewing", "learned"]))
            .order_by(UserWordProgress.is_weak.desc(), UserWordProgress.last_seen_at.asc().nullsfirst())
        )
    )
    selected: list[int] = []
    for progress in rows:
        last_seen_date = progress.last_seen_at.date() if progress.last_seen_at else None
        first_seen_date = progress.first_seen_at.date() if progress.first_seen_at else None
        if progress.is_weak or last_seen_date is None or last_seen_date < today:
            if progress.is_weak or first_seen_date != today:
                selected.append(progress.word_id)
        if len(selected) >= 20:
            break
    if not selected:
        return []
    return list(db.scalars(select(VocabularyItem).where(VocabularyItem.id.in_(selected))))


def complete_review(db: Session, user_id: str, word_ids: list[int]) -> list[UserWordProgress]:
    get_or_create_profile(db, user_id)
    now = datetime.now(timezone.utc)
    progress_rows: list[UserWordProgress] = []
    for word_id in word_ids:
        progress = db.scalar(
            select(UserWordProgress).where(
                UserWordProgress.user_id == user_id, UserWordProgress.word_id == word_id
            )
        )
        if progress is None:
            progress = UserWordProgress(user_id=user_id, word_id=word_id, first_seen_at=now)
            db.add(progress)
        if progress.status != "learned":
            progress.status = "reviewing"
        progress.last_seen_at = now
        progress_rows.append(progress)
    db.commit()
    for progress in progress_rows:
        db.refresh(progress)
    return progress_rows
