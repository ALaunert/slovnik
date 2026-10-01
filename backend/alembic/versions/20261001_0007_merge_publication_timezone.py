"""Merge independently deployed publication integrity and learner timezone branches.

Retain both existing revision IDs so databases at either prior head execute the
missing branch before recording this common head.
"""

revision = "20261001_0007"
down_revision = ("20260925_0006", "20261001_0006")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
