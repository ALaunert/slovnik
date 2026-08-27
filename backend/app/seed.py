from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.domain.curriculum import PrerequisiteKind
from app.domain.shared import Capability
from app.models import VocabularyItem
from app.services.domain_bootstrap_service import (
    PilotLexicalTargetRef,
    PilotPrerequisiteSeed,
    bootstrap_domain,
)

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

PILOT_PREREQUISITES = (
    PilotPrerequisiteSeed(
        prerequisite=PilotLexicalTargetRef(
            "hvala", Capability.RECOGNIZE_MEANING
        ),
        dependent=PilotLexicalTargetRef("hvala", Capability.RETRIEVE_FORM),
        kind=PrerequisiteKind.HARD,
    ),
    PilotPrerequisiteSeed(
        prerequisite=PilotLexicalTargetRef(
            "hvala", Capability.RECOGNIZE_MEANING
        ),
        dependent=PilotLexicalTargetRef(
            "molim", Capability.RECOGNIZE_MEANING
        ),
        kind=PrerequisiteKind.SOFT,
    ),
)


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


def seed_database(
    db: Session,
    *,
    bootstrap_at: datetime | None = None,
) -> int:
    created = seed_words(db)
    bootstrap_domain(
        db,
        bootstrap_at=bootstrap_at or datetime.now(timezone.utc),
        prerequisite_seeds=PILOT_PREREQUISITES,
    )
    return created


if __name__ == "__main__":
    from app.db import SessionLocal

    with SessionLocal() as db:
        created = seed_database(db)
    print(f"Seeded {created} vocabulary words.")
