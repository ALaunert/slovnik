from fastapi.testclient import TestClient


def test_create_or_load_profile(client: TestClient):
    response = client.post("/api/profiles", json={"user_id": "learner-1"})

    assert response.status_code == 200
    assert response.json()["user_id"] == "learner-1"
    assert response.json()["preferred_level"] == "A1"
    assert response.json()["daily_new_word_count"] == 5


def test_update_profile_settings(client: TestClient):
    client.post("/api/profiles", json={"user_id": "learner-1"})

    response = client.patch(
        "/api/profiles/learner-1",
        json={"preferred_level": "A2", "daily_new_word_count": 7, "ui_language": "sr"},
    )

    assert response.status_code == 200
    assert response.json()["preferred_level"] == "A2"
    assert response.json()["daily_new_word_count"] == 7
    assert response.json()["ui_language"] == "sr"


def test_update_profile_ignores_explicit_nulls(client: TestClient):
    client.post("/api/profiles", json={"user_id": "learner-1"})

    response = client.patch(
        "/api/profiles/learner-1",
        json={"preferred_level": None, "daily_new_word_count": None, "ui_language": None},
    )

    assert response.status_code == 200
    assert response.json()["preferred_level"] == "A1"
    assert response.json()["daily_new_word_count"] == 5
    assert response.json()["ui_language"] == "ru"


def test_profile_update_rejects_too_long_user_id(client: TestClient):
    response = client.patch(f"/api/profiles/{'x' * 81}", json={"preferred_level": "A2"})

    assert response.status_code == 422
