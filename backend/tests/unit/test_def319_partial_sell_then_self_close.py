"""DEF319 — a partial sell followed by a stop-out was double-counted, in both
readers of the trade ledger. These are the regression tests for the two halves.

The sequence is ordinary and, since CR188 slice 2 made ticket-sell the only
training exit, common:

    buy 10 @ $100 (Aug 1)  ·  sell 4 @ $103 (Aug 2)  ·  the other 6 stop out (Aug 3)

Two independent readers got it wrong for the same reason. `cost_basis_lots`
treated a self-close as a *property of the buy row*, which dates it to
`opened_at` and erases every sell that landed in between — the lot was "fully
closed for 10" before the sell of 4 could draw from it, and the module logged
`cost_basis_oversell unmatched=4.0` about its own reconstruction. And
`def110_backfill.py::expected()` carried a second derivation,
`Σ open buys − Σ open sells`, whose docstring claimed it was "the same rule
`cost_basis_lots.py` already applies". It was not: the stopped-out BUY row
leaves the open set carrying all 10 while the SELL row keeps subtracting its 4,
so the phantom-share detector reported **4 shares that do not exist**.

The shared premise is stated plainly in `cost_basis_lots`' own docstring —
*"self-closed buys and sell orders are disjoint records (a self-close never
produces a sell row)"* — and is **true of whole positions and false of partial
ones** (P23). Both readers were built on it, so reading either confirmed the
other.

## Why these tests exist as a separate file, and what shape they had to take

The R70 audit found DEF319 shipped with no regression test for either half, and
that the one claimed for it *could not exist in the form claimed*: the autouse
ledger invariant sums `quantity_open`, and `Σ quantity_open` is **identical**
fixed or broken on this sequence — 10 either way, because the oversell is
clamped rather than propagated. The aggregate the guard watches is blind to
this fix by construction.

So each test below pins something the aggregate cannot express: the per-lot
**realised P&L attribution** (which differs by the whole value of the sell), the
**absence of the oversell warning** the module logs about itself, and the
detector's **verdict on a book that is in fact clean**.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from app.services import cost_basis_lots
from app.services.coach_engine import hydrate_coach_mandate
from app.services.cost_basis_lots import compute_lots_fifo, open_quantity
from app.services.market_data import Quote
from app.services.sim_engine import SimEngine
from app.schemas.trade import OrderType, Side

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from def110_backfill import _plan_and_apply  # noqa: E402

_AUG1 = datetime(2026, 8, 1, 14, 30, tzinfo=timezone.utc)


@dataclass
class _Trade:
    """Duck-typed stand-in for `sim_engine.SimTrade` — read fields only.

    `closed_at` is the field that matters here and the one the older fixtures in
    `test_cost_basis_lots.py` do not carry: without it `_event_stream` falls back
    to `opened_at`, which is the pre-fix behaviour. A test for this defect that
    omitted it would be testing the bug.
    """

    id: str
    side: str
    quantity: float
    entry_price: float
    opened_at: datetime
    status: str = "open"
    closed_at: datetime | None = None
    realised_pnl: float = 0.0


def _the_sequence() -> list[_Trade]:
    """Buy 10 @ $100, sell 4 @ $103 the next day, stop out the rest the day after.

    The stop-out realises on the 6 shares actually left — `(94 − 100) × 6` — which
    is what `_close_lot` stamps and what `evaluate_outcomes` writes to the row.
    """
    return [
        _Trade(
            id="A", side="buy", quantity=10, entry_price=100.0, opened_at=_AUG1,
            status="lost", closed_at=_AUG1 + timedelta(days=2), realised_pnl=-36.0,
        ),
        _Trade(
            id="S", side="sell", quantity=4, entry_price=103.0,
            opened_at=_AUG1 + timedelta(days=1),
        ),
    ]


class _Recorder:
    """Stand-in for the module logger — `logger.warn` is the defect's own alarm."""

    def __init__(self) -> None:
        self.warnings: list[tuple[str, dict]] = []

    def warn(self, event: str, **kw) -> None:
        self.warnings.append((event, kw))

    def info(self, *a, **kw) -> None:  # pragma: no cover
        pass


# ── Half 1 — `cost_basis_lots._event_stream` ────────────────────────────────


def test_a_sell_between_the_open_and_the_stop_out_is_credited_to_the_lot():
    """The per-lot attribution, which is what the ordering fix actually changes.

    The lot closes for 10 either way, so `quantity_closed` cannot tell the two
    apart and neither can any sum of `quantity_open`. **Realised P&L can**: the
    sell of 4 at $103 against a $100 entry realised $12, and dating the
    self-close to `opened_at` throws that away by closing the lot before the
    sell arrives. −$24.00 (12 − 36) fixed; −$36.00 (0 − 36) broken. The number
    is rendered on the per-lot card the user reads (CR029).
    """
    lots = compute_lots_fifo(_the_sequence())

    assert len(lots) == 1
    lot = lots[0]
    assert lot.quantity_open == 0.0
    assert lot.quantity_closed == 10.0
    assert lot.status == "closed"
    assert lot.realised_pnl == -24.0, (
        "the $12 realised on the sell of 4 was dropped — the self-close was "
        "dated to the buy, so the sell had nothing left to draw from"
    )


def test_the_reconstruction_does_not_report_an_oversell_against_itself(monkeypatch):
    """The documented symptom, pinned directly.

    `cost_basis_oversell` means a sell outran the open lots, and its comment says
    it "only fires on ledger inconsistency — surface it, don't swallow it". On
    this sequence the ledger was consistent and the *reconstruction* was not, so
    the module was warning about its own arithmetic. Nothing in the suite read
    that warning, which is how a log line that fires on an ordinary user action
    stayed unnoticed.
    """
    recorder = _Recorder()
    monkeypatch.setattr(cost_basis_lots, "logger", recorder)

    compute_lots_fifo(_the_sequence())

    assert recorder.warnings == []


def test_the_open_total_is_the_same_either_way_which_is_why_it_is_not_the_guard():
    """The audit's finding, kept as an executable note rather than prose.

    `open_quantity` — the single derivation the detector, the engine's bracket
    gates and the autouse ledger invariant all read — returns 10.0 on the
    two-lot form of this sequence whether the ordering is fixed or broken, since
    the unmatched 4 is clamped at `max(quantity_open, 0)` rather than propagated.
    Anyone reaching for that aggregate to guard this fix will get a green test
    that proves nothing. Pinning the 10.0 says so where the next person will
    look, beside the two tests that do carry the fix.
    """
    seq = _the_sequence()
    seq.append(
        _Trade(id="B", side="buy", quantity=10, entry_price=103.0,
               opened_at=_AUG1 + timedelta(days=3)),
    )

    assert open_quantity(seq) == 10.0


# ── Half 2 — `def110_backfill.py::expected()` ───────────────────────────────


class _Pinned:
    name = "pinned"

    def __init__(self, price: float) -> None:
        self.price = price

    def quote(self, ticker: str) -> Quote:
        return Quote(price=self.price, source="pinned")

    def get_price(self, ticker: str) -> float:
        return self.price


def _mandate():
    # `post_loss_cooldown_hours: 0` is deliberate and is the only way to write
    # this sequence: the stop-out in step 3 arms CR129's post-loss cooldown,
    # which hard-blocks the re-entry in step 4. The cooldown is not what is
    # under test, and the re-entry is what makes the drift visible at all.
    return hydrate_coach_mandate({
        "plan": "trader", "single_name_cap_pct": 100.0, "max_open_risk_pct": 100.0,
        "post_loss_cooldown_hours": 0,
    })


def test_the_detector_finds_no_phantom_after_a_partial_sell_then_a_stop_out():
    """The second derivation, through the script that carried it.

    The whole sequence is driven through the real engine, so the book is by
    construction correct: 10 bought, 4 sold through the ticket, 6 stopped out, 5
    bought back. Five shares held, five shares of open lot. The detector must
    find nothing.

    Under the old `Σ open buys − Σ open sells` it finds four. The stopped-out BUY
    row is no longer `open` so it contributes nothing to the positive side, while
    its SELL row is `open` forever and keeps subtracting 4 — leaving `expected`
    at 1 against a holding of 5. This script does not merely *report*: with
    `--apply` it would delete four real shares and credit their proceeds as cash,
    a repair script corrupting a correct book on a routine trade.

    The re-entry is what makes it visible at all. Sell out completely and the
    holding row is deleted, and a detector that iterates holdings has nothing to
    compare — the drift is real and silent until the user buys back in.
    """
    prov = _Pinned(100.0)
    sim = SimEngine(provider=prov)
    user_id = uuid4()

    def _submit(side: Side, qty: float, **kw):
        r = sim.submit(user_id=user_id, ticker="NVDA", side=side, quantity=qty,
                       mandate=_mandate(), order_type=OrderType.MARKET, **kw)
        assert r.accepted, r.compliance.violations
        return r

    _submit(Side.BUY, 10, stop=95.0)
    prov.price = 103.0
    _submit(Side.SELL, 4)
    prov.price = 94.0
    assert len(sim.evaluate_outcomes(user_id)) == 1, "precondition: the rest stops out"
    _submit(Side.BUY, 5)

    p = sim.ensure_portfolio(user_id)
    assert [(h.ticker, h.quantity) for h in p.holdings] == [("NVDA", 5.0)]
    cash_before = p.current_cash

    from app.db.session import get_sessionmaker

    s = get_sessionmaker()()
    try:
        lines, shares, credited, unattributed = _plan_and_apply(s, SimEngine())
        s.commit()
    finally:
        s.close()

    assert (lines, shares, credited, unattributed) == ([], 0.0, 0.0, 0)
    after = sim.ensure_portfolio(user_id)
    assert [(h.ticker, h.quantity) for h in after.holdings] == [("NVDA", 5.0)]
    assert after.current_cash == cash_before
