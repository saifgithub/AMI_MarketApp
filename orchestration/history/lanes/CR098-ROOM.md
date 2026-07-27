# CR098-ROOM — closed lane archive (AT:R65, 2026-07-27)

Room analyst pullback by **plan + account tenure**: roster resolver, three `.env` thresholds,
roster-gated fetch, fact-sheet stripping, `agent_withheld` on the wire, and a **`NO_VERDICT`** built
in code when the Market analyst is withheld. Fundamentals is unwithholdable **in code**, not config.

Audited **COMPLETE round 3** by track U (independent) — zero BLOCKER, zero MAJOR, zero MINOR.
**Three rounds, eight findings, every one re-proved by the auditor's own mutations rather than the
hand-off's.** Merged to `main`; full suite **1366 passed** re-verified post-merge from the repo root.
Worktree + branch reaped.

**Two budget deaths and one Architect error along the way, all recorded in the trail:**
rounds 1 and 2 died on a $5 cap that was the Architect's sizing error (14 acceptance criteria), which
produced the `DISPATCH_BUDGET_USD` override; round 2's worker was the first clean lane in ~28h at
$7.64 of $15. The round-2 MAJOR was against the **Architect's own merge resolution** — during the
DEF116 rebase only one direction of the collision hazard was proved.

**The seam three lanes collided on in one day (CR090 → DEF116 → CR098) is now pinned from BOTH
directions:** DEF116's AST guard catches loss of the `to_thread` hoist, and
`test_run_wiring_passes_withheld_into_profile_for_ticker` catches loss of the `withheld=` kwarg.

**Still open:** the mobile half (spec scope item 8) is unbuilt — `CR098-MOBILE-LIVE` and
`CR098-MOBILE-VERDICT`, $15 each. **CR104 will replace this lane's per-block `*_state` scheme with
per-field provenance.**

## assign

<!-- dispatch assign lane — Architect-owned. CR052. -->
# CR098-ROOM — assign (Phase A + B: mechanism + FOMO surface, backend)

KIND: code
INSTANCE: coder.room
GATE: independent    <!-- Touches the safety-adjacent PM verdict path, adds a new VerdictAction, and changes what a user is charged (see D2). The CR's own Governance section already specifies independent audit. -->
ACCEPTANCE: docs/forward_planning/CR098_room_analyst_pullback/CR098_room_analyst_pullback.md — **277 lines, 14 numbered acceptance criteria, design fully locked. Read it in full. Do not re-derive the design; it is Saiful-approved and amended twice.**
DEPENDS-ON: **CR090 (all three sub-lanes) — integrated and closed on `main` today, 2026-07-27.** Branch from `main` @ `b7ac8e9` or later. This is not a soft dependency: CR090-ROOM rewrote the exact functions you are about to change. **DEF116 is IN AUDIT and WILL land under you in `room_runner.py` — see D6 below. Branch from `main`, not from the DEF116 lane.**
HOT-FILES: `backend/app/services/room_runner.py` (**changed today** — CR090-ROOM merged +658/−34 into it), `backend/app/services/room_prompts.py` (**changed today**), `backend/app/services/entitlements.py`, `backend/app/services/config.py`, `backend/app/schemas/room.py`, `docker-compose.yml`. **`coder.api` is concurrently in `reputation_service.py` (CR091-STREAKS) and `coder.web` in `website_api/` (CR049 r2) — neither overlaps you.**

## Read this before the spec — two things in the spec are now STALE

The CR was written 2026-07-26 and amended 2026-07-27 **before CR090-ROOM merged**. Two of its
statements were true when written and are false now. Verified against `main` this session:

### STALE 1 — "first production caller" of the CR090 layer

The spec (scope item 4) says wiring `resolve_news_feed`/`resolve_social_feed` makes CR098 the
**first production caller**. It is not. **CR090-ROOM is**, as of today. Both resolvers are live.

### STALE 2 — "CR090's surcharge is related, not touched here"

The spec's *Out of scope* says `live_data_surcharge(n_live_analysts)` is "designed-but-unwired…
not touched here." **It is wired now**, and your change hits it directly. See D2.

---

## Architect decisions — settled, do not re-open

**D1 — `entitled=` now has TWO meanings competing for one parameter. Compose them, don't overwrite.**

On `main` today, `room_runner.py:1493`:

```python
entitled = n_available > 0 and balance_for(user_id)[0] >= base + surcharge
```

That is CR090's meaning: **"this user's credit balance covers the live-data surcharge."**
CR098 wants (scope item 4): `entitled = analyst ∈ present` — **"this analyst is on the user's
roster for their plan and account age."**

These are different questions and a user can fail either independently: a day-3 `FLOOR_PASS` user
with zero credits is roster-entitled but credit-unentitled; a day-50 user with a full wallet is the
reverse. **The composition is AND** — live data is fetched only when the analyst is on the roster
**and** the user can pay for it. Do not replace CR090's predicate with yours; do not add a second
call site with different semantics. One composed predicate, one resolver call per feed.

**D2 — Withholding an analyst changes what the user is CHARGED. Make that deliberate and pin it.**

`live_data_surcharge(n)` charges per *live* feed. Skipping a withheld analyst's fetch reduces
`n_available`, which reduces the surcharge inside CR090-ROOM's single atomic
`spend(base + surcharge)`. That is **correct** — never charge for data you did not fetch — but right
now it would happen as a *side effect* of your change rather than as a tested decision.

Required: a test asserting that an aged `FLOOR_PASS` user with Social withheld is debited
**strictly less** than the same user with Social present, and that the amount equals
`base + live_data_surcharge(feeds actually fetched)`. **Money that moves as a side effect is how
money bugs ship.** CR090-ROOM's `spend()` must remain the **only** call site (its D1) — do not add a
second debit anywhere.

**D3 — The disclosure must say WHICH lever the user can pull. Credits ≠ plan.**

CR090 ships a 3-state marker: `LIVE` / `WITHHELD_PAID` / `UNAVAILABLE`, and CR090-MOBILE renders
`withheld_paid` with a **credits** CTA and `unavailable` with **no CTA at all**.

A CR098 withhold is a *third* reason: the data exists, the user could pay, but the analyst is off
their roster on tenure. If you route that through `WITHHELD_PAID`, the client tells the user to buy
credits — which will **not** bring the analyst back. If you route it through `UNAVAILABLE`, the
client says nobody has the data, which is a lie, and shows no CTA at all.

**Either is a DEF059-class inversion: a truthful-looking disclosure pointing at the wrong remedy.**
Introduce a distinct state/reason for roster-withheld and carry it through `agent_withheld` and the
fact-sheet declared line. If that means a fourth `LiveDataState` member, say so in the hand-off and
flag the client impact — CR090-MOBILE's switch has a logging `default:` so an unknown value will not
crash it, but it will render nothing, which is the dark-feature class all over again.

**D4 — `_profile_for_ticker`'s fetch seam was repaired today. Preserve its symmetry.**

CR090-ROOM's recovery included one Architect production fix: `_profile_for_ticker`'s social fallback
had gone through `resolve_social_feed(ticker, entitled=True)` while the *news* branch beside it kept
the raw module-level `fetch_live_news`. That asymmetry moved the seam every existing test patches
(`room_runner.fetch_live_sentiment`) into `social_context` and silently voided those patches —
`test_profile_overlays_live_sentiment_when_enabled` went red with `KeyError: 'social_source'`.

You are adding a *third* gate to these same branches. **Keep news and social structurally
symmetric.** If you change the seam, change both and re-run the existing patch-based tests; a green
new-test file next to a silently-voided old one is exactly the failure this lane must not repeat.

**D5 — The no-op proof is the acceptance that matters most. Do it first, not last.**

Acceptance #2: all three thresholds `0` → convene transcript + verdict **byte-identical** to today.
Build the mechanism, prove the no-op, commit that, and only then build the FOMO surface. That
ordering means a budget death still leaves a safely-promotable increment on the branch — and two of
the three lane deaths in the last 24h were budget caps, one with the entire lane uncommitted.

**D6 — DEF116 lands under you in `_profile_for_ticker`'s call site. Keep the leaf SYNCHRONOUS.**

DEF116 (blocking I/O, MVP show-stopper) is `IN_AUDIT` right now on `lane/DEF116.coder.api` @
`d68a028`. It touches `room_runner.py` in exactly one place — the call you are about to gate:

```python
profile = await asyncio.to_thread(
    _profile_for_ticker, ticker, news_feed=news_feed, social_feed=social_feed
)
ctx = _RoomContext(..., profile=profile)
```

(previously `profile=_profile_for_ticker(...)` inline in the `_RoomContext(...)` kwargs).

Three consequences, all binding:

1. **Branch from `main`, NOT from the DEF116 lane.** DEF116 is unaudited; basing on it means a
   round-2 fix there invalidates your base. You rebase after it lands — that ordering was chosen
   deliberately.
2. **`_profile_for_ticker` must stay plain `def`, never `async def`.** DEF116's whole design (its
   D2) is that leaves stay synchronous so the ~15 existing `monkeypatch.setattr` tests keep working
   from inside a `to_thread` worker. You are adding a *third* gate inside those same news/social
   branches — do it with plain synchronous code. Making the leaf async silently voids DEF116 and
   ~15 tests at once.
3. **At rebase, the `await asyncio.to_thread(...)` wrapper must survive.** A keep-both merge that
   restores a direct `_profile_for_ticker(...)` call re-opens an MVP show-stopper. DEF116 ships an
   AST guard (`backend/tests/unit/test_no_blocking_io_in_async_routes.py`) that turns **red** if it
   does — the Architect proved that by mutation, and the failure names the whole call chain
   `stream_room -> _profile_for_ticker (via run) (via _pump) (via start_run)`. **Run that one test
   file after your rebase**; it is the cheapest possible check that you did not undo the fix.

Related and NOT yours: **DEF120** (filed today) covers the same blocking-I/O class in
`SimEngine`'s per-ticker loops, which reaches `stream_room` via `_build_room_sector_context`. Don't
touch it; don't be surprised to see it named in guard output.

---

## Scope for THIS lane

**In:** spec scope items **1–7 and 9** — roster resolver, the three `.env` ints, phase-loop filter +
`agent_withheld` event, fetch gating, fact-sheet stripping (Amendment 1), PM disclosure +
`NO_VERDICT` (Amendment 2), prompt-copy softening, and the `agent_data_blueprint.md` doc update.

**Out:**
- **Scope item 8, the mobile UI** — separate `coder.mobile` lane, not yours. Emit the events and
  fields it will need, and say in the hand-off exactly what shape they take so its assign can be
  written without re-reading your diff.
- **Do NOT edit DEF098.** The spec says to *flag* to the architect that DEF098's parity guard must
  treat a withheld analyst as a declared omission for a degraded `FLOOR_PASS`. Flag it; leave the
  file alone.
- Convene price stays flat per plan. You are not changing the pricing table — only which feeds are
  fetched (D2).

## Non-negotiables carried from the spec

- **Fundamentals is unwithholdable in CODE, not config.** No `.env` key may exist that can withhold
  it. A config-only guarantee is not a guarantee.
- **A negative threshold FAILS BOOT** (CR040 degrade-loudly), and all three settings must be
  forwarded in `docker-compose.yml`'s `api-alpha` block or `test_config_compose_parity.py` fails —
  DEF038 and DEF063 were each dark for months for want of that one line.
- **NO_VERDICT is built in code, bypassing `_parse_pm_verdict`.** Acceptance #10 demands it hold
  **even when the LLM emits a well-formed APPROVE block** (force-fed fixture). CR038 measured ~70%
  prompt-instruction non-compliance — the code path decides, not the prompt.
- **No agent voice ever sells.** No plan names, no "upgrade", no pricing in any prompt or
  agent-authored string (acceptance #13). The CTA is app chrome.
- **No synthetic stand-in ever renders for a withheld domain** (Amendment 1). Assert on the exact
  rendered prompt string, not on fetch-call counts — acceptance #6 says so explicitly, because
  counting fetches is exactly the check that passes while fabricated RSI still sits in the prompt.

## Verify

- Full suite **from the repo root**, absolute venv path, foreground:
  `./backend/.venv/bin/python -m pytest backend/tests/unit/ -q` — **1332 passed** on `main` today,
  ~170s. Never bare `pytest`, never `cd backend` first; worktrees have no `.venv`.
- Migration single-head if you add one.
- Walk all **14** acceptance criteria explicitly in the hand-off and say which you proved by
  execution versus by reading.

## Working rules

- **Create your own worktree** (`DISPATCH_PROTOCOL.md` §183) — `.claude/worktrees/coder.room-CR098`,
  branch `lane/CR098-ROOM.coder.room`. A worker branched inside the shared `main` checkout today and
  it put another track's commit onto its lane branch.
- **Commit incrementally.** Three lane workers died in 24h, two on budget caps; CR090-ROOM's died
  with the entire lane uncommitted and needed hand recovery. D5's ordering exists to make a partial
  death survivable — use it.
- **Never background a command then emit your final message** (CR057 / failure_patterns P7).
- **Pathspec-commit only** — never `git add -A`, `-am`, or bare.
- Report measurements, not expectations. List what you did **not** verify; the auditor is told to
  weight self-reports sceptically and an honest gap costs far less than a claim that won't reproduce.

## FLAGS — raise, don't decide

1. **The D3 fourth-state question** — whether roster-withheld gets a new `LiveDataState` member, a
   separate reason field, or something else. Pick what you can defend, implement it, and flag the
   choice plus its client impact.
2. **Spec's own open operator question** — at the NO_VERDICT step, Trader + the 3 Risk debators still
   run and burn ~25s of decode producing nothing actionable. The spec recommends **keeping** them
   (the debate is the product; the wall lands harder after a full session). Build it that way, flag
   the cost, let Saiful cut it in Phase C.
3. **DEF098 parity-guard interaction** (see Out of scope) — flag, don't touch.

---

ASSIGNED: coder.room round 1
DISPATCH: ACCEPTED (round 3)

---

## coder hand-off

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

(superseded round-2 mark — token neutralised; the live one is at the foot of this file)


---

# Round 3 — the round-2 MAJOR closed (Architect, AT:R65, 2026-07-27)

STATUS: READY_FOR_AUDIT (round 3)

**Scope: 1 file, test-only.** No production code touched. Done by the Architect rather than a worker
round because the finding is against **my own merge resolution**, not the worker's work.

**Suite: 1366 passed** (round 2 was 1365, `+1` = exactly the new test).

## The finding, and why it was mine

You measured that dropping `withheld=frozenset(roster.withheld)` from the hoisted `to_thread` call
left the **full suite at 1365 green** — while a withheld Market analyst's real RSI/trend/volume
would render in every agent's prompt, contradicting the `NO_VERDICT` copy on the same screen.

I made that merge resolution during the DEF116 rebase, and I proved **one** direction — that
DEF116's guard turns red if the `to_thread` hoist is lost. I did not pin the other. You had already
written in round 1's FLAG 1 that this direction is "caught by nothing," and it still wasn't.

## The fix

`test_run_wiring_passes_withheld_into_profile_for_ticker` — drives the **real `run()`** with a
Market-withheld roster and asserts three things: `compute_technicals` never executes (it raises if
it does), the kwargs actually reaching `_profile_for_ticker` carry
`frozenset({MARKET_ANALYST})`, and the resulting profile is marked `withheld_tenure`.

The distinction that matters: every pre-existing #6 and fetch-gating test calls
`_profile_for_ticker` / `_format_profile` **directly**, passing `withheld=` by hand — so all of them
stay green while the production call site drops it. This one asserts **through** the wiring.

**Mutation-verified with your exact probe:** removed `withheld=frozenset(roster.withheld)` from the
hoisted call ⇒ **only** `test_run_wiring_passes_withheld_into_profile_for_ticker` failed (24 others
in the file passed). Reverted, 1366 green, tree clean. `__pycache__` cleared between every step per
this worktree's coarse-mtime caveat.

## Your out-of-lane finding — accepted and fixed on `main`

You were right that DEF122's pin grouped `room_runner.py` with `revenuecat_client.py` under a
threadpool justification that is **false** for `room_runner.py`. Verified independently:
`main.py:125` is `async def lifespan`, and `:132` awaits `resume_pending_retries()` — so that
`httpx.get` runs **on the event loop**, not in a threadpool.

Corrected on `main` (`638bdfc`, this lane has merged it) with the real reason: it fires at most once
per process during lifespan startup, before uvicorn serves traffic, guarded by
`_PREFIX_CACHE_STATUS_LOGGED` (`room_runner.py:2554`) — and an explicit note that **a second httpx
call in that module would not inherit the reasoning.** Your framing was right: a pin with a wrong
reason is worse than a pin with none.

## Not verified — unchanged

- **Acceptance #14 live smoke** — untestable from the Mac by design. Post-promote.
- **DEF098 parity blind spot** — still out of scope, still needs an Architect decision on whether a
  withheld analyst counts as a declared omission for a degraded `FLOOR_PASS`.
- I did not re-run the five round-1 mutations this round; you re-ran all five yourself at round 2
  and they held.
- **The mobile half is still unbuilt** — `CR098-MOBILE-LIVE` and `CR098-MOBILE-VERDICT` are written,
  `$15` each, `UNASSIGNED`, held on this verdict.

---

## architect bridge

<!--
CR098-ROOM.architect.md — architect/coder submission lane (track R owns).
State derives from round numbers here vs CR098-ROOM.auditor.md (see PROTOCOL.md).
-->

# CR098-ROOM — audit lane (Room analyst pullback: mechanism + FOMO surface, backend)

SUBMITTED: round 3

**Item:** withhold analysts from a Room convene based on plan **and account tenure**, disclose the
withholding honestly, strip any synthetic stand-in for the withheld domain from the rendered
prompt, and terminate in a **`NO_VERDICT`** when the Market analyst is withheld. Fundamentals is
unwithholdable.

Acceptance: `docs/forward_planning/CR098_room_analyst_pullback/CR098_room_analyst_pullback.md`
— 277 lines, **14 numbered acceptance criteria**, design Saiful-approved and amended twice.
Assign (carries **D1–D6**): `orchestration/dispatch/lanes/CR098-ROOM.assign.md`
Hand-off: `orchestration/dispatch/lanes/CR098-ROOM.coder.room.md`

**Code branch:** `lane/CR098-ROOM.coder.room` @ **`908119d`**, off `main` @ `2f22a7e`.
Scope **15 files, +1224/−38** (production code unchanged since `4a50c2e`; `908119d` only
neutralises two superseded `STATUS:` tokens in the hand-off so exactly one machine-parseable
line remains).

**GATE: independent** — changes what a user is **charged** (D2), adds a new `VerdictAction` on the
safety-adjacent PM verdict path, and introduces a 4th `LiveDataState`. The CR's own Governance
section specifies independent audit.

## Provenance — two budget deaths, and the honesty held both times

**Round 1 died on the $5 cap; round 2 died on it too.** Neither was a capability failure — the
budget was the **Architect's sizing error** (a 277-line spec with 14 acceptance criteria was never
going to fit $5), and it is recorded as such in the trail.

**Both workers failed well**, which is why this lane is submittable at all: each committed
incrementally per D5's ordering, left a clean worktree, and wrote a hand-off that **explicitly
refused to claim audit-readiness** and enumerated its own gaps. Round 2 started far ahead of round 1
purely because round 1 was honest. Contrast the same day's CR091-STREAKS (no report at all) and
DEF116 (whole lane abandoned uncommitted).

Round 2's hand-off was left **uncommitted** in the worktree when its budget expired. The Architect
committed it as found, closed the remaining gaps (they were Architect verification work, not coder
work), and submitted. **No production code was changed after round 2.**

## Round 2's own catch — a real defect it found in round 1's branch

`_format_profile`'s three withheld-domain declared lines carried
`"(upgrade to include the X Analyst)"`, spliced into **every agent's rendered prompt** via
`profile_block`. That is acceptance #13 — *no agent voice ever sells* — broken in agent voice
itself. Round 2 found it, fixed it to a bare factual declaration, and tested it. Worth weighing when
you calibrate how much to trust the rest of round 2's work.

## Already proved — don't re-spend budget establishing these

| Claim | Evidence |
|---|---|
| Suite | **1359 passed**, 178s, re-measured **by the Architect** in the worktree — exactly `1338 baseline + 21 new`. Coder's claim matched to the test. |
| Acceptance #10 (the safety-critical one) | **Mutation-verified by the Architect.** Disabling the short-circuit at `room_runner.py:2075` (`if False and AgentId.MARKET_ANALYST in ctx.withheld:`) drove the run into the PM LLM turn and produced **`room_completed action=APPROVE`** — the exact DEF059 inversion the criterion exists to prevent — and **exactly one** test went red: `test_no_verdict_never_reaches_llm_pm_turn`. Reverted, 21/21 green. |
| Acceptance #9 compose parity | **Closed, and the green suite IS the proof.** `test_config_compose_parity.py` is generic — it walks *every* `Settings` field and demands each be forwarded or waived-with-reason. The three keys are forwarded at `docker-compose.yml:129-131` and `room_pullback` appears **zero** times in `_NOT_FORWARDED`. DEF038/DEF063 class closed. |
| Acceptance #13 | `room_prompts.py` grepped: no `upgrade`, no plan names, no pricing. |

## Audit this hardest

1. **D2 — the money.** A withheld analyst is never probed, so it never reaches `n_available`, so the
   surcharge inside CR090-ROOM's single atomic `spend(base + surcharge)` drops. There is a test
   asserting an aged `FLOOR_PASS` user with Social withheld is debited **strictly less**, equal to
   `base + live_data_surcharge(feeds actually fetched)`. **Verify `spend()` still has exactly one
   call site** (CR090-ROOM's D1) — a second debit anywhere is a 402-mid-stream bug.

2. **D3 — the 4th `LiveDataState.WITHHELD_TENURE`, and its client consequence.** The point of the
   distinct state is that a roster-withhold's remedy is *tenure/plan*, not *credits*. Routing it
   through `WITHHELD_PAID` would tell the user to buy credits, which will not bring the analyst
   back — a DEF059-class inversion. Confirm the new state genuinely carries through `agent_withheld`
   and the fact-sheet line. **Then note the shipped-client reality:** CR090-MOBILE's switch has a
   logging `default:`, so it will not crash on the unknown value — **it will render nothing.** The
   mobile half (scope item 8) is a separate unlaned surface. Judge whether that is the CR100 /
   DEF038 / DEF063 dark-feature class again.

3. **Acceptance #2, the no-op proof.** D5 called this the acceptance that matters most: all three
   thresholds `0` ⇒ transcript + verdict byte-identical to today. The coder describes its test as a
   "practical form" of the proof. **Judge whether the practical form is actually equivalent** to the
   byte-identical claim the criterion makes.

4. **Acceptance #6 — assert on the rendered string, not fetch counts.** The spec is explicit that
   counting fetch calls is exactly the check that passes while fabricated RSI still sits in the
   prompt. The coder says it asserts the exact declared line and proves synthetic
   RSI/range/volume/catalyst/sentiment absent. Verify it is really asserting on rendered output.

5. **D4 — news/social seam symmetry.** CR090-ROOM's recovery repaired an asymmetry here that had
   silently voided existing `monkeypatch` tests (`test_profile_overlays_live_sentiment_when_enabled`
   went red with `KeyError: 'social_source'`). This lane adds a *third* gate to those same branches.
   Confirm the old patch-based tests still genuinely exercise the patched path rather than passing
   vacuously.

6. **The settled simplification.** `_assemble_no_verdict` uses **fixed copy**, not the spec's
   narrow-prompt + post-hoc contradiction check. **This was the Architect's decision, not the
   coder's drift** — structural beats prompt-dependent (CR038 measured ~70% instruction
   non-compliance) and it satisfies #10/#11 by construction. Honest cost: the PM's NO_VERDICT beat
   is always the identical words. Push back if you disagree; it is a decision, not a finding.

## Not verified — stated plainly

- **Acceptance #14 live smoke — untestable from here by design.** Mac is a pure editor. Post-promote.
- **No rebase onto DEF116.** DEF116 is still `IN_AUDIT` and has not landed. Per D6, whoever
  integrates second runs `test_no_blocking_io_in_async_routes.py` — a keep-both merge that restores
  a direct `_profile_for_ticker(...)` call re-opens an MVP show-stopper.
- **The Architect mutation-probed #10 only.** The other 20 tests were not individually probed.
- Round 1's residual arguments — that `NO_VERDICT` opens no journal/simulated position, and that
  `_compute_agent_text`/`_speak_one_agent` signatures are unaffected by the phase-filter change —
  are consistent with a green suite but **were never independently proven**.
- **Acceptance #11** is N/A by the settled design (no LLM narration exists that could contradict),
  not satisfied by test.


---

# Round 2 — all five findings closed, then rebased onto DEF116 (AT:R65, 2026-07-27)

**Branch:** `lane/CR098-ROOM.coder.room` @ **`73dbcce`**. Scope vs `main`: **16 files, +1288/−44**.
**Suite: 1365 passed**, re-measured by the Architect in the worktree after the rebase
(worker measured 1362 pre-rebase; `+3` = DEF116's three guard tests arriving with `main`).

**The worker was clean this round** — six incremental commits, one per finding, clean worktree,
**$7.64 of a $15 cap**, and it re-ran your two mutations itself rather than asserting they were
covered. First lane worker in ~28h to finish without the Architect recovering it.

| Your finding | What landed |
|---|---|
| **MAJOR 1** — `agent_withheld` never reaches the wire | `elif` branch added to `room.py`'s SSE dispatcher, modelled on `live_data_notice` at `:225`. Test asserts the frame appears **through the real route**, not that the runner emitted it |
| **MAJOR 2** — nothing tests the defining behaviour | Test asserts no `agent_token`/`agent_done` carries a withheld `agent_id` and that present analysts are correctly attributed. **Both of your mutations re-run and now RED** (previously undetected at 1359) |
| **MINOR 1** — respawn path's feeds ungated | Feed fallback gated by roster, matching Market's existing treatment; test reproduces the pre-fix bug |
| **MINOR 2** — acceptance #2's test didn't test acceptance #2 | Rewritten to use a real aged `FLOOR_PASS` user through the actual DB-lookup path instead of `uuid4()`; now catches the off-by-one **directly** rather than incidentally via the money test |
| **MINOR 3** — contradictory scaffolding header | Stripped for a withheld domain; contradiction assertions confirmed failing pre-fix |

## ⚠️ The D6 rebase hazard fired for real — read this before auditing `room_runner.py`

DEF116 landed on `main` between your verdict and this resubmission, and the rebase **conflicted in
exactly the seam D6 predicted**. The two sides were:

- **DEF116 (`main`)**: `profile = await asyncio.to_thread(_profile_for_ticker, …)` hoisted out of
  the `_RoomContext(...)` kwargs.
- **CR098 (lane)**: still calling `_profile_for_ticker(...)` **inline** in those kwargs, now with a
  new `withheld=` argument.

A keep-both resolution here restores a direct blocking call and **silently re-opens an MVP
show-stopper**. Resolved by keeping DEF116's `to_thread` hoist and carrying CR098's `withheld=`
kwarg into it. **The proof is not my say-so:** DEF116's own AST guard turns red naming
`stream_room -> _profile_for_ticker (via run) (via _pump) (via start_run)` if the direct call comes
back, and it is **green** on this branch. Please re-run it as your own check —
`backend/tests/unit/test_no_blocking_io_in_async_routes.py`.

## DEF122 — a defect in DEF116's guard, found by this rebase and fixed

The same rebase exposed that DEF116's httpx inventory pin was keyed on `file:line`. CR098 added
~146 lines to `room_runner.py`, an **untouched** `httpx.get` moved `:2618` → `:2764`, and the guard
reported a **NEW blocking call that did not exist**. Filed and fixed as **DEF122** (on `main`):
pinned by **file + count** instead. Mutation-verified both ways — a new call in an unlisted file
(0 → 1) fails, and a **second** call in an already-pinned file (1 → 2) also fails, which is the
obvious weakness of count-based pinning and is closed. Line numbers are still reported in the
failure text as diagnostics, not identity.

## Worth knowing — an environment trap, not a code issue

The worker reported that this worktree sits on an **external volume with coarse mtime resolution**,
which produced one false mutation-test reading until `__pycache__` was cleared between steps. If a
mutation of yours appears not to take effect, clear `__pycache__` before concluding the test is
blind.

## Not verified — unchanged from round 1

- **Acceptance #14 live smoke — untestable from here by design.** Mac is a pure editor. Post-promote.
- **DEF098 parity blind spot** — correctly out of scope; still needs the Architect to decide whether
  a withheld analyst counts as a declared omission for a degraded `FLOOR_PASS`.
- The Architect re-measured the suite and re-ran the D6 guard, but did **not** independently re-run
  the worker's five fixes' mutations — the worker did, and reported them; that is a self-report.
- **The mobile half is still unbuilt.** `CR098-MOBILE-LIVE` and `CR098-MOBILE-VERDICT` are written
  and `UNASSIGNED`, deliberately held on this verdict.


---

# Round 3 — the MAJOR closed (AT:R65, 2026-07-27)

**Branch:** `lane/CR098-ROOM.coder.room` @ **`e932a36`**. Round-3 scope: **1 file, test-only.**
No production code touched. **Suite: 1366 passed** (round 2 was 1365, `+1` = exactly the new test).

Done by the Architect, not a worker round: the finding is against **my own merge resolution**.

**The fix:** `test_run_wiring_passes_withheld_into_profile_for_ticker` drives the real `run()` with a
Market-withheld roster and asserts `compute_technicals` never executes, that the kwargs actually
reaching `_profile_for_ticker` carry `frozenset({MARKET_ANALYST})`, and that the resulting profile
is marked `withheld_tenure`. The distinction you identified is the whole point: every pre-existing
#6 and fetch-gating test passes `withheld=` **by hand** to a direct call, so all of them stay green
while the production call site drops it. This one asserts **through** the wiring.

**Mutation-verified with your exact probe:** removing `withheld=frozenset(roster.withheld)` from the
hoisted `to_thread` call fails **only** that test — the other 24 in the file pass. Reverted, 1366
green, tree clean, `__pycache__` cleared between steps.

You were right that I proved only one direction of the hazard I created. DEF116's guard covers
losing `to_thread`; nothing covered losing `withheld=`, and you had already said so in round 1's
FLAG 1. It is covered now.

**Your out-of-lane finding is accepted and already fixed on `main` (`638bdfc`).** Verified
independently: `main.py:125` is `async def lifespan` and `:132` awaits `resume_pending_retries()`,
so `room_runner.py`'s `httpx.get` is on the event loop — the threadpool reason I wrote was simply
wrong. Replaced with the real one (fires once per process at lifespan startup, before uvicorn serves
traffic, guarded by `_PREFIX_CACHE_STATUS_LOGGED`), plus an explicit warning that a second httpx
call in that module would **not** inherit it.

**Unchanged and still not verified:** acceptance #14 live smoke (untestable from the Mac by design);
the DEF098 parity question (out of scope, needs an Architect decision); and the mobile half remains
unbuilt — `CR098-MOBILE-LIVE` and `CR098-MOBILE-VERDICT` are written, $15 each, held on this verdict.

---

## auditor verdicts

<!--
CR098-ROOM.auditor.md — auditor lane file (track U owns). State derives from
round numbers here vs CR098-ROOM.architect.md (see PROTOCOL.md).
-->

# CR098-ROOM — audit lane (auditor)

**Item:** Room analyst pull-back — withhold analysts on plan + account tenure, disclose it
honestly, strip synthetic stand-ins for the withheld domain, and terminate in `NO_VERDICT` when
Market is withheld. Fundamentals unwithholdable.

**Gate:** independent — changes what a user is charged (D2), adds a new `VerdictAction` on the
safety-adjacent PM verdict path, adds a 4th `LiveDataState`.

**Audited SHA:** `908119d`, off `main` @ `2f22a7e`. Isolated worktree
`.claude/worktrees/audit-CR098-ROOM/`, own venv. **Provenance:** two budget deaths; both workers
failed well (incremental commits, honest gap lists); round 2 caught a real acceptance-#13
violation in round 1's branch. The Architect committed round 2's uncommitted hand-off as found
and closed the verification gaps. No production code changed after round 2.

## Round 1

### Reproduced independently

| Check | Result |
|---|---|
| Scope | `git diff 2f22a7e 908119d --stat` — 15 files, **+1224/−38**, exact match. |
| Full suite | **1359 passed** in 201s — exactly the Architect's re-measured figure. |
| Compose parity | All three `ROOM_PULLBACK_DAYS_*` forwarded in the `api-alpha` block; `field_validator` already imported at `config.py:6`. |

### What holds — mutation-tested, not read

Every mutation reverted individually; the CR098 file re-confirmed 21/21 green after each.

| Probe | Result |
|---|---|
| **Fundamentals made withholdable** (added to `_WITHHOLDABLE_ORDER` + a threshold + removed the unconditional prepend) | **3 tests red** — the code-not-config guarantee is real |
| **`n_available` counts a `WITHHELD_TENURE` feed** (D2 money) | **1 test red** — `test_aged_floor_pass_social_withheld_debited_strictly_less` |
| **Roster-withhold routed through `WITHHELD_PAID`** (the D3 inversion) | **2 tests red** |
| **`threshold >= 1` dropped** — 0 stops meaning "never" | **1 test red** (see MINOR 2 — not the test you'd expect) |

Read directly and confirmed:

- **#10 is structural.** The `if AgentId.MARKET_ANALYST in ctx.withheld:` branch is **first** in the
  VERDICT if/elif/else, so `_stream_pm_response`, `_parse_pm_verdict` and `enforce_safety_floor`
  are all bypassed — there is no code path from a withheld-Market run to a parsed LLM verdict.
  `_WellFormedApproveGateway.pm_called is False` proves it by execution.
- **#8's single insertion point** sits after the whole if/elif/else, so `opinions_not_included` is
  stamped on all four verdict paths (NO_VERDICT / APPROVE / PASS / fail-safe).
- **D3 has no inversion at the finalisation point** — `_final_state` (`room_runner.py:1575`) only
  maps `LIVE → WITHHELD_PAID` when unentitled; `WITHHELD_TENURE` passes through untouched.
- **D4 symmetry is preserved by non-modification** — CR098 gates News/Social *upstream* in
  `_resolve_and_charge_feeds`; `_profile_for_ticker`'s news/social branches are untouched and
  `profile["news_state"]/["social_state"]` are set unconditionally from the feed. Proved the old
  patch-based tests are **not** vacuous: disabling the social overlay turned
  `test_profile_overlays_live_sentiment_when_enabled` red (the exact test CR090's asymmetry
  silently voided), plus 2 parity tests.
- **#6 asserts on rendered output**, not fetch counts — the tests poison the profile with
  `"SHOULD NOT APPEAR"` / `rsi: 999` and assert against `_format_profile`'s string. Correct.

### MAJOR 1 — `agent_withheld` never reaches the wire

`backend/app/api/room.py`'s SSE dispatcher is an explicit if/elif over exactly seven kinds —
`started`, `live_data_notice`, `phase`, `agent_token`, `agent_done`, `verdict`, `error` — with
**no `agent_withheld` branch and no `else`**. The event the runner emits at `room_runner.py:1988`
is silently dropped at the API boundary and never becomes an SSE frame. Grep across the worktree:
`agent_withheld` appears in exactly three places in backend source, **all inside
`room_runner.py`**, and zero times under `app/api/`.

So the three `RoomEvent` fields added expressly for the client countdown (`reason`,
`next_step_agent`, `next_step_days`) are unreachable from outside the process, and the entire FOMO
surface has no wire format at all.

**This corrects the hand-off's framing.** It states CR090-MOBILE's switch has a logging `default:`
"so it will not crash on the unknown value — it will render nothing." That presumes the value
reaches the client. It does not. Scope item 8 is not blocked on UI work — it has nothing to
consume. CR090's own `live_data_notice` **is** wired in this same file (`room.py:225`), so the
pattern was established one CR earlier and one branch was missed here.

Partial mitigation: the closing disclosure does survive — `Verdict.opinions_not_included` rides
`ev.verdict.model_dump_json()` on the `verdict` event. The verdict-level disclosure works; the
per-analyst locked chair and countdown do not.

This is the DEF038 / DEF063 / CR100 shipped-but-dark class, and it is inside this lane's own
backend scope (item 3, "phase-loop filter + `agent_withheld` event"), not the out-of-scope mobile
half. Fix is one `elif` branch.

### MAJOR 2 — nothing tests the defining behaviour: that a withheld analyst does not run

Two mutations, each run against the **full** suite, not just the CR098 file:

| Mutation | Full suite |
|---|---|
| `phase_agents = tuple(a for a in phase.agents if a not in ctx.withheld)` → `phase_agents = phase.agents` — the withheld analyst **speaks anyway** | **1359 passed** |
| `zip(phase_agents, results)` → `zip(phase.agents, results)` — each analyst's text attributed to the **wrong agent** | **1359 passed** |

Both are undetected. The first makes the app emit `agent_withheld` for an analyst that then speaks
in the transcript and appears in `opinions_not_included` — directly self-contradicting output, and
the withheld analyst's decode is billed to the operator. The second is silent misattribution.

All 21 new tests assert *around* the mechanism — the fetch is skipped, the event is emitted, the
verdict lists it — and none asserts the withheld analyst's voice is **absent from the transcript**.
That is the CR's defining behaviour.

This is not hypothetical exposure. `phase_agents` has three separate uses (the `asyncio.gather`
comprehension, the emit-order `zip`, the sequential loop) sitting inside CR077's parallel/sequential
branch split, and this exact seam is about to be rebased under DEF116. A merge that drops one of
the three restores full-roster behaviour — or misattribution — with a green suite.

Fix is small: assert no `agent_token`/`agent_done` event carries a withheld `agent_id`, and that
each analyst's text lands under its own id.

### MINOR 1 — the respawn path resolves the roster but not the feeds

`_respawn_run_from_row` (production — wired at `main.py:132` via `resume_pending_retries`) calls
`run()` with no `roster`, `news_feed` or `social_feed`. `run()` resolves the roster fresh, so
analysts *are* filtered and `NO_VERDICT` can fire — but the feed fallback resolves news/social at
`entitled=True` **ungated by that roster**. A withheld News/Social analyst's real data is then
fetched and rendered in the fact sheet, and `live_data_notice` reports `news: "live"` for an
analyst that was withheld. Market is gated correctly (it reads `withheld` directly), so the path
is internally asymmetric — the D4 concern one layer up. Zero users affected today (thresholds ship
at 0). Fix: gate the two fallbacks the same way `_resolve_and_charge_feeds` does.

*(Checked and cleared: `credit_cost=None` on this path is guarded at `room_runner.py:1807`.)*

### MINOR 2 — acceptance #2's own test does not test acceptance #2

**Answering the hand-off's question directly: the "practical form" is not equivalent, and it is
weaker in exactly the dimension the criterion names.** `test_default_roster_is_full_no_op` runs
with `user_id=uuid4()` — a **nonexistent** user, which takes `resolve_roster_for_user`'s
missing-row full-roster fallback. It therefore never exercises the real no-op case (an aged
`FLOOR_PASS` user with all three thresholds at 0), never captures a transcript, and never compares
against a pre-CR098 baseline.

Measured: the realistic off-by-one that breaks the no-op guarantee — `threshold >= 1 and
account_age_days >= threshold` → `account_age_days >= threshold`, making 0 mean *always* instead of
*never* — is caught **only** by `test_aged_floor_pass_social_withheld_debited_strictly_less`, the
D2 **money** test. The guarantee D5 called "the acceptance that matters most" survives incidentally,
through a test written for something else.

### MINOR 3 — the fact-sheet disclosure header still describes stripped fields

Rendered a Market-withheld profile: the header still carries *"RSI, trend, volume,
support/breakout: alpha simulation scaffolding — NOT computed from real price history"*
immediately above *"Market technicals: not included in this session."* Same shape for Social. Low
impact (prompt copy, not user copy) but it is contradictory text fed to every agent, and CR038's
own finding is that inconsistent prompt copy degrades compliance.

### FLAGS

1. **D6 integration hazard — measured, and worse-shaped than D6 describes.** Trial-merged DEF116
   (`d68a028`) into this SHA. Git **auto-merged DEF116's hoisted call without CR098's `withheld=`
   kwarg** (no conflict marker there at all) and raised a conflict only inside the
   `_RoomContext(...)` kwargs. Taking HEAD re-opens the blocking call — DEF116's AST guard catches
   that, as D6 says. Taking DEF116's side silently **drops `withheld=`**, disabling the Market
   fact-sheet strip — and that direction is caught by **nothing**, because CR098's tests call
   `_profile_for_ticker` and `_format_profile` directly rather than through `run()`. The correct
   resolution is a single call carrying both:
   ```python
   profile = await asyncio.to_thread(
       _profile_for_ticker, ticker, news_feed=news_feed, social_feed=social_feed,
       withheld=frozenset(roster.withheld),
   )
   ```
2. **DEF098 parity blind spot — measured, confirming the coder's flag.** With Market withheld the
   synthetic `rsi` is still *produced* in the profile dict (58 in my probe) and no longer
   *rendered*. DEF098's "every produced field is rendered or declared" guard would flag that if it
   ever ran against a withheld profile; no test constructs one. Real, quantified, and correctly
   left untouched by this lane.
3. **The fixed-copy `NO_VERDICT` simplification — no pushback, I agree.** Structural beats
   prompt-dependent (CR038's ~70% non-compliance) and it satisfies #10/#11 by construction. The
   honest cost — identical wording every time — is acceptable for a rare wall state.
4. **Trader + Risk still burn ~25s producing nothing actionable** at the NO_VERDICT step —
   built per the spec's recommendation. Saiful's call, Phase C.

### Not verified

- **Acceptance #14 live smoke** — untestable from a pure-editor Mac. Post-promote.
- **Not merged onto current `main`** — I measured only the DEF116 seam (FLAG 1), not a full
  integration.

### Findings

1. **MAJOR** — `agent_withheld` is emitted by the runner but has no branch in `room.py`'s SSE
   dispatcher, so it never reaches the wire; the countdown fields are unreachable. Shipped-dark.
2. **MAJOR** — no test asserts a withheld analyst is absent from the transcript. Removing the
   phase filter, and mismatching the emit-order `zip`, each leave the **full suite at 1359 passed**.
3. **MINOR** — the production respawn path resolves the roster but leaves the News/Social feed
   fallback ungated by it.
4. **MINOR** — acceptance #2's test uses a nonexistent user and never exercises the real no-op
   path; the guarantee is held only incidentally by the D2 money test.
5. **MINOR** — the fact-sheet disclosure header still describes fields the withhold stripped.

### Verdict

**VERDICT: AWAITING_FIXES (round 1)** — two MAJOR, three MINOR. (Round 1 is the round *audited*,
per `PROTOCOL.md` — the architect bumps to `SUBMITTED: round 2`.)

The mechanism itself is well built. The resolver, the money path, the fourth `LiveDataState`, the
`NO_VERDICT` short-circuit and the fact-sheet stripping all survive mutation, and D4's symmetry is
preserved in the strongest possible way — by not touching the seam. Both MAJORs are about the
edges: the disclosure that never leaves the process, and the one behaviour the test file walks all
the way around without ever asserting. Both fixes are small.

Run report: [`../runs/2026-07-27_run-65/run_report.md`](../runs/2026-07-27_run-65/run_report.md)

---

## Round 2

**Audited SHA:** `73dbcce` (`lane/CR098-ROOM.coder.room`), rebased onto `main` past DEF116 +
DEF121 + DEF122. Scope vs `main`: **16 files, +1288/−44**; the backend code delta is confined to
the expected files (`room.py +13`, `room_prompts.py`, `room_runner.py`, `entitlements.py`,
`config.py`, `news_context.py`, `schemas/room.py`, `docker-compose.yml`) — no strays. Isolated
worktree `.claude/worktrees/audit-CR098-r2/`, own venv. **Full suite 1365 passed** in 215s on a
verified-clean tree, matching the Architect's re-measure exactly.

The Architect states plainly that they did **not** re-run the worker's five fixes' mutations — the
worker did and self-reported. So I ran all five myself, verbatim from round 1, clearing
`__pycache__` between every step (the hand-off warns this external volume's coarse mtime can mask
an edit).

### All five findings genuinely closed — my own mutations, not the self-report

| Round-1 finding | My mutation | Result |
|---|---|---|
| **MAJOR 1** — `agent_withheld` never reaches the wire | deleted the new `elif ev.kind == "agent_withheld"` branch from `room.py`'s dispatcher | **RED** — `test_agent_withheld_reaches_the_sse_wire` |
| **MAJOR 2a** — withheld analyst not proven absent | `phase_agents = phase.agents` | **RED** (was undetected at 1359) |
| **MAJOR 2b** — emit-order misattribution | `zip(phase.agents, results)` | **RED** (was undetected at 1359) |
| **MINOR 1** — respawn feeds ungated | un-gated the respawn news fallback | **RED** — `test_respawn_path_gates_feed_fallback_by_roster` |
| **MINOR 2** — #2's test didn't test #2 | dropped `threshold >= 1` (0 stops meaning "never") | **RED in `test_default_roster_is_full_no_op` itself**, no longer only incidentally via the money test |
| **MINOR 3** — contradictory scaffolding header | restored the unconditional header line | **RED** |

The MAJOR 2 test is better than the one I asked for: it withholds **News** (3rd of 4) rather than
the last slot, because withholding the tail makes the correct and buggy `zip` coincide on every
surviving pair. That is the detail that decides whether the test catches the misattribution at all,
and they found it.

**D6 seam, re-checked as the Architect asked.** The merged call site carries **both**
`await asyncio.to_thread(...)` **and** `withheld=frozenset(roster.withheld)` — the exact resolution
I specified when I measured the hazard in round 1. Restoring the inline blocking call turns
DEF116's guard **RED**, naming `room.py:stream_room -> _profile_for_ticker` and
`-> yf.Ticker`. The guard genuinely protects that direction.

### MAJOR — the merge hazard's *other* direction is still unguarded, and I measured it

Round 1's FLAG 1 recorded two ways a keep-both merge of this seam goes wrong. DEF116's guard covers
one (losing `to_thread`). I wrote then that the other — **losing `withheld=` while keeping the
hoist** — is "caught by nothing." It still is.

Dropped `withheld=frozenset(roster.withheld)` from the hoisted call and ran the **full** suite:
**1365 passed.** CR098's own file: 24 passed. DEF116's guard: 3 passed. Nothing anywhere.

What that regression does in production: `_profile_for_ticker` receives an empty `withheld`, so the
Market gate never fires — `compute_technicals(ticker)` runs (the yfinance OHLCV pull the roster gate
exists to bank) and `technicals_state` is never set to `withheld_tenure`. `_format_profile` then
renders **real RSI, trend, volume and range for a withheld Market analyst** — the Amendment 1 /
acceptance #6 rule this CR exists to enforce. On a `NO_VERDICT` run it is self-contradicting output:
the PM refuses because *"this session ran without a market read"* while the fact sheet in every
agent's prompt contains a full market read.

Why nothing catches it: **every** #6 and fetch-gating test calls `_profile_for_ticker` or
`_format_profile` **directly** with an explicit `withheld=` argument. None exercises the
`run()` → `_profile_for_ticker` wiring. That is precisely round-1 MAJOR 2's shape — tests asserting
*around* the mechanism instead of *through* it — one layer further out, on a call site that three
lanes have now collided on (CR090 → DEF116 → CR098) and that I measured git resolving silently
wrong in this exact direction.

Fix is one assertion: drive `run()` with a Market-withheld roster and assert the rendered profile
carries `technicals_state == "withheld_tenure"` (or that `compute_technicals` is never called).
DEF120 lands in `room_runner.py` next, and the two CR098-MOBILE lanes follow — this seam will be
disturbed again.

### Out of lane — DEF122 closed my DEF116 round-3 MINOR with the wrong reason

`_KNOWN_SYNC_HTTPX_COUNTS` now groups `room_runner.py` with `revenuecat_client.py` under *"both
called from a sync `def` context (FastAPI runs those in a threadpool), so they do not park the event
loop."* That is **not** true of `room_runner.py`. `log_prefix_cache_status()`'s
`httpx.get(timeout=5.0)` (now `:2764`) is reached first from `main.py:132` —
`await get_room_runner().resume_pending_retries()` inside `async def lifespan` — i.e. **directly on
the event loop**, not through a threadpooled `Depends`.

It is still safe, for a different reason: it fires once per process during lifespan startup, before
uvicorn serves traffic, guarded by `_PREFIX_CACHE_STATUS_LOGGED`. My round-3 finding was a pin with
*no* stated reason; it now has a *wrong* one, which is worse — a reader could add a second httpx
call to that module on the same false premise. Architect's call (DEF122 is on `main`, not this
lane); the correct reason is the paragraph above.

### Findings

1. **MAJOR** — nothing pins the `roster → _profile_for_ticker` wiring. Dropping `withheld=` from
   the hoisted `to_thread` call leaves the **full suite at 1365 passed**, while a withheld Market
   analyst's real technicals render in every agent's prompt and contradict the `NO_VERDICT` copy.
   The other half of the same merge hazard is guarded; this half is not.

### Verdict

**VERDICT: AWAITING_FIXES (round 2)** — one MAJOR. (Round 2 is the round *audited*.)

The worker's round was clean and its self-reports check out under my own probes — first lane in
~28h to come back without Architect recovery, and the MAJOR 2 test is sharper than what I asked
for. The remaining MAJOR is the second direction of the hazard I flagged in round 1 and is the same
class as round-1 MAJOR 2: correct code, unpinned wiring, on the one call site three lanes keep
colliding on. One assertion closes it.

Run report: [`../runs/2026-07-27_run-67/run_report.md`](../runs/2026-07-27_run-67/run_report.md)

---

## Round 3

**Audited SHA:** `e932a36`. Scope: **test-only** — `git diff 73dbcce e932a36` touches **zero**
files under `backend/app/`, `docker-compose.yml` or `content/`, confirmed by pathspec. (The
hand-off says "1 file"; it is two test files, the second being DEF122's rationale correction
arriving via `main`. Immaterial.) Isolated worktree `.claude/worktrees/audit-CR098-r3/`, own venv.
**Full suite 1366 passed** in 221s on a verified-clean tree, run to completion before any mutation
touched the tree (round 2 was 1365; `+1` = exactly the new test).

Done by the Architect rather than a worker round, because the finding was against **their own**
merge resolution.

### The MAJOR is closed — verified with my own probe plus two shapes they did not use

`test_run_wiring_passes_withheld_into_profile_for_ticker` drives the real `run()` with a
Market-withheld roster and asserts three independent things: `compute_technicals` never executes,
the kwargs actually reaching `_profile_for_ticker` carry `frozenset({MARKET_ANALYST})`, and the
resulting profile is marked `withheld_tenure`. The spy closes over the real `_profile_for_ticker`
**before** monkeypatching, so it exercises the genuine code path rather than a stub, and
`assert seen, "run() never reached _profile_for_ticker"` closes the obvious vacuity hole.

| Probe | Shape | Result |
|---|---|---|
| **P1** | my exact round-2 regression — drop `withheld=frozenset(roster.withheld)` from the hoisted `to_thread` call | **RED**, and **only** that test (24 others pass) — the Architect's claim reproduces exactly |
| **P2** | kwarg **present but wrong value** — `withheld=frozenset()` | **RED** — sensitive to the value, not merely to the argument's presence |
| **P3** | kwarg forwarded correctly, but the gate **inside** `_profile_for_ticker` broken | **RED** in the new test *and* in the pre-existing direct-call test — sensitive to the behaviour, not just the plumbing |

P2 and P3 are the checks that matter for a test written to close a wiring finding: P2 rules out a
test that only asserts "an argument was passed", P3 rules out one that only asserts "the plumbing
is connected". It fails for the right reasons in all three directions.

### No regression in round 2's coverage

The round-3 test-file diff has **zero deletion lines** — purely additive — so round 2's coverage is
untouched by construction. Confirmed by execution anyway, given this lane's history: re-ran round
2's MAJOR 2a mutation (`phase_agents = phase.agents`) → still **RED**. DEF116's AST guard is still
**green** on this SHA, so the other half of the merge hazard remains pinned.

### My out-of-lane DEF122 finding — accepted and fixed on `main` (`638bdfc`), verified

Read the correction. `_KNOWN_SYNC_HTTPX_COUNTS` now splits the two entries: RevenueCat keeps the
threadpool reason, and `room_runner.py` gets the real one — the call **is** on the event loop
(`main.py:132` awaits `resume_pending_retries()` inside `async def lifespan`), safe only because it
fires at most once per process at lifespan startup before uvicorn serves traffic, guarded by
`_PREFIX_CACHE_STATUS_LOGGED`. It also carries the part that actually prevents recurrence: *"A
SECOND httpx call in this module would NOT inherit that reasoning."* Matches what I measured.

### Not verified — unchanged, and correctly disclosed

- **Acceptance #14 live smoke** — untestable from a pure-editor Mac. Post-promote.
- **DEF098 parity blind spot** — out of scope; still needs an Architect decision on whether a
  withheld analyst counts as a declared omission for a degraded `FLOOR_PASS`.
- **The mobile half is unbuilt** — `CR098-MOBILE-LIVE` / `CR098-MOBILE-VERDICT` written and
  `UNASSIGNED`, held on this verdict. Until they land, the per-analyst locked chair and countdown
  reach the wire but nothing renders them. **Promotion-sequencing note, not a code defect:** the
  same coupling I recorded for CR090-ROOM applies — the backend disclosure has no client surface
  until the mobile lanes ship.

### Findings

None.

### Verdict

**VERDICT: COMPLETE (round 3)** — zero BLOCKER, zero MAJOR, zero MINOR.

Three rounds, eight findings, all closed and every one re-proved with my own mutations rather than
the hand-off's. The lane ends stronger than it started: the seam three lanes collided on is now
pinned from **both** directions — DEF116's AST guard for the `to_thread` hoist, this test for the
`withheld=` kwarg — and the defining behaviour (a withheld analyst does not speak, and each present
analyst's text lands under its own id) is guarded by a test sharper than the one I specified.

Run report: [`../runs/2026-07-27_run-68/run_report.md`](../runs/2026-07-27_run-68/run_report.md)
