from datetime import datetime
import unicodedata
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator


def _normalize_nfc(value: str) -> str:
    return unicodedata.normalize("NFC", value)


class ProfileCreate(BaseModel):
    user_id: str = Field(min_length=1, max_length=80)


class ProfileUpdate(BaseModel):
    preferred_level: Literal["A1", "A2", "B1", "B2", "C1", "C2"] | None = None
    daily_new_word_count: int | None = Field(default=None, ge=1, le=50)
    ui_language: Literal["ru", "sr"] | None = None


class ProfileRead(BaseModel):
    user_id: str
    preferred_level: Literal["A1", "A2", "B1", "B2", "C1", "C2"]
    daily_new_word_count: int
    ui_language: Literal["ru", "sr"]

    model_config = {"from_attributes": True}


class StressPattern(BaseModel):
    cyrillic_syllables: list[str] = Field(min_length=1)
    latin_syllables: list[str] = Field(min_length=1)
    stressed_syllable_index: int = Field(ge=0, strict=True)


class VocabularyCreate(BaseModel):
    serbian_cyrillic: str = Field(min_length=1, max_length=160)
    serbian_latin: str = Field(min_length=1, max_length=160)
    russian_translation: str = Field(min_length=1, max_length=240)
    cefr_level: Literal["A1", "A2", "B1", "B2", "C1", "C2"]
    theme: str = Field(min_length=1, max_length=80)
    usage_register: str | None = Field(default=None, max_length=80)
    stress_marker: str | None = Field(default=None, max_length=160)
    stress_pattern: StressPattern | None = None
    meaning_notes: str | None = None
    example_sentences: str | None = None
    example_translations: str | None = None

    @model_validator(mode="after")
    def validate_stress_pattern(self) -> "VocabularyCreate":
        pattern = self.stress_pattern
        if pattern is None:
            return self

        syllable_count = len(pattern.cyrillic_syllables)
        if syllable_count == 0 or syllable_count != len(pattern.latin_syllables):
            raise ValueError("Stress syllable counts must match and be non-zero")
        if any(
            not segment.strip()
            for segment in pattern.cyrillic_syllables + pattern.latin_syllables
        ):
            raise ValueError("Stress syllable segments must not be empty")
        if pattern.stressed_syllable_index >= syllable_count:
            raise ValueError("Stress index is out of range")
        if _normalize_nfc("".join(pattern.cyrillic_syllables)) != _normalize_nfc(self.serbian_cyrillic):
            raise ValueError("Cyrillic syllables must reconstruct the word")
        if _normalize_nfc("".join(pattern.latin_syllables)) != _normalize_nfc(self.serbian_latin):
            raise ValueError("Latin syllables must reconstruct the word")
        return self


class VocabularyUpdate(VocabularyCreate):
    pass


class VocabularyRead(VocabularyCreate):
    id: int

    model_config = {"from_attributes": True}


AiFillTheme = Literal[
    "greetings",
    "personal-info",
    "family-relationships",
    "home",
    "daily-life",
    "food-drink",
    "shopping-money",
    "travel-transport",
    "places-directions",
    "health-body",
    "education",
    "work",
    "free-time",
    "nature-weather",
    "services",
    "language-communication",
    "technology-media",
    "emotions-qualities",
    "time-numbers",
    "grammar-functions",
    "other",
]


class AiFillRequest(BaseModel):
    source_word: str
    current_word_id: int | None = Field(default=None, ge=1)


class AiFillPayload(BaseModel):
    serbian_cyrillic: str | None = None
    serbian_latin: str | None = None
    russian_translation: str | None = None
    cefr_level: Literal["A1", "A2", "B1", "B2", "C1", "C2"] | None = None
    theme: AiFillTheme | None = None
    usage_register: str | None = None
    stress_pattern: StressPattern | None = None
    meaning_notes: str | None = None
    example_sentences: str | None = None
    example_translations: str | None = None


class AiFillGeneratedResponse(BaseModel):
    status: Literal["generated"] = "generated"
    source: Literal["openai", "store"]
    payload: AiFillPayload
    missing_required_fields: list[str]


class AiFillExistingResponse(BaseModel):
    status: Literal["already_exists"] = "already_exists"
    word_id: int
    message: str = "Word already exists."


AiFillResponse = Annotated[
    AiFillGeneratedResponse | AiFillExistingResponse,
    Field(discriminator="status"),
]


class WordIdsPayload(BaseModel):
    word_ids: list[int]


class UserWordProgressRead(BaseModel):
    id: int
    user_id: str
    word_id: int
    status: str
    correct_count: int
    incorrect_count: int
    is_weak: bool
    next_review_at: datetime | None
    review_interval_days: int
    review_streak: int

    model_config = {"from_attributes": True}


class ReviewAnswerPayload(BaseModel):
    word_id: int
    rating: Literal["again", "hard", "good", "easy"]


class ReviewAnswerRead(BaseModel):
    progress: UserWordProgressRead


class ReviewStatusRead(BaseModel):
    is_due: bool


class LearningWordsRead(BaseModel):
    words: list[VocabularyRead]


class ReviewVocabularyRead(VocabularyRead):
    incorrect_count: int
    is_weak: bool


class ReviewWordsRead(BaseModel):
    words: list[ReviewVocabularyRead]


class LearningProgressRead(BaseModel):
    progress: list[UserWordProgressRead]


class QuizStartPayload(BaseModel):
    quiz_type: Literal["daily", "weekly"] = "daily"


class QuizQuestionRead(BaseModel):
    word_id: int
    question_type: Literal["sr_to_ru_choice", "ru_to_sr_typing", "remembered_forgot_self_check"]
    prompt: str
    choices: list[str] = []


class QuizStartRead(BaseModel):
    attempt_id: int
    quiz_type: str
    questions: list[QuizQuestionRead]


class QuizAnswerPayload(BaseModel):
    word_id: int
    question_type: Literal["sr_to_ru_choice", "ru_to_sr_typing", "remembered_forgot_self_check"]
    answer: str = Field(max_length=4096)


class QuizAnswerRead(BaseModel):
    is_correct: bool
    repeat_word: bool
    is_weak: bool


class QuizRevealAnswerRead(BaseModel):
    answer: str


class QuizCompleteRead(BaseModel):
    score: int
    total_questions: int
    weak_word_ids: list[int]
    mistakes: list[dict]
    result_version: Literal[2]
    first_attempt_correct: int = Field(ge=0)
    first_attempt_eligible: int = Field(ge=0)
    first_attempt_status: Literal["available", "not_measured", "unavailable"]
    recovered_objective_items: int = Field(ge=0)
    self_report_remembered: int = Field(ge=0)
    self_report_total: int = Field(ge=0)
