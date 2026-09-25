import json
import logging
import unicodedata
from datetime import datetime, time, timedelta, timezone
from random import SystemRandom
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import QuizAnswer, QuizAttempt, UserWordProgress, VocabularyItem
from app.services.profile_service import get_or_create_profile
from app.services.shadow_quiz_service import ShadowQuizFailure, ShadowQuizService

QUESTION_TYPES = ["sr_to_ru_choice", "ru_to_sr_typing", "remembered_forgot_self_check"]
logger = logging.getLogger(__name__)


class InvalidQuizSubmission(ValueError):
    pass


def _raise_shadow_failure(phase: str) -> None:
    logger.error("quiz_shadow_failure phase=%s", phase)
    raise ShadowQuizFailure("Shadow quiz operation failed") from None


def _day_start(value: datetime) -> datetime:
    return datetime.combine(value.date(), time.min, tzinfo=timezone.utc)


def _week_start(value: datetime) -> datetime:
    week_start_date = value.date() - timedelta(days=value.weekday())
    return datetime.combine(week_start_date, time.min, tzinfo=timezone.utc)


def _source_progress(db: Session, user_id: str, quiz_type: str) -> list[UserWordProgress]:
    get_or_create_profile(db, user_id)
    statement = select(UserWordProgress).where(UserWordProgress.user_id == user_id)
    now = datetime.now(timezone.utc)
    if quiz_type == "weekly":
        current_week_start = _week_start(now)
        statement = statement.where(
            (UserWordProgress.first_seen_at >= current_week_start)
            | (UserWordProgress.last_seen_at >= current_week_start)
            | (UserWordProgress.is_weak.is_(True))
        )
    else:
        today_start = _day_start(now)
        touched_today = case(
            (
                (UserWordProgress.first_seen_at >= today_start)
                | (UserWordProgress.last_seen_at >= today_start),
                1,
            ),
            else_=0,
        )
        last_touch = func.coalesce(UserWordProgress.last_seen_at, UserWordProgress.first_seen_at)
        statement = statement.where(
            (UserWordProgress.first_seen_at.is_not(None))
            | (UserWordProgress.last_seen_at.is_not(None))
            | (UserWordProgress.is_weak.is_(True))
        ).order_by(UserWordProgress.is_weak.desc(), touched_today.desc(), last_touch.desc(), UserWordProgress.id)
        return list(db.scalars(statement))
    return list(db.scalars(statement.order_by(UserWordProgress.is_weak.desc(), UserWordProgress.id)))


def _choice_label(value: str) -> str:
    return unicodedata.normalize("NFC", " ".join(value.split()))


def _distractors(db: Session, word: VocabularyItem) -> list[str]:
    correct_label = _choice_label(word.russian_translation)
    if not correct_label:
        return []
    choices = [correct_label]
    seen = {correct_label.casefold()}
    candidates = (
        select(VocabularyItem.russian_translation)
        .where(VocabularyItem.id != word.id)
        .order_by(
            (VocabularyItem.cefr_level == word.cefr_level).desc(),
            (VocabularyItem.theme == word.theme).desc(),
            VocabularyItem.id,
        )
    )
    batch_size = 32
    offset = 0
    while len(choices) < 4:
        rows = list(db.scalars(candidates.limit(batch_size).offset(offset)))
        for value in rows:
            label = _choice_label(value)
            normalized = label.casefold()
            if label and normalized not in seen:
                choices.append(label)
                seen.add(normalized)
            if len(choices) == 4:
                break
        if len(rows) < batch_size:
            break
        offset += batch_size
    if len(choices) < 2:
        return []
    SystemRandom().shuffle(choices)
    return choices


def _question_for(db: Session, word: VocabularyItem, question_type: str) -> dict[str, Any] | None:
    answer_key = {
        "russian_translation": word.russian_translation,
        "serbian_latin": word.serbian_latin,
        "serbian_cyrillic": word.serbian_cyrillic,
    }
    if question_type == "sr_to_ru_choice":
        choices = _distractors(db, word)
        if not choices:
            return None
        return {
            "word_id": word.id,
            "question_type": question_type,
            "prompt": f"{word.serbian_cyrillic} / {word.serbian_latin}",
            "choices": choices,
            "answer_key_version": 1,
            "answer_key": answer_key,
        }
    if question_type == "ru_to_sr_typing":
        return {
            "word_id": word.id,
            "question_type": question_type,
            "prompt": word.russian_translation,
            "choices": [],
            "answer_key_version": 1,
            "answer_key": answer_key,
        }
    return {
        "word_id": word.id,
        "question_type": question_type,
        "prompt": f"{word.serbian_cyrillic} / {word.serbian_latin}",
        "choices": [],
        "answer_key_version": 1,
        "answer_key": answer_key,
    }


def _question_plan(attempt: QuizAttempt) -> list[dict[str, Any]]:
    try:
        parsed = json.loads(attempt.question_plan or "[]")
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def _matching_question(attempt: QuizAttempt, word_id: int, question_type: str) -> dict[str, Any] | None:
    for question in _question_plan(attempt):
        if question.get("word_id") == word_id and question.get("question_type") == question_type:
            return question
    return None


def _answer_history(db: Session, attempt_id: int, word_id: int, question_type: str) -> list[QuizAnswer]:
    return list(
        db.scalars(
            select(QuizAnswer)
            .where(
                QuizAnswer.quiz_attempt_id == attempt_id,
                QuizAnswer.word_id == word_id,
                QuizAnswer.question_type == question_type,
            )
            .order_by(QuizAnswer.id)
        )
    )


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
    words_by_id = {word.id: word for word in words}
    ordered_words = [words_by_id[word_id] for word_id in word_ids if word_id in words_by_id]
    questions = []
    for index, word in enumerate(ordered_words):
        question = _question_for(db, word, QUESTION_TYPES[index % len(QUESTION_TYPES)])
        if question is not None:
            questions.append(question)
    if ordered_words and len({q["question_type"] for q in questions}) < len(QUESTION_TYPES):
        for question_type in QUESTION_TYPES:
            if question_type not in {q["question_type"] for q in questions}:
                question = _question_for(db, ordered_words[0], question_type)
                if question is not None:
                    questions.append(question)
    attempt = QuizAttempt(
        user_id=user_id,
        quiz_type=quiz_type,
        total_questions=len(questions),
        question_plan=json.dumps(questions, ensure_ascii=False),
    )
    db.add(attempt)
    if settings.language_assistant_shadow_enabled and questions:
        try:
            db.flush()
            ShadowQuizService(db).start(attempt, questions)
            db.commit()
        except Exception:
            db.rollback()
            _raise_shadow_failure("start")
    else:
        db.commit()
    db.refresh(attempt)
    public_questions = [
        {field: question[field] for field in ("word_id", "question_type", "prompt", "choices")}
        for question in questions
    ]
    return {"attempt_id": attempt.id, "quiz_type": quiz_type, "questions": public_questions}


def reveal_question_answer(db: Session, user_id: str, attempt_id: int, word_id: int, question_type: str) -> dict:
    attempt = _get_user_attempt(db, user_id, attempt_id)
    question = _matching_question(attempt, word_id, question_type)
    if question is None:
        raise InvalidQuizSubmission("Question does not match this quiz attempt")
    if question_type != "remembered_forgot_self_check":
        raise InvalidQuizSubmission("Question answer cannot be revealed")
    key = _answer_key(question)
    if key is not None:
        return {"answer": key["russian_translation"]}
    if not question.get("answer"):
        raise InvalidQuizSubmission("Question answer cannot be revealed")
    return {"answer": str(question["answer"])}


def _answer_key(question: dict[str, Any]) -> dict[str, str] | None:
    if "answer_key_version" not in question:
        return None  # Existing stored attempts retain legacy mutable-content behavior.
    version = question["answer_key_version"]
    if type(version) is not int or version != 1:
        raise InvalidQuizSubmission("Unsupported quiz answer key version")
    key = question.get("answer_key")
    if not isinstance(key, dict) or any(
        not isinstance(key.get(field), str)
        for field in ("russian_translation", "serbian_latin", "serbian_cyrillic")
    ):
        raise InvalidQuizSubmission("Invalid quiz answer key")
    return key


def _is_correct(word: VocabularyItem, question_type: str, answer: str) -> bool:
    normalized = answer.strip().casefold()
    if question_type == "sr_to_ru_choice":
        return normalized == word.russian_translation.casefold()
    if question_type == "ru_to_sr_typing":
        return normalized in {word.serbian_latin.casefold(), word.serbian_cyrillic.casefold()}
    return normalized == "remembered"


def _is_correct_for_question(question: dict[str, Any], word: VocabularyItem, answer: str) -> bool:
    key = _answer_key(question)
    if key is None:
        return _is_correct(word, question["question_type"], answer)
    normalized = answer.strip().casefold()
    if question["question_type"] == "sr_to_ru_choice":
        return _choice_label(answer).casefold() == _choice_label(key["russian_translation"]).casefold()
    if question["question_type"] == "ru_to_sr_typing":
        return normalized in {key["serbian_latin"].casefold(), key["serbian_cyrillic"].casefold()}
    return normalized == "remembered"


def _get_user_attempt(db: Session, user_id: str, attempt_id: int) -> QuizAttempt:
    attempt = db.get(QuizAttempt, attempt_id)
    if attempt is None or attempt.user_id != user_id:
        raise ValueError("Quiz attempt not found")
    return attempt


def _lock_user_attempt(db: Session, user_id: str, attempt_id: int) -> QuizAttempt:
    attempt = db.scalar(
        select(QuizAttempt)
        .where(QuizAttempt.id == attempt_id, QuizAttempt.user_id == user_id)
        .with_for_update()
    )
    if attempt is None:
        raise ValueError("Quiz attempt not found")
    return attempt


def submit_answer(db: Session, user_id: str, attempt_id: int, word_id: int, question_type: str, answer: str) -> dict:
    shadow = None
    if settings.language_assistant_shadow_enabled:
        shadow = ShadowQuizService(db)
        try:
            attempt = shadow.lock_for_answer(
                learner_id=user_id,
                attempt_id=attempt_id,
                word_id=word_id,
                question_type=question_type,
            )
        except (ValueError, InvalidQuizSubmission):
            raise
        except Exception:
            db.rollback()
            _raise_shadow_failure("answer_enrollment")
        if not shadow.enrolled:
            shadow = None
    else:
        attempt = _get_user_attempt(db, user_id, attempt_id)
    if attempt.completed_at is not None:
        raise InvalidQuizSubmission("Quiz attempt is already complete")
    question = _matching_question(attempt, word_id, question_type)
    if question is None:
        raise InvalidQuizSubmission("Answer does not match this quiz attempt")
    word = db.get(VocabularyItem, word_id)
    if word is None:
        raise ValueError("Word not found")
    previous_answers = _answer_history(db, attempt_id, word_id, question_type)
    if any(previous.is_correct for previous in previous_answers) or len(previous_answers) >= 2:
        raise InvalidQuizSubmission("Question has already reached its answer limit")
    progress = db.scalar(
        select(UserWordProgress).where(
            UserWordProgress.user_id == attempt.user_id, UserWordProgress.word_id == word_id
        )
    )
    if progress is None:
        progress = UserWordProgress(user_id=attempt.user_id, word_id=word_id)
        db.add(progress)
    correct = _is_correct_for_question(question, word, answer)
    incorrect_before = sum(1 for previous in previous_answers if not previous.is_correct)
    now = datetime.now(timezone.utc)
    progress.last_quizzed_at = now
    if correct:
        progress.correct_count = (progress.correct_count or 0) + 1
        if attempt.quiz_type == "weekly" and progress.is_weak:
            progress.is_weak = False
            progress.weak_since = None
    else:
        progress.incorrect_count = (progress.incorrect_count or 0) + 1
        progress.is_weak = True
        progress.weak_since = progress.weak_since or now
        progress.next_review_at = None
    quiz_answer = QuizAnswer(
        quiz_attempt_id=attempt_id,
        word_id=word_id,
        question_type=question_type,
        prompt=str(question.get("prompt") or ""),
        answer=answer,
        is_correct=correct,
    )
    db.add(quiz_answer)
    if shadow is not None:
        try:
            db.flush()
            shadow.record_answer(
                quiz_answer,
                create_retry=not correct and incorrect_before == 0,
            )
            db.commit()
        except Exception:
            db.rollback()
            _raise_shadow_failure("answer")
    else:
        db.commit()
    db.refresh(progress)
    return {"is_correct": correct, "repeat_word": not correct and incorrect_before == 0, "is_weak": progress.is_weak}


def _correct_answer_for(word: VocabularyItem, question_type: str) -> str:
    if question_type == "ru_to_sr_typing":
        return f"{word.serbian_latin} / {word.serbian_cyrillic}"
    return word.russian_translation


def _correct_answer_for_question(question: dict[str, Any], word: VocabularyItem | None) -> str:
    key = _answer_key(question)
    if key is not None:
        if question["question_type"] == "ru_to_sr_typing":
            return f"{key['serbian_latin']} / {key['serbian_cyrillic']}"
        return key["russian_translation"]
    if word is None:
        raise ValueError("Word not found")
    return _correct_answer_for(word, question["question_type"])


def _completion_breakdown(
    planned_questions: list[dict[str, Any]],
    answers_by_key: dict[tuple[int, str], list[QuizAnswer]],
) -> dict[str, int | str]:
    result: dict[str, int | str] = {
        "result_version": 2,
        "first_attempt_correct": 0,
        "first_attempt_eligible": 0,
        "first_attempt_status": "not_measured",
        "recovered_objective_items": 0,
        "self_report_remembered": 0,
        "self_report_total": 0,
    }
    if any("answer_key_version" not in question for question in planned_questions):
        result["first_attempt_status"] = "unavailable"
        return result
    for question in planned_questions:
        history = answers_by_key[(question["word_id"], question["question_type"])]
        first = history[0]
        if question["question_type"] == "remembered_forgot_self_check":
            result["self_report_total"] += 1
            result["self_report_remembered"] += int(first.is_correct)
            continue
        result["first_attempt_eligible"] += 1
        result["first_attempt_correct"] += int(first.is_correct)
        if not first.is_correct and len(history) > 1 and history[1].is_correct:
            result["recovered_objective_items"] += 1
    if result["first_attempt_eligible"]:
        result["first_attempt_status"] = "available"
    return result


def complete_quiz(db: Session, user_id: str, attempt_id: int) -> dict:
    attempt = _get_user_attempt(db, user_id, attempt_id)
    if attempt.completed_at is not None:
        raise InvalidQuizSubmission("Quiz attempt is already complete")
    planned_questions = _question_plan(attempt)
    for question in planned_questions:
        _answer_key(question)
    if settings.language_assistant_shadow_enabled and planned_questions:
        attempt = _lock_user_attempt(db, user_id, attempt_id)
        planned_questions = _question_plan(attempt)
    answers = list(db.scalars(
        select(QuizAnswer).where(QuizAnswer.quiz_attempt_id == attempt_id).order_by(QuizAnswer.id)
    ))
    answers_by_key = {
        (question.get("word_id"), question.get("question_type")): [
            answer
            for answer in answers
            if answer.word_id == question.get("word_id") and answer.question_type == question.get("question_type")
        ]
        for question in planned_questions
    }
    incomplete_keys = [
        key
        for key, history in answers_by_key.items()
        if not history or (not any(answer.is_correct for answer in history) and len(history) < 2)
    ]
    if incomplete_keys:
        raise InvalidQuizSubmission("Quiz attempt has unanswered repeat questions")
    score = sum(1 for history in answers_by_key.values() if any(answer.is_correct for answer in history))
    breakdown = _completion_breakdown(planned_questions, answers_by_key)
    weak_word_ids = [
        progress.word_id
        for progress in db.scalars(
            select(UserWordProgress).where(
                UserWordProgress.user_id == attempt.user_id, UserWordProgress.is_weak.is_(True)
            )
        )
    ]
    attempt.score = score
    attempt.total_questions = len(planned_questions)
    attempt.completed_at = datetime.now(timezone.utc)
    if settings.language_assistant_shadow_enabled and planned_questions:
        try:
            ShadowQuizService(db).complete(attempt)
            db.commit()
        except Exception:
            db.rollback()
            _raise_shadow_failure("complete")
    else:
        db.commit()
    words_by_id = {
        word.id: word
        for word in db.scalars(select(VocabularyItem).where(VocabularyItem.id.in_({answer.word_id for answer in answers})))
    }
    mistakes = [
        {
            "word_id": answer.word_id,
            "prompt": answer.prompt,
            "answer": answer.answer,
            "correct_answer": _correct_answer_for_question(
                next(question for question in planned_questions if question["word_id"] == answer.word_id
                     and question["question_type"] == answer.question_type),
                words_by_id.get(answer.word_id),
            ),
            "question_type": answer.question_type,
        }
        for answer in answers
        if not answer.is_correct and any(
            question["word_id"] == answer.word_id and question["question_type"] == answer.question_type
            for question in planned_questions
        )
    ]
    return {
        "score": score,
        "total_questions": len(planned_questions),
        "weak_word_ids": weak_word_ids,
        "mistakes": mistakes,
        **breakdown,
    }
