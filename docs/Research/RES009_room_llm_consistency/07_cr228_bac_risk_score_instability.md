# 07 — CR228 risk_score sweep, BAC: instability traced to the `trader` agent

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

Both `trader` calls cite the **same numbers** — $56.70 price, $55.29 200-day,
$68.62 Street target, 18 days to the 2026-10-14 print, both `STANCE: for`,
both `CONVICTION: medium`. The fork is a genuine judgment call on one
specific question: **is "2.6% above the ideal entry level, with a binary
catalyst 18 days out" close enough to initiate a small position now, or does
it warrant waiting for the pullback / the print to resolve first?** One
`trader` draw says wait (`Side: WAIT`, 0% size, a *conditional* future trade);
the other says buy now at reduced size. Neither is an error — both are
internally coherent, cite correct figures, and reach a defensible conclusion
from the same inputs.

## Read

- **The instability is not upstream-data noise, not a PM-sampling artifact, and
  not attributable to `research_manager`'s stance alone.** It is a genuine
  disagreement, reproduced live, at the `trader` agent — the one stage that
  converts a qualitative "for" lean into a concrete Side/Size decision. This is
  a *narrower and more specific* finding than "risk_score=2 is noisy": the
  noise has a location.
- **This is a close call, not a bug.** $56.70 vs. a $55.29 target entry (2.6%
  away) with an earnings print 18 days out is exactly the kind of setup where
  "wait for the better price" and "small size now, add later" are both
  reasonable trading stances. The two `trader` draws are not contradicting
  facts — they're weighting the same acknowledged tension differently.
- **Practical implication for CR228**: risk_score=2 (a specific point, not the
  full 1–5 range) may sit in a genuinely higher-variance region of Kimi's
  behavior on setups near-but-not-at a `trader` agent's own stated ideal entry
  zone. Whether this is Kimi-specific or would reproduce on vLLM too, and
  whether it's particular to BAC-like near-threshold technical setups or
  general to risk_score=2, is not established by this one ticker — it would
  need the same trader-level trace repeated on other tickers with a similarly
  marginal entry setup before generalizing.
- Consistent with [06](06_pivot_and_growth_threshold_test.md)'s broader
  finding: confident, fluent, well-reasoned model output is not the same
  thing as consistent model output. Both `trader` draws here would pass a
  spot-check on their own — the disagreement only shows up by deliberately
  running the same setup more than once.
