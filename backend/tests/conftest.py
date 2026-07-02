import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)
    with TestingSession() as session:
        yield session
    Base.metadata.drop_all(engine)


@pytest.fixture()
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def seeded_words(db_session):
    from app.models import VocabularyItem

    words = [
        VocabularyItem(
            serbian_cyrillic=f"реч {index}",
            serbian_latin=f"rec {index}",
            russian_translation=f"слово {index}",
            cefr_level="A1",
            theme="daily",
        )
        for index in range(1, 8)
    ]
    db_session.add_all(words)
    db_session.commit()
    for word in words:
        db_session.refresh(word)
    return words


@pytest.fixture()
def weak_progress(db_session, seeded_words):
    from datetime import datetime, timedelta, timezone
    from app.models import UserProfile, UserWordProgress

    db_session.add(UserProfile(user_id="learner-1"))
    progress = UserWordProgress(
        user_id="learner-1",
        word_id=seeded_words[0].id,
        status="reviewing",
        first_seen_at=datetime.now(timezone.utc) - timedelta(days=2),
        last_seen_at=datetime.now(timezone.utc),
        incorrect_count=1,
        is_weak=True,
        weak_since=datetime.now(timezone.utc),
    )
    db_session.add(progress)
    db_session.commit()
    db_session.refresh(progress)
    return progress


@pytest.fixture()
def seen_today_progress(db_session, seeded_words):
    from datetime import datetime, timezone
    from app.models import UserProfile, UserWordProgress

    db_session.add(UserProfile(user_id="learner-1"))
    progress = UserWordProgress(
        user_id="learner-1",
        word_id=seeded_words[1].id,
        status="seen",
        first_seen_at=datetime.now(timezone.utc),
        last_seen_at=datetime.now(timezone.utc),
    )
    db_session.add(progress)
    db_session.commit()
    db_session.refresh(progress)
    return progress
