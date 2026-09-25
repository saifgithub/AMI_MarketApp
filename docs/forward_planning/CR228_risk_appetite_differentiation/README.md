# CR228 — Risk appetite produces no behavioural differentiation

**Filed:** 2026-09-22 · **Status:** in progress (Step 1 pilot running)

## Why

Users on the Day Trader preset report they cannot get a ticket APPROVED. Saiful's
reframing, 2026-09-22:

> *"i am at this point wondering if the risk appetite setting, along with all the
> other settings, are too narrow and may need to be widen to allow for real
> differentiated responses."*

And the target:

> *"In the end, I expect that we will be recommending more when the risk appetite
> is higher. And at the highest risk appetite, we should recommend even more than
> the market. So the risk appetite spread should really be reflected. And the
> calculation of the risk appetite should be based on all the parameters in the app."*

## What the code already proves (no measurement needed)

**`risk_score` is a sizing dial, not an approval dial.**

1. `DEFAULT_RISK_TIER_CAPS = {1: 1.5, 2: 1.5, 3: 3.0, 4: 4.5, 5: 4.5}`
   (`trading_math/sizing.py:22`). **Risk 1 ≡ 2, risk 4 ≡ 5** — five slider
   positions, three distinct caps. The UI (`app_en.arb:1792-1796`) promises five
   personalities the enforcement layer cannot deliver.
2. **The gatekeeper has no risk branch.** `_portfolio_manager_block`
   (`agents/overlay_generator.py:883`) is a plain f-string. Its only mention of
   risk appetite is `- Consider risk_score={m.risk_score} and current drawdown`
   (:900) — a bare number with **no stated direction**. Every other agent has a
   risk branch (:560, :621, :688, :827, :855); the one agent that decides
   APPROVE/PASS never got one.
3. **Risk appetite uses 3 of 7 interview answers.** `_derive_risk_score`
   (`services/concierge_engine.py:455`) reads only `drawdown_response`,
   `regret_asymmetry`, `concentration_tolerance`. Dropped: `horizon`,
   `primary_goal`, `compliance`, and — most sharply — `max_drawdown_pct`, where
   **the causality runs backwards**: `q6_text` (:99) uses risk_score to *suggest* a
   drawdown, and the user's actual answer never feeds back. A user offered 50% who
   picks 10% is saying the score is wrong, and nothing listens.
4. `risk_quotes` — the three verbatim sentences the user gave about losing money —
   is written, hydrated, journal-diffed, and read by **zero prompts**. It is
   user-editable in Settings (CR220) and reaches nothing.

## The finding that reframes the fix

CR197 ablated the risk debate over 136 convenes
(`CR197_risk_debate_effectiveness/REPORT.md:172-179`):

> "The debate's function is **option generation**, not persuasion. It hands the PM
> a middle-sized alternative it does not construct on its own; without it the PM
> sees only the Trader's raw take-it-or-leave-it proposal, and leaves it."

Same ticker, same eleven upstream turns: *with* debate → APPROVE at 1.5%
("down-sizing the Trader's 3.0% proposal"); *without* → PASS ("1:1 is insufficient
for a 3/5 risk score").

**The Room does not PASS because it is frightened. It PASSes because it has nothing
to approve except one number.** Widening the cap table is therefore not only a
differentiation fix — it is the option-generation fix, which is why it goes first.

Corroborating, already built and switched OFF: `pm_option_ladder_enabled`
(`core/config.py:802`) hands the CIO a trim/reference/press ladder. Measured
16.3% → 21.1% approve (+4.8pp) over the same 136 convenes.

## Baseline contamination — why the pilot segments

`core/config.py:138` records ~7% of PM calls being **killed** at the old 90s
timeout, each degrading to a DEF059 fail-safe PASS. The timeout is now 180s
(deployed: verified `ROOM_AGENT_TIMEOUT_S=180.0` on `ami_api_alpha`, 2026-09-22).
So the 26.5% live figure (CR214, 2026-09-01) is partly infrastructure, not
judgement. The pilot must exclude `overridden_from_llm=true` and null
`approve_votes` or a later "improvement" will partly be the timeout fix.

DEF230's standing rule also applies: **do not pool.** Its pooled number misled
twice (benchmark contamination, then tier-mix shift).

## Step 1 result (2026-09-22 → 2026-09-23)

**The pilot's own prediction was wrong, and the reason matters more than the
number.** Predicted: no significant approve-rate difference, size differs. Measured:

| | R1 | R5 | delta |
|---|---|---|---|
| approve rate (n=29, FAILSAFE excluded) | 3.4% (1/29) | 24.1% (7/29) | **+20.7pp** |
| mean `approve_votes` (0–5) | 0.31 | 1.24 | **+0.93** |
| mean `size_pct` on APPROVE | 1.00% | 4.50% | +3.50pp |

McNemar exact on the 6 discordant pairs (JPM, MO, PYPL, T, V, WFC — all
PASS→APPROVE, zero the other direction): **p=0.031**. Significant at n=29.
Full data: `results/runs_cr228-r{1,5}-20260922.jsonl`,
`results/pilot_scored_2026-09-22.txt`.

**Why this happened despite the PM prompt being unchanged (verified: 987 chars,
one digit different — `Consider risk_score={1|5}`).** The mechanism is CR197's
option-generation finding operating through the cap table, not through the PM's
judgement changing. The Trader is sized at `min(50%, resolved_single_name_cap_pct)`
per agent — at R1 every proposal is compressed toward ~1.5%, and the risk debate's
Aggressive/Conservative/Neutral rungs (`aggressive=trader_size+2`,
`conservative=trader_size-1.5`) collapse into a narrow band around it. At R5 the
same debate spreads across a genuinely wider band up to 4.5%. The PM is not
approving more because it was told to be bolder — **it is approving more because
R5 handed it a bigger, more separated menu of sizes to choose from.** This is the
same lever CR197 measured (16.3% → 7.4% when the debate was removed), now shown to
fire across the risk_score axis too, with no prompt change at all.

Six of six flips ran in the predicted direction and zero against it — before any
of the planned Step 2–4 changes. That is a stronger and cheaper result than the
pilot was designed to produce: **the existing cap-table spread is already doing
part of the job Saiful asked for**, just far too narrow (1.5% → 4.5%, both well
under any Street-beating threshold) and with no signal reaching the one agent that
decides APPROVE/PASS.

**What this does NOT show:** whether the sizing-driven effect is the same
mechanism a direct approval-propensity lever (Step 3/4) would add, or whether the
two stack. n=29 pairs is not enough to rule out a ceiling effect. Both R1 (3.4%)
and R5 (24.1%) remain far below the Street's 60.0% on this exact 30-ticker sample
— so "risk-5 beats the Street" is not remotely reached by the cap-table effect
alone; Steps 2–4 are still the plan, not optional polish.

**Revise the Step 2 framing:** widening the cap table is not just the
option-generation fix reasoned about in the CR — it is now the *measured*
differentiation fix. Steps 3–4 (PM prompt branch, graded vote threshold) should
be scoped and measured as an *addition on top of* this baseline, not as the first
source of any spread, since this pilot shows the spread already exists without
them.

## Step 1 — the pilot (as designed, for the record)

**Question:** how large is the R1→R5 difference today, with fail-safe PASSes
excluded?

**Design:** 2 arms × 30 tickers = 60 convenes, ~3.5h serial.

| arm | batch-id | risk_score | everything else |
|---|---|---|---|
| A | `cr228-r1-<date>` | 1 | identical |
| B | `cr228-r5-<date>` | 5 | identical |

- Harness: `backend/scripts/room_benchmark.py`, unchanged. `--mandate-json` +
  `--fresh-user` already exist.
- **`--fresh-user` is mandatory**: `resolve_mandate` (`services/mandate_store.py:292`)
  **ignores `mandate_override` when the user has a stored mandate**. Without it both
  arms would silently run the same mandate.
- Same 30 tickers both arms ⇒ paired comparison, ticker difficulty cancels.
- Primary outcome: **mean `approve_votes` (0–5)**, not APPROVE/PASS. CR214 measured
  the binary verdict as a ~12–20% coin flip (three byte-identical replays of 136
  convenes disagreed on 26 of 132); the graded score is why `approve_votes` exists
  (`schemas/room.py:99-108`). Secondary: approve rate, and mean `size_pct` — which
  *should* differ (1.5% vs 4.5% cap) even if approval does not.
- Plan pinned to `trader` both arms: `tier_policy.pick_tier` selects models by plan.
- `pm_option_ladder_enabled=false` both arms (verified deployed).

**Expected result: no significant difference in approve rate, a clear difference in
size.** That is the null this step exists to put on record — it is the before-number
every later claim is measured against, and without it any improvement is
unfalsifiable (`feedback_no_extrapolated_numbers`).

**Universe:** `tickers_30.txt` — proportional stratified draw (seed 2026) from the
142-name pool (`tickers_150.txt` minus the 8 DEF335 split names). Strata: sell 2
(the entire pool) / hold 10 / buy 14 / strong_buy 4. Street Buy-or-better: **18/30 =
60.0%** vs pool 63.4%. Per-ticker Street ground truth: `CR035_room_benchmark/results/consensus.jsonl`.

**Live-Alpha safety:** the mandate is a per-run input, so this does NOT have CR035
arms-B/C's problem (those flipped container env vars and degraded live Alpha while
open). Nothing global is changed. Cost: 8 credits/convene on the benchmark users,
granted on 402.

## Steps 2–4 (sequencing set by Saiful, 2026-09-22)

2. **Widen the cap table** — five distinct values, and widen `_derive_risk_score`
   to take `max_drawdown_pct`, `horizon`, `primary_goal`. Also the CR197
   option-generation fix.
3. **Prompt** — give `_portfolio_manager_block` the risk branch it never had.
   Per CLAUDE.md, prompt instructions are not controls: measure, don't assume.
4. **Structural** — graded `approve_votes` threshold by risk tier. Guarantees
   monotonicity regardless of model compliance, and fixes the tie-breaks-to-PASS
   asymmetry (`room_runner.py:6634`).

### Step 2 done (2026-09-23)

**`DEFAULT_RISK_TIER_CAPS`** (`trading_math/sizing.py:22`) widened from
`{1: 1.5, 2: 1.5, 3: 3.0, 4: 4.5, 5: 4.5}` (3 distinct values) to
`{1: 1.0, 2: 2.0, 3: 3.0, 4: 4.0, 5: 5.0}` (5 distinct, evenly spaced).
Ceiling capped at 5.0, not higher: `DEFAULT_MAX_OPEN_RISK_FRACTION_OF_DRAWDOWN`
(`risk_limits.py`, left unchanged) couples the single-name cap to
`DIVERSIFICATION_FLOOR`'s "≥30 names reachable" invariant
(`test_cr129_risk_limits_from_risk_tolerance.py`) — 5.1+ at tier 5 breaks it.
The four sibling `risk_limits.py` tables (max_open_positions,
post_loss_cooldown, trades/day, trades/week) were **not** touched — the pilot
implicated the single-name cap specifically (via CR197's option-generation
mechanism), and there's no measurement yet that the others gate approvals the
same way. `DEFAULT_CONCENTRATION_TOLERANCE_CAPS` already had 5 distinct values
(25–60pp) and didn't need widening.

**`_derive_risk_score`** (`services/concierge_engine.py:456`) now nudges the
Q3-Q5 scenario base (still dominant — bounded at ±0.5 per input, ÷ by however
many of the three are present) with `max_drawdown_pct`, `horizon`, and
`primary_goal`. Fixes the backwards-causality gap: `q6_text`'s *suggestion* is
still scenario-only (session.answers has no `max_drawdown_pct` yet — Q6 IS
that question), but the **readback** score (after Q6+Q7 are answered) now
reads the user's actual drawdown answer, not just what was suggested to them.
`compliance` (Q7) was explicitly NOT included, per Saiful's selection.

Not yet re-measured against the pilot's 30-ticker sample — the code-level
change is in place and unit-tested (`test_concierge_engine.py`,
`test_trading_math.py`, `test_cr129_risk_limits_from_risk_tolerance.py`); a
follow-up pilot-shaped run is what Step 2's acceptance actually needs before
calling the spread claim measured rather than reasoned.

**Audit round 1 (2026-09-23) — 1 MAJOR fixed, 2 MINOR fixed.** The
independent audit caught a real defect the submission itself didn't
mention: an early version of `_derive_risk_score` changed the ORDER of the
scenario base's rounding — `round((a+c)/2) + asym` became
`round((a+c)/2 + asym)` — alongside adding the three nudges. That silently
moved the scenario-only score (zero nudge inputs present) for 10 of 45
reachable `(drawdown_response, regret_asymmetry, concentration_tolerance)`
combinations, including a loss-averse user's enforced single-name cap
rising 1.5%→2.0% — the wrong direction for a change whose whole point is
tighter differentiation. **Fixed by restoring the pre-CR228 rounding order**
(`round((a+c)/2) + asym`) and applying the bounded nudges strictly on top of
that unchanged base, matching what Change 2 was always described as doing.
Pinned with a 45-row table test
(`test_cr228_scenario_only_base_matches_the_pre_widening_rounding_order`)
so this can't silently drift again. Also fixed: a vacuous test assertion in
`test_cr228_q6_suggestion_uses_scenario_only_base` (the disjunct
`"sounds like a fit" in x` was unconditionally true for every risk_score,
so the test could not fail) and no drift guard on the three nudge lookup
tables against their source enums/vocabulary — both closed, detail in
`orchestration/audit/cr/CR228.auditor.md` round 1 and
`CR228.architect.md` round 2.

**Audit round 2 (2026-09-23) — 1 MAJOR (fixing round 1's own fix) fixed.**
Fixing MAJOR-1's rounding order made the base an integer, and the
pre-existing `/2` nudge damping — tuned against round 1's half-integer base
— became too weak to ever cross an integer's rounding boundary once all
three inputs are present (the realistic case: Q1/Q2 are always answered by
Q6/readback time). Measured: **0 of 45 reachable scenario bases could have
their score moved by Q6's drawdown answer at neutral Q1/Q2, down from 16/45
at round 1** — the CR's own headline case (README's own words: *"A user
offered 50% who picks 10% is saying the score is wrong, and nothing
listens"*) silently reintroduced by fixing a different bug, and invisible
to the existing readback test because its Q2 fixture ("10+ years") was
itself carrying the movement. **Fixed by dropping the `/2`** — nudges are
now averaged but not halved, restoring 43/45 reachable-base coverage while
the dominance property still holds at both extremes (verified: a
maximally-conservative scenario base against the most aggressive possible
nudge still clamps to 1, and the reverse to 5). Pinned with the CR's own
sentence as a test (`test_cr228_offered_50_picks_10_the_scores_moves`) and
the existing readback test's Q2 fixture corrected to a genuinely neutral
value so it tests what its docstring claims. Detail:
`orchestration/audit/cr/CR228.auditor.md` round 2,
`CR228.architect.md` round 3.

### Step 3 done (2026-09-23)

**`_portfolio_manager_block`** (`agents/overlay_generator.py:920`) — the ONE agent that
decides APPROVE/PASS — gets a directional risk branch via the new
`_pm_risk_appetite_line` helper, following the same `risk_score<=2` / `>=4` / else
pattern already used by every other agent (analysts at :560/:621/:688, the risk
debators at :827/:855). Before this, the PM's only mention of risk_score was `Consider
risk_score={n} and current drawdown` — a bare number with **no stated direction**
(verified in Step 1's pilot: byte-identical 987-char PM prompts across risk tiers,
differing only in that one digit).

The new line, inserted inside DECISION SEQUENCE step 3 (after the compliance-check
gate, never touching it):

- risk_score ≤2: *"the debate needs a genuinely clean case before you APPROVE... Do
  not read 'thorough debate happened' as a reason to approve on its own."*
- risk_score ≥4: *"they have told AMI they can sit through more drawdown to pursue
  more upside... Weigh the debate on its merits, not against a caution calibrated to
  a more conservative user."*
- risk_score 3: unchanged framing, no lean either way.

Per CLAUDE.md ("prompt instructions are not controls"), **this is a hypothesis, not an
assumed fix** — Step 1's pilot already showed Step 2's cap-table widening produces a
real approve-rate spread through sizing alone, with the PM prompt held byte-identical.
This line is additive on top of that mechanism, not a replacement for it, and per
CR197/CR199's own precedent needs an ablation-style measurement (not just "it reads
plausibly") before it's credited with any effect. The compliance-check sequence,
APPROVE/PASS-only vocabulary, and UNCOACHABLE boundary text are all unchanged and
pinned by a new test (`test_cr228_pm_risk_branch_does_not_touch_the_uncoachable_boundary`).

Not yet measured. Steps 2 and 3 are both in place; a follow-up pilot-shaped run (same
30 tickers, `score_pilot.py`) is what would show whether Step 3 adds anything on top
of Step 2's already-measured spread, or whether the sizing mechanism was already doing
all of the work — the question CR228's Step 1 result explicitly left open.

### Step 4 done (2026-09-23)

**`_vote_pm_samples`** (`services/room_runner.py:6640`) — the mechanical CR197
aggregator over `pm_self_consistency_samples` independent CIO reads — gets a new
`_approve_vote_threshold(risk_score, n)` helper and a `risk_score` parameter
(default 3, so every pre-CR228 caller is unaffected). Before this, APPROVE needed a
flat strict majority regardless of the mandate's risk appetite, and any tie fell to
PASS uniformly (`room_runner.py:6634` in the original plan doc's line numbering) —
the exact "structural bias toward not trading that no risk setting adjusts" the plan
named. Now the bar itself is graded:

- risk_score ≤2: majority **+1** — needs a clean super-majority, not just more
  APPROVEs than PASSes.
- risk_score 3: unchanged — `n // 2 + 1`, i.e. the original strict-majority,
  tie-to-PASS arithmetic, byte-for-byte.
- risk_score ≥4: majority **−1** — one vote short of a majority is enough, directly
  fixing the tie-breaks-to-PASS asymmetry for a user who told AMI they can sit
  through more drawdown. At odd n (the production default is 5) this is a genuine
  minority — 2 APPROVE vs 3 PASS wins at n=5 — not merely a tie, and the CR040
  split-disclosure (`room_runner.py:~5584`) says so in the verdict the user reads:
  *"Your team was split on this — 2/5 of the independent reads landed here."*

At the production default of 5 samples (`Settings().pm_self_consistency_samples`,
CR214): conservative needs 4/5, neutral needs 3/5, aggressive needs 2/5 — three
distinct, monotonic bars, verified never to collapse to the same number at that n
(`test_at_the_production_default_of_five_samples_the_three_tiers_are_distinct`).
The call site (`room_runner.py:~5533`) passes `ctx.mandate.risk_score` — the same
mandate the run is for, not a hardcoded neutral value.

Unlike Step 3, this is **structural, not a prompt hope** — it holds regardless of
how well any model complies with Step 3's new PM prompt line, because it's the
vote-counting arithmetic itself. Pinned in
`tests/unit/test_cr228_graded_vote_threshold.py` (10 tests: the threshold table
across risk_score × n, monotonicity, the tie-break-asymmetry fix at n=5 and n=4,
unanimous votes at every tier, and an AST-source pin that the call site wires the
mandate's own risk_score). Mutation-tested: reverting the grading (bar flattened to
the plain majority for every risk_score) fails exactly the 4 tests that assert
tier-dependent behaviour and none of the tier-independent ones, as expected.

Not yet measured against the pilot. All of Steps 2–4 are now in place; the
follow-up pilot-shaped run (same 30 tickers) is what would show the combined
effect, and whether Step 4 changes the *measured* spread at all given it only
engages once `pm_self_consistency_samples > 1` (production default 5).

## Open question for Saiful

The Street's 64% Buy rate is a **biased** baseline (sell-side Buy skew;
`docs/Research/benchmark/claude/02_sellside_analysts.md`). The levers above can hit
any number named, but "beat 64%" means beating a benchmark known to be inflated, in
a simulator whose measured edge is ~0 (CR214: placebo-adjusted +0.30% at 4w).
Suggested reframing: risk-5 is **more permissive than the sell-side**, with a
monotonic and visible R1→R5 spread — rather than claiming greater accuracy.

**Asked 2026-09-23 (daily check-in):** reframe now to "monotonic spread" / keep
"beat 64%" as the bar / decide after Steps 2-4 land. Saiful: **"Decide after
Steps 2-4."** No target framing is committed yet — Steps 2-4 (widen cap table,
PM prompt branch, graded vote threshold) proceed as scoped, and the
success-definition question stays open until there's more data to frame it
against.

**Decided 2026-09-25.** Saiful: **"Test as per recommendation"** — the success target is
the **monotonic R1→R5 spread**, not "beat 64%". Measured by a full-dial re-run
(`ARMS="1 2 3 4 5" run_pilot.sh`, same 30 tickers, batches `cr228-r{1..5}-20260925`),
scored by `score_dial.py`, whose PASS criterion is fixed in its docstring and committed
before the run starts: Page's L trend test on per-ticker `approve_votes`, one-sided
p < 0.05, **and** mean `approve_votes` never falling from one arm to the next. The
verdict is read by that letter. Honest caveat recorded up front: at n≈30 with CR214's
12–20% verdict noise, criterion 2 can fail on a single noisy adjacent step even when the
trend is real — if that happens it is a FAIL, reported as such, with the step named.
