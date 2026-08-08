# CR143 research — improving agent conclusion accuracy

> Research memo. Author: Kimi (track K).
> Evidence base: the 12 per-agent audits in `../external_review/room/kimi/`
> (codebase-verified) plus the real prompt/reply samples in `../real_samples/`.
> Every technique below is mapped to a failure we actually observed, not generic
> prompt-engineering advice.

## 0. What "accuracy" decomposes into

The audits show the Room's errors are not one thing. Five distinct classes,
with very different fixes:

| # | Error class | Observed in | Root cause |
|---|---|---|---|
| E1 | Numeric hallucination | rare (0 of 12 replies fabricated a datum from memory) | — |
| E2 | Arithmetic error on supplied data | trader (0.00:1.00 R:R), conservative_debator (1.17%), research_manager ("symmetric" premise), bull_researcher (22.9% vs 23.05%) | LLM forced to do math Python already does |
| E3 | Format non-compliance | 8 of 12 agents (stance line position, missing bullets, dual schema, wrong length) | contradictory output specs inside one prompt |
| E4 | Scope bleed (using another agent's lane/data) | fundamentals, news, social (live), RM (moderate) | one shared fact sheet for all analysts |
| E5 | Reasoning from missing state | PM (drawdown/open-risk), debators (existing risk), trader (journal), RM (journal, sector weights) | data computed per run, never rendered |

Headline implication: **E1 — the failure everyone worries about — is already
the rarest.** The accuracy ceiling is set by E2–E5, all of which are
engineering problems with deterministic fixes, not model-quality problems.

## 1. Lever: precompute every number the LLM is tempted to derive

The single strongest pattern in the audit: **every arithmetic error happened at
a spot where the LLM had to compute something the backend already computes (or
trivially could).**

- `trade_asymmetry` (`backend/app/trading_math/trade.py:47`) is computed every
  run and fed only to the scripted template fallback (`room_runner.py:2923,
  2959-2963`). Render the actual numbers — upside %, downside %, R:R — into the
  prompt for RM, trader, debators, PM. The trader's false "symmetric" verdict
  and the RM's false premise both die the moment the correct ratio is printed
  in the block.
- Position-in-range %, upside-to-consensus-target %, drawdown consumption per
  unit of size — all one-line derivations from data already in
  `_RoomContext`. Precompute, label, inject.
- Rule of thumb for all future prompt work: **if a number can be produced by a
  line of Python, it must not be produced by the model.** LLMs are good at
  weighing evidence, bad at long-division. Play to that.

Expected gain: eliminates E2 entirely. Cost: render-only changes in
`room_prompts.py`. This is the cheapest accuracy lever in the whole system.

## 2. Lever: render the risk state the roles already demand

Seven agents are told to weigh drawdown, open-risk, pace, or sector exposure —
none of it is in their prompts, all of it is computed per run
(`sim_engine.py:481-503`, `room_runner.py:2864-2869`) and consumed only by the
deterministic safety floor.

Render into the RISK/EXECUTION/VERDICT prompts:

- per-position stops (with a loud "no stop recorded" state for `stop=None`),
- `existing_open_risk_pct` and the remaining headroom vs the 60% cap,
- `current_drawdown_pct` and remaining drawdown capacity,
- pace counts (trades today / this week vs caps),
- sector weights (currently PM-only, `room_prompts.py:453-455`; RM and
  researchers need them to apply the 20% sector cap).

Expected gain: kills E5; converts "the agent said something plausible about
risk" into "the agent reasoned over the same numbers the safety floor enforces."
Cost: render-only, zero new provider calls, zero rate-limit exposure.

## 3. Lever: one output contract per agent, enforced server-side

E3 was prompt-caused in every observed case: STANCE-first vs prose openers
(debators), "2 sentences" vs mandated bullets (4 agents), dual schemas (trader
emitted both), PM's JSON-only contract vs the safety floor's mandated trailing
tag line (`safety_floor.py:121-122` — a string that can never legally appear).

Two-part fix:

1. **Unify the contract.** Per agent, exactly one output spec — delete the
   losing half of every contradiction. The audits contain the per-agent list.
2. **Validate and repair, don't hope.** A deterministic post-processor:
   - stance-line regex + position check,
   - HEADLINE ≤ 32 chars,
   - bullet count / sentence count bounds,
   - JSON schema parse for the PM verdict.
   On failure: one automatic regeneration with the validation error appended
   ("your previous reply violated X; correct only that"). Self-correction loops
   of this shape reliably fix format errors in one retry, and the retry only
   fires when needed — near-zero steady-state cost.

Expected gain: E3 → near zero. Bonus: the validator doubles as the measurement
instrument for §7.

## 4. Lever: numeric grounding check on every reply

Even though E1 is rare today, it is cheap to keep it rare forever — and it
catches the E2 residue that survives §1:

- Extract every numeral from the reply; check each against the set of numbers
  present in the prompt block plus an allowlist of derived values the backend
  itself injected. Flag anything else.
- Numbers failing the check are either hallucinations or unlabeled derivations;
  route to the same repair loop as §3 with "this figure appears nowhere in
  your data — remove it or mark it as your own estimate."

This is deterministic, fast, and model-free. It converts the audit I ran
manually on 12 replies into a per-turn guard. The trader's `0.00:1.00` and the
conservative debator's `1.17%` would both have been caught at generation time.

## 5. Lever: per-agent fact-sheet views

All four analysts receive one identical fact sheet by design
(`room_runner.py:145-156`). E4 is the direct consequence: fundamentals quoted
RSI, news quoted P/E, social quoted valuation — each drifting into a sibling's
lane because the sibling's data was sitting in front of it.

- Filter fields per agent at render time (`room_prompts._format_profile`):
  fundamentals gets valuation/growth/balance-sheet fields; market gets
  price/technicals; news gets catalysts/macro; social gets sentiment. Shared
  context (ticker, date, mandate, portfolio) stays common.
- Side benefits: smaller prompts (the RM is already the truncation-worst
  agent), less cross-domain anchoring, and the blind reviews' CUT lists become
  enforceable structure instead of instructions the model may ignore.

This is a renderer change, not a data change — the supplier checks in the
audits confirm every field already flows through one assembly point.

Expected gain: E4 → near zero. Note the trade-off: some cross-domain awareness
is deliberate (the debators argue over everything) — filter the four analysts
and the social/news/fundamentals lanes first; leave debate-phase agents on the
full transcript.

## 6. Lever: break transcript contagion with verified anchors

The worst conclusion failure in the samples was a cascade: research_manager
mis-derived "symmetric risk-reward" → trader adopted and hardened it into a
fake 0.00:1.00 ratio. Sequential phases mean early errors compound downstream.

Mitigations, in increasing order of strength:

1. §1 removes the root: the numbers the cascade formed around become
   precomputed anchors in the block, so a downstream agent can see the upstream
   claim contradicts the sheet.
2. Label upstream claims that fail the §4 check when appending them to the
   transcript ("[unverified figure]"). Downstream agents discount flagged
   content.
3. For the PM specifically — the conclusion that matters — inject a
   "verified facts" recap line above the transcript: the deterministic numbers
   (asymmetry, caps, risk state) restated, so the gatekeeper's final read
   anchors on ground truth, not on 11 turns of telephone.

## 7. Lever: an eval harness — the meta-fix

Every fix above is unverifiable without measurement. Build the regression gate:

- **Golden set:** the 12 `real_samples/` pairs (plus future captures) as fixtures.
  Re-capture stale ones first — `market_analyst.prompt.txt` predates
  DEF227/DEF228 and misrepresents HEAD.
- **Deterministic scorers:** the §3 format validator and §4 numeric checker run
  as scorers — free, reproducible.
- **Rubric scorer (LLM-as-judge):** scope discipline, stance-evidence
  alignment, thesis quality — scored against a fixed rubric, judge pinned to a
  specific model version.
- **CI gate:** prompt or renderer changes run the suite; a regression on any
  axis blocks the change. This turns CR143's one-off audit into a permanent
  quality bar, and gives the CR-writing agent a before/after measurement for
  every fix it ships.

## 8. Secondary levers (lower priority, real gains)

- **Structured output for the PM.** The verdict is already JSON; enforce it
  with guided decoding (vLLM supports JSON-schema-constrained generation) or
  tool-call style responses on the Anthropic fallback. Parse failures become
  impossible rather than retryable.
- **Few-shot anchoring.** One golden reply per agent embedded in the prompt
  improves format adherence more reliably than any instruction wording. Costs
  tokens; apply first to the agents with the worst E3 record (debators,
  trader, RM).
- **Freshness honesty.** The social cache is 30 days (`config.py:210`) while
  the header claims "LIVE as of this call" — render cache age next to stale
  fields. Accuracy includes the model knowing how much to trust its inputs.
- **Tiering and temperature.** `tier_policy.py` already maps (plan, agent) →
  model. Analytic turns (RM, PM, trader) justify the strongest tier and low
  temperature; debator rhetoric tolerates more. Cheap config-level tuning once
  the eval harness exists to measure it.

## 9. Prioritisation

| Order | Lever | Kills | Effort | Notes |
|---|---|---|---|---|
| 1 | §1 precomputed numbers | E2 | days | render-only; biggest accuracy-per-line |
| 2 | §3 unified contract + validator | E3 | days | validator doubles as eval instrumentation |
| 3 | §2 render risk state | E5 | days | render-only; aligns agents with safety floor |
| 4 | §5 per-agent fact sheets | E4 | ~1 week | renderer change; cut token bloat too |
| 5 | §4 numeric grounding guard | E1/E2 residue | days | needs §3's repair loop to be useful |
| 6 | §6 verified anchors for PM | cascade failures | days | depends on §1 |
| 7 | §7 eval harness | regressions, all classes | ~1 week | start with golden set + deterministic scorers |
| 8 | §8 structured output / few-shot / freshness / tiering | polish | varies | sequence after harness exists to measure |

The first three are mutually independent, render-only, and together address
every error class that appeared more than once in 12 live samples. Everything
after that is compounding refinement.

## 10. What not to chase

- **Bigger models as the first fix.** E1 is already near-zero on the current
  tier; E2–E5 survive model upgrades because they're structural. Revisit
  tiering only after the harness can prove a residual model-quality gap.
- **More instructions.** Every E3 failure came from prompts with *too many*
  output specs, not too few. The direction is subtraction and enforcement,
  not addition.
- **Real-time fact APIs to fight hallucination.** The supply side is mostly
  already fetched and discarded (see the supplier tables in each audit).
  Wire what we have before buying new providers.
