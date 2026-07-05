from app.config import settings
from app.models import VocabularyItem


def test_editor_can_create_word_with_password(client):
    response = client.post(
        "/api/vocabulary",
        headers={"X-Editor-Password": settings.editor_password},
        json={
            "serbian_cyrillic": "добар дан",
            "serbian_latin": "dobar dan",
            "russian_translation": "добрый день",
            "cefr_level": "A1",
            "theme": "greetings",
        },
    )
    assert response.status_code == 201
    assert response.json()["serbian_latin"] == "dobar dan"


def test_create_word_rejects_wrong_editor_password(client):
    response = client.post("/api/vocabulary", headers={"X-Editor-Password": "bad"}, json={})
    assert response.status_code == 403


def test_list_words_filters_by_level_and_theme(client, db_session):
    db_session.add_all([
        VocabularyItem(
            serbian_cyrillic="хвала",
            serbian_latin="hvala",
            russian_translation="спасибо",
            cefr_level="A1",
            theme="greetings",
        ),
        VocabularyItem(
            serbian_cyrillic="храна",
            serbian_latin="hrana",
            russian_translation="еда",
            cefr_level="A2",
            theme="food",
        ),
    ])
    db_session.commit()

    response = client.get("/api/vocabulary?cefr_level=A1&theme=greetings")

    assert response.status_code == 200
    assert [word["serbian_latin"] for word in response.json()] == ["hvala"]


def test_list_themes_returns_distinct_sorted_values(client, db_session):
    db_session.add_all([
        VocabularyItem(serbian_cyrillic="а", serbian_latin="a", russian_translation="а", cefr_level="A1", theme="z"),
        VocabularyItem(serbian_cyrillic="б", serbian_latin="b", russian_translation="б", cefr_level="A1", theme="a"),
        VocabularyItem(serbian_cyrillic="в", serbian_latin="v", russian_translation="в", cefr_level="A1", theme="a"),
    ])
    db_session.commit()

    response = client.get("/api/vocabulary/themes")

    assert response.status_code == 200
    assert response.json() == ["a", "z"]


def test_get_word_by_id(client, db_session):
    word = VocabularyItem(
        serbian_cyrillic="здраво",
        serbian_latin="zdravo",
        russian_translation="привет",
        cefr_level="A1",
        theme="greetings",
    )
    db_session.add(word)
    db_session.commit()

    response = client.get(f"/api/vocabulary/{word.id}")

    assert response.status_code == 200
    assert response.json()["serbian_latin"] == "zdravo"


def test_editor_password_verify_accepts_correct_password(client):
    response = client.post("/api/vocabulary/editor/verify", headers={"X-Editor-Password": settings.editor_password})

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_editor_password_verify_rejects_wrong_password(client):
    response = client.post("/api/vocabulary/editor/verify", headers={"X-Editor-Password": "bad"})

    assert response.status_code == 403
