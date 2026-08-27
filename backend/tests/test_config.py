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


def test_openai_settings_have_backend_defaults(monkeypatch):
    for name in ["OPENAI_API_KEY", "OPENAI_MODEL", "OPENAI_TIMEOUT_SECONDS"]:
        monkeypatch.delenv(name, raising=False)

    config = Settings(_env_file=None, environment="test", editor_password="secret")

    assert config.openai_api_key == ""
    assert config.openai_model == "gpt-5.6-luna"
    assert config.openai_timeout_seconds == 20.0


def test_openai_settings_support_environment_overrides(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-api-key")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    monkeypatch.setenv("OPENAI_TIMEOUT_SECONDS", "45.5")

    config = Settings(_env_file=None, environment="test", editor_password="secret")

    assert config.openai_api_key == "test-api-key"
    assert config.openai_model == "test-model"
    assert config.openai_timeout_seconds == 45.5


@pytest.mark.parametrize("timeout", [0, -1, 120.1])
def test_openai_timeout_must_be_positive_and_bounded(timeout):
    with pytest.raises(ValidationError):
        Settings(
            environment="test",
            editor_password="secret",
            openai_timeout_seconds=timeout,
        )


def test_language_assistant_shadow_is_disabled_by_default(monkeypatch):
    for name in (
        "LANGUAGE_ASSISTANT_SHADOW_ENABLED",
        "LANGUAGE_ASSISTANT_SHADOW_DATA_LIFECYCLE_READY",
        "LANGUAGE_ASSISTANT_SHADOW_TRUSTED_IDENTITY_READY",
    ):
        monkeypatch.delenv(name, raising=False)

    config = Settings(_env_file=None, environment="test", editor_password="secret")

    assert config.language_assistant_shadow_enabled is False


@pytest.mark.parametrize("environment", ["test", "development", "LOCAL"])
def test_local_environments_can_enable_language_assistant_shadow(environment):
    config = Settings(
        _env_file=None,
        environment=environment,
        editor_password="secret",
        language_assistant_shadow_enabled=True,
    )

    assert config.language_assistant_shadow_enabled is True


@pytest.mark.parametrize(
    ("data_lifecycle_ready", "trusted_identity_ready"),
    [(False, False), (True, False), (False, True)],
)
def test_production_shadow_requires_both_release_gates(
    data_lifecycle_ready,
    trusted_identity_ready,
):
    with pytest.raises(ValidationError, match="shadow.*gates"):
        Settings(
            _env_file=None,
            environment="PrOdUcTiOn",
            editor_password="secret",
            language_assistant_shadow_enabled=True,
            language_assistant_shadow_data_lifecycle_ready=data_lifecycle_ready,
            language_assistant_shadow_trusted_identity_ready=trusted_identity_ready,
        )


def test_production_shadow_accepts_both_release_gates():
    config = Settings(
        _env_file=None,
        environment="production",
        editor_password="secret",
        language_assistant_shadow_enabled=True,
        language_assistant_shadow_data_lifecycle_ready=True,
        language_assistant_shadow_trusted_identity_ready=True,
    )

    assert config.language_assistant_shadow_enabled is True
