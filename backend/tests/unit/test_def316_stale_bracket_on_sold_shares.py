"""DEF316 — a bracket outlived the shares it protected, and fired on them.

A ticket SELL reduces the holding and writes its OWN `sim_trades` row. It
deliberately leaves the original BUY row `status='open'`, and that is not an
oversight: `def110_backfill.py`'s phantom-share detector computes

    expected(portfolio, ticker) = Σ qty over open BUY rows
                                − Σ qty over open SELL rows

so closing the buy row on a sell would subtract the same exit twice and drive
`expected` negative. The row is *meant* to outlive its position.

What was never connected is the row's own **stop/target**. `evaluate_outcomes`
selects every open BUY row and compares it to the mark, so once the shares were
gone the sweep would still "stop out" a position that no longer existed:

  1. Buy 10 NVDA at $100 with a stop at $95.
  2. Sell all 10 through the ticket at $103. Holding → 0, a SELL row is written,
     the BUY row stays open with its stop still live.
  3. Price drifts to $94. The sweep transitions the BUY row to `lost`.

Three things break at once. The exit is now recorded twice, so `expected()` goes
negative and the detector reports phantom shares against a holding of zero. The
user is shown a LOST outcome on a position they exited days earlier. And its
realised P&L is **$0.00**, because `_apply_sell_row` clamps to a holding that is
gone — so History shows a stopped-out trade that lost nothing, which is the
DEF166 clamp telling the truth about a close that should never have happened.

This is DEF311 one layer in. That fix retired the orphaned RESTING sell at
`_apply_sell_row`, "the chokepoint every share reduction crosses" — and left the
trade row's own bracket, which crosses nothing, connected to nothing. Both now
ask `_held_quantity` the same question through the same function.

## DEF318 — and then the gate itself was too coarse

`_held_quantity` asks *"is this TICKER flat"*, which is right when the user
exited and blind when they re-entered. Sell out of NVDA at $103, buy back in
with a stop at $90, and the first lot's dead $95 stop is live again against the
second lot's shares — measured firing at $94, stamping −$60.00 against the wrong
entry, stopping the user out at a price they never named. The gate is now per
LOT, off `compute_lots_fifo`'s `quantity_open` (CR029-MATH, audited), and the
close is capped at the lot's own remaining shares so a half-consumed lot cannot
eat a later one's. Both gates stay: `lot_open` is the trade ledger's view,
`_held_quantity` is what `sim_holdings` carries, and a gap between them is the
exact phantom-share condition `def110_backfill.py` exists to find.

## Why this became reachable now

`sim_trades` has never held a training SELL row on Alpha (measured 2026-08-15:
38 training buys, 0 sells). Every one of the 31 training exits went through
`manual_close` or `evaluate_outcomes`, both of which close the BUY row and write
no sell row, so no buy row was ever left standing over sold shares. CR188 slice 2
deleted CLOSE POSITION and the per-row `×` — ticket-sell is now the only training
exit, so the path that leaves a stale bracket is the only path there is.

`manual_close` carries the identical gate, and is the one that actually left
residue: pre-DEF269 it reached across lanes and stamped three GAME buy rows
`closed` against the TRAINING portfolio, which held none of those tickers. Each
recorded a close that moved no shares and no cash, and 2,317 shares of
`expected()` went permanently negative behind them (DEF317 cleans the data).
"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select

from app.db import get_session
from app.db.models import SimTradeRow
from app.schemas.trade import OrderType, Side
from app.services.coach_engine import hydrate_coach_mandate
from app.services.market_data import Quote
from app.services.sim_engine import SimEngine


class _Pinned:
    def __init__(self, prices: dict[str, float], source: str = "yfinance"):
        self.prices = {k.upper(): v for k, v in prices.items()}
        self.source = source

    def quote(self, ticker: str) -> Quote | None:
        return Quote(price=self.prices.get(ticker.upper(), 100.0), source=self.source)

    def history(self, *a, **k):  # pragma: no cover
        return []

    def news(self, *a, **k):  # pragma: no cover
        return []

    def earnings(self, *a, **k):  # pragma: no cover
        return None


def _mandate(**over):
    base = {"plan": "trader", "single_name_cap_pct": 100.0, "max_open_risk_pct": 100.0}
    base.update(over)
    return hydrate_coach_mandate(base)


def _buy(sim, user_id, ticker, qty, **kw):
    r = sim.submit(user_id=user_id, ticker=ticker, side=Side.BUY, quantity=qty,
                   mandate=_mandate(), order_type=OrderType.MARKET, **kw)
    assert r.accepted and r.trade is not None
    return r.trade


def _sell(sim, user_id, ticker, qty):
    r = sim.submit(user_id=user_id, ticker=ticker, side=Side.SELL, quantity=qty,
                   mandate=_mandate(), order_type=OrderType.MARKET)
    assert r.accepted, "precondition: the sell must fill"
    return r


def _row(trade_id) -> SimTradeRow:
    with get_session() as s:
        return s.get(SimTradeRow, trade_id)


def _expected(user_id, ticker) -> float:
    """`def110_backfill.py`'s formula, re-derived here on purpose.

    Importing the script is not possible (it lives outside the image and expects
    a real `DATABASE_URL`), so the invariant is asserted against a local copy of
    the arithmetic. If the formula there changes, this test still pins what the
    ENGINE must keep true for any such formula to work: one exit, counted once.
    """
    with get_session() as s:
        rows = s.execute(
            select(SimTradeRow).where(
                SimTradeRow.user_id == user_id,
                SimTradeRow.ticker == ticker,
                SimTradeRow.status == "open",
            )
        ).scalars().all()
    total = 0.0
    for t in rows:
        side = t.side.value if hasattr(t.side, "value") else str(t.side)
        total += float(t.quantity) if side == "buy" else -float(t.quantity)
    return total


# ── The defect ─────────────────────────────────────────────────────────────


def test_the_sweep_does_not_stop_out_shares_already_sold():
    """The reported sequence. Before the fix the BUY row transitioned to `lost`."""
    prov = _Pinned({"NVDA": 100.0})
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    trade = _buy(sim, user_id, "NVDA", 10, stop=95.0)

    prov.prices["NVDA"] = 103.0
    _sell(sim, user_id, "NVDA", 10)
    assert _row(trade.id).status == "open", (
        "precondition: the BUY row must survive the sell — expected() needs it"
    )

    prov.prices["NVDA"] = 94.0  # straight through the stop
    updates = sim.evaluate_outcomes(user_id)

    assert updates == []
    assert _row(trade.id).status == "open"


def test_the_exit_stays_counted_exactly_once():
    """The precondition `expected()` rests on, asserted directly.

    Buy 10, sell 10: `expected` is 10 − 10 = 0 against a holding of 0. The sweep
    must not change that. Transitioning the buy row drops it out of the sum and
    leaves the sell row subtracting alone — `expected` = −10 against a holding of
    0, which the detector reads as 10 PHANTOM shares that do not exist.
    """
    prov = _Pinned({"NVDA": 100.0})
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    _buy(sim, user_id, "NVDA", 10, stop=95.0)
    _sell(sim, user_id, "NVDA", 10)

    assert _expected(user_id, "NVDA") == 0.0

    prov.prices["NVDA"] = 94.0
    sim.evaluate_outcomes(user_id)

    assert _expected(user_id, "NVDA") == 0.0, "the exit was counted twice"


def test_manual_close_refuses_a_row_whose_shares_are_gone():
    """Returns None, which the route already renders as "trade not found or
    already closed" — the true statement. The position IS closed; this row just
    never recorded it, and stamping it now would record the exit a second time.
    """
    prov = _Pinned({"NVDA": 100.0})
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    trade = _buy(sim, user_id, "NVDA", 10)
    _sell(sim, user_id, "NVDA", 10)

    assert sim.manual_close(user_id, trade.id) is None
    assert _row(trade.id).status == "open"
    assert _expected(user_id, "NVDA") == 0.0


# ── The gate must not make the sweep inert (P21) ────────────────────────────


def test_a_real_stop_still_fires():
    """The half that matters more than the fix: this project's recurring defect
    is a check that is present in the source and inert at runtime. A gate on
    "is the position flat" placed one step too early would silently disable
    every bracket in the app, and every other test here would still pass.
    """
    prov = _Pinned({"NVDA": 100.0})
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    trade = _buy(sim, user_id, "NVDA", 10, stop=95.0)

    prov.prices["NVDA"] = 94.0
    updates = sim.evaluate_outcomes(user_id)

    assert [u.new_status for u in updates] == ["lost"]
    assert _row(trade.id).status == "lost"
    assert _row(trade.id).realised_pnl < 0


def test_a_partial_sell_leaves_the_bracket_live_on_what_is_still_held():
    """The gate is "flat", not "fewer shares than the row bought".

    Sell 4 of 10 and the remaining 6 are still a real position with a real stop.
    DEF166 already settled what a clamped close does to P&L — it stamps on the
    shares actually sold — and this must keep reaching that path rather than
    skipping the row for being partially reduced.
    """
    prov = _Pinned({"NVDA": 100.0})
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    trade = _buy(sim, user_id, "NVDA", 10, stop=95.0)
    _sell(sim, user_id, "NVDA", 4)

    prov.prices["NVDA"] = 94.0
    updates = sim.evaluate_outcomes(user_id)

    assert [u.new_status for u in updates] == ["lost"]
    # Clamped to the 6 still held, not the 10 the row bought: (94 − 100) × 6.
    assert _row(trade.id).realised_pnl == -36.0


def test_a_short_bracket_is_untouched_by_the_gate():
    """Shorts do not live in `sim_trades` at all — they are
    `sim_short_positions`, swept by `evaluate_short_brackets`. A gate reading
    `sim_holdings` must not reach them: a short's holding is legitimately zero,
    so a gate applied one table over would disable every short's stop.
    """
    prov = _Pinned({"TSLA": 100.0})
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    r = sim.submit(
        user_id=user_id, ticker="TSLA", side=Side.SELL, quantity=10,
        # `long_only` lives under `compliance`; passing it flat hydrates to the
        # default (`True`) and the short is refused before the sweep is reached.
        mandate=_mandate(compliance={"long_only": False, "halal": False}),
        order_type=OrderType.MARKET, stop=110.0, target=90.0,
    )
    assert r.accepted, r.compliance.violations

    prov.prices["TSLA"] = 89.0  # through the short's TARGET
    closed = sim.evaluate_short_brackets(user_id)

    assert closed == ["TSLA"]


# ── DEF318 — the gate was per TICKER, and a re-entry walks straight past it ──


def test_a_dead_lots_stop_does_not_fire_on_a_later_lots_shares():
    """The measured case. DEF316's gate asks "is this ticker flat" — correct
    when the user exited, blind when they re-entered.

    Lot 1: 10 NVDA @ $100, stop $95. Sold out in full at $103. Lot 2: 10 NVDA
    @ $103, stop $90 — deliberately BELOW lot 1's. At $94 the position is
    comfortably above its own stop, and lot 1's dead $95 stop fired anyway:
    10 shares sold, `realised_pnl` −$60.00 stamped against lot 1's $100 entry
    rather than lot 2's $103. The user was stopped out at a price they had
    never named a stop at.
    """
    prov = _Pinned({"NVDA": 100.0})
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    dead = _buy(sim, user_id, "NVDA", 10, stop=95.0)

    prov.prices["NVDA"] = 103.0
    _sell(sim, user_id, "NVDA", 10)
    live = _buy(sim, user_id, "NVDA", 10, stop=90.0)

    prov.prices["NVDA"] = 94.0  # above the LIVE stop, below the DEAD one
    updates = sim.evaluate_outcomes(user_id)

    assert updates == []
    assert _row(dead.id).status == "open"
    assert _row(live.id).status == "open"
    p = sim.ensure_portfolio(user_id)
    assert [h.quantity for h in p.holdings] == [10.0], "the position was liquidated"


def test_the_live_lots_own_stop_still_fires_after_a_re_entry():
    """Non-vacuity for the case above: the same book, the price through the
    stop the user actually set. Skipping BOTH lots would satisfy the previous
    test and silently disarm every re-entered position (P21)."""
    prov = _Pinned({"NVDA": 100.0})
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    _buy(sim, user_id, "NVDA", 10, stop=95.0)
    prov.prices["NVDA"] = 103.0
    _sell(sim, user_id, "NVDA", 10)
    live = _buy(sim, user_id, "NVDA", 10, stop=90.0)

    prov.prices["NVDA"] = 89.0  # through the LIVE stop
    updates = sim.evaluate_outcomes(user_id)

    assert [u.new_status for u in updates] == ["lost"]
    assert _row(live.id).status == "lost"
    # Against lot 2's own entry — (89 − 103) × 10 — not lot 1's $100.
    assert _row(live.id).realised_pnl == -140.0


def test_each_lot_realises_against_its_own_entry_on_a_shared_trigger():
    """The lot-accounting half, which CR189 does NOT change.

    One trigger closes the whole position (CR189 — the level is per position),
    but the money is still per lot: lot 1 has 4 shares left behind it after an
    earlier sell of 6, lot 2 has 10, and they were bought $10 apart. Each must
    realise on its own share count at its own entry price. Closing lot 1 for the
    row's original 10 would eat 6 shares belonging to lot 2 (DEF318's second
    half), and stamping both against one entry would misreport both.

    Only lot 1 carries a stop, so the position's stop is $95.00 — the
    "protection carried across the whole position" case, and here it is doing
    exactly that: lot 2 is unprotected on its own and exits with the position.
    """
    prov = _Pinned({"NVDA": 100.0})
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    partial = _buy(sim, user_id, "NVDA", 10, stop=95.0)
    _sell(sim, user_id, "NVDA", 6)                 # FIFO: consumes 6 of lot 1
    prov.prices["NVDA"] = 110.0
    later = _buy(sim, user_id, "NVDA", 10)         # no stop of its own

    prov.prices["NVDA"] = 94.0
    sim.evaluate_outcomes(user_id)

    assert _row(partial.id).status == "lost"
    assert _row(later.id).status == "lost"
    # (94 − 100) × 4 — its own 4 remaining shares, not the row's original 10.
    assert _row(partial.id).realised_pnl == -24.0
    # (94 − 110) × 10 — its own entry, $10 above lot 1's.
    assert _row(later.id).realised_pnl == -160.0
    p = sim.ensure_portfolio(user_id)
    assert not any(h.ticker == "NVDA" for h in p.holdings)
