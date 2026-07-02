from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import VocabularyItem
from app.schemas import VocabularyCreate, VocabularyUpdate


def create_word(db: Session, payload: VocabularyCreate) -> VocabularyItem:
    word = VocabularyItem(**payload.model_dump())
    db.add(word)
    db.commit()
    db.refresh(word)
    return word


def update_word(db: Session, word_id: int, payload: VocabularyUpdate) -> VocabularyItem | None:
    word = db.get(VocabularyItem, word_id)
    if word is None:
        return None
    for field, value in payload.model_dump().items():
        setattr(word, field, value)
    db.commit()
    db.refresh(word)
    return word


def list_words(db: Session, cefr_level: str | None = None, theme: str | None = None) -> list[VocabularyItem]:
    statement = select(VocabularyItem).order_by(VocabularyItem.cefr_level, VocabularyItem.theme, VocabularyItem.id)
    if cefr_level:
        statement = statement.where(VocabularyItem.cefr_level == cefr_level)
    if theme:
        statement = statement.where(VocabularyItem.theme == theme)
    return list(db.scalars(statement))


def list_themes(db: Session) -> list[str]:
    return list(db.scalars(select(VocabularyItem.theme).distinct().order_by(VocabularyItem.theme)))
