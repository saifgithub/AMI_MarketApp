<!-- dispatch hand-off — coder.room, CR098-ROOM round 2 -->
# CR098-ROOM — coder.room hand-off (round 2, PARTIAL — closer, still not audit-ready)

## Round 2 update (this session, budget-capped)

Ran the full suite for the first time this lane (round 1 never ran it): **1338 baseline
green on `main`, unchanged on round 1's mechanism commit** — no regressions. Then, in D5
priority order:

1. **Found and fixed a real acceptance #13 violation**: `_format_profile`'s three
   withheld-domain declared lines said `"...not included in this session (upgrade to
   include the X Analyst)."` — that parenthetical was spliced directly into every agent's
   rendered prompt via `profile_block` (room_prompts.py:290). The non-negotiable is
   explicit: no "upgrade" in any prompt. Stripped the CTA from all three lines
   (market/news/social); they now read as a bare factual declaration. The CTA belongs in
   app chrome (coder.mobile), never agent voice. `RoomEvent(reason="upgrade")` is
   unaffected — that's structural event metadata per the spec's own scope item 3, not
   agent-authored prose.
2. **New test file** `backend/tests/unit/test_cr098_room_analyst_pullback.py` — 21 tests,
   all proven by execution (not by reading):
   - #3/#4 resolver matrix + `next_step` (clock-injected thresholds)
   - Fundamentals structurally unwithholdable; negative threshold fails boot (CR040)
   - #2 no-op proof (practical form — see caveat below)
   - #10 NO_VERDICT: **proved the PM LLM turn is never even called** when Market is
     withheld, using a gateway that would answer a well-formed APPROVE block if reached.
     Strongest available proof the code path decides, not the prompt (CR038).
   - #6 fact-sheet stripping: exact declared-line string asserted, synthetic RSI/
     range/volume/catalyst/sentiment proven absent from the rendered block
   - #13 (+ the fix above): withheld declared lines and the NO_VERDICT fixed copy
     asserted free of "upgrade"/plan names/pricing
   - #5 fetch gating: `resolve_social_feed`/`resolve_news_feed`/`compute_technicals`
     proven never invoked for a withheld analyst (raise-if-called stubs); Fundamentals
     fetch proven to always run
   - D2 (assign) money test: aged FLOOR_PASS user with Social withheld debited strictly
     less than the same-starting-balance present user, amount == `base +
     live_data_surcharge(feeds actually fetched)`
   - Safety-floor regression (#7/#12): `enforce_safety_floor`'s signature carries no
     roster/withheld parameter at all — structurally roster-independent; a NO_VERDICT
     input passed through it is a verbatim no-op (defensive; the live path never calls it
     for NO_VERDICT at all — see the design note below)
   - #8 `opinions_not_included` deterministic from roster, present in `model_dump`
3. **Scope item 7** — softened "the 4 Analysts" in `bull_researcher.md:16`,
   `bear_researcher.md:16`, `research_manager.md:18`, and `room_runner.py:6`'s docstring.
4. **Scope item 9** — `agent_data_blueprint.md` Room section now notes the roster is
   plan-and-tenure-dependent, Fundamentals is the unwithholdable floor, Market-withheld
   terminates in NO_VERDICT.
5. **Register row** — `CR098.row.md` moved `proposed` → `started` (round 1+2 landed real
   mechanism + tests, but this is explicitly NOT a READY_FOR_AUDIT claim).
   `gen_registers.py gen cr` run, `verify all` passes (CR 97 rows, DEF 120 rows, both
   identical to source).

Final suite run this round: **1359 passed** (1338 baseline + 21 new), foreground, from
this worktree.

### What's still NOT done — this round ran out of budget before these

- **#9 CR040 compose parity** — not walked explicitly against
  `test_config_compose_parity.py`. The full suite is green, which is *consistent with*
  the three `.env` ints being correctly forwarded (round 1 claims they are, in
  `docker-compose.yml`), but I did not open that test file and confirm it exercises all
  three new keys by name.
- **#11 contradiction guard** — still N/A by the settled design (see below), not
  independently re-verified this round.
- **#14 live smoke** — not run. Requires a live Alpha environment; this lane only ran the
  unit suite from the Mac worktree.
- **D6 / DEF116 rebase** — not done. DEF116 was `IN_AUDIT` at assign time; not checked
  this round whether it landed on `main` yet. If it has, round 3 must rebase and run
  `test_no_blocking_io_in_async_routes.py` per the assign's D6.
- Live smoke acceptance #14's specific claim ("Adanos not hit, no OHLCV pull") is proven
  at the `_resolve_and_charge_feeds`/`_profile_for_ticker` unit level (this round's new
  #5 tests) but not via an actual live-provider integration run.

### Deliberate design simplification — UNCHANGED, confirmed by round 1 + architect

Per the assign: **KEEP the fixed-copy `_assemble_no_verdict`**, do not build the
narrow-prompt + post-hoc contradiction-check version. This round's #10 test (PM turn
proven never called) is the strongest possible evidence this holds structurally. Cost,
recorded honestly: the PM's NO_VERDICT beat is always the identical words, never a live
narration of that session's specific fundamentals debate.

---

# Round 1 hand-off (superseded above, kept for history)

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

(superseded round-1 mark: NOT READY — token neutralised so exactly one machine-parseable STATUS line remains in this file)

---

(superseded round-2 mark: NOT READY — token neutralised) Round 2 closed the suite-run gap, fixed a real acceptance
#13 violation, and landed 21 executed tests plus scope items 7/9/register.
Remaining before READY_FOR_AUDIT: #9 explicit compose-parity walk, #14 live
smoke, and the D6/DEF116 rebase check. Budget-capped again — do not treat this
as READY_FOR_AUDIT; hand to round 3.

---

# Architect verification + submission (AT:R65, 2026-07-27)

Round 2 also died on the $5 cap, with the hand-off above **uncommitted in the worktree**. The
Architect committed it as found and closed the remaining gaps rather than spending a third worker
round on work that was Architect verification anyway.

**Every number below was re-measured by the Architect, not relayed from the coder.**

## Re-measured

| Check | Result |
|---|---|
| Full suite, worktree, root venv, foreground | **1359 passed**, 178s — exactly `1338 baseline + 21 new`. Matches the coder's claim precisely. |
| New test file alone | 21 passed |

## Gap list from round 2 — resolved

- **#9 compose parity — CLOSED, and it is proved by the green suite, not by inspection.**
  `test_config_compose_parity.py` is **generic**: it walks *every* `Settings` field and requires
  each to be either forwarded in `docker-compose.yml`'s `api-alpha` block or listed in
  `_NOT_FORWARDED` with a stated reason. Verified the three keys are forwarded
  (`docker-compose.yml:129-131`, `ROOM_PULLBACK_DAYS_{SOCIAL,NEWS,MARKET}`) and that
  `room_pullback` appears **zero** times in the waiver dict. So a green suite is a positive proof of
  parity here, not merely consistent with it. DEF038/DEF063 class closed.
- **#11 contradiction guard — N/A by settled Architect decision**, not an outstanding gap. The
  fixed-copy `_assemble_no_verdict` means no LLM narration exists that *could* contradict.
- **#14 live smoke — untestable from here by design.** Mac is a pure editor. Post-promote check.
- **D6 / DEF116 rebase — nothing to rebase yet.** DEF116 is still `IN_AUDIT`; it has not landed on
  `main`. When it does, whoever integrates runs `test_no_blocking_io_in_async_routes.py` per D6.

## Mutation-verified by the Architect

Acceptance #10 is the safety-critical one, so it was proved rather than read. Disabling the
short-circuit at `room_runner.py:2075` (`if False and AgentId.MARKET_ANALYST in ctx.withheld:`)
made the run reach the PM LLM turn and emit **`room_completed action=APPROVE`** — precisely the
DEF059-class inversion the criterion exists to prevent — and **exactly one** test went red:
`test_no_verdict_never_reaches_llm_pm_turn`. Reverted; 21/21 green again. The guard is
load-bearing and precisely targeted.

Also confirmed acceptance #13 directly: `room_prompts.py` contains **no** occurrence of
`upgrade` / plan names / pricing.

## Round 2's own catch, worth recording

Round 2 found a **real acceptance #13 violation that round 1 had shipped into the branch**:
`_format_profile`'s three withheld-domain declared lines carried
`"(upgrade to include the X Analyst)"`, spliced into **every agent's rendered prompt** via
`profile_block`. That is the "no agent voice ever sells" non-negotiable, broken in agent voice
itself. Fixed to a bare factual declaration; the CTA stays app chrome. `RoomEvent(reason="upgrade")`
is untouched — structural event metadata, not agent-authored prose.

## Not verified — stated plainly

- **Acceptance #14 live smoke.** Untestable from the Mac; post-promote.
- **No rebase onto DEF116** has happened (it has not landed).
- The Architect mutation-tested **#10 only**. The other 20 tests were not individually
  mutation-probed — that is the audit's job.
- Round 1's gap items 9 (`NO_VERDICT` opens no journal/simulated position) and 11
  (`_compute_agent_text`/`_speak_one_agent` signatures) were argued sound by the coder and are
  consistent with a green suite, but neither was independently proven.

(superseded round-2 hand-off mark: READY_FOR_AUDIT — token neutralised so exactly one machine-parseable STATUS line remains in this file)

---

# coder.room round 2 (AT:coder.room, 2026-07-27)

Fixed all 5 findings from the round-1 audit verdict
([`orchestration/audit/cr/CR098-ROOM.auditor.md`](../../audit/cr/CR098-ROOM.auditor.md)),
committed incrementally. $15 budget, not the $5 that killed rounds 1/2.

## MAJOR 1 — agent_withheld wired onto the SSE wire

`room.py`'s SSE if/elif had no `agent_withheld` branch and no `else`, so the runner's event was
silently dropped at the API boundary — the whole per-analyst countdown surface had no wire format.
Added the branch (modelled on `live_data_notice`, the same pattern one CR earlier), serialising
`agent_id`/`reason`/`next_step_agent`/`next_step_days`. Added a wire-level test that drives the
real route via `TestClient` with a fake runner whose `subscribe()` yields the event, and asserts
the SSE frame is present and byte-parseable — not merely that the runner emitted it.

## MAJOR 2 — the defining behaviour now has a test

Added `test_withheld_analyst_absent_and_present_analysts_correctly_attributed`: runs a full Room
with News withheld (deliberately NOT the last ANALYSTS-phase slot, where a shifted `zip` would
coincidentally still line up and hide the bug) and asserts no `agent_token`/`agent_done` carries
the withheld agent_id, and each present analyst's concatenated text matches its own scripted
marker (`_scripted_for` monkeypatched to `f"SCRIPT::{agent_id.value}"` so attribution can be
checked without depending on real template contents).

Mutation-verified against both auditor-identified mutations — reverted each time, full CR098 file
back to green before proceeding:

| Mutation | Result before this fix | Result now |
|---|---|---|
| `phase_agents = phase.agents` (withheld analyst speaks anyway) | 1359 passed (undetected) | **1 test RED** |
| `zip(phase_agents, results) -> zip(phase.agents, results)` (emit-order misattribution) | 1359 passed (undetected) | **1 test RED** |

One caveat surfaced and worked around: this worktree sits on an external volume, and pyc mtime
resolution is coarse enough that a sed-mutate-revert cycle without clearing `__pycache__` between
steps can run stale bytecode and misreport. Every mutation run above cleared `__pycache__` first;
the numbers are real.

## MINOR 1 — respawn path's feed fallback gated by roster

`_respawn_run_from_row` (production, `main.py:132` via `resume_pending_retries`) calls `run()` with
`roster=None, news_feed=None, social_feed=None`. The roster resolves fresh so analysts filter
correctly, but the feed fallback resolved news/social at `entitled=True` **ungated** by that same
roster — a withheld analyst's real data got fetched and rendered anyway, and `live_data_notice`
reported "live" for an analyst that never ran. Gated both fallbacks the same way
`_resolve_and_charge_feeds` already does (`roster.withheld` check, `WITHHELD_TENURE` short-circuit).
Added a test simulating the exact respawn call shape for a real aged FLOOR_PASS user with
News+Social withheld; confirmed it reproduces the pre-fix bug (stubbed feeds report LIVE; asserted
red against the un-gated code, then reverted) and is green against the fix.

## MINOR 2 — acceptance #2's no-op test now exercises the real path

`test_default_roster_is_full_no_op` used `user_id=uuid4()` — a nonexistent user — which took
`resolve_roster_for_user`'s missing-row full-roster fallback and never exercised the real no-op
case. Rewrote it with a real aged (100-day) FLOOR_PASS user and all three thresholds explicitly at
0, resolved through the actual `resolve_roster_for_user` DB-lookup path. Mutation-verified: the
auditor's exact off-by-one (`threshold >= 1 and account_age_days >= threshold` ->
`account_age_days >= threshold`, making 0 mean "always" instead of "never") now turns THIS test red
directly — previously caught only incidentally by the D2 money test.

## MINOR 3 — contradictory scaffolding header stripped for a withheld domain

The fact-sheet header unconditionally claimed a withheld domain's fields were "alpha simulation
scaffolding — NOT computed from real price history" immediately above the body's "not included in
this session" line. Moved the three `_withheld_tenure` flags ahead of the header (previously
computed only after it) and skip the header's scaffolding line for a withheld domain. Added
contradiction-check assertions to both existing fact-sheet tests; confirmed they fail against the
pre-fix code (stashed the fix, re-ran, restored) and pass against the fix.

## Verified this round

- Full suite, foreground, absolute venv path, from repo root: **1362 passed**, 188s — exactly
  1359 baseline + 3 new tests (wire test, attribution test, respawn-gating test; MINOR 2 rewrote
  an existing test in place, MINOR 3 added assertions to existing tests — neither adds a new test
  function).
- `backend/tests/unit/test_cr098_room_analyst_pullback.py` alone: 24 passed (was 21).
- Both MAJOR 2 mutations and the MINOR 2 off-by-one re-run against the CURRENT branch, each
  confirmed RED, each reverted and reconfirmed GREEN, `__pycache__` cleared before every run to
  rule out the stale-bytecode artifact described above.

## Not verified — stated plainly

- **Acceptance #14 live smoke.** Untestable from the Mac; post-promote, unchanged from round 1.
- **No rebase onto DEF116** has happened this round either — still `IN_AUDIT` per round 1's note.
  FLAG 1's correct resolution (both `withheld=` kwarg AND the hoisted call) is documented in the
  auditor's verdict for whoever does that merge.
- DEF098 parity blind spot (auditor FLAG 2) — real, quantified, left untouched per the auditor's
  own call that it's correctly out of this lane's scope.
- The three MINOR fixes were each mutation- or contradiction-tested individually; no new
  cross-cutting mutation sweep was run over the round-2 diff as a whole beyond what's listed above.

STATUS: READY_FOR_AUDIT (round 3)
