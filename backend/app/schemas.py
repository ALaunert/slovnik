from pydantic import BaseModel, Field


class ProfileCreate(BaseModel):
    user_id: str = Field(min_length=1, max_length=80)


class ProfileUpdate(BaseModel):
    preferred_level: str | None = None
    daily_new_word_count: int | None = Field(default=None, ge=1, le=50)
    ui_language: str | None = None


class ProfileRead(BaseModel):
    user_id: str
    preferred_level: str
    daily_new_word_count: int
    ui_language: str

    model_config = {"from_attributes": True}
