"""Initial schema.

Revision ID: 20260702_0001
Revises:
Create Date: 2026-07-02
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260702_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vocabulary_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("serbian_cyrillic", sa.String(length=160), nullable=False),
        sa.Column("serbian_latin", sa.String(length=160), nullable=False),
        sa.Column("russian_translation", sa.String(length=240), nullable=False),
        sa.Column("cefr_level", sa.String(length=2), nullable=False),
        sa.Column("theme", sa.String(length=80), nullable=False),
        sa.Column("usage_register", sa.String(length=80), nullable=True),
        sa.Column("stress_marker", sa.String(length=160), nullable=True),
        sa.Column("meaning_notes", sa.Text(), nullable=True),
        sa.Column("example_sentences", sa.Text(), nullable=True),
        sa.Column("example_translations", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_vocabulary_items_cefr_level", "vocabulary_items", ["cefr_level"])
    op.create_index("ix_vocabulary_items_theme", "vocabulary_items", ["theme"])

    op.create_table(
        "user_profiles",
        sa.Column("user_id", sa.String(length=80), primary_key=True),
        sa.Column("preferred_level", sa.String(length=2), nullable=False),
        sa.Column("daily_new_word_count", sa.Integer(), nullable=False),
        sa.Column("ui_language", sa.String(length=8), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "user_word_progress",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(length=80), sa.ForeignKey("user_profiles.user_id"), nullable=False),
        sa.Column("word_id", sa.Integer(), sa.ForeignKey("vocabulary_items.id"), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_quizzed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("correct_count", sa.Integer(), nullable=False),
        sa.Column("incorrect_count", sa.Integer(), nullable=False),
        sa.Column("is_weak", sa.Boolean(), nullable=False),
        sa.Column("weak_since", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("user_id", "word_id", name="uq_user_word_progress"),
    )
    op.create_index("ix_user_word_progress_user_id", "user_word_progress", ["user_id"])
    op.create_index("ix_user_word_progress_word_id", "user_word_progress", ["word_id"])

    op.create_table(
        "quiz_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(length=80), sa.ForeignKey("user_profiles.user_id"), nullable=False),
        sa.Column("quiz_type", sa.String(length=20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("total_questions", sa.Integer(), nullable=False),
    )
    op.create_index("ix_quiz_attempts_user_id", "quiz_attempts", ["user_id"])

    op.create_table(
        "quiz_answers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("quiz_attempt_id", sa.Integer(), sa.ForeignKey("quiz_attempts.id"), nullable=False),
        sa.Column("word_id", sa.Integer(), sa.ForeignKey("vocabulary_items.id"), nullable=False),
        sa.Column("question_type", sa.String(length=40), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_quiz_answers_quiz_attempt_id", "quiz_answers", ["quiz_attempt_id"])
    op.create_index("ix_quiz_answers_word_id", "quiz_answers", ["word_id"])


def downgrade() -> None:
    op.drop_index("ix_quiz_answers_word_id", table_name="quiz_answers")
    op.drop_index("ix_quiz_answers_quiz_attempt_id", table_name="quiz_answers")
    op.drop_table("quiz_answers")
    op.drop_index("ix_quiz_attempts_user_id", table_name="quiz_attempts")
    op.drop_table("quiz_attempts")
    op.drop_index("ix_user_word_progress_word_id", table_name="user_word_progress")
    op.drop_index("ix_user_word_progress_user_id", table_name="user_word_progress")
    op.drop_table("user_word_progress")
    op.drop_table("user_profiles")
    op.drop_index("ix_vocabulary_items_theme", table_name="vocabulary_items")
    op.drop_index("ix_vocabulary_items_cefr_level", table_name="vocabulary_items")
    op.drop_table("vocabulary_items")
