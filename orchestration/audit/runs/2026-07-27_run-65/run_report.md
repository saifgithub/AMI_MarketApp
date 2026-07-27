<!--
Auditor run report — run-65 (2026-07-27, session auditor.core/track U). Round-1
audit of CR098-ROOM. Audited SHA 908119d on lane/CR098-ROOM.coder.room. Verdict
AWAITING_FIXES round 2 — two MAJOR. Owner: AUDITOR.
-->

# run-65 (round 1) — CR098-ROOM analyst pull-back → AWAITING_FIXES

- **Auditor session:** auditor.core (track U), 2026-07-27.
- **Audited SHA:** `908119d`, off `main` @ `2f22a7e`. Isolated worktree
  `.claude/worktrees/audit-CR098-ROOM/`, own venv.
- **Provenance:** two budget deaths, both workers failed well (incremental commits, honest gap
  lists); round 2 caught a real acceptance-#13 violation in round 1's branch (`"(upgrade to
  include the X Analyst)"` spliced into every agent's rendered prompt). The Architect committed
  round 2's uncommitted hand-off as found, closed the verification gaps, and submitted. No
  production code changed after round 2.
- **The item:** withhold Room analysts on plan + account tenure, disclose it honestly, strip any
  synthetic stand-in for the withheld domain from the rendered prompt, and terminate in
  `NO_VERDICT` when Market is withheld. Fundamentals unwithholdable.
- **Gate:** independent — changes what a user is charged (D2), adds a `VerdictAction` on the
  safety-adjacent PM verdict path, adds a 4th `LiveDataState`.

## Reproduced independently

Scope `git diff 2f22a7e 908119d --stat` → 15 files, **+1224/−38**, exact match. Full suite
`./backend/.venv/bin/python -m pytest backend/tests/unit/ -q` → **1359 passed** in 201s, exactly
the Architect's re-measured figure (1338 baseline + 21). Compose parity: all three
`ROOM_PULLBACK_DAYS_*` forwarded in `docker-compose.yml`'s `api-alpha` block; `field_validator`
already imported at `config.py:6`, so the boot-fail validator is live.

## What holds — mutation-tested rather than read

Each mutation reverted individually; the CR098 file re-confirmed 21/21 green after each.

| Probe | Result |
|---|---|
| Fundamentals made withholdable (added to `_WITHHOLDABLE_ORDER` + a threshold + dropped the unconditional prepend) | **3 tests red** — the code-not-config guarantee is genuinely structural |
| `n_available` counts a `WITHHELD_TENURE` feed (the D2 money path) | **1 test red** — `test_aged_floor_pass_social_withheld_debited_strictly_less` |
| Roster-withhold routed through `WITHHELD_PAID` (the D3 inversion the assign exists to prevent) | **2 tests red** |
| `threshold >= 1` dropped — 0 stops meaning "never" | **1 test red** — but not the test that should have caught it (MINOR 2) |

Confirmed by reading the real source, not the hand-off:

- **#10 is structural, not prompt-dependent.** The `if AgentId.MARKET_ANALYST in ctx.withheld:`
  branch is **first** in the VERDICT if/elif/else, so `_stream_pm_response`, `_parse_pm_verdict`
  and `enforce_safety_floor` are all bypassed — there is no code path from a withheld-Market run
  to a parsed LLM verdict at all. `_WellFormedApproveGateway.pm_called is False` proves it by
  execution, and the gateway returns a syntactically perfect APPROVE block that would parse.
- **#8's insertion point** sits after the whole if/elif/else, so `opinions_not_included` is stamped
  on all four verdict paths (NO_VERDICT / APPROVE / PASS / fail-safe) — the comment's claim checks
  out against the indentation.
- **D3 carries through with no inversion.** `_final_state` (`room_runner.py:1575`) maps only
  `LIVE → WITHHELD_PAID` when unentitled; `WITHHELD_TENURE` passes through untouched.
- **D4 symmetry preserved in the strongest possible way — by non-modification.** CR098 gates
  News/Social *upstream* in `_resolve_and_charge_feeds`; `_profile_for_ticker`'s news/social
  branches are untouched, and `profile["news_state"]`/`["social_state"]` are set unconditionally
  from the feed (`room_runner.py:466,492`), so `WITHHELD_TENURE` flows through automatically.
  Proved the pre-existing patch-based tests are **not** vacuous: disabling the social overlay
  turned `test_profile_overlays_live_sentiment_when_enabled` red — the exact test CR090's
  asymmetry silently voided — plus two `test_prompt_data_parity` cases.
- **#6 asserts on rendered output**, as the criterion demands. The tests poison the profile with
  `"SHOULD NOT APPEAR"` and `rsi: 999` and assert against `_format_profile`'s returned string,
  not fetch counts.
- **Fetch gating (#5)** is pinned by three tests that monkeypatch the provider to a function that
  *raises* — the strongest available shape.

## MAJOR 1 — `agent_withheld` never reaches the wire

`backend/app/api/room.py`'s SSE dispatcher is an explicit if/elif over exactly seven event kinds —
`started`, `live_data_notice`, `phase`, `agent_token`, `agent_done`, `verdict`, `error` — with
**no `agent_withheld` branch and no `else`**. The event emitted at `room_runner.py:1988` is
silently dropped at the API boundary and never becomes an SSE frame.

Grep across the whole worktree: `agent_withheld` appears in exactly three places in backend
source — the `RoomEvent.kind` docstring, the field comment, and the emission site — **all inside
`room_runner.py`**, and zero times anywhere under `app/api/`.

The three `RoomEvent` fields added expressly for the client countdown (`reason`,
`next_step_agent`, `next_step_days`) are therefore unreachable from outside the process, and the
entire FOMO surface has no wire format.

**This corrects the hand-off's framing of the question it asked me to judge.** It states that
CR090-MOBILE's switch has a logging `default:` "so it will not crash on the unknown value — it
will render nothing," and asks whether that is the dark-feature class. That framing presumes the
value reaches the client. It does not. Scope item 8 is not merely unlaned — when it is laned it
will have nothing to consume. CR090's own `live_data_notice` **is** wired in this same file
(`room.py:225`), so the pattern was established one CR earlier and one branch was missed here.

Partial mitigation, verified: the closing disclosure does survive — `Verdict.opinions_not_included`
rides `ev.verdict.model_dump_json()` on the `verdict` event, so the verdict-level disclosure
reaches the client. The per-analyst locked chair and the countdown do not.

This is the DEF038 / DEF063 / CR100 shipped-but-dark class, and it sits inside this lane's own
backend scope (item 3, "phase-loop filter + `agent_withheld` event"), not the out-of-scope mobile
half. The fix is one `elif` branch.

## MAJOR 2 — nothing tests the defining behaviour: that a withheld analyst does not run

Two mutations, each run against the **full** suite rather than just the CR098 file:

| Mutation | Full suite |
|---|---|
| `phase_agents = tuple(a for a in phase.agents if a not in ctx.withheld)` → `phase_agents = phase.agents` — the withheld analyst **speaks anyway** | **1359 passed** |
| `zip(phase_agents, results)` → `zip(phase.agents, results)` — each analyst's text attributed to the **wrong agent** | **1359 passed** |

Neither is detected anywhere.

The first produces directly self-contradicting output: the run emits `agent_withheld` for an
analyst that then speaks in the transcript and is listed in `opinions_not_included`, while the
operator is billed for its decode. The second is silent misattribution — Fundamentals' text under
the Market label and so on, with a three-element `results` truncating a four-element `zip`.

All 21 new tests assert *around* the mechanism — the fetch is skipped, the event is emitted, the
verdict lists it, the fact sheet strips the lines — and **none asserts the withheld analyst's
voice is absent from the transcript**. That is the CR's defining behaviour.

The exposure is not hypothetical. `phase_agents` has three separate uses (the `asyncio.gather`
comprehension, the emit-order `zip`, and the sequential loop), sitting inside CR077's
parallel/sequential branch split, and this exact seam is about to be rebased under DEF116. A merge
that drops any one of the three restores full-roster behaviour — or misattribution — with a fully
green suite.

Fix is small: assert that no `agent_token`/`agent_done` event carries a withheld `agent_id`, and
that each analyst's text lands under its own id.

## MINOR 1 — the respawn path resolves the roster but not the feeds

`_respawn_run_from_row` (a production path — `resume_pending_retries` is wired at `main.py:132`)
calls `self.run()` with no `roster`, `news_feed` or `social_feed`. `run()` resolves the roster
fresh, so analysts *are* filtered and `NO_VERDICT` can fire — but the feed fallback
(`room_runner.py:1843-1853`) resolves news/social at `entitled=True` **ungated by that roster**.

Consequence on a respawned run for a pulled-back user: the withheld News/Social analyst's real
data is fetched (the API call the roster gate exists to bank) and renders in full in the fact
sheet, and `live_data_notice` reports `news: "live"` for an analyst that was withheld. Market is
gated correctly on that same path because `_profile_for_ticker` reads `withheld` directly — so the
path is internally asymmetric, which is the D4 concern one layer up.

Zero users affected today (thresholds ship at 0). Fix: gate the two fallbacks the same way
`_resolve_and_charge_feeds` already does.

*Checked and cleared while here:* `credit_cost=None` on this same path is guarded at
`room_runner.py:1807` (`credit_cost if credit_cost is not None else room_cost_for_plan(plan)`), so
the `surcharge_charged` subtraction at :1854 cannot see a `None`.

## MINOR 2 — acceptance #2's own test does not test acceptance #2

The hand-off asks: *"Judge whether the practical form is actually equivalent to the byte-identical
claim the criterion makes."* **It is not, and it is weaker in exactly the dimension the criterion
names.**

`test_default_roster_is_full_no_op` runs `run()` with `user_id=uuid4()` — a **nonexistent** user,
which takes `resolve_roster_for_user`'s missing-row full-roster fallback. It therefore never
exercises the real no-op case (an aged `FLOOR_PASS` user with all three thresholds at 0), never
captures a transcript, and never compares against a pre-CR098 baseline.

Measured: the realistic off-by-one that breaks the guarantee — `threshold >= 1 and
account_age_days >= threshold` → `account_age_days >= threshold`, turning 0 from *never* into
*always* — is caught **only** by `test_aged_floor_pass_social_withheld_debited_strictly_less`, the
D2 **money** test (`assert 10 == 12`). The acceptance D5 called "the acceptance that matters most"
survives incidentally, through a test written for something else.

Separately worth stating plainly: strict byte-identity was never achievable, because acceptance #8
adds `opinions_not_included` to every serialized `Verdict`. The two criteria are in tension and #2
can only mean "same transcript text, same decision content." That is a defensible reading — but it
should be the *stated* one, and the test should exercise the aged-user path.

## MINOR 3 — the fact-sheet disclosure header still describes stripped fields

Rendered a Market-withheld profile directly. The block still carries *"RSI, trend, volume,
support/breakout: alpha simulation scaffolding — NOT computed from real price history"* in the
header, immediately above *"Market technicals: not included in this session."* Same shape for
Social. Low impact — prompt copy, not user copy, and nothing fabricated — but it is contradictory
text fed to every agent, and CR038's own finding is that inconsistent prompt copy degrades
compliance.

## FLAGS

1. **D6 integration hazard — measured, and worse-shaped than D6 describes.** Trial-merged DEF116
   (`d68a028`) into this SHA. Git **auto-merged DEF116's hoisted call without CR098's `withheld=`
   kwarg** — no conflict marker there at all — and raised a conflict *only* inside the
   `_RoomContext(...)` kwargs:
   ```
   1904:  profile = await asyncio.to_thread(
   1905:      _profile_for_ticker, ticker, news_feed=news_feed, social_feed=social_feed
   1906:  )
   ...
   1921: <<<<<<< HEAD
   1924:      profile=_profile_for_ticker(ticker, …, withheld=frozenset(roster.withheld)),
   1928: =======
   1929:      profile=profile,
   1930: >>>>>>> d68a028
   ```
   Taking HEAD re-opens the blocking call — DEF116's AST guard catches that, exactly as D6 says.
   Taking DEF116's side silently **drops `withheld=`**, disabling the Market fact-sheet strip — and
   that direction is caught by **nothing**, because CR098's tests call `_profile_for_ticker` and
   `_format_profile` directly rather than through `run()`. D6 only warns about one of the two
   directions. Correct resolution:
   ```python
   profile = await asyncio.to_thread(
       _profile_for_ticker, ticker, news_feed=news_feed, social_feed=social_feed,
       withheld=frozenset(roster.withheld),
   )
   ```
2. **DEF098 parity blind spot — measured, confirming the coder's flag.** With Market withheld the
   synthetic `rsi` is still *produced* in the profile dict (58 in my probe) and no longer
   *rendered*. DEF098's "every produced field is rendered or declared" guard would flag that if it
   ever ran against a withheld profile; no test constructs one. Real, quantified, correctly left
   untouched by this lane.
3. **The fixed-copy `NO_VERDICT` simplification — no pushback, I agree.** Structural beats
   prompt-dependent (CR038's ~70% instruction non-compliance) and it satisfies #10/#11 by
   construction. The honest cost — identical wording every time — is acceptable for a rare wall
   state, and the alternative reintroduces exactly the prompt-dependence the project has already
   measured as unreliable.
4. **Trader + the 3 Risk debators still burn ~25s producing nothing actionable** at the NO_VERDICT
   step. Built per the spec's own recommendation. Saiful's call, Phase C.

## Not verified

- **Acceptance #14 live smoke** — untestable from a pure-editor Mac. Post-promote check.
- **Not merged onto current `main`** — I measured only the DEF116 seam (FLAG 1), not a full
  integration merge.

## Findings

1. **MAJOR** — `agent_withheld` is emitted by the runner but has no branch in `room.py`'s SSE
   dispatcher (7 kinds, no `else`), so it never reaches the wire; the countdown fields are
   unreachable from outside the process. Shipped-dark, DEF038/DEF063/CR100 class, inside this
   lane's backend scope. One `elif` fixes it.
2. **MAJOR** — no test asserts a withheld analyst is absent from the transcript. Removing the
   phase filter, and mismatching the emit-order `zip`, each leave the **full suite at 1359
   passed**. The defining behaviour of the CR is unguarded at the seam most likely to be disturbed
   by the imminent DEF116 rebase.
3. **MINOR** — the production respawn path resolves the roster but leaves the News/Social feed
   fallback ungated by it; withheld data is fetched and rendered, and `live_data_notice` reports
   `live` for a withheld analyst.
4. **MINOR** — acceptance #2's test uses a nonexistent user and never exercises the real no-op
   path; the guarantee is held only incidentally by the D2 money test.
5. **MINOR** — the fact-sheet disclosure header still describes fields the withhold stripped.

## Verdict

**VERDICT: AWAITING_FIXES (round 1)** — two MAJOR, three MINOR. (Round 1 is the round *audited*,
per `PROTOCOL.md`'s amended rule — the architect bumps to `SUBMITTED: round 2`.)

The mechanism itself is well built and I tried hard to break it. The resolver, the money path, the
fourth `LiveDataState`, the `NO_VERDICT` short-circuit and the fact-sheet stripping all survive
mutation; D4's symmetry is preserved in the strongest possible way (by not touching the seam), and
I confirmed the previously-voided patch-based test is genuinely live again. Both MAJORs are about
the edges rather than the core: the disclosure that never leaves the process, and the one
behaviour the test file walks all the way around without ever asserting. Both fixes are small and
confined.
