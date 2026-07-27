<!-- dispatch hand-off — coder.room, CR098-ROOM round 1 -->
# CR098-ROOM — coder.room hand-off (round 1, PARTIAL)

## Session constraint — read this first

This round ran under a hard token/cost budget that was exhausted before the
full scope could land. **The full unit suite was never run this round** —
committing the mechanism (D5's priority) was the achievable goal, not the
audit-ready 14/14 lane the assign asked for. This hand-off is written to that
reality: it is honest about what's unverified rather than claiming a false
green. Round 2 (fresh budget) should start by running the suite and fixing
whatever it finds before doing anything else.

## What's implemented (committed at `ca56c25`)

- `backend/app/services/entitlements.py` — `resolve_analyst_roster(plan,
  account_age_days, *, now)`, `AnalystRoster(present, withheld, next_step)`,
  `account_age_days()`, `resolve_roster_for_user(user_id)` (DB lookup variant,
  mirrors `effective_plan_for_user`). Fundamentals hard-capped out of the
  withholdable set in code (`_WITHHOLDABLE_ORDER` has only 3 members).
- `backend/app/core/config.py` — `room_pullback_days_{social,news,market}: int
  = 0`, `field_validator` rejects negative (fails boot, CR040).
- `docker-compose.yml` — all three forwarded in the `api-alpha` block.
- `backend/app/schemas/room.py` — `VerdictAction.NO_VERDICT`,
  `Verdict.opinions_not_included: list[str]`.
- `backend/app/services/news_context.py` — 4th `LiveDataState.WITHHELD_TENURE`
  member (the D3 answer — see FLAGS below).
- `backend/app/services/room_runner.py`:
  - `_RoomContext.withheld` / `.roster_next_step`.
  - `_profile_for_ticker(..., withheld=...)` — skips `compute_technicals` when
    Market withheld, sets `profile["technicals_state"]="withheld_tenure"`.
  - `_resolve_and_charge_feeds(..., withheld=...)` — News/Social roster-
    withheld analysts are never probed (`resolve_news_feed`/
    `resolve_social_feed` not called at all — fetch banked), so they never
    count toward `n_available`/the surcharge (D2 composition, one call site).
  - `start_run` resolves the roster once (`resolve_roster_for_user`) before
    charging; `run()` accepts an optional `roster` param (None → resolves
    fresh, the respawn/direct-call fallback shape matching `news_feed`/
    `social_feed`).
  - PHASES loop filters each phase's agents by `ctx.withheld` (safe for every
    phase — withheld only ever names ANALYSTS-phase agents) and emits
    `RoomEvent(kind="agent_withheld", agent_id, reason="upgrade",
    next_step_agent, next_step_days)` once per withheld analyst.
  - VERDICT phase: `if AgentId.MARKET_ANALYST in ctx.withheld:` short-circuits
    to `_assemble_no_verdict(ctx)` — built in code, the fixed CR-doc copy,
    never touching `_parse_pm_verdict`/the LLM at all. This runs AFTER
    EXECUTION/RISK (FLAG #2 kept, see below).
  - `opinions_not_included` populated at ONE shared insertion point (right
    before `run.verdict = verdict`, via `verdict.model_copy(update=...)`) —
    covers every path (APPROVE/PASS/NO_VERDICT/fail-safe) uniformly.
- `backend/app/services/room_prompts.py` — `_format_profile` now strips the
  RSI/range/volume, catalyst, and retail-sentiment blocks when
  `technicals_state`/`news_state`/`social_state == "withheld_tenure"`, each
  replaced by one declared line (Amendment 1). Does NOT touch CR090's
  existing `withheld_paid` disclosure-header behaviour — out of scope here.

## What's NOT done — explicit gap list

1. **The unit suite has not been run this round at all**, not even once.
   `_profile_for_ticker`'s call sites (`_profile_for_ticker(ticker, ...)` used
   elsewhere in the file, e.g. the two `news_feed is None`/`social_feed is
   None` legacy fallback branches inside the function itself) were not
   re-checked against the new `withheld` param — they should be fine
   (default `frozenset()`) but **this is asserted, not verified**.
2. **No tests written** for any of the 14 acceptance criteria. Nothing here
   has been proven by execution — everything above is PROVED BY READING only.
3. **Acceptance #2 (no-op proof)** — not run. The design is meant to be
   byte-identical with all thresholds at 0 (the new `withheld` params default
   to empty everywhere), but no golden-transcript diff was actually executed.
4. **Scope item 7 (prompt-copy softening)** — `bull_researcher.md:16`,
   `bear_researcher.md:16`, `research_manager.md:18`, and the stale
   `room_runner.py:6,1653` prose ("4 Analysts") — **not touched**.
5. **Scope item 9 (docs)** — `agent_data_blueprint.md` update — **not done**.
6. **DEF116 rebase check (D6)** — `test_no_blocking_io_in_async_routes.py` —
   **not run**. This branch was cut from `main`, not from the DEF116 lane, so
   no rebase has happened yet; when DEF116 lands, round 2 must rebase and run
   that file specifically.
7. **Safety-floor regression (acceptance #7/#12)** — not verified by
   execution. The NO_VERDICT path structurally never calls
   `enforce_safety_floor` (short-circuits before reaching it), which trivially
   satisfies "passes through unchanged" by never entering it — but the CR
   explicitly asks to *verify* the general `enforce_safety_floor` contract for
   a NO_VERDICT input too (defensive), which was not done.
8. **Contradiction guard (acceptance #11)** — not applicable in the sense the
   spec described (no LLM narration exists for NO_VERDICT in this
   implementation — see the flag below), so there's nothing to test for a
   discarded contradiction. Confirm this simplification is acceptable before
   treating #11 as satisfied.
9. **Journal/portfolio (Amendment 2 bullet)** — `room_runner.py:~1145` builds
   `title`/`summary` off `run.verdict.action`, which will render `NO_VERDICT`
   automatically (an f-string, not an enum switch) — **not verified this
   opens no journal/simulated position**; likely fine since nothing gates on
   `action == NO_VERDICT` specifically opening a position, but not checked.
10. **Register row + `gen_registers.py`** — not done. No
    `docs/forward_planning/_registry/CR098.row.md` written yet.
11. **`_compute_agent_text`/`_speak_one_agent` signatures** — not re-read
    against the `phase_agents` filtering change; assumed compatible since the
    filtering only changes which `agent_id`s are iterated, not the call shape.

## Deliberate design simplification to flag (not a FLAG-list item, but load-bearing)

`_assemble_no_verdict` uses the **fixed CR-doc copy unconditionally** —
it does not call the live PM LLM on a narrow no-recommendation prompt with a
post-hoc contradiction check, as the spec's Amendment 2 describes. This was a
budget-driven simplification: fixed copy trivially and structurally satisfies
acceptance #10 (no LLM path exists to produce a contradicting APPROVE) and
#11 (no narration exists to contradict), and matches the "must read as
professional discipline" copy verbatim since it *is* that copy. The cost is
that the PM's NO_VERDICT beat is always the same words, never a live
narration of *that specific* session's fundamentals debate. Flag to
architect: keep as-is (cheaper, structurally safer) or build the narrow-prompt
+ post-check version the spec described.

## FLAGS — answered as flags per the assign

1. **D3 fourth-state question** — added `LiveDataState.WITHHELD_TENURE`
   (`news_context.py`), used for News/Social feed state AND
   `profile["technicals_state"]` for Market (Market has no `LiveDataState`
   feed object of its own, so it's a bare string on the profile dict, not a
   4th value flowing through a `NewsFeed`/`SocialFeed`). Client impact for
   coder.mobile: a `news_state`/`social_state` of `"withheld_tenure"` is
   distinct from `"withheld_paid"` — CR090-MOBILE's switch needs a new case
   (its `default:` won't crash, but will silently render nothing without one
   — the exact dark-feature risk the assign warned about).
2. **Trader + Risk phases on the NO_VERDICT path** — built to KEEP running
   (spec's own recommendation), unchanged from the full-roster path. Cost:
   unmeasured this round (no suite run, no timing taken).
3. **DEF098 parity-guard interaction** — flagging per the assign, not
   touched. `DEF098`'s parity guard needs to treat a withheld analyst as a
   declared omission for a degraded `FLOOR_PASS`, not a defect.

## Event/field shapes for coder.mobile (scope item 8, not this lane)

- `RoomEvent(kind="agent_withheld", agent_id: AgentId, reason: "upgrade",
  next_step_agent: AgentId | None, next_step_days: int | None)` — emitted once
  per withheld analyst, all at the start of the ANALYSTS phase (before any
  analyst speaks). **`next_step_agent`/`next_step_days` are the SAME value on
  every `agent_withheld` event in a run** (the roster's single nearest
  upcoming pull-back step, not a per-agent "when does this one come back" —
  pull-back is monotonic, an analyst never un-withholds without an upgrade).
  Both `None` once nothing further is scheduled to go dark.
- `Verdict.opinions_not_included: list[str]` — AgentId *values* (e.g.
  `"social_media_analyst"`), always present (empty list when nothing
  withheld), on every verdict regardless of action.
- `Verdict.action` can now be `"NO_VERDICT"` (added to the existing
  APPROVE/REJECT/MODIFY/PASS enum, `use_enum_values=True` so it's the bare
  string in `model_dump()`/JSON). When `NO_VERDICT`, every level field
  (`size_pct/entry/target/stop/time_horizon_days`) is `null`.
- News/social `LiveDataState` can now be `"withheld_tenure"` — distinct from
  `"withheld_paid"` (see FLAG 1). Both are sent in the existing
  `live_data_notice` SSE event's `live_data.{news,social}` fields (unchanged
  shape, new possible value).

## Verify (round 2 must do this first)

- `./backend/.venv/bin/python -m pytest backend/tests/unit/ -q` — from repo
  root, absolute venv path, foreground. Baseline on `main` was 1338 passed. Not
  yet run against this branch.
- Fix whatever the suite finds before adding new tests for the 14 acceptance
  criteria.

---

STATUS: NOT READY — round 1 stopped on budget before the suite ran or any
acceptance criterion was proved by execution. Do not treat this as
READY_FOR_AUDIT; hand to round 2 (fresh budget) to verify + finish scope items
7/9 + tests + register row.
