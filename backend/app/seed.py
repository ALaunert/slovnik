from sqlalchemy.orm import Session

from app.models import VocabularyItem

SAMPLE_WORDS = [
    {
        "serbian_cyrillic": "хвала",
        "serbian_latin": "hvala",
        "russian_translation": "спасибо",
        "cefr_level": "A1",
        "theme": "greetings",
        "usage_register": "common",
    },
    {
        "serbian_cyrillic": "молим",
        "serbian_latin": "molim",
        "russian_translation": "пожалуйста",
        "cefr_level": "A1",
        "theme": "greetings",
        "usage_register": "common",
    },
    {
        "serbian_cyrillic": "вода",
        "serbian_latin": "voda",
        "russian_translation": "вода",
        "cefr_level": "A1",
        "theme": "daily-life",
        "usage_register": "common",
    },
]


def seed_words(db: Session) -> int:
    created = 0
    for item in SAMPLE_WORDS:
        exists = (
            db.query(VocabularyItem)
            .filter(VocabularyItem.serbian_latin == item["serbian_latin"])
            .first()
        )
        if exists:
            continue
        db.add(VocabularyItem(**item))
        created += 1
    db.commit()
    return created


if __name__ == "__main__":
    from app.db import SessionLocal

    with SessionLocal() as db:
        created = seed_words(db)
    print(f"Seeded {created} vocabulary words.")
