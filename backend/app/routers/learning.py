from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import LearningProgressRead, LearningWordsRead, ReviewWordsRead, WordIdsPayload
from app.services.learning_service import (
    complete_new_words,
    complete_review,
    get_daily_new_words,
    get_review_words,
)

router = APIRouter(prefix="/api/learning", tags=["learning"])
UserIdPath = Annotated[str, Path(min_length=1, max_length=80)]


@router.get("/{user_id}/new-words", response_model=LearningWordsRead)
def new_words(user_id: UserIdPath, db: Session = Depends(get_db)):
    return {"words": get_daily_new_words(db, user_id)}


@router.post("/{user_id}/new-words/complete", response_model=LearningProgressRead)
def complete_new_words_route(user_id: UserIdPath, payload: WordIdsPayload, db: Session = Depends(get_db)):
    try:
        return {"progress": complete_new_words(db, user_id, payload.word_ids)}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{user_id}/review", response_model=ReviewWordsRead)
def review_words(user_id: UserIdPath, db: Session = Depends(get_db)):
    return {"words": get_review_words(db, user_id)}


@router.post("/{user_id}/review/complete", response_model=LearningProgressRead)
def complete_review_route(user_id: UserIdPath, payload: WordIdsPayload, db: Session = Depends(get_db)):
    try:
        return {"progress": complete_review(db, user_id, payload.word_ids)}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
