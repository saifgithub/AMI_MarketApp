"""DEF377 — the sweep fired on a stored bracket nobody had validated.

Found on 2026-08-26 by querying live Alpha for open positions whose bracket sits
on the wrong side of its own entry. Four rows, all long:

    IBM    1 @ 220.34   stop 345.96  target 415.89  -> closed "lost"
    TSLA   1 @ 422.24   stop 350.00  target 410.00  -> closed "won"
    HPQ    5 @  28.52   stop  31.28  target  37.61  -> closed "lost"
    GGG    5 @  81.94   stop 179.72  target 216.04  -> still open

Every closed one resolved within a second of opening, at `closed_price ==
entry_price`, `realised_pnl = 0.00` and no `close_price_source`. So the money
did not move — but the *verdict* did: two fabricated losses and one fabricated
win, stamped on the agent's track record, on positions the market never touched.
GGG was the one still live, and the next market-hours sweep would have force-sold
it against a real $78.70 quote for a real loss.

**Why the existing guards could not catch it.** DEF312 refuses a wrong-side
bracket at `_execute_fill`, and CR189 acceptance 6 refuses a BLEND that lands
wrong-side. Both are submit-time. Neither can reach a row that is already in the
table — written before those guards existed, or by a backfill, or by a migration.
`evaluate_outcomes` read `stop`/`target` straight off the row and handed them to
`bracket_hit`, which had no `entry` and therefore no way to ask. DEF190's shape,
for the third time in this file's neighbourhood: the guard is real, it is just
not on the path that moves the money.

**The fix is structural, not another call-site check.** `bracket_hit` now takes a
REQUIRED `entry` and RAISES `WrongSideBracketError` — a return value would be
ignorable, and forgetting to check is the exact failure being fixed. A future
third fire site cannot omit the argument and cannot silently swallow the result.

Aimed at the PATHS as well as the predicate, for the reason DEF305's file states:
a predicate that is correct and uncalled is what this defect already was.
"""

from __future__ import annotations

import ast
from pathlib import Path
from uuid import uuid4

import pytest
import structlog

from app.db import get_session
from app.db.models import SimTradeRow
from app.schemas.trade import OrderType, Side
from app.services.coach_engine import hydrate_coach_mandate
from app.services.market_data import Quote
from app.services.sim_engine import SimEngine
from app.trading_math.order_pricing import (
    LotBracket,
    WrongSideBracketError,
    blended_bracket,
    bracket_hit,
)

_ENGINE = Path(__file__).resolve().parents[2] / "app" / "services" / "sim_engine.py"

#: The four rows exactly as they were found on Alpha, as
#: (ticker, entry, stop, target). Not invented fixtures.
LIVE_ROWS = [
    ("IBM", 220.335, 345.96, 415.89),
    ("TSLA", 422.24, 350.00, 410.00),
    ("HPQ", 28.52, 31.28, 37.61),
    ("GGG", 81.94, 179.72, 216.04),
]


# ── The rule ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("ticker,entry,stop,target", LIVE_ROWS)
def test_every_row_found_on_alpha_is_refused(ticker, entry, stop, target):
    """At the mark that actually liquidated it, and at a mark far away from it.

    The second half is the point: a wrong-side bracket is not wrong *at some
    price*, it is wrong at every price, which is why "wait for a better quote"
    is not a remedy and why this is an ERROR rather than a WARNING.
    """
    for mark in (entry, stop, target, 0.01, 10_000.0):
        with pytest.raises(WrongSideBracketError):
            bracket_hit(
                is_short=False, mark=mark, entry=entry, stop=stop, target=target,
            )


def test_the_refusal_names_the_level_and_the_entry():
    """CR040 — an operator has to be able to act on the line. A reason that says
    only "invalid" sends them back to the database to work out which number."""
    with pytest.raises(WrongSideBracketError) as exc:
        bracket_hit(
            is_short=False, mark=81.5, entry=81.94, stop=179.72, target=216.04,
        )
    assert "179.72" in exc.value.reason
    assert "81.94" in exc.value.reason


def test_a_correct_long_bracket_still_fires_both_ways():
    """Non-vacuity. A fix that raises on everything passes every test above and
    silently disables every stop and target in the product."""
    assert bracket_hit(
        is_short=False, mark=94.0, entry=100.0, stop=95.0, target=120.0,
    ) == "lost"
    assert bracket_hit(
        is_short=False, mark=121.0, entry=100.0, stop=95.0, target=120.0,
    ) == "won"
    assert bracket_hit(
        is_short=False, mark=100.0, entry=100.0, stop=95.0, target=120.0,
    ) is None


def test_a_correct_short_bracket_still_fires_both_ways():
    """CR171 §5's inversion survives the new argument — and the SAME numbers
    that are legal for a short are refused for a long, so an implementation
    that ignored `is_short` could not pass both halves."""
    assert bracket_hit(
        is_short=True, mark=106.0, entry=100.0, stop=105.0, target=80.0,
    ) == "lost"
    assert bracket_hit(
        is_short=True, mark=79.0, entry=100.0, stop=105.0, target=80.0,
    ) == "won"
    with pytest.raises(WrongSideBracketError):
        bracket_hit(
            is_short=False, mark=106.0, entry=100.0, stop=105.0, target=80.0,
        )


def test_a_half_set_bracket_is_judged_on_the_half_that_exists():
    """A stop-only position is normal. Refusing it because `target is None`
    would take the guard from "refuses four rows" to "refuses the book"."""
    assert bracket_hit(
        is_short=False, mark=94.0, entry=100.0, stop=95.0, target=None,
    ) == "lost"
    with pytest.raises(WrongSideBracketError):
        bracket_hit(
            is_short=False, mark=94.0, entry=100.0, stop=105.0, target=None,
        )
    assert bracket_hit(
        is_short=False, mark=100.0, entry=100.0, stop=None, target=None,
    ) is None


def test_entry_is_a_required_argument():
    """The structural half. `bracket_hit` cannot be called the old way, so a
    third fire site cannot inherit the defect by simply not knowing about it."""
    with pytest.raises(TypeError):
        bracket_hit(is_short=False, mark=94.0, stop=95.0, target=120.0)


# ── The blend carries its own entry ────────────────────────────────────────

def test_the_blend_returns_the_share_weighted_entry():
    """CR189 weights the levels by open shares; DEF377 needs the entry weighted
    the same way, from the same loop. Two derivations of one weighting is
    DEF098's shape one layer in, which is why it is not computed at the call
    site."""
    blend = blended_bracket([
        LotBracket(quantity_open=10, stop=95.0, target=120.0, entry=100.0),
        LotBracket(quantity_open=30, stop=99.0, target=130.0, entry=110.0),
    ])
    assert blend.entry == 107.5
    assert (blend.stop, blend.target) == (98.0, 127.5)


def test_a_sold_out_lot_weighs_nothing_in_the_entry_either():
    blend = blended_bracket([
        LotBracket(quantity_open=0.0, stop=95.0, target=None, entry=1_000.0),
        LotBracket(quantity_open=10, stop=99.0, target=None, entry=110.0),
    ])
    assert blend.entry == 110.0


def test_an_unbracketed_lot_still_counts_toward_the_entry():
    """It holds shares the blended stop would liquidate, so it must be weighed
    in the entry that stop is judged against — even though it contributes no
    level of its own."""
    blend = blended_bracket([
        LotBracket(quantity_open=10, stop=95.0, target=None, entry=100.0),
        LotBracket(quantity_open=10, stop=None, target=None, entry=200.0),
    ])
    assert blend.stop == 95.0
    assert blend.entry == 150.0


# ── The paths ──────────────────────────────────────────────────────────────

def _functions() -> dict[str, ast.FunctionDef]:
    tree = ast.parse(_ENGINE.read_text(encoding="utf-8"))
    return {
        n.name: n for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


#: Every function in `sim_engine` that fires an exit bracket.
BRACKET_FIRING = ["evaluate_outcomes", "evaluate_short_brackets"]


@pytest.mark.parametrize("name", BRACKET_FIRING)
def test_every_bracket_firing_path_handles_the_refusal(name):
    fns = _functions()
    assert name in fns, f"{name} no longer exists in sim_engine — update this list"
    body = ast.unparse(fns[name])
    assert "WrongSideBracketError" in body, (
        f"{name} fires an exit bracket and does not handle the refusal. Either "
        "it swallows it as a generic exception, or it is about to crash a sweep."
    )
    assert "_log_wrong_side" in body, (
        f"{name} refuses silently. A position that stops being liquidated also "
        "stopped being protected, and nobody learns why (CR040)."
    )


def test_the_sweep_skips_rather_than_crashing_the_whole_pass():
    """One bad row must not take the other positions down with it — that would
    turn a wrong verdict on one ticker into no verdicts on any."""
    src = ast.unparse(_functions()["evaluate_outcomes"])
    idx = src.index("WrongSideBracketError")
    assert "continue" in src[idx : idx + 200]


# ── The behaviour, end to end ──────────────────────────────────────────────

class _Pinned:
    def __init__(self, price: float):
        self.price = price

    def quote(self, ticker: str) -> Quote:
        return Quote(price=self.price, source="yfinance")

    def history(self, *a, **k):  # pragma: no cover
        return []

    def news(self, *a, **k):  # pragma: no cover
        return []

    def earnings(self, *a, **k):  # pragma: no cover
        return None


def _mandate():
    return hydrate_coach_mandate(
        {"plan": "trader", "single_name_cap_pct": 100.0, "max_open_risk_pct": 100.0}
    )


def _buy(sim, user_id, ticker, qty, **kw):
    r = sim.submit(user_id=user_id, ticker=ticker, side=Side.BUY, quantity=qty,
                   mandate=_mandate(), order_type=OrderType.MARKET, **kw)
    assert r.accepted and r.trade is not None, r.compliance.violations
    return r.trade


def _corrupt(trade_id, *, stop=None, target=None):
    """Write the bracket straight to the row, bypassing every submit guard.

    This is not a contrivance — it is precisely how the four live rows exist.
    They were written before DEF312 shipped, by a path that no longer runs, and
    no submit-time guard however good can reach backwards and fix them.
    """
    with get_session() as s:
        row = s.get(SimTradeRow, trade_id)
        if stop is not None:
            row.stop = stop
        if target is not None:
            row.target = target
        s.flush()


def test_the_ggg_row_is_not_liquidated():
    """The live one, reproduced. Entry $81.94, stop $179.72, real mark $78.70:
    `mark <= stop` is true, so before this fix the sweep sold 5 shares at market
    and recorded a stop-out the market never delivered."""
    prov = _Pinned(81.94)
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    trade = _buy(sim, user_id, "GGG", 5, stop=75.0, target=95.0)
    _corrupt(trade.id, stop=179.72, target=216.04)

    prov.price = 78.70
    # `structlog.testing.capture_logs`, not `capsys`: the renderer writes to the
    # stdout it captured at configure time, so a stdout assertion passes alone
    # and fails inside the full suite depending on which test configured logging
    # first. Both of these did exactly that. Capturing the EVENT also asserts
    # more than the string did — the level and the fields, not their rendering.
    with structlog.testing.capture_logs() as logs:
        updates = sim.evaluate_outcomes(user_id)

    assert updates == []
    with get_session() as s:
        assert s.get(SimTradeRow, trade.id).status == "open"
    assert sim.ensure_portfolio(user_id).holdings[0].quantity == 5
    refusals = [e for e in logs if e["event"] == "sim_bracket_wrong_side"]
    assert len(refusals) == 1
    assert refusals[0]["log_level"] == "error", (
        "a row that never self-heals is not a warning"
    )
    assert refusals[0]["positions"][0]["ticker"] == "GGG"
    reason = refusals[0]["positions"][0]["reason"]
    assert "179.72" in reason and "81.94" in reason


def test_a_healthy_position_beside_a_corrupt_one_still_fires():
    """The refusal is per position, not per pass. Otherwise one bad row on a
    portfolio disables every stop the user has — a far worse defect than the
    one being fixed, and one that would pass every other test here."""
    prov = _Pinned(100.0)
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    bad = _buy(sim, user_id, "GGG", 5, stop=90.0)
    good = _buy(sim, user_id, "NVDA", 5, stop=95.0)
    _corrupt(bad.id, stop=179.72)

    prov.price = 94.0
    updates = sim.evaluate_outcomes(user_id)

    assert [u.new_status for u in updates] == ["lost"]
    with get_session() as s:
        assert s.get(SimTradeRow, bad.id).status == "open"
        assert s.get(SimTradeRow, good.id).status == "lost"


def test_the_sweep_still_liquidates_a_correctly_bracketed_position():
    """Non-vacuity for the whole file. Every test above passes on a build where
    `evaluate_outcomes` returns immediately, which would be a silently dead
    risk control on every position in the product."""
    prov = _Pinned(100.0)
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    trade = _buy(sim, user_id, "NVDA", 10, stop=95.0, target=120.0)

    prov.price = 94.0
    updates = sim.evaluate_outcomes(user_id)

    assert [u.new_status for u in updates] == ["lost"]
    with get_session() as s:
        assert s.get(SimTradeRow, trade.id).status == "lost"


def test_a_corrupt_lot_diluted_by_a_large_healthy_one_is_judged_on_the_blend():
    """The documented edge, asserted rather than left implicit.

    CR189 is explicit that a position has ONE level and the sweep fires on that
    level, so that level is what gets validated. 1000 shares at $100 stop $90
    beside 1 share at $50 stop $200 blends to stop $90.11 against entry $99.95 —
    which is a sane bracket, and firing it is correct. The guard protects the
    number that actually fires; it is not a per-row integrity scan, and this
    test exists so nobody later reads it as one.
    """
    blend = blended_bracket([
        LotBracket(quantity_open=1000, stop=90.0, target=None, entry=100.0),
        LotBracket(quantity_open=1, stop=200.0, target=None, entry=50.0),
    ])
    assert bracket_hit(
        is_short=False, mark=89.0, entry=blend.entry, stop=blend.stop, target=None,
    ) == "lost"


# ── The short book's half of the same fix ──────────────────────────────────

@pytest.fixture
def _no_borrow_socket(monkeypatch):
    """§4 resolves the borrow rate at open through yfinance. Pinned so these
    tests do not depend on Yahoo being up (CR171's own fixture, same reason)."""
    monkeypatch.setattr(
        "app.services.short_borrow_rate._fetch_info", lambda ticker: {},
    )


def _short_mandate():
    return hydrate_coach_mandate({
        "plan": "trader",
        "single_name_cap_pct": 100.0,
        "max_open_risk_pct": 100.0,
        "compliance": {"long_only": False},
    })


def _open_short(sim, user_id, *, ticker="AAPL", qty=10, **kw):
    r = sim.submit(
        user_id=user_id, ticker=ticker, side=Side.SELL, quantity=qty,
        mandate=_short_mandate(), order_type=OrderType.MARKET, **kw,
    )
    assert r.accepted, r.compliance.violations
    return r


def _short_row(user_id):
    from sqlalchemy import select

    from app.db.models import SimShortPositionRow
    with get_session() as s:
        return s.execute(
            select(SimShortPositionRow).where(
                SimShortPositionRow.user_id == user_id
            )
        ).scalars().all()


def _corrupt_short(user_id, *, stop):
    from sqlalchemy import select

    from app.db.models import SimShortPositionRow
    with get_session() as s:
        row = s.execute(
            select(SimShortPositionRow).where(
                SimShortPositionRow.user_id == user_id
            )
        ).scalars().first()
        row.stop = stop
        s.flush()


def test_a_stored_short_bracket_on_the_wrong_side_is_not_covered(
    _no_borrow_socket,
):
    """The short book's version, and the reason it is a separate test.

    `evaluate_short_brackets` reads its own table and passes its own entry, so
    a fix that plumbed `entry` correctly into the long sweep and passed a zero
    into this one would refuse nothing here and every path assertion in this
    file would still be green. The consequence is worse than the long case:
    a wrong-side short is force-covered at market and the user is BILLED the
    difference.
    """
    prov = _Pinned(100.0)
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    _open_short(sim, user_id, qty=2, stop=105.0, target=90.0)
    _corrupt_short(user_id, stop=95.0)

    prov.price = 96.0
    with structlog.testing.capture_logs() as logs:
        assert sim.evaluate_short_brackets(user_id) == []
    assert _short_row(user_id)[0].state == "open"
    refusals = [e for e in logs if e["event"] == "sim_bracket_wrong_side"]
    assert len(refusals) == 1
    assert refusals[0]["function"] == "evaluate_short_brackets"
    assert refusals[0]["log_level"] == "error"


def test_a_correctly_bracketed_short_is_still_covered(_no_borrow_socket):
    """Non-vacuity for the test above — CR171 acceptance 9, re-pinned."""
    prov = _Pinned(100.0)
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    _open_short(sim, user_id, qty=2, stop=105.0, target=90.0)

    prov.price = 106.0
    assert sim.evaluate_short_brackets(user_id) == ["AAPL"]
    assert _short_row(user_id)[0].close_reason == "stop"


# ── The census gate must not fail on rows nobody can act on ────────────────

def test_the_census_only_fails_on_a_bracket_a_sweep_can_still_read():
    """The first run of the census against the promoted build exited 1 on three
    rows that had already been remediated: their `status` was corrected but the
    levels they were entered with are still on the row, as history.

    A gate whose failing state is its normal state teaches the operator to
    reason past it — DEF277's shape, and `/promote-to-alpha` carries three
    separate scars from it (the tree gate, the audit gate, the `/v1/llm/status`
    403). So the exit code is ACTIVE only.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "def377_census",
        Path(__file__).resolve().parents[2] / "scripts"
        / "def377_wrong_side_census.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert mod.is_actionable("open") is True
    for terminal in ("won", "lost", "closed"):
        assert mod.is_actionable(terminal) is False, (
            f"a {terminal!r} row's levels are a record, not an instruction"
        )
    assert mod.is_actionable(None) is False


def test_the_census_actionable_set_matches_what_the_sweeps_actually_filter():
    """Non-vacuity, and the reason the set is not just a literal in the script.

    `evaluate_outcomes` keeps rows on `status == "open"` and
    `evaluate_short_brackets` queries `state == "open"`. If either filter
    changes, the census silently stops covering a state that CAN act — which is
    the vacuity DEF200's ratchet exists to catch, one gate over.
    """
    long_src = ast.unparse(_functions()["evaluate_outcomes"])
    short_src = ast.unparse(_functions()["evaluate_short_brackets"])
    assert "r.status == 'open'" in long_src or 'r.status == "open"' in long_src
    assert "state == 'open'" in short_src or 'state == "open"' in short_src
