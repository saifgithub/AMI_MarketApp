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
DISPATCH: OPEN
