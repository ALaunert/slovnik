from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://slovnik:slovnik@localhost:5432/slovnik"
    editor_password: str = "dev-editor-password"
    environment: str = ""
    cors_origins: list[str] = ["http://localhost:5173"]

    model_config = SettingsConfigDict(env_file="../.env", env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def reject_placeholder_editor_password_outside_local_env(self) -> "Settings":
        placeholder_passwords = {"", "change-me", "changeme", "dev-editor-password"}
        local_environments = {"development", "local", "test"}
        is_placeholder = self.editor_password.strip().casefold() in placeholder_passwords
        is_local_env = self.environment.strip().casefold() in local_environments
        if is_placeholder and not is_local_env:
            raise ValueError("EDITOR_PASSWORD placeholders are allowed only in explicit local/test environments")
        return self


settings = Settings()
