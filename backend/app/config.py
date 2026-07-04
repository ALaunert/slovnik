from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://slovnik:slovnik@localhost:5432/slovnik"
    editor_password: str = "dev-editor-password"
    environment: str = "development"
    cors_origins: list[str] = ["http://localhost:5173"]

    model_config = SettingsConfigDict(env_file="../.env", env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def reject_default_editor_password_in_production(self) -> "Settings":
        if self.environment == "production" and self.editor_password == "dev-editor-password":
            raise ValueError("EDITOR_PASSWORD must be set in production")
        return self


settings = Settings()
