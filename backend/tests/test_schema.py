from sqlalchemy import select

from app.models import UserProfile, VocabularyItem


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


def test_can_create_user_profile(db_session):
    profile = UserProfile(user_id="learner-1", preferred_level="A1", daily_new_word_count=5)

    db_session.add(profile)
    db_session.commit()

    saved = db_session.get(UserProfile, "learner-1")
    assert saved is not None
    assert saved.daily_new_word_count == 5
