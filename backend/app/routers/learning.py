from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import LearningProgressRead, LearningWordsRead, WordIdsPayload
from app.services.learning_service import (
    complete_new_words,
    complete_review,
    get_daily_new_words,
    get_review_words,
)

router = APIRouter(prefix="/api/learning", tags=["learning"])


@router.get("/{user_id}/new-words", response_model=LearningWordsRead)
def new_words(user_id: str, db: Session = Depends(get_db)):
    return {"words": get_daily_new_words(db, user_id)}


@router.post("/{user_id}/new-words/complete", response_model=LearningProgressRead)
def complete_new_words_route(user_id: str, payload: WordIdsPayload, db: Session = Depends(get_db)):
    return {"progress": complete_new_words(db, user_id, payload.word_ids)}


@router.get("/{user_id}/review", response_model=LearningWordsRead)
def review_words(user_id: str, db: Session = Depends(get_db)):
    return {"words": get_review_words(db, user_id)}


@router.post("/{user_id}/review/complete", response_model=LearningProgressRead)
def complete_review_route(user_id: str, payload: WordIdsPayload, db: Session = Depends(get_db)):
    return {"progress": complete_review(db, user_id, payload.word_ids)}
