from datetime import datetime, timezone

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.models import (
    AiVocabularyGeneration,
    AiVocabularyGenerationReservation,
    UserProfile,
    VocabularyItem,
)


def test_can_create_vocabulary_item(db_session):
    word = VocabularyItem(
        serbian_cyrillic="хвала",
        serbian_latin="hvala",
        russian_translation="спасибо",
        cefr_level="A1",
        theme="greetings",
    )

    db_session.add(word)
    db_session.commit()

    saved = db_session.scalar(select(VocabularyItem).where(VocabularyItem.serbian_latin == "hvala"))
    assert saved is not None
    assert saved.serbian_cyrillic == "хвала"


def test_vocabulary_item_accepts_structured_stress(db_session):
    stress_pattern = {
        "cyrillic_syllables": ["ра", "ди", "ти"],
        "latin_syllables": ["ra", "di", "ti"],
        "stressed_syllable_index": 0,
    }
    word = VocabularyItem(
        serbian_cyrillic="радити",
        serbian_latin="raditi",
        russian_translation="делать",
        cefr_level="A1",
        theme="work",
        stress_pattern=stress_pattern,
    )

    db_session.add(word)
    db_session.commit()
    db_session.expire_all()

    saved = db_session.get(VocabularyItem, word.id)
    assert saved is not None
    assert saved.stress_pattern == stress_pattern


def test_clearing_structured_stress_persists_sql_null(db_session):
    word = VocabularyItem(
        serbian_cyrillic="радити",
        serbian_latin="raditi",
        russian_translation="делать",
        cefr_level="A1",
        theme="work",
        stress_pattern={
            "cyrillic_syllables": ["ра", "ди", "ти"],
            "latin_syllables": ["ra", "di", "ti"],
            "stressed_syllable_index": 0,
        },
    )
    db_session.add(word)
    db_session.commit()

    word.stress_pattern = None
    db_session.commit()

    is_sql_null = db_session.scalar(
        text("SELECT stress_pattern IS NULL FROM vocabulary_items WHERE id = :word_id"),
        {"word_id": word.id},
    )
    assert is_sql_null == 1


def test_ai_generation_normalized_source_is_unique(db_session):
    first = AiVocabularyGeneration(
        source_word="raditi",
        normalized_source_word="raditi",
        generated_payload={"serbian_latin": "raditi", "russian_translation": "делать"},
        missing_required_fields=["serbian_cyrillic", "cefr_level", "theme"],
        model="test-model",
        prompt_version="v1",
    )
    duplicate = AiVocabularyGeneration(
        source_word="Raditi",
        normalized_source_word="raditi",
        generated_payload={"serbian_latin": "Raditi", "russian_translation": "делать"},
        missing_required_fields=[],
        model="test-model",
        prompt_version="v1",
    )

    db_session.add(first)
    db_session.commit()
    db_session.add(duplicate)

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_ai_generation_persists_required_json_values(db_session):
    generation = AiVocabularyGeneration(
        source_word="raditi",
        normalized_source_word="raditi",
        generated_payload={"serbian_latin": "raditi"},
        missing_required_fields=["serbian_cyrillic"],
        model="test-model",
        prompt_version="v1",
    )

    db_session.add(generation)
    db_session.commit()
    db_session.expire_all()

    saved = db_session.get(AiVocabularyGeneration, generation.id)
    assert saved is not None
    assert saved.generated_payload == {"serbian_latin": "raditi"}
    assert saved.missing_required_fields == ["serbian_cyrillic"]


def test_ai_generation_reservation_normalized_source_is_unique(db_session):
    expires_at = datetime.now(timezone.utc)
    db_session.add(
        AiVocabularyGenerationReservation(
            normalized_source_word="raditi",
            owner_token="first-owner",
            expires_at=expires_at,
        )
    )
    db_session.commit()
    db_session.add(
        AiVocabularyGenerationReservation(
            normalized_source_word="raditi",
            owner_token="second-owner",
            expires_at=expires_at,
        )
    )

    with pytest.raises(IntegrityError):
        db_session.commit()


@pytest.mark.parametrize("field_name", ["generated_payload", "missing_required_fields"])
def test_ai_generation_rejects_none_for_required_json(db_session, field_name):
    values = {
        "source_word": "raditi",
        "normalized_source_word": "raditi",
        "generated_payload": {"serbian_latin": "raditi"},
        "missing_required_fields": [],
        "model": "test-model",
        "prompt_version": "v1",
    }
    values[field_name] = None

    db_session.add(AiVocabularyGeneration(**values))

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_can_create_user_profile(db_session):
    profile = UserProfile(user_id="learner-1", preferred_level="A1", daily_new_word_count=5)

    db_session.add(profile)
    db_session.commit()

    saved = db_session.get(UserProfile, "learner-1")
    assert saved is not None
    assert saved.daily_new_word_count == 5
