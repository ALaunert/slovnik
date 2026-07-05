import pytest
from pydantic import ValidationError

from app.config import Settings


def test_rejects_placeholder_editor_password_without_local_environment():
    for placeholder in ["", "change-me", "dev-editor-password"]:
        with pytest.raises(ValidationError):
            Settings(environment="", editor_password=placeholder)


def test_production_rejects_default_editor_password():
    for placeholder in ["", "change-me", "dev-editor-password"]:
        with pytest.raises(ValidationError):
            Settings(environment="production", editor_password=placeholder)


def test_development_allows_default_editor_password():
    settings = Settings(environment="development", editor_password="dev-editor-password")

    assert settings.editor_password == "dev-editor-password"


def test_production_environment_check_is_case_insensitive():
    with pytest.raises(ValidationError):
        Settings(environment="Production", editor_password="change-me")
