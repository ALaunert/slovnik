import pytest

from app.config import settings
from app.models import VocabularyItem


BASE_WORD = {
    "serbian_cyrillic": "радити",
    "serbian_latin": "raditi",
    "russian_translation": "работать",
    "cefr_level": "A1",
    "theme": "verbs",
}

VALID_STRESS = {
    "cyrillic_syllables": ["ра", "ди", "ти"],
    "latin_syllables": ["ra", "di", "ti"],
    "stressed_syllable_index": 0,
}


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


def test_editor_can_create_and_persist_structured_stress(client, db_session):
    response = client.post(
        "/api/vocabulary",
        headers={"X-Editor-Password": settings.editor_password},
        json={**BASE_WORD, "stress_pattern": VALID_STRESS},
    )

    assert response.status_code == 201
    assert response.json()["stress_pattern"] == VALID_STRESS
    saved = db_session.get(VocabularyItem, response.json()["id"])
    assert saved is not None
    assert saved.stress_pattern == VALID_STRESS


def test_editor_can_update_structured_stress(client, db_session):
    word = VocabularyItem(**BASE_WORD)
    db_session.add(word)
    db_session.commit()

    response = client.put(
        f"/api/vocabulary/{word.id}",
        headers={"X-Editor-Password": settings.editor_password},
        json={**BASE_WORD, "stress_pattern": {**VALID_STRESS, "stressed_syllable_index": 1}},
    )

    assert response.status_code == 200
    assert response.json()["stress_pattern"]["stressed_syllable_index"] == 1
    db_session.refresh(word)
    assert word.stress_pattern == {**VALID_STRESS, "stressed_syllable_index": 1}


@pytest.mark.parametrize(
    "stress_pattern",
    [
        {**VALID_STRESS, "stressed_syllable_index": 3},
        {**VALID_STRESS, "latin_syllables": ["ra", "diti"]},
        {
            **VALID_STRESS,
            "cyrillic_syllables": ["", "ра", "дити"],
            "latin_syllables": ["", "ra", "diti"],
        },
        {
            **VALID_STRESS,
            "cyrillic_syllables": ["ра", " ", "дити"],
            "latin_syllables": ["ra", " ", "diti"],
        },
        {**VALID_STRESS, "cyrillic_syllables": ["рад", "и", "тих"]},
        {**VALID_STRESS, "latin_syllables": ["rad", "i", "ti-x"]},
    ],
    ids=[
        "index-out-of-range",
        "unequal-counts",
        "empty-segments",
        "whitespace-segments",
        "cyrillic-mismatch",
        "latin-mismatch",
    ],
)
def test_editor_rejects_invalid_structured_stress(client, stress_pattern):
    response = client.post(
        "/api/vocabulary",
        headers={"X-Editor-Password": settings.editor_password},
        json={**BASE_WORD, "stress_pattern": stress_pattern},
    )

    assert response.status_code == 422


def test_editor_accepts_canonically_equivalent_stress_reconstruction(client):
    response = client.post(
        "/api/vocabulary",
        headers={"X-Editor-Password": settings.editor_password},
        json={
            **BASE_WORD,
            "serbian_cyrillic": "жена",
            "serbian_latin": "žena",
            "stress_pattern": {
                "cyrillic_syllables": ["же", "на"],
                "latin_syllables": ["z\u030ce", "na"],
                "stressed_syllable_index": 0,
            },
        },
    )

    assert response.status_code == 201
    assert response.json()["stress_pattern"]["latin_syllables"] == ["z\u030ce", "na"]


def test_legacy_stress_marker_remains_supported(client):
    response = client.post(
        "/api/vocabulary",
        headers={"X-Editor-Password": settings.editor_password},
        json={**BASE_WORD, "stress_marker": "ра́дити"},
    )

    assert response.status_code == 201
    assert response.json()["stress_marker"] == "ра́дити"
    assert response.json().get("stress_pattern") is None


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


def test_create_word_rejects_overlong_bounded_fields(client):
    payload = {
        "serbian_cyrillic": "добар дан",
        "serbian_latin": "dobar dan",
        "russian_translation": "добрый день",
        "cefr_level": "A1",
        "theme": "x" * 81,
        "usage_register": "x" * 81,
        "stress_marker": "x" * 161,
    }

    response = client.post("/api/vocabulary", headers={"X-Editor-Password": settings.editor_password}, json=payload)

    assert response.status_code == 422
