"""DEF305 — the stop-gap that stops automatic closes booking fabricated prices.

`SimEngine.current_price` returns a float and drops `Quote.source`, so
`evaluate_outcomes` cannot tell a yfinance quote from `MockWalkProvider`'s
`[50, 450]` random draw. On 2026-08-14 three sweeps closed nine positions across
two portfolios at mock prices — HPQ, a $30 stock, was booked out at $334.96 —
and credited the proceeds as real cash. The audited fix (a source check at every
money-moving site) is laned as `SIM-DEF305`; this switch buys the time.

**Both automatic paths, because they do not go through one another.** The
background tick calls `_sweep_position_brackets`; `POST /v1/sim/trades/{id}
/evaluate` calls `SimEngine.evaluate_outcomes` directly, and `SimNotifier
.refresh()` hits that route on **every app open**. Gating only the tick would
leave a real guard sitting beside one of the two paths that move the money,
which is DEF305's own shape.

**What these tests deliberately do not assert.** That `manual_close` or
`submit` are gated — they are not, by design. A user tapping *close* or *buy*
is asking for a fill now; silently doing nothing when someone taps a button is a
different defect. Those sites belong to the audited fix.
"""

from __future__ import annotations

import pytest

from app.api import sim as sim_api
from app.core.config import settings
from app.services import sim_resting_orders


@pytest.fixture
def sweep_off(monkeypatch):
    monkeypatch.setattr(settings, "sim_bracket_sweep_enabled", False)


@pytest.fixture
def sweep_on(monkeypatch):
    monkeypatch.setattr(settings, "sim_bracket_sweep_enabled", True)


def test_the_default_is_on() -> None:
    """The switch suppresses a SAFETY feature, so its default must be the safe
    direction. A stop-gap that ships defaulting to off is a stop-gap that
    silently becomes the behaviour — DEF038 and DEF063 both ran dark for months
    on exactly that.

    Read from the class default, not the live `settings` object, which the
    environment may legitimately have turned off.
    """
    assert type(settings).model_fields["sim_bracket_sweep_enabled"].default is True


def test_neither_bracket_leg_runs_when_the_switch_is_off(sweep_off, monkeypatch) -> None:
    """The behavioural half: with the switch off, nothing that closes a
    position off an unchecked price is even called.

    Both legs, and the margin one matters more: `_sweep_short_positions`
    force-closes a short the user never asked to close.
    """
    called: list[str] = []
    monkeypatch.setattr(
        sim_resting_orders, "_sweep_position_brackets",
        lambda *a, **k: called.append("brackets") or 0,
    )
    monkeypatch.setattr(
        sim_resting_orders, "_sweep_short_positions",
        lambda *a, **k: called.append("shorts") or (0, 0),
    )
    monkeypatch.setattr(sim_resting_orders, "is_us_market_open", lambda _now: True)
    monkeypatch.setattr(sim_resting_orders, "_live_orders", lambda _uid: [])
    monkeypatch.setattr(sim_resting_orders, "_expire_elapsed", lambda *a: 0)
    monkeypatch.setattr(sim_resting_orders, "_reap_stale_claims", lambda *a: 0)
    monkeypatch.setattr(sim_resting_orders, "_accrue_borrow", lambda *a: 0.0)

    stats = sim_resting_orders.sweep_resting_orders()

    assert called == [], f"a suppressed sweep still called {called}"
    assert stats["brackets_closed"] == 0
    assert stats["brackets_suppressed"] == 1


def test_both_legs_run_when_the_switch_is_on(sweep_on, monkeypatch) -> None:
    """The non-vacuity half. Without this, deleting the call sites entirely
    would pass the test above.
    """
    called: list[str] = []
    monkeypatch.setattr(
        sim_resting_orders, "_sweep_position_brackets",
        lambda *a, **k: called.append("brackets") or 0,
    )
    monkeypatch.setattr(
        sim_resting_orders, "_sweep_short_positions",
        lambda *a, **k: called.append("shorts") or (0, 0),
    )
    monkeypatch.setattr(sim_resting_orders, "is_us_market_open", lambda _now: True)
    monkeypatch.setattr(sim_resting_orders, "_live_orders", lambda _uid: [])
    monkeypatch.setattr(sim_resting_orders, "_expire_elapsed", lambda *a: 0)
    monkeypatch.setattr(sim_resting_orders, "_reap_stale_claims", lambda *a: 0)
    monkeypatch.setattr(sim_resting_orders, "_accrue_borrow", lambda *a: 0.0)

    stats = sim_resting_orders.sweep_resting_orders()

    assert called == ["brackets", "shorts"]
    assert stats["brackets_suppressed"] == 0


def test_the_resting_book_still_works_when_the_switch_is_off(sweep_off, monkeypatch) -> None:
    """The switch's blast radius is deliberately narrow.

    The resting **entry** book already refuses a fabricated price via
    `_quote_is_fillable` — it was never part of this defect — so suppressing it
    too would remove a working feature for no reason. Expiry and borrow accrual
    likewise: an order dies at its session close and borrow accrues on calendar
    days whether or not brackets are firing.
    """
    monkeypatch.setattr(sim_resting_orders, "is_us_market_open", lambda _now: True)
    monkeypatch.setattr(sim_resting_orders, "_live_orders", lambda _uid: [])
    monkeypatch.setattr(sim_resting_orders, "_expire_elapsed", lambda *a: 3)
    monkeypatch.setattr(sim_resting_orders, "_reap_stale_claims", lambda *a: 2)
    monkeypatch.setattr(sim_resting_orders, "_accrue_borrow", lambda *a: 1.25)

    stats = sim_resting_orders.sweep_resting_orders()

    assert stats["expired"] == 3
    assert stats["reaped"] == 2
    assert stats["borrow_charged_cents"] == 125


def test_the_app_open_route_is_gated_too() -> None:
    """The caller-side assertion, and the reason this file exists at all.

    A test that only drives `sweep_resting_orders` proves the tick is gated and
    says nothing about the route — and the route is the path a user actually
    triggers, on every single app open. DEF190: a helper passing says nothing
    about whether the argument arrives.

    Source-level because the route is `async` and its gate is a conditional
    expression around an `asyncio.to_thread` call; what must hold is that
    `evaluate_outcomes` is not reachable without consulting the switch, and
    that is a property of the call site.
    """
    import inspect

    src = inspect.getsource(sim_api.evaluate_trades)
    assert "bracket_closing_enabled()" in src, (
        "POST /trades/{id}/evaluate calls evaluate_outcomes without consulting "
        "the DEF305 switch — SimNotifier.refresh() hits this on every app open")
    call = src.index("sim.evaluate_outcomes")
    gate = src.index("bracket_closing_enabled()")
    assert gate > call, (
        "the gate must be the conditional ON the evaluate_outcomes call, not an "
        "unrelated earlier mention")


def test_the_switch_is_visible_to_an_operator() -> None:
    """A suppressed control whose state nobody can read is how a temporary
    stop-gap becomes permanent. `/v1/admin/config-check` is step 7b of the
    promotion protocol, so this is where "is it still off" gets answered.

    Deliberately NOT a `FeatureGate`: those ask "is a key present" and feed
    `dark_count`, where a deliberately-off safety switch would read as a
    misconfiguration and train the operator to ignore the count.
    """
    from app.schemas.admin import AdminConfigCheckResponse

    assert "sim_bracket_sweep_enabled" in AdminConfigCheckResponse.model_fields
