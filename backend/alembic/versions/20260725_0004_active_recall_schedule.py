"""Add active recall scheduling state.

Revision ID: 20260725_0004
Revises: 20260725_0003
Create Date: 2026-07-25
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260725_0004"
down_revision: str | None = "20260725_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_word_progress",
        sa.Column("next_review_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "user_word_progress",
        sa.Column(
            "review_interval_days",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "user_word_progress",
        sa.Column(
            "review_streak",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.create_index(
        "ix_user_word_progress_next_review_at",
        "user_word_progress",
        ["next_review_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_user_word_progress_next_review_at",
        table_name="user_word_progress",
    )
    op.drop_column("user_word_progress", "review_streak")
    op.drop_column("user_word_progress", "review_interval_days")
    op.drop_column("user_word_progress", "next_review_at")
