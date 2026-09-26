# 07 — CR228 risk_score sweep, BAC: instability compounds through the pipeline, not a single fork

**Correction, same session:** an earlier version of this doc concluded the
divergence traced to a single fork point at the `trader` agent, based on
comparing 2 of the 6 draws and their `system_prompt`s. Checking all 6 draws
and diffing `trader`'s actual input (not just its output) found that claim
wrong — see "Result 4" below. Left the original findings in place and added
the correction rather than rewriting history, per RES009's own "if the spec
changes after seeing results, say so" rule.

Note on numbering: this doc's `out/` data files are prefixed `08*`, not `07*` —
[06](06_pivot_and_growth_threshold_test.md)'s own data already claimed `07a`/`07b`
before this doc existed. Doc-number and out-prefix have drifted apart; noted here
rather than renumbering everything retroactively.

## Context

CR228 (risk-appetite differentiation) needed a same-day, cross-provider
comparison at `risk_score=3`. Running that comparison (vLLM on melehost,
Kimi locally on the Mac — see [`run_local_kimi.py`](../../forward_planning/CR228_risk_appetite_differentiation/run_local_kimi.py))
surfaced two things worth investigating on their own:

1. A full AAPL longitudinal (risk_score 1–5, Kimi, thinking disabled) came back
   **unanimous 0/5 PASS at every single risk_score tested** — not a threshold
   effect, since the underlying vote was never marginal enough for a threshold
   change to matter.
2. The same sweep on **BAC** came back APPROVE at risk_score 1, 3, 4, 5 —
   but **PASS at risk_score=2**, breaking what was otherwise a clean,
   consistent pattern. This doc investigates that one result.

## Method

Kimi (`kimi-k3`, Moonshot Open Platform, thinking disabled —
`{"thinking": {"type": "disabled"}}`, established in
[05](05_kimi_cross_check.md)), full `RoomRunner.run()` convenes, fresh
synthetic `user_id` per draw, mandate fixed at `risk_score=2` (with
`drawdown_response`/`concentration_tolerance` tracking the same value, per
CR228's own mandate convention — see `run_pilot.sh`'s `base_mandate()`).
6 independent draws total: the original sweep draw plus a 5x repeat
(`run_local_kimi_bac_repeat_r2.py`). Full data:
[`out/08a_bac_risk_sweep_kimi.jsonl`](out/08a_bac_risk_sweep_kimi.jsonl),
[`out/08c_bac_repeat_r2_kimi.jsonl`](out/08c_bac_repeat_r2_kimi.jsonl).

For comparison, risk_score=3 was independently repeated 6x as well
(1 original + 5x via `run_local_kimi_bac_repeat.py`):
[`out/08b_bac_repeat_r3_kimi.jsonl`](out/08b_bac_repeat_r3_kimi.jsonl).

## Result 1: risk_score=2 is genuinely unstable; risk_score=3 is not

| risk_score | draws | distribution |
|---|---|---|
| 2 | 6 | **4 APPROVE / 2 PASS** |
| 3 | 6 | **6 APPROVE / 0 PASS** — unanimous every draw |

risk_score=3's APPROVE is a settled, repeatable result. risk_score=2's is not
— roughly a 2-in-3 coin flip on the identical ticker, mandate shape, and
trading-day data. This rules out the original single risk_score=2 PASS draw
being "the" answer for that mandate setting; it was one draw of an unstable
distribution, not a stable finding on its own.

## Result 2: the instability is not in the PM's own 5-sample vote

The Room's PM stage already runs 5 independent samples and takes a majority
(`_vote_pm_samples`, CR197) specifically because single-draw PM verdicts are
known to be unreliable. Checking `room_pm_self_consistency` log lines across
all 6 risk_score=2 runs:

| run | PM agreement | approve_votes | final action |
|---|---|---|---|
| 1 | 5/5 | 5 | APPROVE |
| 2 (original) | 5/5 | 0 | PASS |
| 3 | 4/5 | 4 | APPROVE |
| 4 | 5/5 | 5 | APPROVE |
| 5 | 5/5 | 5 | APPROVE |
| 6 | 4/5 | 1 | PASS |

5 of 6 runs show **near-total internal PM agreement** (4/5 or 5/5) — within a
given run, the 5 PM samples mostly agree with each other. The instability is
almost entirely **between** runs, not within a single run's PM sampling. That
rules out "the PM's self-consistency mechanism is noisy" as the explanation
and points upstream: something earlier in the pipeline is producing a
different consensus stance from one full convene to the next, which the PM
then faithfully reflects.

## Result 3: traced to the `trader` agent, not `research_manager`

Pulled `research_manager` and `trader` output (`response_text`, via
`llm_audit`, correlated by the run's synthetic `user_id` — `llm_audit` has no
`run_id`/`ticker` column) for two PASS runs and two APPROVE runs. Full text:
[`out/08d_bac_r2_agent_trace.json`](out/08d_bac_r2_agent_trace.json).

`research_manager`'s own `[STANCE: ...]` tag:

| run | research_manager stance |
|---|---|
| PASS (run 2 of the repeat set) | `neutral` |
| PASS (run 6 of the repeat set) | **`for`** |
| APPROVE (run 1) | `for` |
| APPROVE (run 4) | `for` |

One PASS run's `research_manager` was already `neutral` — consistent with the
eventual PASS. But the **other PASS run's `research_manager` said `for`**,
identical to both APPROVE runs' stance. So `research_manager`'s stance alone
does not explain the split; the fork happens later.

Comparing `trader` output for that specific pair (`research_manager: for` in
both, but one run PASSed and the other APPROVEd):

**PASS run's `trader`:**
> `[STANCE: for | CONVICTION: medium | HEADLINE: 2.6% above 200-day, wait for pullback]`
> `Side: WAIT` · `Size: 0.00% of portfolio`
> "Current price $56.70 sits only 2.6% above the 200-day average of $55.29.
> With -13.1% already off the 52-week high and earnings in 18 days,
> risk/reward favors patience over initiation at this level." Proposes a
> conditional trigger: enter 2.0% if price pulls back to $55.00–$55.50, or
> post-earnings.

**APPROVE run's `trader`:**
> `[STANCE: for | CONVICTION: medium | HEADLINE: $55.29 stop caps risk at 0.05pt]`
> `Side: BUY` · `Size: 2.00% of portfolio` · immediate entry at $56.70,
> stop $55.29, target $68.62, R:R 8.5:1.
> "2.0% size with a 2.5% stop distance contributes 0.05 percentage points to
> portfolio drawdown — negligible against the 30% cap."

Both `trader` calls cite the **same headline numbers** — $56.70 price, $55.29
200-day, $68.62 Street target, 18 days to the 2026-10-14 print, both
`STANCE: for`, both `CONVICTION: medium` — which read at first as "the fork is
at `trader`." Checking `trader`'s actual *input* (not just its output) shows
that framing was wrong.

## Result 4 (correction): the fork isn't at `trader` — every stage upstream of it already differs

Extending Result 3 to all 6 draws, not the 2 spot-checked:

| run | trader Side | trader Size | final action |
|---|---|---|---|
| APPROVE_1 | BUY | 2.0% | APPROVE |
| APPROVE_2 | BUY | 2.0% | APPROVE |
| APPROVE_3 | BUY | 2.0% | APPROVE |
| APPROVE_4 | BUY | 2.0% | APPROVE |
| PASS_1 | **WAIT** | **0.0%** | PASS |
| PASS_2 | **WAIT** | **0.0%** | PASS |

`trader`'s Side/Size is a perfect 6/6 predictor of the final action — stronger
than Result 3's "close call" framing suggested. That raised the real
question: **why does `trader` itself flip?** Full `trader` output for all 6
draws, plus the `fundamentals_analyst` and `trader` system_prompt diffs cited
below:
[`out/08e_bac_r2_all6_trader_and_diff.json`](out/08e_bac_r2_all6_trader_and_diff.json).

Diffing `trader`'s full `system_prompt` (not just its `response_text`)
between a WAIT draw (PASS_1) and a BUY draw (APPROVE_1) — i.e., the actual
text `trader` was given to read, built from every upstream agent's output —
found it is **not the same prompt with a different trader judgment on top**.
Every upstream stage already differs in substance:

- **News catalysts differ**: PASS_1's prompt includes a Citigroup/Banamex IPO
  headline that APPROVE_1's does not; headline "hours ago" timestamps differ
  beyond what the ~4-minute gap between the two draws would explain.
- **`fundamentals_analyst`'s own framing differs**, even though both cite
  identical underlying numbers (13.1x trailing P/E, 17.8x own-history median,
  PEG 0.85, $34.8B total capital return, 2.28% yield, 26% payout — see
  [`out/08d_bac_r2_agent_trace.json`](out/08d_bac_r2_agent_trace.json)).
  PASS_1's version leads with "PEG 0.85 signals growth at a reasonable
  price"; APPROVE_1's omits that framing sentence entirely and leads with
  buyback pace instead. Same facts, different emphasis, from the very first
  LLM call in the chain.
- **A grounding/self-correction block appears in both, flagging different
  hallucinated figures each time** (`[AMI checked "10" against the fact
  sheet: the sheet's own figure is 10.7, not 10...]` in one draw,
  `[AMI checked "17" against the fact sheet: the sheet's own figure is 13.1,
  not 17...]` in the other) — each draw's chain independently hallucinated
  and then self-corrected a *different* number.
- **`bear_researcher`'s actual argument is a different argument, not a
  reworded one**: PASS_1's bear case is balance-sheet/leverage fragility
  ("$789B gross debt... ROA of 1%... structural constraints"); APPROVE_1's
  bear case is a "peak earnings, the multiple discount is a value trap"
  thesis. These are two different bear theses on the same ticker, not the
  same thesis in different words.
- **`research_manager`'s output text differs throughout**, not only its
  `[STANCE:]` tag (already shown in Result 3).

## Read

- **The instability does not have a single location — it compounds through
  the whole sequential pipeline.** `fundamentals_analyst`, the earliest
  narrative-generating call, already produces different emphasis on identical
  numbers between draws. Each subsequent agent (technical strategist,
  macro/events, bull, bear, research_manager) reads the previous agents'
  *already-diverged* text and adds its own independent variation on top,
  compounding by the time it reaches `trader`. `trader`'s WAIT-vs-BUY split
  is the point where compounding upstream variance finally resolves into a
  visible binary outcome — not the point where the disagreement originates.
  The original "genuine judgment call at `trader`" framing (struck through
  above) implied the two `trader` calls saw the same inputs and reasoned
  differently from them; they did not see the same inputs.
- **This reframes "risk_score=2 is noisy" as "risk_score=2 is where noise that
  exists at every stage happens to land on different sides of a binary
  decision."** risk_score=3's identically-repeated APPROVE (6/6, Result 1)
  doesn't mean risk_score=3's upstream agent chain is more stable per se — it
  may mean risk_score=3's setup is far enough from any agent's decision
  boundary that the same kind of per-stage variance never changes the final
  binary outcome. risk_score=2's BAC setup (price 2.6% above the trader's own
  stated ideal entry, 18 days to a binary earnings catalyst) appears to sit
  close enough to that boundary that ordinary per-call variance — the same
  kind RES009's [01](01_divergence_sources.md) and
  [06](06_pivot_and_growth_threshold_test.md) already documented at the
  single-agent level — is enough to flip it.
- **Practical implication for CR228**: this is not evidence that risk_score=2
  specifically is broken, or that the vote-threshold mechanism is wrong. It is
  evidence that **any** Room verdict near a genuine decision boundary — for
  any risk_score, any ticker — inherits instability from every one of the
  ~6-9 sequential LLM calls that precede the final vote, not just from the
  PM's own 5-sample stage that CR197 already accounts for. Whether that
  argues for self-consistency sampling earlier in the pipeline (not just at
  the PM), for a different aggregation approach, or for accepting this as an
  inherent property of a long LLM-agent chain, is a CR228/Room-architecture
  question, not something this doc resolves.
- Consistent with [06](06_pivot_and_growth_threshold_test.md)'s broader
  finding: confident, fluent, well-reasoned model output is not the same
  thing as consistent model output — now shown to hold at every stage of a
  12-agent pipeline, not just a single isolated call.
