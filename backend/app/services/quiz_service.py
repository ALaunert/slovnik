from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import QuizAnswer, QuizAttempt, UserWordProgress, VocabularyItem
from app.services.profile_service import get_or_create_profile

QUESTION_TYPES = ["sr_to_ru_choice", "ru_to_sr_typing", "remembered_forgot_self_check"]


def _source_progress(db: Session, user_id: str, quiz_type: str) -> list[UserWordProgress]:
    get_or_create_profile(db, user_id)
    statement = select(UserWordProgress).where(UserWordProgress.user_id == user_id)
    if quiz_type == "weekly":
        week_start = datetime.now(timezone.utc) - timedelta(days=7)
        statement = statement.where(
            (UserWordProgress.first_seen_at >= week_start)
            | (UserWordProgress.last_seen_at >= week_start)
            | (UserWordProgress.is_weak.is_(True))
        )
    else:
        statement = statement.where(
            (UserWordProgress.first_seen_at.is_not(None))
            | (UserWordProgress.last_seen_at.is_not(None))
            | (UserWordProgress.is_weak.is_(True))
        )
    return list(db.scalars(statement.order_by(UserWordProgress.is_weak.desc(), UserWordProgress.id)))


def _distractors(db: Session, word: VocabularyItem) -> list[str]:
    rows = list(
        db.scalars(
            select(VocabularyItem)
            .where(VocabularyItem.id != word.id)
            .order_by(
                (VocabularyItem.cefr_level == word.cefr_level).desc(),
                (VocabularyItem.theme == word.theme).desc(),
                VocabularyItem.id,
            )
            .limit(3)
        )
    )
    choices = [word.russian_translation, *[row.russian_translation for row in rows]]
    return choices[:4]


def _question_for(db: Session, word: VocabularyItem, question_type: str) -> dict:
    if question_type == "sr_to_ru_choice":
        return {
            "word_id": word.id,
            "question_type": question_type,
            "prompt": f"{word.serbian_cyrillic} / {word.serbian_latin}",
            "choices": _distractors(db, word),
        }
    if question_type == "ru_to_sr_typing":
        return {
            "word_id": word.id,
            "question_type": question_type,
            "prompt": word.russian_translation,
            "choices": [],
        }
    return {
        "word_id": word.id,
        "question_type": question_type,
        "prompt": f"{word.serbian_cyrillic} / {word.serbian_latin}",
        "answer": word.russian_translation,
        "choices": [],
    }


def start_quiz(db: Session, user_id: str, quiz_type: str) -> dict:
    progress_rows = _source_progress(db, user_id, quiz_type)
    limit = 40 if quiz_type == "weekly" else 20
    word_ids = []
    for progress in progress_rows:
        if progress.word_id not in word_ids:
            word_ids.append(progress.word_id)
        if len(word_ids) >= limit:
            break
    words = list(db.scalars(select(VocabularyItem).where(VocabularyItem.id.in_(word_ids)))) if word_ids else []
    attempt = QuizAttempt(user_id=user_id, quiz_type=quiz_type, total_questions=0)
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    questions = []
    for index, word in enumerate(words):
        questions.append(_question_for(db, word, QUESTION_TYPES[index % len(QUESTION_TYPES)]))
    if words and len({q["question_type"] for q in questions}) < len(QUESTION_TYPES):
        for question_type in QUESTION_TYPES:
            if question_type not in {q["question_type"] for q in questions}:
                questions.append(_question_for(db, words[0], question_type))
    attempt.total_questions = len(questions)
    db.commit()
    return {"attempt_id": attempt.id, "quiz_type": quiz_type, "questions": questions}


def _is_correct(word: VocabularyItem, question_type: str, answer: str) -> bool:
    normalized = answer.strip().casefold()
    if question_type == "sr_to_ru_choice":
        return normalized == word.russian_translation.casefold()
    if question_type == "ru_to_sr_typing":
        return normalized in {word.serbian_latin.casefold(), word.serbian_cyrillic.casefold()}
    return normalized == "remembered"


def submit_answer(db: Session, attempt_id: int, word_id: int, question_type: str, answer: str) -> dict:
    attempt = db.get(QuizAttempt, attempt_id)
    word = db.get(VocabularyItem, word_id)
    if attempt is None or word is None:
        raise ValueError("Quiz attempt or word not found")
    progress = db.scalar(
        select(UserWordProgress).where(
            UserWordProgress.user_id == attempt.user_id, UserWordProgress.word_id == word_id
        )
    )
    if progress is None:
        progress = UserWordProgress(user_id=attempt.user_id, word_id=word_id)
        db.add(progress)
    correct = _is_correct(word, question_type, answer)
    now = datetime.now(timezone.utc)
    progress.last_quizzed_at = now
    if correct:
        progress.correct_count += 1
        if attempt.quiz_type == "weekly" and progress.is_weak:
            progress.is_weak = False
            progress.weak_since = None
    else:
        progress.incorrect_count += 1
        progress.is_weak = True
        progress.weak_since = progress.weak_since or now
    db.add(
        QuizAnswer(
            quiz_attempt_id=attempt_id,
            word_id=word_id,
            question_type=question_type,
            prompt=word.russian_translation if question_type == "ru_to_sr_typing" else word.serbian_latin,
            answer=answer,
            is_correct=correct,
        )
    )
    db.commit()
    db.refresh(progress)
    return {"is_correct": correct, "repeat_word": not correct, "is_weak": progress.is_weak}


def complete_quiz(db: Session, attempt_id: int) -> dict:
    attempt = db.get(QuizAttempt, attempt_id)
    if attempt is None:
        raise ValueError("Quiz attempt not found")
    answers = list(db.scalars(select(QuizAnswer).where(QuizAnswer.quiz_attempt_id == attempt_id)))
    score = sum(1 for answer in answers if answer.is_correct)
    weak_word_ids = [
        progress.word_id
        for progress in db.scalars(
            select(UserWordProgress).where(
                UserWordProgress.user_id == attempt.user_id, UserWordProgress.is_weak.is_(True)
            )
        )
    ]
    attempt.score = score
    attempt.total_questions = len(answers)
    attempt.completed_at = datetime.now(timezone.utc)
    db.commit()
    mistakes = [
        {"word_id": answer.word_id, "answer": answer.answer, "question_type": answer.question_type}
        for answer in answers
        if not answer.is_correct
    ]
    return {"score": score, "total_questions": len(answers), "weak_word_ids": weak_word_ids, "mistakes": mistakes}
