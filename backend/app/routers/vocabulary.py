from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.schemas import VocabularyCreate, VocabularyRead, VocabularyUpdate
from app.services.vocabulary_service import create_word, get_word, list_themes, list_words, update_word

router = APIRouter(prefix="/api/vocabulary", tags=["vocabulary"])


def require_editor_password(x_editor_password: str = Header(default="")) -> None:
    if x_editor_password != settings.editor_password:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid editor password")


@router.post("", response_model=VocabularyRead, status_code=status.HTTP_201_CREATED)
def post_word(
    payload: VocabularyCreate,
    _: None = Depends(require_editor_password),
    db: Session = Depends(get_db),
):
    return create_word(db, payload)


@router.put("/{word_id}", response_model=VocabularyRead)
def put_word(
    word_id: int,
    payload: VocabularyUpdate,
    _: None = Depends(require_editor_password),
    db: Session = Depends(get_db),
):
    word = update_word(db, word_id, payload)
    if word is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Word not found")
    return word


@router.get("", response_model=list[VocabularyRead])
def get_words(
    cefr_level: str | None = None,
    theme: str | None = None,
    db: Session = Depends(get_db),
):
    return list_words(db, cefr_level=cefr_level, theme=theme)


@router.get("/themes", response_model=list[str])
def get_themes(db: Session = Depends(get_db)):
    return list_themes(db)


@router.get("/{word_id}", response_model=VocabularyRead)
def get_word_route(word_id: int, db: Session = Depends(get_db)):
    word = get_word(db, word_id)
    if word is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Word not found")
    return word
