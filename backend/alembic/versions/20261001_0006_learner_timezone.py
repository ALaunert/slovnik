"""Add explicit UTC profile fallback and deferred learner timezone changes."""

from alembic import op
import sqlalchemy as sa

revision = "20261001_0006"
down_revision = "20260826_0005"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("user_profiles", sa.Column("timezone", sa.String(80), nullable=False, server_default="UTC"))
    op.add_column("user_profiles", sa.Column("previous_timezone", sa.String(80), nullable=False, server_default="UTC"))
    op.add_column("user_profiles", sa.Column("timezone_change_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("user_profiles", sa.Column("timezone_window_start", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("user_profiles", "timezone_window_start")
    op.drop_column("user_profiles", "timezone_change_at")
    op.drop_column("user_profiles", "previous_timezone")
    op.drop_column("user_profiles", "timezone")
