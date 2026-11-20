"""DEF308 / ISS001 Phase 3 (site 9 of 9) — `games_service.ensure_field` creates one open field per
(cadence, starts_on) even when two callers first-touch the same period at once.

The arbiter is the partial unique index `uq_game_fields_open_cadence_start`; the outcome is
`or_update` (the loser still refreshes the state column, exactly as the found-row branch does). The
Postgres path of the same shape is covered by `backend/scripts/iss001_pg_concurrency.py`.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db import get_session
from app.db.models import GameFieldRow
from app.services import games_service as games
from tests.unit.iss001_race import winner_commits_first

_NOW = datetime(2026, 8, 10, 3, 0, tzinfo=timezone.utc)


def _open_rows(cadence: str, *, include_abandoned: bool = False) -> list[GameFieldRow]:
    with get_session() as s:
        q = select(GameFieldRow).where(GameFieldRow.cadence == cadence, GameFieldRow.kind == "open")
        if not include_abandoned:
            q = q.where(GameFieldRow.state != "abandoned")
        rows = s.execute(q).scalars().all()
        s.expunge_all()
        return list(rows)


def _probe(cadence: str) -> dict:
    """The column values `ensure_field` would insert for `cadence` at `_NOW`, read by letting it
    insert once and then removing that row, so a test can stage a winner with identical values."""
    with get_session() as s:
        f = games.ensure_field(s, cadence, now=_NOW)
        vals = dict(
            cadence=f.cadence, starts_on=f.starts_on, ends_on=f.ends_on, locks_at=f.locks_at,
            entry_opens_at=f.entry_opens_at, kind="open", points_policy="full",
            benchmark_ticker="SPY", entrant_count=0, min_entrants=f.min_entrants,
            max_wait_days=f.max_wait_days,
        )
        s.delete(f)
    return vals


@pytest.mark.parametrize("cadence", ["week", "quarter"])
def test_ensure_field_that_loses_the_race_returns_the_winners_row(monkeypatch, cadence):
    """Lost race: another container committed the period's field between our SELECT and INSERT.
    The winner is stored with a stale `state`; the loser returns the same row, refreshed."""
    vals = _probe(cadence)
    key = {"cadence": vals.pop("cadence"), "starts_on": vals.pop("starts_on")}
    race = winner_commits_first(monkeypatch, games, GameFieldRow, winner_values={**vals, "state": "announced"})
    with get_session() as s:
        field = games.ensure_field(s, cadence, now=_NOW)
        got_id, got_state = field.id, field.state
    assert race["fired"]
    assert got_id == race["winner_id"]
    assert got_state in ("announced", "entry_open", "locked", "live")
    rows = _open_rows(cadence)
    assert [r.id for r in rows] == [race["winner_id"]]
    assert rows[0].starts_on == key["starts_on"]


def test_the_loser_is_not_handed_an_abandoned_twin(monkeypatch):
    """A rolling lobby abandoned at the same calendar start is outside the index; the loser's
    re-read must carry the index predicate or it could return the dead row."""
    vals = _probe("quarter")
    dead_id = None
    with get_session() as s:
        dead = GameFieldRow(**{**vals, "state": "abandoned"})
        s.add(dead)
        s.flush()
        dead_id = dead.id
    race = winner_commits_first(monkeypatch, games, GameFieldRow, winner_values={**vals, "state": "entry_open"})
    with get_session() as s:
        field = games.ensure_field(s, "quarter", now=_NOW)
        got_id = field.id
    assert race["fired"]
    assert got_id == race["winner_id"] != dead_id
    assert len(_open_rows("quarter")) == 1
    assert len(_open_rows("quarter", include_abandoned=True)) == 2


def test_the_index_rejects_a_second_live_open_field_but_not_abandoned_or_private():
    vals = _probe("week")
    with get_session() as s:
        s.add(GameFieldRow(**{**vals, "state": "entry_open"}))
    with get_session() as s:
        s.add(GameFieldRow(**{**vals, "state": "abandoned"}))
        s.add(GameFieldRow(**{**vals, "state": "entry_open", "kind": "private", "join_code": "J-1"}))
    with pytest.raises(IntegrityError):
        with get_session() as s:
            s.add(GameFieldRow(**{**vals, "state": "locked"}))


def test_concurrent_first_touch_of_a_period_creates_one_field():
    n = 6
    barrier, ids, errors = threading.Barrier(n), [], []

    def work():
        try:
            barrier.wait()
            with get_session() as s:
                ids.append(games.ensure_field(s, "week", now=_NOW).id)
        except Exception as e:  # pragma: no cover - would fail the assert below
            errors.append(e)

    ts = [threading.Thread(target=work) for _ in range(n)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert errors == []
    assert len(ids) == n and len(set(ids)) == 1
    assert len(_open_rows("week")) == 1
