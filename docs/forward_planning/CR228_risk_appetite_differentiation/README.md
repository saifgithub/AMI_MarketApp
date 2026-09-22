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

## Step 1 — the pilot (this step)

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

## Open question for Saiful

The Street's 64% Buy rate is a **biased** baseline (sell-side Buy skew;
`docs/Research/benchmark/claude/02_sellside_analysts.md`). The levers above can hit
any number named, but "beat 64%" means beating a benchmark known to be inflated, in
a simulator whose measured edge is ~0 (CR214: placebo-adjusted +0.30% at 4w).
Suggested reframing: risk-5 is **more permissive than the sell-side**, with a
monotonic and visible R1→R5 spread — rather than claiming greater accuracy.
