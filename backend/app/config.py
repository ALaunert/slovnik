from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://slovnik:slovnik@localhost:5432/slovnik"
    editor_password: str = "dev-editor-password"
    environment: str = "development"
    cors_origins: list[str] = ["http://localhost:5173"]

    model_config = SettingsConfigDict(env_file="../.env", env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def reject_placeholder_editor_password_in_production(self) -> "Settings":
        placeholder_passwords = {"", "change-me", "changeme", "dev-editor-password"}
        if self.environment == "production" and self.editor_password.strip().casefold() in placeholder_passwords:
            raise ValueError("EDITOR_PASSWORD must be set to a non-placeholder value in production")
        return self


settings = Settings()
