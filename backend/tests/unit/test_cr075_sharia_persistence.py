"""CR075 — persist the Sharia universe: storage, read-from-row, daily refresh.

One guard per acceptance criterion (A1-A6) plus the refresh-failure-visibility
check. Never touches the network: the read path resolves from a stored snapshot
row (a local sqlite read via the autouse `_isolated_db` fixture), and the refresh
is exercised with an injected fetcher — the same fixture style as
`test_sharia_universe.py`. Any real socket on the read path is asserted to be a
bug (httpx.Client patched to raise).

The through-line is DEF093's softening: persisting the universe means a source
outage serves the held list (disclosing its held as-of) instead of blocking every
halal trade, while genuine out-of-window staleness still pauses loudly.
"""

from datetime import date, datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import select

from app.core.config import settings
from app.db import get_session
from app.db.models import ShariaUniverseSnapshotRow
from app.schemas.sharia import ShariaStatus
from app.services import sharia_universe as su
from app.services.sharia_universe import (
    STANDARD,
    ShariaSourceError,
    ShariaUniverseProvider,
    consecutive_refresh_failures,
    default_halal_universe,
    latest_snapshot,
    reset_refresh_failures,
    reset_sharia_universe_provider,
    run_sharia_refresh_tick,
    write_snapshot,
)

_HOLD_WINDOW = 30  # settings.sharia_hold_window_days default

# AAA/AAB/AAC compliant; ZZZ in the parent index but NOT compliant → SCREENED_OUT;
# anything else (NEVR) is outside the parent → UNKNOWN. Mirrors the three-state map.
_COMPLIANT = {"AAA", "AAB", "AAC"}
_PARENT = {"AAA", "AAB", "AAC", "ZZZ"}


@pytest.fixture(autouse=True)
def _reset_provider_and_counter():
    """The provider singleton and the failure counter are module globals; the
    shared `_isolated_db` fixture does not touch them, so reset both around every
    test to stop an enabled provider or a raised count leaking across cases."""
    reset_sharia_universe_provider(None)
    reset_refresh_failures()
    yield
    reset_sharia_universe_provider(None)
    reset_refresh_failures()


def _seed(*, as_of, fetched_at, compliant=_COMPLIANT, parent=_PARENT, standard=STANDARD):
    with get_session() as s:
        write_snapshot(
            s,
            standard=standard,
            source_url="spus://test",
            parent_source_url="parent://test",
            compliant=compliant,
            as_of=as_of,
            parent=parent,
            fetched_at=fetched_at,
        )


def _read_provider(*, hold_window=_HOLD_WINDOW) -> ShariaUniverseProvider:
    """A provider wired exactly like production's read path — the real
    `_snapshot_fetcher` (a local DB read), the hold window, re-reading every call."""
    return ShariaUniverseProvider(
        compliant_url="unused://",
        parent_url="unused://",
        staleness_days=hold_window,
        enabled=True,
        fetcher=su._snapshot_fetcher,
        refetch_interval_s=0,
    )


def _no_socket(monkeypatch):
    """Patch httpx.Client so any socket attempt on the read path fails loudly."""
    def _boom(*a, **k):
        raise AssertionError("read path opened a socket — httpx.Client constructed")

    monkeypatch.setattr(su.httpx, "Client", _boom)


# ── A1: a fresh stored row ⇒ resolve performs no network fetch ────────────────


def test_a1_read_resolves_from_row_without_a_socket(monkeypatch):
    _no_socket(monkeypatch)
    _seed(as_of=date(2026, 7, 22), fetched_at=datetime(2026, 7, 22, tzinfo=timezone.utc))

    # Wire the real production accessor (built from settings) and resolve through
    # it — proving the whole read path is socket-free, not just a hand-built one.
    monkeypatch.setattr(settings, "sharia_screen_enabled", True)
    monkeypatch.setattr(settings, "sharia_hold_window_days", _HOLD_WINDOW)
    reset_sharia_universe_provider(None)

    u = default_halal_universe()
    assert u.stale is False
    assert u.resolve("AAA").status is ShariaStatus.PASS
    assert u.resolve("ZZZ").status is ShariaStatus.SCREENED_OUT
    assert u.resolve("NEVR").status is ShariaStatus.UNKNOWN
    assert u.as_of == date(2026, 7, 22)


def test_a1_refresh_is_idempotent_a_fresh_row_skips_the_fetch(monkeypatch):
    """A restart performs no network fetch when a fresh row exists — the refresh
    tick finds a row younger than its fresh window and does nothing."""
    monkeypatch.setattr(settings, "sharia_screen_enabled", True)
    now = datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc)
    _seed(as_of=date(2026, 7, 25), fetched_at=now - timedelta(hours=2))  # <20h → fresh

    calls = {"n": 0}

    def _fetch():
        calls["n"] += 1
        return frozenset(_COMPLIANT), date(2026, 7, 25), frozenset(_PARENT)

    assert run_sharia_refresh_tick(fetcher=_fetch, now=now) == "skipped_fresh"
    assert calls["n"] == 0


# ── A2: source unreachable, held in-window row ⇒ resolves normally, held as-of ─


def test_a2_source_outage_with_held_in_window_row_resolves_normally(monkeypatch):
    _no_socket(monkeypatch)  # the source is "down" — the reader must not call it
    now = date(2026, 7, 25)
    held_as_of = date(2026, 7, 20)  # 5 days < 30-day hold window
    _seed(as_of=held_as_of, fetched_at=datetime(2026, 7, 20, tzinfo=timezone.utc))

    u = _read_provider().get(now=now)
    assert u.stale is False
    v = u.resolve("AAA")
    assert v.status is ShariaStatus.PASS
    assert v.as_of == held_as_of  # the surfaced date is the HELD date


# ── A3: held row aged past its window ⇒ pauses loudly ─────────────────────────


def test_a3_held_row_aged_past_window_pauses(monkeypatch):
    _no_socket(monkeypatch)
    now = date(2026, 7, 25)
    aged_as_of = now - timedelta(days=40)  # > 30-day hold window
    _seed(as_of=aged_as_of, fetched_at=datetime(2026, 7, 25, tzinfo=timezone.utc))

    u = _read_provider().get(now=now)
    assert u.stale is True
    assert u.resolve("AAA").status is ShariaStatus.UNAVAILABLE


# ── A4: fetched_at advances on a refresh where as_of does not ─────────────────


def test_a4_fetched_at_advances_while_as_of_holds(monkeypatch):
    monkeypatch.setattr(settings, "sharia_screen_enabled", True)
    fixed_as_of = date(2026, 7, 20)

    def _fetch():
        return frozenset(_COMPLIANT), fixed_as_of, frozenset(_PARENT)

    t1 = datetime(2026, 7, 24, 6, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 7, 25, 6, 0, tzinfo=timezone.utc)
    assert run_sharia_refresh_tick(fetcher=_fetch, now=t1, force=True) == "stored"
    assert run_sharia_refresh_tick(fetcher=_fetch, now=t2, force=True) == "stored"

    with get_session() as s:
        rows = (
            s.execute(
                select(ShariaUniverseSnapshotRow).order_by(
                    ShariaUniverseSnapshotRow.fetched_at
                )
            )
            .scalars()
            .all()
        )
        latest_id = latest_snapshot(s).id

    # Two append-only rows, identical source as-of, advancing fetched_at — the
    # frozen-mirror freshness signal the parent list never publishes.
    assert len(rows) == 2
    assert rows[0].as_of == fixed_as_of and rows[1].as_of == fixed_as_of
    assert rows[1].fetched_at > rows[0].fetched_at
    assert latest_id == rows[1].id  # read = latest by fetched_at


# ── A5: two processes reading the same row resolve identically ────────────────


def test_a5_two_providers_read_the_same_row_identically(monkeypatch):
    _no_socket(monkeypatch)
    now = date(2026, 7, 25)
    _seed(as_of=date(2026, 7, 22), fetched_at=datetime(2026, 7, 22, tzinfo=timezone.utc))

    p1, p2 = _read_provider(), _read_provider()
    for ticker in ("AAA", "ZZZ", "NEVR"):
        v1 = p1.get(now=now).resolve(ticker)
        v2 = p2.get(now=now).resolve(ticker)
        assert v1.status is v2.status
        assert v1.as_of == v2.as_of
    assert p1.get(now=now).resolve("AAA").status is ShariaStatus.PASS
    assert p1.get(now=now).resolve("ZZZ").status is ShariaStatus.SCREENED_OUT
    assert p1.get(now=now).resolve("NEVR").status is ShariaStatus.UNKNOWN


# ── A6: seed (empty table + unreachable source) ⇒ UNAVAILABLE, the only path ───


def test_a6_seed_empty_table_is_unavailable_and_is_the_only_outage_path(monkeypatch):
    _no_socket(monkeypatch)
    now = date(2026, 7, 25)

    # Empty table + source "down": an absent row is the seed state → UNAVAILABLE.
    u = _read_provider().get(now=now)
    assert u.stale is True
    assert u.resolve("AAA").status is ShariaStatus.UNAVAILABLE

    # Contrast — the identical outage with a valid held in-window row does NOT
    # produce UNAVAILABLE. The seed (no row) is the only outage path to it.
    _seed(as_of=date(2026, 7, 22), fetched_at=datetime(2026, 7, 22, tzinfo=timezone.utc))
    assert _read_provider().get(now=now).resolve("AAA").status is ShariaStatus.PASS


def test_seed_fetcher_raises_on_empty_table():
    """The seam that makes A6 work: with no row, the read-path fetcher raises,
    which the provider converts into a loud pause rather than an empty universe."""
    with pytest.raises(ShariaSourceError):
        su._snapshot_fetcher()


# ── Refresh-failure visibility: loud on the REFRESHER, not the reader ─────────


class _CapturingLogger:
    def __init__(self):
        self.events: list[tuple[str, dict]] = []

    def _rec(self, event, **kw):
        self.events.append((event, kw))

    error = warning = info = exception = _rec

    @property
    def names(self):
        return [e for e, _ in self.events]


def test_refresh_failure_is_loud_on_the_refresher_not_the_reader(monkeypatch):
    monkeypatch.setattr(settings, "sharia_screen_enabled", True)
    now = datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc)
    # Held row: in-window as-of, but fetched_at 2 days ago → a refresh is due.
    _seed(as_of=date(2026, 7, 22), fetched_at=now - timedelta(days=2))

    cap = _CapturingLogger()
    monkeypatch.setattr(su, "logger", cap)

    def _boom():
        raise ShariaSourceError("source 503")

    for _ in range(su._REFRESH_FAILURE_LOUD_THRESHOLD):
        assert run_sharia_refresh_tick(fetcher=_boom, now=now) == "fetch_failed"

    # The refresher's degrade-loudly signal rises and fires its distinct alarm.
    assert consecutive_refresh_failures() == su._REFRESH_FAILURE_LOUD_THRESHOLD
    assert "sharia_refresh_failing_repeatedly" in cap.names
    assert cap.names.count("sharia_refresh_failed") == su._REFRESH_FAILURE_LOUD_THRESHOLD

    # The reader is untouched — the held in-window row still resolves normally.
    _no_socket(monkeypatch)
    assert _read_provider().get(now=now.date()).resolve("AAA").status is ShariaStatus.PASS


def test_a_successful_refresh_resets_the_failure_counter(monkeypatch):
    monkeypatch.setattr(settings, "sharia_screen_enabled", True)
    now = datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc)

    def _boom():
        raise ShariaSourceError("down")

    assert run_sharia_refresh_tick(fetcher=_boom, now=now, force=True) == "fetch_failed"
    assert consecutive_refresh_failures() == 1

    def _ok():
        return frozenset(_COMPLIANT), date(2026, 7, 25), frozenset(_PARENT)

    assert run_sharia_refresh_tick(fetcher=_ok, now=now, force=True) == "stored"
    assert consecutive_refresh_failures() == 0


def test_refresh_disabled_does_no_network_and_writes_nothing(monkeypatch):
    monkeypatch.setattr(settings, "sharia_screen_enabled", False)
    calls = {"n": 0}

    def _fetch():
        calls["n"] += 1
        return frozenset(_COMPLIANT), date(2026, 7, 25), frozenset(_PARENT)

    assert run_sharia_refresh_tick(fetcher=_fetch, force=True) == "disabled"
    assert calls["n"] == 0
    with get_session() as s:
        assert latest_snapshot(s) is None
