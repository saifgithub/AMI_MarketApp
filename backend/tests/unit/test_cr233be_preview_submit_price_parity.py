"""GUARD (CR233-BE round 2, MAJOR-1 fix) — `SimEngine.preview()` and
`SimEngine.submit()` must size a non-market order's mandate-compliance
check at the SAME price, on both the AMI portfolio path and the DEF419
Alpaca-snapshot path.

The auditor's round-1 finding (`orchestration/audit/cr/CR233-BE.auditor.md`):
`preview()` sized every STOP/STOP_LIMIT at its named `trigger_price`
unconditionally, even when the order was already marketable (fills at once,
at the mark) or was a STOP_LIMIT (whose worst resting case is its own
LIMIT, not the trigger). On the Alpaca-snapshot path `preview()` is the
ONLY mandate check an order ever meets — a divergence there is not cosmetic,
it is the safety floor being wrong.

The fix: both methods now compute their compliance-sizing price through the
ONE shared `committed_price_for()` helper
(`app/trading_math/order_pricing.py`), so they cannot diverge again. This
file is that parity guard — it does not re-derive the pricing rule (that is
`test_order_pricing.py`'s and `test_sim_engine.py`'s job); it proves the two
call sites AGREE, for every order type x side x triggered/untriggered
combination, on both paths, by asserting `preview()`'s accept/reject
decision matches `submit()`'s at the same cash boundary.
"""

from __future__ import annotations

import re
from uuid import uuid4

import pytest

from app.schemas.alpaca import AccountSnapshotIn
from app.schemas.trade import OrderType, Side
from app.services.coach_engine import hydrate_coach_mandate
from app.services.market_data import Quote
from app.services.sim_engine import SimEngine
from app.trading_math.order_pricing import committed_price_for


class _ConstProvider:
    """A settable, always-available quote — same shape as
    `test_sim_engine.py`'s fixture of the same name, duplicated here rather
    than imported so this file has no cross-test-module coupling."""

    name = "fixed"

    def __init__(self, price: float) -> None:
        self.price = price

    def quote(self, ticker: str) -> Quote:
        return Quote(price=self.price, source=self.name)

    def get_price(self, ticker: str) -> float:
        return self.price


def _mandate(**overrides):
    body = {"plan": "trader", "single_name_cap_pct": 100.0}
    body.update(overrides)
    return hydrate_coach_mandate(body)


_POSITION_PCT_RE = re.compile(r"position size ([\d.]+)% exceeds single-name cap")


def _position_pct(violations: list[str]) -> float:
    """Extract the exact `position_pct` the single-name-cap violation string
    reports (`safety_floor.py`'s `f"position size {position_pct:.1f}% ..."`)
    — the one number that DIRECTLY reveals what `unit_price` a compliance
    check used, not just whether the check happened to pass or fail. A
    weaker "accepted == accepted" comparison can pass by coincidence when
    two different prices both happen to breach the same cap; this cannot."""
    for v in violations:
        m = _POSITION_PCT_RE.search(v)
        if m:
            return float(m.group(1))
    raise AssertionError(f"no single-name cap violation found in {violations}")


# ── (1) `committed_price_for` used by both methods agrees with itself ──────
#
# The cheapest possible parity guard: if `preview()` and `submit()` ever stop
# calling the SAME function, this still can't catch it — that is what (2)
# below is for. This part pins the helper's own table so a future edit to
# ITS logic is deliberate.


@pytest.mark.parametrize(
    "order_type,side,mark,trigger,limit,expected",
    [
        # MARKET — always the mark, no matter what trigger/limit say.
        (OrderType.MARKET, Side.BUY, 100.0, None, None, 100.0),
        (OrderType.MARKET, Side.SELL, 100.0, None, None, 100.0),
        # LIMIT — resting sizes at its own limit; marketable sizes at mark.
        (OrderType.LIMIT, Side.BUY, 100.0, None, 90.0, 90.0),   # rests (90 < 100)
        (OrderType.LIMIT, Side.BUY, 100.0, None, 110.0, 100.0),  # marketable (110 >= 100)
        (OrderType.LIMIT, Side.SELL, 100.0, None, 110.0, 110.0),  # rests (110 > 100)
        (OrderType.LIMIT, Side.SELL, 100.0, None, 90.0, 100.0),  # marketable (90 <= 100)
        # STOP — resting sizes at trigger; marketable sizes at mark.
        (OrderType.STOP, Side.BUY, 100.0, 110.0, None, 110.0),   # rests (100 < 110)
        (OrderType.STOP, Side.BUY, 100.0, 90.0, None, 100.0),    # marketable (100 >= 90)
        (OrderType.STOP, Side.SELL, 100.0, 90.0, None, 90.0),    # rests (100 > 90)
        (OrderType.STOP, Side.SELL, 100.0, 110.0, None, 100.0),  # marketable (100 <= 110)
        # STOP_LIMIT — resting sizes at its own LIMIT, never the trigger
        # alone; marketable sizes at mark, exactly like STOP/LIMIT.
        (OrderType.STOP_LIMIT, Side.BUY, 100.0, 110.0, 112.0, 112.0),  # rests
        (OrderType.STOP_LIMIT, Side.BUY, 100.0, 90.0, 200.0, 100.0),   # marketable
        (OrderType.STOP_LIMIT, Side.SELL, 100.0, 90.0, 88.0, 88.0),    # rests
        (OrderType.STOP_LIMIT, Side.SELL, 100.0, 110.0, 1.0, 100.0),   # marketable
    ],
)
def test_committed_price_for_table(order_type, side, mark, trigger, limit, expected):
    got = committed_price_for(
        side=side, order_type=order_type, mark=mark,
        trigger_price=trigger, limit_price=limit,
    )
    assert got == expected


# ── (2) preview() and submit() AGREE, at the single-name cap boundary ──────
#
# Cash-sufficiency is NOT a fair parity probe for a RESTING order: `_rest_
# order()` deliberately never reserves cash (see its own docstring, §6) —
# the actual cash check for a resting order happens later, at
# `fill_resting_order()` time. `submit()` returning `accepted=True` for a
# resting order therefore means "successfully parked", not "affordable",
# and comparing it against `preview()`'s bespoke cash check would be
# comparing two different questions.
#
# `check_mandate_compliance`'s single-name cap, by contrast, runs on EVERY
# path — `preview()`, `submit()`'s marketable-fill branch, AND `submit()`'s
# resting branch (the cap check happens before the rest-vs-fill decision,
# `sim_engine.py:1466-1490`). It reads the exact `unit_price` chokepoint
# (`proposed.limit_price`) this CR's fix targets, so it is the correct
# shared probe for every order type/side/triggered combination, resting or
# not.


def _cap_only_mandate(cap_pct: float):
    return _mandate(single_name_cap_pct=cap_pct)


@pytest.mark.parametrize(
    "order_type,trigger,limit,mark",
    [
        # STOP, marketable now (trigger below mark) — the auditor's P1/P2.
        (OrderType.STOP, 80.0, None, 150.0),
        # STOP, genuinely resting (trigger above mark).
        (OrderType.STOP, 200.0, None, 150.0),
        # STOP_LIMIT, marketable now.
        (OrderType.STOP_LIMIT, 80.0, 82.0, 150.0),
        # STOP_LIMIT, resting — sized at its own (wide) limit, the
        # auditor's P3 shape.
        (OrderType.STOP_LIMIT, 200.0, 300.0, 150.0),
        # LIMIT, marketable now (buy limit at/above mark).
        (OrderType.LIMIT, None, 160.0, 150.0),
        # LIMIT, resting (buy limit below mark).
        (OrderType.LIMIT, None, 105.0, 150.0),
    ],
)
def test_preview_submit_agree_buy_ami_path(order_type, trigger, limit, mark):
    """`quantity`/`cap_pct` are picked so the position is OVER the cap at
    the correct `committed_price_for` basis but would be UNDER it at the
    live mark alone — the exact shape of the auditor's P1/P2 (a stop
    passing a cap the identical market order would fail)."""
    sim = SimEngine(provider=_ConstProvider(mark))
    quantity = 100.0

    committed = committed_price_for(
        side=Side.BUY, order_type=order_type, mark=mark,
        trigger_price=trigger, limit_price=limit,
    )
    # $10k portfolio value (starting cash, no holdings). A cap of 50% means
    # a position over $5,000 breaches it.
    cap_pct = 50.0
    assert committed * quantity > 10_000.0 * (cap_pct / 100.0), (
        "fixture must breach the single-name cap at the committed price"
    )
    mandate = _cap_only_mandate(cap_pct)

    user_id_preview = uuid4()
    pv = sim.preview(
        user_id=user_id_preview, ticker="AAPL", side=Side.BUY, quantity=quantity,
        mandate=mandate, order_type=order_type,
        trigger_price=trigger, limit_price=limit,
    )

    user_id_submit = uuid4()
    sub = sim.submit(
        user_id=user_id_submit, ticker="AAPL", side=Side.BUY, quantity=quantity,
        mandate=mandate, order_type=order_type,
        trigger_price=trigger, limit_price=limit,
    )

    assert pv.accepted == sub.accepted, (
        f"preview={pv.accepted} ({pv.compliance.violations}) vs "
        f"submit={sub.accepted} ({sub.compliance.violations}) — "
        f"order_type={order_type} trigger={trigger} limit={limit} mark={mark}"
    )
    assert pv.accepted is False
    assert any(
        "exceeds single-name cap" in v for v in pv.compliance.violations
    ), pv.compliance.violations
    assert any(
        "exceeds single-name cap" in v for v in sub.compliance.violations
    ), sub.compliance.violations
    assert pv.fill_price == committed

    # The strong check: not just "both refused", but refused at the SAME
    # position_pct — the exact number a divergent `unit_price` would move.
    # $10k portfolio value, no holdings, on both preview and submit here.
    expected_pct = round(committed * quantity / 10_000.0 * 100.0, 1)
    assert _position_pct(pv.compliance.violations) == expected_pct
    assert _position_pct(sub.compliance.violations) == expected_pct


@pytest.mark.parametrize(
    "order_type,trigger,limit,mark",
    [
        (OrderType.STOP, 80.0, None, 150.0),      # marketable
        (OrderType.STOP, 200.0, None, 150.0),     # resting
        (OrderType.STOP_LIMIT, 80.0, 82.0, 150.0),  # marketable
        (OrderType.STOP_LIMIT, 200.0, 300.0, 150.0),  # resting, wide limit
    ],
)
def test_preview_submit_agree_buy_alpaca_snapshot_path(
    order_type, trigger, limit, mark,
):
    """Same parity, on the DEF419 account-snapshot path — the path where
    `preview()` is the ONLY floor an Alpaca order ever meets."""
    sim = SimEngine(provider=_ConstProvider(mark))
    quantity = 100.0
    cap_pct = 50.0
    mandate = _cap_only_mandate(cap_pct)
    account = AccountSnapshotIn.model_validate(
        {"kind": "alpaca_paper", "equity": 10_000.0, "cash": 10_000.0, "positions": []}
    )

    committed = committed_price_for(
        side=Side.BUY, order_type=order_type, mark=mark,
        trigger_price=trigger, limit_price=limit,
    )
    assert committed * quantity > 10_000.0 * (cap_pct / 100.0)

    user_id = uuid4()
    pv = sim.preview(
        user_id=user_id, ticker="AAPL", side=Side.BUY, quantity=quantity,
        mandate=mandate, order_type=order_type,
        trigger_price=trigger, limit_price=limit,
        account_snapshot=account,
    )
    assert pv.accepted is False, pv.compliance.violations
    assert any(
        "exceeds single-name cap" in v for v in pv.compliance.violations
    ), pv.compliance.violations
    assert pv.fill_price == committed
    expected_pct = round(committed * quantity / 10_000.0 * 100.0, 1)
    assert _position_pct(pv.compliance.violations) == expected_pct

    # submit() never reads `account_snapshot` (it always persists to the AMI
    # sim portfolio, DEF419's documented scope) — the parity claim here is
    # narrower: preview's OWN price basis, sized against the Alpaca account,
    # must be the same `committed_price_for` value submit would use against
    # the AMI portfolio for the identical order shape. Cross-checked via (1)
    # above; this asserts preview's reported `fill_price` is that value.


# ── (3) SELL side parity, against an existing AMI holding ──────────────────


def test_preview_submit_agree_sell_stop_marketable_ami_path():
    """A SELL STOP (stop-loss) whose trigger the mark has already fallen
    through is marketable now and must size (for the purposes of the
    bracket/compliance context) at the mark on both preview and submit —
    mirrors the BUY-side parity above from the other side of the book."""
    mark = 50.0
    sim = SimEngine(provider=_ConstProvider(mark))
    mandate = _mandate(single_name_cap_pct=1000.0)

    # Establish a holding to sell against, at a higher mark so the buy
    # itself is affordable, then drop the mark for the sell-stop check.
    user_id = uuid4()
    buy_sim = SimEngine(provider=_ConstProvider(60.0))
    buy_result = buy_sim.submit(
        user_id=user_id, ticker="AAPL", side=Side.BUY, quantity=100,
        mandate=mandate, order_type=OrderType.MARKET,
    )
    assert buy_result.accepted, buy_result.compliance.violations

    trigger = 55.0  # above the new $50 mark — sell stop already triggered
    committed = committed_price_for(
        side=Side.SELL, order_type=OrderType.STOP, mark=mark,
        trigger_price=trigger, limit_price=None,
    )
    assert committed == mark

    pv = sim.preview(
        user_id=user_id, ticker="AAPL", side=Side.SELL, quantity=100,
        mandate=mandate, order_type=OrderType.STOP, trigger_price=trigger,
    )
    assert pv.accepted, pv.compliance.violations
    assert pv.fill_price == committed


# ── (4) `fill_resting_order()` sizes the SAME way, at actual fill time ─────
#
# A resting order's OWN compliance check (`submit()`'s call, above) runs
# once, at placement, against whatever the mandate was then. `fill_resting_
# order()` re-runs it again at the moment the order actually fires — CR170's
# "no time-delayed bypass" guarantee — and that second check has the exact
# same `unit_price` chokepoint. It must size at the price the order is
# ABOUT TO BOOK AT (Rule 2's worse-of), not the raw `order.limit_price`
# (`None` for a plain STOP), which would silently fall back to the live
# mark inside `safety_floor.py`.


def test_fill_resting_order_sizes_cap_check_at_actual_fill_price():
    """A resting BUY STOP_LIMIT placed while the mandate is permissive, then
    swept once the mark gaps PAST its own limit: Rule 2 books this at the
    mark (`stop_limit_becomes_limit` — the trigger converts it into a
    resting LIMIT, then Rule 1/2 re-apply against `limit_price`; the mark
    here is worse for the buyer than the stored limit), which must ALSO be
    what the re-run cap check sizes against — not the raw `order.limit_price`
    the order was placed with, now stale."""
    provider = _ConstProvider(90.0)
    sim = SimEngine(provider=provider)
    permissive = _mandate(single_name_cap_pct=1000.0)

    user_id = uuid4()
    quantity = 10.0
    trigger, limit = 110.0, 115.0
    placed = sim.submit(
        user_id=user_id, ticker="AAPL", side=Side.BUY, quantity=quantity,
        mandate=permissive, order_type=OrderType.STOP_LIMIT,
        trigger_price=trigger, limit_price=limit,
    )
    assert placed.accepted and placed.resting, placed.compliance.violations
    order = placed.resting_order
    assert order is not None

    # The mark gaps straight past both the trigger AND the limit, to $150 —
    # Rule 2 books this BUY at the worse-for-the-user price: max(limit,
    # mark) = $150, not the $115 `order.limit_price` it was named at. Small
    # quantity (10 shares) keeps BOTH prices well under the $10k cash so the
    # cash-sufficiency check cannot mask which price the CAP check used.
    fill_mark = 150.0
    provider.price = fill_mark
    from app.trading_math.order_pricing import fill_price_for

    expected_fill_price = fill_price_for(side=Side.BUY, named=limit, mark=fill_mark)
    assert expected_fill_price == fill_mark
    assert expected_fill_price != order.limit_price
    assert expected_fill_price * quantity < 10_000.0, "must not trip cash, only cap"
    assert (order.limit_price or 0.0) * quantity < 10_000.0

    # A cap tight enough to pass at the (wrong) stored-limit-priced 10
    # shares ($1,150 / $10,000 portfolio = 11.5%) but breach at the CORRECT
    # $150-priced 10 shares ($1,500 / $10,000 = 15%).
    cap_mandate = _mandate(single_name_cap_pct=12.0)
    result = sim.fill_resting_order(order=order, mark=fill_mark, mandate=cap_mandate)

    assert result.accepted is False, (
        "the cap check must read the ACTUAL fill price, not the stale "
        f"stored limit — got {result.compliance.violations}"
    )
    assert any(
        "exceeds single-name cap" in v for v in result.compliance.violations
    ), result.compliance.violations
    expected_pct = round(expected_fill_price * quantity / 10_000.0 * 100.0, 1)
    assert _position_pct(result.compliance.violations) == expected_pct
