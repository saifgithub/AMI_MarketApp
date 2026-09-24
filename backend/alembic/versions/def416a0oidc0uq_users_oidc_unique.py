"""DEF416 — users.apple_id / users.google_id / users.hms_unionid get partial unique indexes.

Revision ID: def416a0oidc0uq
Revises: cr230a0order0log

`auth_service.py`'s Apple (`sign_in_with_apple`) and Google (`sign_in_with_google`)
claim paths SELECT by `apple_id`/`google_id`, find nothing, and INSERT a fresh
`User` row — a check-then-insert (`failure_patterns.md` P15) with NO database
constraint behind it at all. Unlike DEF401's `uq_verdict_outcomes_room_run`,
which already existed and only needed the catch/recover code, these three
columns have never had a constraint: two concurrent first-time sign-ins with
the same OIDC `sub` do not raise `IntegrityError`, they silently write two
`User` rows for one real identity. `hms_unionid` is unwritten today (no
Huawei AppGallery flow — CLAUDE.md: "Huawei AppGallery at v1.1") but carries
the exact same column shape, so it is closed now rather than left as the next
instance of this class.

Same race class as ISS001 (`docs/dilemmas/ISS001_DB_INSERT_RACE/` — still
open, no verdict; this migration does not wait on it) and DEF401. Reuses
DEF401's shipped shape: a DB-level unique constraint is the backstop, and
`auth_service.py` gets the `begin_nested()` / catch-`IntegrityError` /
re-SELECT-and-return-the-winner recovery in the same commit.

PARTIAL — `WHERE <col> IS NOT NULL` — because every column is nullable and a
user who has never linked Apple/Google/Huawei has NULL in all three. NULLs
already don't collide in a plain unique index on either Postgres or SQLite,
so the WHERE clause is not load-bearing for that reason; it is here because
it states the actual invariant ("no two REAL sub values collide") rather than
relying on incidental NULL semantics, and it keeps this identical in spelling
to `uq_journal_dedupe` (`d3e4f5a60029`) and `uq_reputation_event_dedup`
(`d1e2f3a40015`), which both run the same on Postgres and SQLite.

Pre-check: existing duplicates cannot be created by this migration (it only
adds constraints), but a duplicate that predates it would make
`CREATE UNIQUE INDEX` fail. Query first, and if any conflicting group exists,
raise with every row's `id` listed — never silently delete or merge a user
row. Operator remedy is documented in `docs/defect/DEF416_oidc_unique.md`.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "def416a0oidc0uq"
down_revision: Union[str, Sequence[str], None] = "cr230a0order0log"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_COLUMNS = ("apple_id", "google_id", "hms_unionid")

_DUP_CHECK_SQL = """
    SELECT {col} AS value, COUNT(*) AS n,
           array_agg(id ORDER BY id) AS ids
    FROM users
    WHERE {col} IS NOT NULL
    GROUP BY {col}
    HAVING COUNT(*) > 1
"""


def _check_no_duplicates(bind) -> None:
    """Fail loudly, listing every conflicting id, rather than let
    `CREATE UNIQUE INDEX` die on an opaque constraint-violation error — or
    worse, silently drop/merge rows to make room. See DEF416_oidc_unique.md
    for the operator remedy.
    """
    problems: list[str] = []
    for col in _COLUMNS:
        rows = bind.execute(text(_DUP_CHECK_SQL.format(col=col))).fetchall()
        for value, n, ids in rows:
            problems.append(
                f"users.{col} = {value!r} is shared by {n} rows: "
                f"{[str(i) for i in ids]}"
            )
    if problems:
        raise RuntimeError(
            "DEF416: cannot add unique index — existing duplicate rows found:\n  "
            + "\n  ".join(problems)
            + "\n\nThis migration refuses to run over pre-existing duplicates "
            "rather than silently delete or merge user rows. See "
            "docs/defect/DEF416_oidc_unique.md for the operator remedy "
            "(manually decide which row is canonical, re-key or merge by "
            "hand, then re-run `alembic upgrade head`)."
        )


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # `array_agg` is Postgres syntax, and Postgres is the only dialect
        # that ever replays this chain (see `8c5b1a70f4d2`'s docstring for
        # why: a fresh SQLite test DB is built by `Base.metadata.create_all()`
        # and stamped straight to head).
        _check_no_duplicates(bind)

    for col in _COLUMNS:
        op.create_index(
            f"uq_users_{col}",
            "users",
            [col],
            unique=True,
            sqlite_where=text(f"{col} IS NOT NULL"),
            postgresql_where=text(f"{col} IS NOT NULL"),
        )


def downgrade() -> None:
    for col in _COLUMNS:
        op.drop_index(f"uq_users_{col}", table_name="users")
