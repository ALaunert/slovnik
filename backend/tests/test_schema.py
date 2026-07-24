import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import AiVocabularyGeneration, UserProfile, VocabularyItem


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


def test_can_create_user_profile(db_session):
    profile = UserProfile(user_id="learner-1", preferred_level="A1", daily_new_word_count=5)

    db_session.add(profile)
    db_session.commit()

    saved = db_session.get(UserProfile, "learner-1")
    assert saved is not None
    assert saved.daily_new_word_count == 5
