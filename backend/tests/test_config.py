import pytest
from pydantic import ValidationError

from app.config import Settings


def test_production_rejects_default_editor_password():
    with pytest.raises(ValidationError):
        Settings(environment="production", editor_password="dev-editor-password")


def test_development_allows_default_editor_password():
    settings = Settings(environment="development", editor_password="dev-editor-password")

    assert settings.editor_password == "dev-editor-password"
