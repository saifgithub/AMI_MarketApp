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
