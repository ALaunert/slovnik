from datetime import datetime
from typing import Literal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

CEFRLevel = Literal["A1", "A2", "B1", "B2", "C1", "C2"]


class VocabularyItem(Base):
    __tablename__ = "vocabulary_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    serbian_cyrillic: Mapped[str] = mapped_column(String(160), nullable=False)
    serbian_latin: Mapped[str] = mapped_column(String(160), nullable=False)
    russian_translation: Mapped[str] = mapped_column(String(240), nullable=False)
    cefr_level: Mapped[str] = mapped_column(String(2), nullable=False, index=True)
    theme: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    usage_register: Mapped[str | None] = mapped_column(String(80))
    stress_marker: Mapped[str | None] = mapped_column(String(160))
    meaning_notes: Mapped[str | None] = mapped_column(Text)
    example_sentences: Mapped[str | None] = mapped_column(Text)
    example_translations: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class UserProfile(Base):
    __tablename__ = "user_profiles"

    user_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    preferred_level: Mapped[str] = mapped_column(String(2), nullable=False, default="A1")
    daily_new_word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    ui_language: Mapped[str] = mapped_column(String(8), nullable=False, default="ru")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserWordProgress(Base):
    __tablename__ = "user_word_progress"
    __table_args__ = (UniqueConstraint("user_id", "word_id", name="uq_user_word_progress"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.user_id"), index=True)
    word_id: Mapped[int] = mapped_column(ForeignKey("vocabulary_items.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="new")
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_quizzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    incorrect_count: Mapped[int] = mapped_column(Integer, default=0)
    is_weak: Mapped[bool] = mapped_column(Boolean, default=False)
    weak_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    word: Mapped[VocabularyItem] = relationship()


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.user_id"), index=True)
    quiz_type: Mapped[str] = mapped_column(String(20), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    score: Mapped[int] = mapped_column(Integer, default=0)
    total_questions: Mapped[int] = mapped_column(Integer, default=0)
    question_plan: Mapped[str] = mapped_column(Text, default="[]")


class QuizAnswer(Base):
    __tablename__ = "quiz_answers"

    id: Mapped[int] = mapped_column(primary_key=True)
    quiz_attempt_id: Mapped[int] = mapped_column(ForeignKey("quiz_attempts.id"), index=True)
    word_id: Mapped[int] = mapped_column(ForeignKey("vocabulary_items.id"), index=True)
    question_type: Mapped[str] = mapped_column(String(40), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
