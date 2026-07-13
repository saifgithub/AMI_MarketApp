# DEF051 — Convene the Room always checks compliance against a fake $100k / 0%-drawdown portfolio

**Status:** open · **Filed:** AT:R57 · **Date:** 2026-07-13
**Source:** prompt — spotted while auditing which of the 12 agents get real data
(same session as CR023/CR024's News/Social truthfulness fix), not a user-reported bug.

## Problem

`SimEngine.submit()` (`backend/app/services/sim_engine.py:395`) and `SimEngine.preview()`
(`:559`) both correctly source the user's real state for their compliance check:

```python
compliance = check_mandate_compliance(
    proposed,
    portfolio_value=self.total_value(user_id),
    current_drawdown_pct=self.current_drawdown_pct(user_id),
    ...
)
```

**Convene the Room does not.** `RoomStartRequest` (`backend/app/api/room.py:72-80`) declares:

```python
portfolio_value: float = 100_000.0
current_drawdown_pct: float = 0.0
```

as request-body fields with hardcoded defaults. The mobile client never overrides them:
`mobile/lib/services/api/api_client.dart:537-543`'s `streamRoom()` method has the *exact
same* defaults (`portfolioValue = 100000.0`, `currentDrawdownPct = 0.0`) as Dart optional
parameters, and its one call site — `mobile/lib/state/room_providers.dart:94` —
`api.streamRoom(userId: userId, ticker: _ticker)` — passes neither. So every Room run,
for every user, on every ticker, checks mandate compliance against a fabricated
$100,000 portfolio at 0% drawdown, never the user's real simulated portfolio.

This is not a narrative/prompt-honesty issue like CR023/CR024 (those were agent
prompts overclaiming a data source). This is the actual input to
`app/agents/safety_floor.py::check_mandate_compliance()` — the deterministic,
"sacred," uncoachable compliance gate. A user whose real simulated portfolio has
already breached their mandate's `max_drawdown_pct` still sees "0% drawdown" on
every Convene the Room run — the drawdown cap effectively never fires for Room
verdicts, only for direct sim-trade submission (`submit`/`preview`, which are
correctly wired). Position-sizing percentages (Trader, 3 Risk Debators) are also
computed against the fake $100k rather than the user's real balance, though the
actual trade ticket (opened from a Room verdict) goes through the correctly-wired
`submit`/`preview` path, so the dollar amount that actually executes is checked
against the real portfolio — it's the Room's own reasoning and PM verdict that are
blind to the user's real state.

## Root cause

`RoomStartRequest.portfolio_value` / `.current_drawdown_pct` were added as
plain request-body fields (presumably to let a caller override them for testing,
or because the Room's rate-limited/heavier flow was built before `SimEngine.total_value()`
/ `.current_drawdown_pct()` existed as the canonical source — both of which the
sim-trade endpoints already use correctly). Nothing was ever added to compute them
server-side from the authenticated user's real state, and the mobile client was never
updated to pass them either — so the defaults silently became "the only value this
ever sees."

## Fix

**Backend** (`backend/app/api/room.py`, `stream_room`): before constructing
`RoomStartRequest`'s values are used, resolve real values server-side —
`sim = get_sim_engine(); portfolio_value = sim.total_value(req.user_id); current_drawdown_pct = sim.current_drawdown_pct(req.user_id)`
— and pass those into `runner.run(...)` instead of `req.portfolio_value` /
`req.current_drawdown_pct`. This closes the gap **regardless of whether the mobile
client ever sends real values** — the server should be the source of truth for the
user's own portfolio state, not trust a client-supplied override for a compliance
check. (Keep the request fields for now as an optional test/admin override if a
call site needs one, but default the route handler to computing real values rather
than trusting `req.portfolio_value`'s literal default.)

**Mobile**: no change strictly required if the backend computes server-side, but
`streamRoom()`'s `portfolioValue`/`currentDrawdownPct` parameters and defaults
become dead weight worth removing once the backend stops trusting them, to avoid
a future caller assuming they still do anything.

**Verification**: a regression test creating a user with a real sim portfolio at a
known value + a known drawdown (via existing sim-trade fixtures), then asserting
`RoomRunner.run(...)`'s resulting verdict's compliance check reflects that real
drawdown — e.g. a mandate with `max_drawdown_pct` set just below the fixture's real
drawdown must REJECT, proving the check no longer sees a hardcoded 0%.

## Acceptance

- [ ] `stream_room` resolves `portfolio_value` / `current_drawdown_pct` from
      `SimEngine.total_value(user_id)` / `.current_drawdown_pct(user_id)` server-side.
- [ ] A user whose real simulated portfolio has breached `max_drawdown_pct` gets a
      Room verdict that REJECTs on drawdown grounds (regression test, currently
      impossible to write truthfully since the check always sees 0%).
- [ ] `RoomStartRequest`'s client-suppliable fields no longer silently override the
      real computed values (or are removed, if no caller needs an override).
- [ ] Existing Room test suite (`test_room_runner.py`) still passes — most tests use
      the default $100k/0% path deliberately (fixture users have no real sim
      portfolio), so those defaults may still need to exist as a *fallback for users
      with no sim portfolio yet* (e.g. `total_value()` on a fresh account), not as
      the permanent value for every account.
