<!--
CR098-ROOM.architect.md — architect/coder submission lane (track R owns).
State derives from round numbers here vs CR098-ROOM.auditor.md (see PROTOCOL.md).
-->

# CR098-ROOM — audit lane (Room analyst pullback: mechanism + FOMO surface, backend)

SUBMITTED: round 1

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
