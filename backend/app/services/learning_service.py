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


def _ensure_words_exist(db: Session, word_ids: list[int]) -> None:
    if not word_ids:
        return
    existing_ids = set(db.scalars(select(VocabularyItem.id).where(VocabularyItem.id.in_(word_ids))))
    missing_ids = sorted(set(word_ids) - existing_ids)
    if missing_ids:
        raise ValueError(f"Unknown word ids: {missing_ids}")


def complete_new_words(db: Session, user_id: str, word_ids: list[int]) -> list[UserWordProgress]:
    get_or_create_profile(db, user_id)
    _ensure_words_exist(db, word_ids)
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
    words_by_id = {
        word.id: word for word in db.scalars(select(VocabularyItem).where(VocabularyItem.id.in_(selected)))
    }
    progress_by_word_id = {progress.word_id: progress for progress in rows}
    result = []
    for word_id in selected:
        word = words_by_id.get(word_id)
        progress = progress_by_word_id.get(word_id)
        if word is None or progress is None:
            continue
        result.append(
            {
                "id": word.id,
                "serbian_cyrillic": word.serbian_cyrillic,
                "serbian_latin": word.serbian_latin,
                "russian_translation": word.russian_translation,
                "cefr_level": word.cefr_level,
                "theme": word.theme,
                "usage_register": word.usage_register,
                "stress_marker": word.stress_marker,
                "meaning_notes": word.meaning_notes,
                "example_sentences": word.example_sentences,
                "example_translations": word.example_translations,
                "incorrect_count": progress.incorrect_count,
                "is_weak": progress.is_weak,
            }
        )
    return result


def complete_review(db: Session, user_id: str, word_ids: list[int]) -> list[UserWordProgress]:
    get_or_create_profile(db, user_id)
    _ensure_words_exist(db, word_ids)
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
