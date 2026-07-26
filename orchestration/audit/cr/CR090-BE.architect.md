<!--
CR090-BE.architect.md — architect/coder submission lane (track R owns the audit lane).
State derives from round numbers here vs CR090-BE.auditor.md (see PROTOCOL.md).
Built by the coder.api lane agent in .claude/worktrees/coder.api-CR090-BE/; surfaced
to main + independently re-verified by the Architect (see §Architect re-verification).
-->

# CR090-BE — audit lane (coder.api submission)

SUBMITTED: round 1

**Item:** CR090 — meter the live News/Social Analyst data feeds via a credit
surcharge; fail LOUDLY (a distinct "paid feature withheld" state) instead of
silently degrading to synthetic. Design RESOLVED to the **surcharge model**
(Saiful 2026-07-26): Room/1-on-1 keep their flat price; live-data turns add an
additive surcharge only when they actually fire with real data. Acceptance:
`docs/forward_planning/CR090_live_data_feed_paywall/CR090_live_data_feed_paywall.md`.
Assign: `orchestration/dispatch/lanes/CR090-BE.assign.md`. Hand-off (incl. the
full CR090-ROOM contract): `orchestration/dispatch/lanes/CR090-BE.coder.api.md`.

**Scope (coder.api core ONLY):** the surcharge cost + accessor, and the 3-state
liveness marker on the News/Social degrade path. The room wiring (charge the
surcharge, render the third disclosure state) is CR090-ROOM (deferred, consumes
this contract); the mobile "upgrade to unlock" copy is CR090-MOBILE (deferred).
No `room_runner.py` / `room_prompts.py` / `agent_runner.py` / Flutter touched.

**Code branch:** `lane/CR090-BE.coder.api` @ **`cd292d3`** (based on `main` @ `16af15a`).

**GATE: independent** — real credit-spend / entitlement contract, same risk
class as CR084 (money/entitlements, D-5).

## Fix shape (3 prod files + 1 test file)

1. `credit_service.py`: `LIVE_DATA_SURCHARGE = 2` + `live_data_surcharge(n) -> n*2`
   (0 for n<=0), beside `room_cost_for_plan`. `ALLOWANCE` / `ROOM_COST_BASIC` /
   `ROOM_COST_PREMIUM` / `_ROOM_COST_BY_PLAN` untouched. No `spend()` here.
2. `news_context.py`: `LiveDataState` enum (LIVE / WITHHELD_PAID / UNAVAILABLE) —
   the single shared marker — + pure classifier `live_data_state(*, available,
   entitled)` + `NewsFeed` + `resolve_news_feed(...)`. Existing `fetch_live_news`
   / `build_news_context_block` untouched.
3. `social_context.py`: imports the shared marker; adds `SocialFeed` +
   `resolve_social_feed(...)`. Existing `fetch_live_sentiment` untouched.

## Adversarial angles worth probing

- **Surcharge fires ONLY on real live data.** `live_data_surcharge` is a pure
  multiply; it is the room's job to pass `n = count of feeds whose .state is
  LIVE`. WITHHELD_PAID and UNAVAILABLE feeds carry NO payload (headlines `()` /
  sentiment `None`) — verify the room can't accidentally count them as live.
- **WITHHELD_PAID is structural, not a prompt string (CR038).** It's an enum
  value on the returned NamedTuple, decided by `live_data_state`, not a line of
  agent-prompt text. Try to find a path where "available but not entitled"
  yields anything other than `WITHHELD_PAID`.
- **DEF059 inversion guard.** `available and not entitled` must NEVER map to
  `UNAVAILABLE` (the honest "no data" fallback) — that would present a gated
  feed as business-as-usual synthetic. The classifier makes it impossible; a
  test asserts `state is not UNAVAILABLE` on the gated path for both feeds.
- **Existing pricing byte-unchanged.** Tests assert `ALLOWANCE`,
  `ROOM_COST_BASIC/PREMIUM`, `_ROOM_COST_BY_PLAN` equal their exact prior values
  — the surcharge is additive (Basic Room 8 + News 2 + Social 2 = 12).
- **Back-compat.** `fetch_live_news` / `fetch_live_sentiment` /
  `build_*_context_block` signatures + returns unchanged; the marker is a NEW
  additive resolver, so the full existing suite passing is the proof.
- **No circular import.** `social_context` imports `news_context`; `news_context`
  does not import `social_context` — clean one-way dependency.

## Evidence (from the lane worktree)

- `cd backend && uv sync --frozen --extra dev` then `.venv/bin/pytest tests/unit/ -q`
  → **1260 passed, exit 0** (146s). New `test_cr090_live_data_surcharge.py`: 18 passed.
- No new env-driven config setting introduced → no `docker-compose.yml` /
  `test_config_compose_parity` change needed (CR040 N/A here).

## Note

The surcharge is not spent and the marker is not consumed until CR090-ROOM wires
`room_runner.py`. This lane is the contract; it is correct and fully testable now.
Do not block the verdict on the deferred ROOM/MOBILE lanes.

## Architect re-verification (surfaced to main 2026-07-26)

Independently re-verified from the repo root before surfacing — not on the
coder's word (the standing "verify git + exit code myself" rule):

- **Full unit suite re-run by the Architect** from the lane worktree
  (`.claude/worktrees/coder.api-CR090-BE/backend`, `.venv/bin/pytest tests/unit/ -q`):
  **1260 passed, 4 pre-existing warnings, exit 0** (150.43s). Matches the coder's report.
- **Scope verified via `git diff main...lane/CR090-BE.coder.api`:** 6 files,
  **+545 / −0** (purely additive). `credit_service.py`'s `ALLOWANCE` /
  `ROOM_COST_BASIC` / `ROOM_COST_PREMIUM` / `_ROOM_COST_BY_PLAN` / `room_cost_for_plan`
  show ZERO diff lines. No `room_runner.py` / `room_prompts.py` / `agent_runner.py` /
  `mobile/` touched. Both hand-off signals present on the branch.

## Integration (AT:R65, 2026-07-27)

Track-U returned `VERDICT: COMPLETE (round 1)` (`orchestration/audit/cr/CR090-BE.auditor.md`,
`c6dba79`) — zero findings, 1260/1260 suite, 3/3 mutation tests caught. `lane/CR090-BE.coder.api`
@ `cd292d3` merged to `main`; re-verified independently post-merge (see commit message for the
suite count). `DISPATCH: ACCEPTED` in `CR090-BE.assign.md`.
