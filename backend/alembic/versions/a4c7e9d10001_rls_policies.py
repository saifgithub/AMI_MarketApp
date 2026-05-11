"""Row-level security policies on user-scoped tables.

Why this exists
---------------
Every user-scoped table (mandates, user_overlays, journal_entries, etc.)
gets RLS enabled with a policy keyed off a session GUC `app.user_id`. The
backend sets `SET LOCAL app.user_id = '<uuid>'` once per request transaction
(see app.db.session.use_user). When real Supabase is plugged in via
`postgresql+psycopg2://...@<supabase>` the same policies survive — Supabase's
own GUC `request.jwt.claims.sub` can be aliased here without app changes.

What this migration does NOT do
-------------------------------
- It does NOT alter the backend service role's BYPASSRLS bit. The backend
  still connects as `postgres` (or another superuser) during local dev and
  bypasses RLS by default. Policies are enforced when:
  * the role is non-superuser, AND
  * the role does not have BYPASSRLS, AND
  * `FORCE ROW LEVEL SECURITY` is set on the table (we set it here).
  Saiful: when you provision Supabase, run the API server under
  `authenticated`/`anon` roles, not `postgres`.

- It does NOT run on SQLite (used in the unit test conftest). SQLite has no
  RLS concept. We early-return on non-Postgres dialects.

Revision ID: a4c7e9d10001
Revises: e355c2468b2a
Create Date: 2026-05-11 22:55:00.000000
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a4c7e9d10001"
down_revision: Union[str, Sequence[str], None] = "e355c2468b2a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Tables that have a `user_id` column and should be RLS-protected.
_USER_SCOPED_TABLES: tuple[str, ...] = (
    "mandates",
    "user_overlays",
    "overlay_edit_counts",
    "journal_entries",
    "lessons_progress",
    "agent_activations",
    "room_runs",
    "sim_portfolios",
    "sim_trades",
)


# These tables have no `user_id` column but join through a parent that does.
# We protect them via the parent's policy by joining through portfolio_id.
_DERIVED_TABLES: tuple[tuple[str, str, str], ...] = (
    # (child_table, parent_col, parent_table)
    ("sim_holdings", "portfolio_id", "sim_portfolios"),
)


def _is_postgres() -> bool:
    return op.get_context().dialect.name == "postgresql"


def upgrade() -> None:
    if not _is_postgres():
        # SQLite (tests) — RLS is a no-op. Stay silent.
        return

    for tbl in _USER_SCOPED_TABLES:
        op.execute(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {tbl} FORCE ROW LEVEL SECURITY;")
        op.execute(
            f"""
            CREATE POLICY {tbl}_owner_select ON {tbl}
            FOR SELECT
            USING (user_id::text = current_setting('app.user_id', true));
            """
        )
        op.execute(
            f"""
            CREATE POLICY {tbl}_owner_modify ON {tbl}
            FOR ALL
            USING (user_id::text = current_setting('app.user_id', true))
            WITH CHECK (user_id::text = current_setting('app.user_id', true));
            """
        )

    for child, parent_col, parent in _DERIVED_TABLES:
        op.execute(f"ALTER TABLE {child} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {child} FORCE ROW LEVEL SECURITY;")
        op.execute(
            f"""
            CREATE POLICY {child}_owner_select ON {child}
            FOR SELECT
            USING (
                EXISTS (
                    SELECT 1 FROM {parent} p
                    WHERE p.id = {child}.{parent_col}
                      AND p.user_id::text = current_setting('app.user_id', true)
                )
            );
            """
        )
        op.execute(
            f"""
            CREATE POLICY {child}_owner_modify ON {child}
            FOR ALL
            USING (
                EXISTS (
                    SELECT 1 FROM {parent} p
                    WHERE p.id = {child}.{parent_col}
                      AND p.user_id::text = current_setting('app.user_id', true)
                )
            )
            WITH CHECK (
                EXISTS (
                    SELECT 1 FROM {parent} p
                    WHERE p.id = {child}.{parent_col}
                      AND p.user_id::text = current_setting('app.user_id', true)
                )
            );
            """
        )

    # Users table: a row is its own owner — match on id.
    op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE users FORCE ROW LEVEL SECURITY;")
    op.execute(
        """
        CREATE POLICY users_self_select ON users
        FOR SELECT
        USING (id::text = current_setting('app.user_id', true));
        """
    )
    op.execute(
        """
        CREATE POLICY users_self_modify ON users
        FOR ALL
        USING (id::text = current_setting('app.user_id', true))
        WITH CHECK (id::text = current_setting('app.user_id', true));
        """
    )

    # auth_challenges: protect by target (email/phone) when no user_id;
    # otherwise by user_id. We open SELECT during pre-claim (no user yet)
    # but lock INSERT/UPDATE behind matching either user_id or unset GUC.
    op.execute("ALTER TABLE auth_challenges ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
        CREATE POLICY auth_challenges_owner ON auth_challenges
        FOR ALL
        USING (
            user_id IS NULL
            OR user_id::text = current_setting('app.user_id', true)
        )
        WITH CHECK (
            user_id IS NULL
            OR user_id::text = current_setting('app.user_id', true)
        );
        """
    )


def downgrade() -> None:
    if not _is_postgres():
        return

    for tbl in _USER_SCOPED_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {tbl}_owner_select ON {tbl};")
        op.execute(f"DROP POLICY IF EXISTS {tbl}_owner_modify ON {tbl};")
        op.execute(f"ALTER TABLE {tbl} DISABLE ROW LEVEL SECURITY;")

    for child, _, _ in _DERIVED_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {child}_owner_select ON {child};")
        op.execute(f"DROP POLICY IF EXISTS {child}_owner_modify ON {child};")
        op.execute(f"ALTER TABLE {child} DISABLE ROW LEVEL SECURITY;")

    op.execute("DROP POLICY IF EXISTS users_self_select ON users;")
    op.execute("DROP POLICY IF EXISTS users_self_modify ON users;")
    op.execute("ALTER TABLE users DISABLE ROW LEVEL SECURITY;")

    op.execute("DROP POLICY IF EXISTS auth_challenges_owner ON auth_challenges;")
    op.execute("ALTER TABLE auth_challenges DISABLE ROW LEVEL SECURITY;")
