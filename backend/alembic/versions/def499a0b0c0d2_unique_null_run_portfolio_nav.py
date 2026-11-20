"""def499_unique_null_run_portfolio_nav - make the NULL-run_id uniqueness real

Revision ID: def499a0b0c0d2
Revises: cr278a0b0c0d1
Create Date: 2026-11-20

AT:B1 DEF499 - `uq_portfolio_user_kind_run (user_id, kind, run_id)` and
`uq_nav_user_run_date (user_id, run_id, as_of_date)` never fired for the
TRAINING portfolio / training NAV curve, because their `run_id` is NULL and
NULLs are distinct in a Postgres unique index. Two concurrent first touches
therefore both inserted (Alpha: two users hold 2 and 3 `training` portfolios,
created ~40 ms apart on 2026-09-28) and every `scalar_one_or_none()` over the
pair raises `MultipleResultsFound`.

This revision dedupes, then adds the partial unique indexes that do fire:
  * `uq_portfolio_user_kind_null_run` on sim_portfolios (user_id, kind) WHERE run_id IS NULL
  * `uq_nav_user_date_null_run`       on portfolio_nav_daily (user_id, as_of_date) WHERE run_id IS NULL

Dedupe rule (degrade loudly: it never silently drops data). Survivor = most
child rows, then earliest created_at, then id. A loser is deleted only when it
holds nothing: zero children and cash == starting capital. A loser with children
is re-pointed to the survivor only when that cannot create a second conflict
(same holding ticker / same snapshot day on the survivor) and its cash is
untouched; anything else ABORTS the migration naming the ids. Duplicate NAV
rows are deleted only when identical to the surviving row's values.

Idempotent: re-running finds no duplicates and skips indexes that exist.
Downgrade drops the two indexes only (deleted duplicates are not restorable).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "def499a0b0c0d2"
down_revision: Union[str, Sequence[str], None] = "cr278a0b0c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PORTFOLIO_INDEX = "uq_portfolio_user_kind_null_run"
NAV_INDEX = "uq_nav_user_date_null_run"

# Every table with an FK to sim_portfolios.id (verified against Alpha's
# pg_constraint 2026-11-20).
_CHILD_TABLES = (
    "sim_holdings",
    "sim_trades",
    "portfolio_value_snapshots",
    "game_short_positions",
    "sim_resting_orders",
    "sim_short_positions",
    "sim_option_legs",
    "sim_option_trades",
)


class DuplicateDataConflict(RuntimeError):
    """Raised when a duplicate cannot be merged without judgement."""


def _child_counts(conn, portfolio_id) -> dict[str, int]:
    return {
        t: conn.execute(
            sa.text(f"SELECT count(*) FROM {t} WHERE portfolio_id = :p"),
            {"p": portfolio_id},
        ).scalar_one()
        for t in _CHILD_TABLES
    }


def _dedupe_portfolios(conn) -> int:
    groups = conn.execute(sa.text(
        "SELECT user_id, kind FROM sim_portfolios WHERE run_id IS NULL "
        "GROUP BY user_id, kind HAVING count(*) > 1"
    )).all()
    removed = 0
    for user_id, kind in groups:
        rows = conn.execute(sa.text(
            "SELECT id, created_at, (current_cash = starting_capital) AS pristine "
            "FROM sim_portfolios WHERE user_id = :u AND kind = :k AND run_id IS NULL"
        ), {"u": user_id, "k": kind}).all()
        ranked = []
        for pid, created_at, pristine in rows:
            counts = _child_counts(conn, pid)
            ranked.append((-sum(counts.values()), str(created_at), str(pid), pid, bool(pristine), counts))
        ranked.sort(key=lambda r: r[:3])
        survivor = ranked[0][3]
        for _n, _c, _i, loser, pristine, counts in ranked[1:]:
            total = sum(counts.values())
            if not pristine:
                raise DuplicateDataConflict(
                    f"DEF499: duplicate portfolio {loser} (user {user_id}, kind {kind}) "
                    f"has cash != starting capital; survivor {survivor}. Merge by hand."
                )
            if total:
                overlap_h = conn.execute(sa.text(
                    "SELECT count(*) FROM sim_holdings a JOIN sim_holdings b "
                    "ON a.ticker = b.ticker WHERE a.portfolio_id = :l AND b.portfolio_id = :s"
                ), {"l": loser, "s": survivor}).scalar_one()
                overlap_s = conn.execute(sa.text(
                    "SELECT count(*) FROM portfolio_value_snapshots a JOIN portfolio_value_snapshots b "
                    "ON a.as_of = b.as_of WHERE a.portfolio_id = :l AND b.portfolio_id = :s"
                ), {"l": loser, "s": survivor}).scalar_one()
                if overlap_h or overlap_s:
                    raise DuplicateDataConflict(
                        f"DEF499: duplicate portfolio {loser} (user {user_id}, kind {kind}) "
                        f"has children that collide with survivor {survivor} "
                        f"(holdings overlap={overlap_h}, snapshot overlap={overlap_s}). Merge by hand."
                    )
                for t in _CHILD_TABLES:
                    conn.execute(
                        sa.text(f"UPDATE {t} SET portfolio_id = :s WHERE portfolio_id = :l"),
                        {"s": survivor, "l": loser},
                    )
            conn.execute(sa.text("DELETE FROM sim_portfolios WHERE id = :l"), {"l": loser})
            removed += 1
    return removed


def _dedupe_nav(conn) -> int:
    groups = conn.execute(sa.text(
        "SELECT user_id, as_of_date FROM portfolio_nav_daily WHERE run_id IS NULL "
        "GROUP BY user_id, as_of_date HAVING count(*) > 1"
    )).all()
    removed = 0
    for user_id, as_of in groups:
        rows = conn.execute(sa.text(
            "SELECT id, created_at, nav, cash, price_source, capital_event "
            "FROM portfolio_nav_daily WHERE user_id = :u AND as_of_date = :d AND run_id IS NULL"
        ), {"u": user_id, "d": as_of}).all()
        rows = sorted(rows, key=lambda r: (str(r[1]), str(r[0])))
        survivor = rows[0]
        for loser in rows[1:]:
            if tuple(loser[2:]) != tuple(survivor[2:]):
                raise DuplicateDataConflict(
                    f"DEF499: duplicate nav row {loser[0]} (user {user_id}, {as_of}) differs "
                    f"from survivor {survivor[0]}. Merge by hand."
                )
            conn.execute(sa.text("DELETE FROM portfolio_nav_daily WHERE id = :i"), {"i": loser[0]})
            removed += 1
    return removed


def _has_index(conn, table: str, name: str) -> bool:
    return any(ix["name"] == name for ix in sa.inspect(conn).get_indexes(table))


def upgrade() -> None:
    conn = op.get_bind()
    _dedupe_portfolios(conn)
    _dedupe_nav(conn)
    if not _has_index(conn, "sim_portfolios", PORTFOLIO_INDEX):
        op.create_index(
            PORTFOLIO_INDEX, "sim_portfolios", ["user_id", "kind"], unique=True,
            postgresql_where=sa.text("run_id IS NULL"),
            sqlite_where=sa.text("run_id IS NULL"),
        )
    if not _has_index(conn, "portfolio_nav_daily", NAV_INDEX):
        op.create_index(
            NAV_INDEX, "portfolio_nav_daily", ["user_id", "as_of_date"], unique=True,
            postgresql_where=sa.text("run_id IS NULL"),
            sqlite_where=sa.text("run_id IS NULL"),
        )


def downgrade() -> None:
    conn = op.get_bind()
    if _has_index(conn, "portfolio_nav_daily", NAV_INDEX):
        op.drop_index(NAV_INDEX, table_name="portfolio_nav_daily")
    if _has_index(conn, "sim_portfolios", PORTFOLIO_INDEX):
        op.drop_index(PORTFOLIO_INDEX, table_name="sim_portfolios")
