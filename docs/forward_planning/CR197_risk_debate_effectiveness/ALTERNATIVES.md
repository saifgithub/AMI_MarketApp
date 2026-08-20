# What to build instead of the debate

> **BUILT AND MEASURED, 2026-08-20 — and the measurement partly falsified this
> document's central prediction. Read §0 before the rest.**

## §0 — What the build actually found

This doc predicted the deterministic ladder would *replace* the debate: "approvals
return to ~16% without any debator prose". Two arms were run to check it, and the
prediction was half right at best.

| arm | prompt | APPROVE | rate | net vs baseline | p |
|---|---|---|---|---|---|
| v1a | baseline — debate, no ladder | 22 | 16.3% | — | — |
| v1b | baseline resampled | 21 | 15.7% | 0 | 1.000 |
| v2 | debate stripped | 10 | 7.4% | +12 | **0.004** |
| **v6** | **debate stripped + ladder** | **16** | **11.8%** | +6 | 0.238 |
| **v7** | **debate + ladder (what ships)** | **28** | **21.1%** | −7 | 0.210 |

1. **The ladder is a partial substitute, not a replacement.** It recovers about half
   the approvals that removing the debate destroys (10 → 16 against a 22 baseline).
   The debate supplies something beyond the arithmetic.
2. **Added to the full prompt it does not merely tidy the numbers — it moves the
   verdict.** Approvals rise 16.3% → 21.1%. Two readings, and the data cannot
   separate them: this is exactly what correcting the DEF066 class predicts (that
   defect overstated risk ~20× and made 16 of 64 benchmark names wrongly un-buyable),
   and it is also what DEF292's failure mode looks like from the other side (rungs
   reading "0.3% of the cap" make the budget feel empty and ours to fill).
3. **It thins judgement.** Interpolation between rungs falls from 32% of approvals
   (7/22) to 11% (3/28), and to 0% when the ladder is the only input. The CIO anchors
   on the menu.

**Consequence:** the ladder shipped **gated off** (`PM_OPTION_LADDER_ENABLED=false`).
It is a behaviour change with a product dimension — "the simulator approves more
trades" — and that is Saiful's call, not an implementation detail. Everything below
stands as the reasoning that motivated it; the numbers above are what happened.

---

**Question (Saiful, 2026-08-20):** so what's a better solution than the debate?

**Short answer:** stop using three LLM calls to generate a menu that arithmetic can produce
exactly, and spend that budget on the defect the ablation actually exposed — that **1 in 5
verdicts is decided by sampling noise**. Keep the three risk officers as narration, because their
product value is real and separable from their decision value.

---

## What the debate is actually for, and why that is the wrong job for an LLM

The ablation established the mechanism: the debate supplies the Portfolio Manager with **sized
alternatives it does not construct on its own**. Remove all three and approvals halve (16.3% →
7.4%, p=0.004) because the PM is left with the Trader's take-it-or-leave-it number and leaves it.

Two measurements say this job belongs in code, not in a language model:

1. **The options are already deterministic.** `risk_debator_sizes()` computes the ladder
   (`trader+2` / `trader−1.5` / `trader`) *before any debator speaks*, and hands each agent the
   figure to argue. The LLM is not choosing the options — it is dressing them.
2. **The PM mostly just picks a rung.** Across 43 baseline approvals, **32 (74%) land exactly on
   a computed ladder value**; the other 11 interpolate (2.0, 2.5, 4.0). So the PM's real need is
   a menu with consequences attached, and a quarter of the time, permission to land between rungs.

Meanwhile the LLM does the *arithmetic* attached to those options badly, repeatedly, and in a way
that has generated its own defect lineage: DEF066 (stop distance compared against the portfolio
cap, ~20× overstatement, 16 of 64 benchmark buys wrongly refused), DEF241, and CR154's hand-read
finding that **4 of 9** numeric cap-consumption claims by the Conservative were wrong — one of
them reproducing DEF066's exact error with DEF066's warning in the same prompt. CR143 M4 found a
published "figures of record" note overstating a contribution by **63×**.

That is the summary of the case: we are paying three LLM calls, three serial round-trips, and a
recurring class of arithmetic defects to produce a table that `trading_math` can emit correctly
in microseconds.

---

## The proposal

### 1. Deterministic option ladder in the PM's prompt — 0 LLM calls

Render a computed table into the VERDICT prompt, replacing the debate's *decision* function:

| option | size | drawdown contribution | open risk after | R:R at Trader's stop/target | headroom left |
|---|---|---|---|---|---|
| trim | 1.5% | 0.18 pt of 30 | … | … | … |
| reference | 3.0% | 0.36 pt | … | … | … |
| press | 5.0% | 0.60 pt | … | … | … |

Everything needed already exists and is already unit-tested:
`risk_debator_sizes` and `resolved_single_name_cap_pct` (`trading_math/sizing.py`),
`drawdown_contribution` (`trading_math/risk.py`), `stop_distance_pct` and
`position_risk_contribution` and `resolved_max_open_risk_pct` (`trading_math/risk_limits.py`),
plus the live consumption already threaded into every prompt by `_risk_state_block`.

Two design requirements the measurement dictates:
- **Permit interpolation.** 26% of approvals land between rungs; a three-rung menu that forbids
  it would be more constraining than today's prose.
- **State it as options, not as a recommendation.** The safety floor stays the only vetoer
  (DEF059); this is a menu, not a decision.

**Precedent, already in production:** this is exactly the CR136 shape —
`portfolio_rules.py` computes deterministically, `portfolio_finding.py` makes **one** LLM call to
narrate, and a validator rejects any number in the generated text that is not one of the computed
slots. That pattern shipped and works; this applies it to the RISK phase.

### 2. Spend the freed budget on self-consistency, not deliberation — 3 LLM calls

The ablation's baseline arms measured something nobody was looking for. Across **132 convenes
with three byte-identical replays**:

| | |
|---|---|
| unanimous 3/3 | 106 (80.3%) |
| **split 2–1** | **26 (19.7%)** |
| single sample vs 3-vote majority | disagrees 6.6% of the time |

The approval *rate* is stable across samples (22 / 21 / 25 of ~135) but **which name gets approved
is not**. About one verdict in five is settled by the sampler. The user sees a confident
`APPROVE` or `PASS` with no indication that a re-run would have said otherwise.

Three independent PM samples with **majority vote on the action and median on the size** costs
exactly what the debate costs today and attacks that directly. It also converts a hidden failure
into a displayable one: a 2–1 verdict is a legitimately close call, and saying so ("your team was
split on this") is *better* pedagogy for a training simulator than false confidence.

**Our own research already says this is the better shape.**
`docs/Research/benchmark/kimi/04_academic_forecasts.md`:

> "The reliable ordering is: best structured aggregation of independent forecasts ≥
> trained/tracked teams > simple average of independent forecasts > average individual >
> **deliberating unstructured group (risk of cascade)**. The Room's architecture … maps onto the
> winning recipe *only if* the specialist passes are genuinely independent and the aggregation is
> mechanical rather than consensus-seeking."

We built the arrangement that ordering ranks **last**, and the condition attached to the winning
recipe — mechanical aggregation — is precisely what we do not do. Self-consistency is the cheapest
step toward the top of that list.

### 3. Keep the risk officers, but as parallel narration — 3 calls, 1 serial step

Their product value is real and was never in question: SSE stream, Journal replay, 3 of 11 comb
voices, 3 unlockable 1-on-1 personas, and D-012's roster. What the ablation showed is that this
value is **separable from the decision path** — the PM does not read the two extremes at all
(net −1 verdict, p=1.0).

So run them for the user, not for the PM. The two extremes have no need to see each other
(measured: the Aggressive speaks first and cannot rebut anyone anyway), so they parallelise
cleanly. That turns three serial round-trips into one, or two if the Balanced officer keeps
synthesising them.

**The CR077 caveat applies and is not optional:** `test_cr077_phase_parallelism.py` exists
precisely because marking a debate phase parallel "would silently delete the debate while every
other test passes and the UI still renders every contribution". Any parallelisation here has to
update that guard deliberately, with the new invariant written down.

---

## Net effect

| | today | proposed |
|---|---|---|
| LLM calls | 12 | 12 (3 narration + 3 PM samples, extremes' narration optional) |
| serial steps in RISK+VERDICT | 4 | 2 |
| option arithmetic | LLM, measured wrong 4/9 | computed, correct by construction |
| verdict stability | 1 in 5 is a coin flip | majority-vote, and the split is displayable |
| user-facing debate | 3 voices | 3 voices, unchanged |

Same budget. The decision gets a correct menu and a stable answer; the user keeps the room.

---

## What still has to be tested before any of this ships

1. **The live two-arm benchmark** (from `REPORT.md`): every ablation arm held the surviving turns
   fixed at what was recorded, so v3 proves the PM does not need the extremes' prose — it does
   **not** prove the Balanced officer doesn't, since its job is to synthesise them. If the option
   ladder replaces that synthesis function, this question partly dissolves; if the officers stay
   as narration only, it dissolves entirely.
2. **Does the ladder actually substitute?** The honest test is an arm that strips the debate *and*
   injects the computed table. Predicted: approvals return to ~16% without any debator prose.
   That is one more run of `pm_debate_ablation.py` with a new variant, and it is the single
   highest-value measurement left — it would confirm the whole proposal for a few hundred calls.
3. **Does majority-vote change outcomes for the better, or just make them stickier?** Variance
   reduction is not accuracy. The corpora carry no trade outcomes, so this cannot be settled here;
   it needs the simulator's own P&L over time.

## What NOT to do

- **Do not cut the debate to save cost.** Measured: approvals drop 16.3% → 7.4%. The Room would
  refuse most trades and teach the user to do nothing.
- **Do not keep the current shape and just reword the prompts.** P2: prompt instruction is not a
  control, and the three attempts already on record (DEF243, DEF251, CR153-155) moved compliance
  by single digits or in the wrong direction.
