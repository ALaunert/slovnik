from datetime import datetime, timedelta, timezone
from typing import Any, Literal, TypedDict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import UserWordProgress, VocabularyItem
from app.services.profile_service import get_or_create_profile

ReviewRating = Literal["again", "hard", "good", "easy"]

AGAIN_DELAY = timedelta(minutes=10)
HARD_INTERVAL_DAYS = 1
GOOD_INITIAL_INTERVAL_DAYS = 2
GOOD_INTERVAL_MULTIPLIER = 2
GOOD_MAX_INTERVAL_DAYS = 180
EASY_INITIAL_INTERVAL_DAYS = 4
EASY_INTERVAL_MULTIPLIER = 3
EASY_MAX_INTERVAL_DAYS = 365
LEARNED_REVIEW_STREAK = 3


class ReviewWord(TypedDict):
    id: int
    serbian_cyrillic: str
    serbian_latin: str
    russian_translation: str
    cefr_level: str
    theme: str
    usage_register: str | None
    stress_marker: str | None
    stress_pattern: dict[str, Any] | None
    meaning_notes: str | None
    example_sentences: str | None
    example_translations: str | None
    incorrect_count: int
    is_weak: bool


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _is_review_due(progress: UserWordProgress, now: datetime) -> bool:
    next_review_at = _as_utc(progress.next_review_at)
    if next_review_at is not None:
        return next_review_at <= now
    if progress.is_weak:
        return True

    first_seen_at = _as_utc(progress.first_seen_at)
    last_seen_at = _as_utc(progress.last_seen_at)
    today = now.date()
    return all(
        value is None or value.date() < today
        for value in (first_seen_at, last_seen_at)
    )


def _review_sort_key(progress: UserWordProgress) -> tuple:
    next_review_at = _as_utc(progress.next_review_at)
    last_seen_at = _as_utc(progress.last_seen_at)
    minimum = datetime.min.replace(tzinfo=timezone.utc)
    return (
        not progress.is_weak,
        next_review_at is not None,
        next_review_at or minimum,
        last_seen_at is not None,
        last_seen_at or minimum,
        progress.id,
    )


def apply_review_rating(
    progress: UserWordProgress, rating: ReviewRating, now: datetime
) -> None:
    if rating not in {"again", "hard", "good", "easy"}:
        raise ValueError(f"Unknown review rating: {rating}")

    current_interval = progress.review_interval_days or 0
    current_streak = progress.review_streak or 0
    progress.last_seen_at = now
    progress.status = "reviewing"

    if rating == "again":
        progress.review_interval_days = 0
        progress.next_review_at = now + AGAIN_DELAY
        progress.review_streak = 0
        progress.is_weak = True
        progress.weak_since = progress.weak_since or now
        return

    if rating == "hard":
        progress.review_interval_days = HARD_INTERVAL_DAYS
        progress.next_review_at = now + timedelta(days=HARD_INTERVAL_DAYS)
        progress.review_streak = 0
        return

    if rating == "good":
        interval_days = (
            GOOD_INITIAL_INTERVAL_DAYS
            if current_interval < GOOD_INITIAL_INTERVAL_DAYS
            else min(
                current_interval * GOOD_INTERVAL_MULTIPLIER,
                GOOD_MAX_INTERVAL_DAYS,
            )
        )
    else:
        interval_days = (
            EASY_INITIAL_INTERVAL_DAYS
            if current_interval < EASY_INITIAL_INTERVAL_DAYS
            else min(
                current_interval * EASY_INTERVAL_MULTIPLIER,
                EASY_MAX_INTERVAL_DAYS,
            )
        )

    progress.review_interval_days = interval_days
    progress.next_review_at = now + timedelta(days=interval_days)
    progress.review_streak = current_streak + 1
    progress.is_weak = False
    progress.weak_since = None
    if progress.review_streak >= LEARNED_REVIEW_STREAK:
        progress.status = "learned"


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


def _ensure_words_selected(selected_ids: set[int], word_ids: list[int]) -> None:
    unselected_ids = sorted(set(word_ids) - selected_ids)
    if unselected_ids:
        raise ValueError(f"Word ids are not in the current session: {unselected_ids}")


def complete_new_words(db: Session, user_id: str, word_ids: list[int]) -> list[UserWordProgress]:
    _ensure_words_exist(db, word_ids)
    selected_ids = {word.id for word in get_daily_new_words(db, user_id)}
    _ensure_words_selected(selected_ids, word_ids)
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
        progress.next_review_at = now + timedelta(days=1)
        progress_rows.append(progress)
    db.commit()
    for progress in progress_rows:
        db.refresh(progress)
    return progress_rows


def get_review_words(db: Session, user_id: str) -> list[ReviewWord]:
    get_or_create_profile(db, user_id)
    now = datetime.now(timezone.utc)
    progress_rows = list(
        db.scalars(
            select(UserWordProgress)
            .where(UserWordProgress.user_id == user_id)
            .where(UserWordProgress.status.in_(["seen", "reviewing", "learned"]))
        )
    )
    due_rows = sorted(
        (progress for progress in progress_rows if _is_review_due(progress, now)),
        key=_review_sort_key,
    )[:20]
    selected = [progress.word_id for progress in due_rows]
    if not selected:
        return []
    words_by_id = {
        word.id: word for word in db.scalars(select(VocabularyItem).where(VocabularyItem.id.in_(selected)))
    }
    progress_by_word_id = {progress.word_id: progress for progress in due_rows}
    result: list[ReviewWord] = []
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
                "stress_pattern": word.stress_pattern,
                "meaning_notes": word.meaning_notes,
                "example_sentences": word.example_sentences,
                "example_translations": word.example_translations,
                "incorrect_count": progress.incorrect_count,
                "is_weak": progress.is_weak,
            }
        )
    return result


def grade_review(
    db: Session,
    user_id: str,
    word_id: int,
    rating: ReviewRating,
) -> UserWordProgress:
    if db.get(VocabularyItem, word_id) is None:
        raise ValueError(f"Unknown word id: {word_id}")
    progress = db.scalar(
        select(UserWordProgress).where(
            UserWordProgress.user_id == user_id,
            UserWordProgress.word_id == word_id,
        )
    )
    if progress is None or progress.status not in {"seen", "reviewing", "learned"}:
        raise ValueError("Word has not been seen by this user")

    now = datetime.now(timezone.utc)
    if not _is_review_due(progress, now):
        raise ValueError("Word is not currently due for review")

    apply_review_rating(progress, rating, now)
    db.commit()
    db.refresh(progress)
    return progress


def complete_review(db: Session, user_id: str, word_ids: list[int]) -> list[UserWordProgress]:
    _ensure_words_exist(db, word_ids)
    selected_ids = {word["id"] for word in get_review_words(db, user_id)}
    _ensure_words_selected(selected_ids, word_ids)
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
        progress.next_review_at = now + timedelta(days=1)
        progress.review_streak = 0
        progress_rows.append(progress)
    db.commit()
    for progress in progress_rows:
        db.refresh(progress)
    return progress_rows
