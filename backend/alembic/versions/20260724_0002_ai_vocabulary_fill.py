"""Add AI vocabulary fill persistence.

Revision ID: 20260724_0002
Revises: 20260702_0001
Create Date: 2026-07-24
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260724_0002"
down_revision: str | None = "20260702_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "vocabulary_items",
        sa.Column("stress_pattern", sa.JSON(), nullable=True),
    )
    op.create_table(
        "ai_vocabulary_generations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_word", sa.String(length=160), nullable=False),
        sa.Column("normalized_source_word", sa.String(length=160), nullable=False),
        sa.Column("generated_payload", sa.JSON(), nullable=False),
        sa.Column("missing_required_fields", sa.JSON(), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("prompt_version", sa.String(length=40), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "normalized_source_word",
            name="uq_ai_vocabulary_generations_normalized_source_word",
        ),
    )


def downgrade() -> None:
    op.drop_table("ai_vocabulary_generations")
    op.drop_column("vocabulary_items", "stress_pattern")
