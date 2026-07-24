"""Add AI vocabulary fill reservations.

Revision ID: 20260725_0003
Revises: 20260724_0002
Create Date: 2026-07-25
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260725_0003"
down_revision: str | None = "20260724_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_vocabulary_generation_reservations",
        sa.Column(
            "normalized_source_word",
            sa.String(length=160),
            nullable=False,
        ),
        sa.Column("owner_token", sa.String(length=36), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.PrimaryKeyConstraint(
            "normalized_source_word",
            name="pk_ai_vocabulary_generation_reservations",
        ),
    )


def downgrade() -> None:
    op.drop_table("ai_vocabulary_generation_reservations")
