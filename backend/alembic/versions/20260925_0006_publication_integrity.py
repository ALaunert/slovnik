"""Pin publication requests and guard children of published lexical units.

Revision ID: 20260925_0006
Revises: 20260826_0005
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260925_0006"
down_revision: str | None = "20260826_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _sqlite_guard(table: str) -> None:
    for operation in ("INSERT", "UPDATE OF lexical_unit_id"):
        suffix = "insert" if operation == "INSERT" else "move"
        op.execute(sa.text(f"""
            CREATE TRIGGER {table}_draft_parent_{suffix}
            BEFORE {operation} ON {table}
            FOR EACH ROW
            WHEN (SELECT status FROM language_lexical_units WHERE id = NEW.lexical_unit_id) IS NOT 'draft'
            BEGIN
                SELECT RAISE(ABORT, 'cannot add child to non-draft lexical unit');
            END
        """))
    op.execute(sa.text(f"""
        CREATE TRIGGER {table}_published_status
        BEFORE UPDATE OF status ON {table}
        FOR EACH ROW
        WHEN (SELECT status FROM language_lexical_units WHERE id = NEW.lexical_unit_id)
             IS NOT 'draft'
         AND NEW.status IS NOT
             (SELECT status FROM language_lexical_units WHERE id = NEW.lexical_unit_id)
        BEGIN
            SELECT RAISE(ABORT, 'child status must match non-draft lexical unit');
        END
    """))


def upgrade() -> None:
    op.add_column("curriculum_versions", sa.Column("publication_request_fingerprint", sa.Text()))
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        _sqlite_guard("language_senses")
        _sqlite_guard("language_forms")
    elif dialect == "postgresql":
        op.execute(sa.text("""
            CREATE FUNCTION require_draft_lexical_parent() RETURNS trigger AS $$
            DECLARE parent_status text;
            BEGIN
                SELECT status INTO parent_status
                FROM language_lexical_units WHERE id = NEW.lexical_unit_id FOR UPDATE;
                IF TG_OP = 'INSERT' THEN
                    IF parent_status IS DISTINCT FROM 'draft' THEN
                        RAISE EXCEPTION 'cannot add child to non-draft lexical unit';
                    END IF;
                ELSIF NEW.lexical_unit_id IS DISTINCT FROM OLD.lexical_unit_id THEN
                    IF parent_status IS DISTINCT FROM 'draft' THEN
                        RAISE EXCEPTION 'cannot add child to non-draft lexical unit';
                    END IF;
                ELSIF parent_status IS DISTINCT FROM 'draft'
                      AND NEW.status IS DISTINCT FROM parent_status THEN
                    RAISE EXCEPTION 'child status must match non-draft lexical unit';
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
        """))
        for table in ("language_senses", "language_forms"):
            op.execute(sa.text(f"""
                CREATE TRIGGER {table}_draft_parent
                BEFORE INSERT OR UPDATE OF lexical_unit_id, status ON {table}
                FOR EACH ROW EXECUTE FUNCTION require_draft_lexical_parent()
            """))


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        for table in ("language_senses", "language_forms"):
            op.execute(sa.text(f"DROP TRIGGER {table}_draft_parent_insert"))
            op.execute(sa.text(f"DROP TRIGGER {table}_draft_parent_move"))
            op.execute(sa.text(f"DROP TRIGGER {table}_published_status"))
    elif dialect == "postgresql":
        for table in ("language_senses", "language_forms"):
            op.execute(sa.text(f"DROP TRIGGER {table}_draft_parent ON {table}"))
        op.execute(sa.text("DROP FUNCTION require_draft_lexical_parent()"))
    op.drop_column("curriculum_versions", "publication_request_fingerprint")
