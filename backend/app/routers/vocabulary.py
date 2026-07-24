from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.schemas import (
    AiFillRequest,
    AiFillResponse,
    VocabularyCreate,
    VocabularyRead,
    VocabularyUpdate,
)
from app.services import ai_vocabulary_service
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


@router.post("/editor/verify")
def verify_editor_password(_: None = Depends(require_editor_password)):
    return {"ok": True}


@router.post(
    "/ai-fill",
    response_model=AiFillResponse,
    response_model_exclude_none=True,
)
def post_ai_fill(
    payload: AiFillRequest,
    x_editor_password: str = Header(default=""),
    db: Session = Depends(get_db),
):
    if x_editor_password != settings.editor_password:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "code": "invalid_editor_password",
                "message": "Invalid editor password.",
            },
        )
    try:
        return ai_vocabulary_service.fill_vocabulary(db, payload)
    except ai_vocabulary_service.AiFillServiceError as error:
        return JSONResponse(
            status_code=error.status_code,
            content={"code": error.code, "message": error.message},
        )


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
