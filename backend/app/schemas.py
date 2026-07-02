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


class VocabularyCreate(BaseModel):
    serbian_cyrillic: str = Field(min_length=1, max_length=160)
    serbian_latin: str = Field(min_length=1, max_length=160)
    russian_translation: str = Field(min_length=1, max_length=240)
    cefr_level: str
    theme: str
    usage_register: str | None = None
    stress_marker: str | None = None
    meaning_notes: str | None = None
    example_sentences: str | None = None
    example_translations: str | None = None


class VocabularyUpdate(VocabularyCreate):
    pass


class VocabularyRead(VocabularyCreate):
    id: int

    model_config = {"from_attributes": True}


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

    model_config = {"from_attributes": True}


class LearningWordsRead(BaseModel):
    words: list[VocabularyRead]


class LearningProgressRead(BaseModel):
    progress: list[UserWordProgressRead]


class QuizStartPayload(BaseModel):
    quiz_type: str = "daily"


class QuizQuestionRead(BaseModel):
    word_id: int
    question_type: str
    prompt: str
    answer: str | None = None
    choices: list[str] = []


class QuizStartRead(BaseModel):
    attempt_id: int
    quiz_type: str
    questions: list[QuizQuestionRead]


class QuizAnswerPayload(BaseModel):
    word_id: int
    question_type: str
    answer: str


class QuizAnswerRead(BaseModel):
    is_correct: bool
    repeat_word: bool
    is_weak: bool


class QuizCompleteRead(BaseModel):
    score: int
    total_questions: int
    weak_word_ids: list[int]
    mistakes: list[dict]
