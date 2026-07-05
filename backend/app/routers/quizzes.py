from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import (
    QuizAnswerPayload,
    QuizAnswerRead,
    QuizCompleteRead,
    QuizRevealAnswerRead,
    QuizStartPayload,
    QuizStartRead,
)
from app.services.quiz_service import (
    InvalidQuizSubmission,
    complete_quiz,
    reveal_question_answer,
    start_quiz,
    submit_answer,
)

router = APIRouter(prefix="/api/quizzes", tags=["quizzes"])
UserIdPath = Annotated[str, Path(min_length=1, max_length=80)]


@router.post("/{user_id}/start", response_model=QuizStartRead)
def start(user_id: UserIdPath, payload: QuizStartPayload, db: Session = Depends(get_db)):
    return start_quiz(db, user_id, payload.quiz_type)


@router.post("/{user_id}/{attempt_id}/answers", response_model=QuizAnswerRead)
def answer(user_id: UserIdPath, attempt_id: int, payload: QuizAnswerPayload, db: Session = Depends(get_db)):
    try:
        return submit_answer(db, user_id, attempt_id, payload.word_id, payload.question_type, payload.answer)
    except InvalidQuizSubmission as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{user_id}/{attempt_id}/questions/{word_id}/{question_type}/answer", response_model=QuizRevealAnswerRead)
def reveal_answer(user_id: UserIdPath, attempt_id: int, word_id: int, question_type: str, db: Session = Depends(get_db)):
    try:
        return reveal_question_answer(db, user_id, attempt_id, word_id, question_type)
    except InvalidQuizSubmission as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{user_id}/{attempt_id}/complete", response_model=QuizCompleteRead)
def complete(user_id: UserIdPath, attempt_id: int, db: Session = Depends(get_db)):
    try:
        return complete_quiz(db, user_id, attempt_id)
    except InvalidQuizSubmission as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
