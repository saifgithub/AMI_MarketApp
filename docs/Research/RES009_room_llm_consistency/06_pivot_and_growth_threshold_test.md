# 06 — Ask the model, then test the answer

## Part 1: what would flip you to FOR?

### Method

`backend/scripts/ibm_stance_pivot_probe.py` sends the real captured
`system_prompt`, the real "Convene on IBM." user turn, one of the model's own
captured NEUTRAL completions as **assistant history** (so the follow-up reacts
to what the model actually said, not a hypothetical), then a new user turn
asking it to name, in 2-3 sentences, the single most decision-relevant fact
that — if meaningfully different — would move it from NEUTRAL to FOR. Run 3x
per run per provider. Full data:
[`out/06a_pivot_probe_run_a_kimi.json`](out/06a_pivot_probe_run_a_kimi.json),
[`out/06b_pivot_probe_run_b_kimi.json`](out/06b_pivot_probe_run_b_kimi.json),
[`out/06c_pivot_probe_run_a_vllm.json`](out/06c_pivot_probe_run_a_vllm.json),
[`out/06d_pivot_probe_run_b_vllm.json`](out/06d_pivot_probe_run_b_vllm.json).

### Result: unanimous, specific, across both runs and both providers

**12 of 12 clean-seed answers named the same fact: TTM revenue growth needs to
reach roughly 5% (from the fact sheet's actual 1%).**

| | Kimi | vLLM |
|---|---|---|
| Run A (3 draws) | 3/3: "5%+" | 3/3: "4-5%" |
| Run B (3 draws) | 3/3: "4-5%" | 3/3: "5%+" |

(One vLLM run was first attempted with the seed file missing on melehost's
container filesystem — a real operational mistake, not a finding — and re-run
correctly once caught; the broken-seed attempt still landed on the same answer
in 2 of 3 draws, with the third naming margin trend instead. Only the
seed-present re-run is counted above.)

This looked, at the time, like a genuinely useful and stable signal: a specific,
falsifiable number, agreed by two independent models, across two different
users' prompt contexts.

## Part 2: testing the claimed threshold directly

### Method

`backend/scripts/ibm_growth_threshold_test.py` patches the single line
`TTM revenue growth: 1%` in the real captured system prompt to `2%`, `3%`,
`4%`, `5%` in turn (exact-text substitution, asserted to match exactly once —
refuses to run silently if the fact sheet's format changed underneath it),
leaving every other field — PEG, P/E, margins, price, all narrative content —
untouched. PEG is not recomputed: it is sourced directly from the market-data
provider's own `trailingPegRatio`/`pegRatio` field
([backend/app/services/fundamentals.py](../../../backend/app/services/fundamentals.py)),
a forward-EARNINGS-growth basis, not mechanically derived from the TTM-REVENUE
growth figure this script changes — so leaving it alone does not introduce an
internal inconsistency into the patched fact sheet.

Cascade per Saiful's instruction: Kimi first, up to 10 draws per growth value,
stopping early once at least half the budget's worth of draws agree
unanimously. Then the same test against vLLM. Full data:
[`out/07a_growth_threshold_run_a_kimi.json`](out/07a_growth_threshold_run_a_kimi.json),
[`out/07b_growth_threshold_run_a_vllm.json`](out/07b_growth_threshold_run_a_vllm.json).

### Result

| TTM revenue growth | Kimi (T=0.6) | vLLM (unpinned default) |
|---|---|---|
| 2% | 4 FOR / 6 NEUTRAL | 3 FOR / 6 NEUTRAL (+1 malformed response) |
| 3% | 8 FOR / 2 NEUTRAL | **0 FOR / 5 NEUTRAL — unanimous, stopped early** |
| 4% | 8 FOR / 2 NEUTRAL | 3 FOR / 7 NEUTRAL |
| 5% | 5 FOR / 5 NEUTRAL | 5 FOR / 5 NEUTRAL |

### The claimed threshold does not survive being tested

**For Kimi:** the real jump happens between 2% and 3% (40%→80% FOR), not
between 4% and 5% as the model itself claimed. 3% and 4% land in the same
place. 5% — the model's own stated threshold — is its *least* consistent point
of the four (a coin flip), not its most.

**For vLLM:** the pattern barely resembles a threshold at all. 3% is the
model's *most* decisive NEUTRAL point (unanimous, 0/5 FOR) — sandwiched between
2% (3/9 FOR) and 4% (3/10 FOR), both more favorable to FOR than the point in
between. 5% — again, the model's own stated threshold — is a coin flip, its
least decisive point.

**The one place the two providers agree: 5% is a toss-up for both** (5/10 FOR,
both). It is the single point both models named as "the" threshold, and it is
the one point where neither model is actually decisive.

## Read

This is the sharpest finding in this research, and it cuts against a specific,
tempting assumption: that asking a model to introspect on its own decision
process ("what would change your mind") produces a trustworthy account of that
process. It does not, here. Both models gave a **confident, specific, mutually
corroborating, wrong** answer. The stated explanation was fluent and internally
coherent — it named a real, relevant fact (revenue growth), used a plausible
number, and was repeated near-verbatim across a dozen independent draws — every
surface signal of a reliable answer was present, and the underlying claim still
did not hold up under direct test.

**Practical implication for anything built on top of these models' self-reports**
(a "why did AMI say this" explainer, a training/coaching feature that asks the
model to justify itself, a debugging aid that asks "what would you need to see
to change your call"): the answer will read as confident and specific whether or
not it is accurate. This research does not show that models' stated reasoning
is *always* wrong — only that it was wrong here, on a real prompt, tested
directly rather than taken on trust. Any feature that surfaces this kind of
self-explanation to a user should treat it as illustrative narrative, not as a
verified account of the model's actual decision boundary — and should not be
built as if asking the model "why" is itself a substitute for testing the claim.
