<!--
Auditor run report — run-16 (2026-07-12, session AT:U1). Round-1 audit of DEF051
(Convene the Room trusted client-suppliable portfolio_value/current_drawdown_pct —
a safety-floor compliance-gate input — instead of the real sim state). Fixed in
22c84c6. Owner: AUDITOR.
-->

# run-16 (round 1) — DEF051 (Room compliance-gate input trusted client body)

- **Auditor session:** AT:U1 (track U), 2026-07-12
- **Audited SHA:** `22c84c6`. `git diff 22c84c6..HEAD -- backend/ mobile/` is empty
  (my later commits touched only `audit/handshake/**` + docs), so the main checkout
  == the committed fix — full suite run there (py 3.13.13, sqlite tempfile) →
  **675 passed**. The revert-check ran in a fresh detached worktree @ `22c84c6`
  (removed after).

---

## DEF051 — Room trusted a client-suppliable compliance input (`22c84c6`) → COMPLETE

**The bug:** `stream_room` passed `req.portfolio_value` / `req.current_drawdown_pct`
(client-suppliable `RoomStartRequest` fields, defaulted to `100_000.0` / `0.0`,
never overridden by the mobile client) into `runner.start_run` — the input to the
Room's deterministic, uncoachable mandate-compliance check. A user whose real
simulated portfolio had breached `max_drawdown_pct` still got a Room verdict
computed against 0% drawdown. Not a prompt-honesty gap (CR023/CR024) — the actual
safety-floor gate input.

**The fix (verified in source):** `stream_room` gains
`sim: SimEngine = Depends(get_sim_engine)` and resolves
`portfolio_value = sim.total_value(req.user_id)` /
`current_drawdown_pct = sim.current_drawdown_pct(req.user_id)` immediately before
`runner.start_run`. The two now-dead fields are removed from `RoomStartRequest`, and
from `mobile/.../api_client.dart::streamRoom()` (params + JSON keys) — the sole call
site already omitted them, so no live client behavior changes. `RoomRunner`'s own
100k/0 defaults are untouched (the runner is exercised directly by ~30
`test_room_runner.py` tests; the bug was in the route). Mirrors the existing
`mandate.py::audit_holdings` server-side-resolution pattern.

**No IDOR (security):** the A6 body-ownership guard
(`if current_user.id != req.user_id: raise 403`, room.py:93) runs **before** the
sim lookup (:159), so `req.user_id` is guaranteed the caller's own — a user can only
resolve their own portfolio value. `total_value`/`current_drawdown_pct`/
`ensure_portfolio` confirmed present on `SimEngine` with `(user_id)` signatures.

**Fresh-user path:** `ensure_portfolio()` auto-creates a portfolio at
`_STARTING_CAPITAL = 10_000` with 0% drawdown (drawdown is vs starting capital, and
no holdings → total_value == cash). So the defect doc's proposed "keep 100k/0% as a
fallback for users with no portfolio" is unnecessary — the real computation already
covers it. No special-case was added; correct.

**Tests (reproduced + adversarially re-verified myself):**
- Full suite **675 passed** (main checkout).
- New `test_room.py` (2): `..._ignores_spoofed_body_uses_real_sim_state` (seeds a
  real 50%-drawdown portfolio, POSTs a lying 999999/0 body, a `_FakeRunner` captures
  the resolved kwargs → asserts 5000.0 / 50.0, the real state) and
  `..._fresh_user_gets_real_starting_capital` (fresh user → 10000.0 / 0.0).
- **Independent revert-check (the trust-but-verify step):** in a worktree @
  `22c84c6`, fixed code → 2 passed; reverted `room.py` to the pre-fix parent
  (`2693849`) → **both fail** (`assert 100000.0 == 10000.0` for the fresh user; the
  spoofed-body test's route forwards 999999 ≠ 5000). The tests are non-vacuous —
  they genuinely exercise the fixed route. The architect's own revert-check claim is
  confirmed (their recalled exact value for the spoof test was imprecise; the
  material "both fail" holds).
- `test_auth_phase1_5_audit_fixes.py` foreign-user test trimmed of the two dead keys
  (still asserts the 403 ownership rejection) — legitimate, not assertion-gutting.

**Register:** `def_list.md` DEF051 = `resolved` at `22c84c6` — matches the
DEF049/DEF050 precedent (register flips on the fix landing; this audit lane is the
added independent-verification layer, not a gate on the register).

**Live:** safety-floor-relevant; **needs `/promote-to-alpha`** before it protects
real users. The unit fixture drives the real FastAPI route (TestClient + seeded
`SimPortfolioRow`); a verdict-level REJECT would need a live LLM Room run + real
mandate on Alpha — honestly deferred (same discipline as DEF049).

---

## Verdicts

| Item | SHA | Verdict |
|---|---|---|
| DEF051 | `22c84c6` | **COMPLETE (round 1)** — zero BLOCKER/MAJOR; compliance input resolved server-side, no IDOR, 675 reproduced, revert-check independently reproduced. |

No OUT-OF-SCOPE findings this round.
