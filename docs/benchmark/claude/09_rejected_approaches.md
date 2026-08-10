# 09 — Approaches considered and rejected

Everything this study evaluated as a way to benchmark the Room and then killed,
with the reason and the pre-condition that would re-open it.

**Why this file exists.** Most of these are attractive on first contact — several
were proposed *during* this study before being worked through. Without a durable
record of why each was rejected, they get re-proposed by the next session that has
the same good idea. Each entry is written to be read by someone who is about to
suggest it.

Format mirrors
[`rejected_features_register.md`](../../initial_specs/11_decisions/rejected_features_register.md).

---

## R1 — Risk-adjusted excess return (M2) via a portfolio-level Room

**Rejected 2026-08-10. Closed in principle, not merely closed today.**

**The proposal.** M2 (alpha / Sharpe / information ratio) isn't computable because
the Room emits per-ticker verdicts and never builds a portfolio (`00` §4). The
obvious repair: have the Room drive a defined simulated portfolio — fixed universe,
assigned weights, a rebalance cadence, an exit rule. That creates an entity with a
real return series, so M2 becomes *defined*.

It becomes defined. It does not become obtainable.

**Why rejected — four independent reasons, each sufficient:**

**1. The time arithmetic doesn't end.** A Sharpe ratio's t-statistic is
approximately `SR × √years` (Lo 2002). To clear t = 1.96:

| True annualized Sharpe | Years of track record required |
|---|---|
| 1.0 | 3.8 |
| **0.5** | **15.4** |
| **0.3** | **42.7** |
| 0.2 | 96.0 |

A good-but-not-legendary active manager runs 0.3–0.5, so this is **15–40 years** of
uninterrupted track record — on a *fixed prompt generation*, which per `07` §1 we
do not hold stable for even a quarter. Every prompt change restarts the clock.
This is not a longer road than M1's n≈783; it is a road with no end.

Those years are computed from Lo's standard-error formula, not quoted from it, and
the formula assumes **IID returns** — which real strategies violate. Serial
correlation and fat tails inflate the true standard error, so **the table is
optimistic**.

**2. It would measure our design choices, not the Room.** Once universe, weights
and rebalance cadence are fixed, those decisions drive most of the realized
risk-adjusted return; security selection is the smaller term. We would build the
entire apparatus and then be unable to attribute the result to the agents — which
is the only thing we wanted to learn.

**3. The exit rule would have to be invented.** The Room has no SELL verdict
(`VerdictAction`, `backend/app/schemas/room.py:13-22`). Exits would run on
stop/target — and a substantial share of those levels are *minted constants*,
`entry × 0.94` and `entry × 1.13`, flagged `ami_default` in `level_provenance`.
The resulting Sharpe would materially be a property of two hardcoded numbers.

**4. It crosses the line in `08`.** A weighted portfolio with a rebalance schedule
and a published track record is precisely the artifact that reads as a performance
claim — on licensing, app-store-review, and plain-truthfulness grounds.

**Pre-condition to re-open.** All four would have to fall, and #1 cannot fall: it
is arithmetic, not engineering. Re-opening requires the product to have become
something else entirely — a tracked model-portfolio service with a decade-plus of
stable-prompt history and a licence to publish performance. That is not this
product.

**What we do instead.** Report the *distribution* of per-verdict excess return vs
SPY over the same window — median, quartiles, both tails (`06` M2). Honest, because
per-verdict is the unit the Room actually produces. **Never labelled risk-adjusted.**

---

## R2 — Comparing Room hit rates directly against SPIVA fund numbers

**Rejected — category error.**

SPIVA measures *portfolios, net of fees, against a benchmark, with survivorship
correction*. The Room has no portfolio and no fees. Placing "the Room hit X%" next
to "84% of funds underperform" invites a comparison neither number supports, and it
is the single most likely way for this research to be misused in a deck.

Kept as the **ceiling** comparator instead — evidence that "beat the market" is a
goal the professional industry fails at, which is a statement about *them*.

**Pre-condition to re-open:** none. The two quantities are not commensurable.
See `00` §4 and `08`.

---

## R3 — Replicating the sell-side long-short recommendation edge

**Rejected — structurally unavailable.**

Barber, Lehavy, McNichols & Trueman (2001) measured 75 bp/month by buying the
most-recommended and **shorting** the least-recommended. The Room is buy-side only
— APPROVE/MODIFY → Buy, PASS → Hold, no SELL. Roughly half the measured effect
comes from the short leg, which we cannot run.

Also worth remembering before anyone quotes the 75 bp: it is *gross*. The same
paper reports net abnormal returns "not reliably greater than zero."

**Pre-condition to re-open:** a SELL verdict action exists and is used. That is a
product decision with its own consequences, not a measurement change.

---

## R4 — Importing a fixed "% of stocks that beat the index" base rate

**Rejected — the base rate is not a constant.**

S&P's own measurement: **62%** of S&P 500 constituents beat the index in Q1 2025,
**29%** in Q2 2025. Consecutive quarters, 33 points apart. Any imported constant
would be a window choice disguised as a fact, and would make every hit-rate
comparison a function of which quarter we happened to pick.

**What we do instead.** Measure the base rate from our own universe over the
identical window — the random-pick control in `07` §3. It costs no LLM calls and
makes every later hit-rate number interpretable.

---

## R5 — Manufacturing a student/CFA outcome baseline

**Rejected — it would have been invented.**

The CFA Research Challenge does not track whether recommendations made money.
SMIF disclosures are self-published by the subset that chooses to publish —
survivorship in its purest form — across incomparable mandates. Any number
synthesised from that would be a survivorship-biased average dressed as a baseline.

`04` states the absence instead, and uses C4 as a **process-rubric** comparator,
which is the thing it can honestly supply — the full 100-point evaluation form.

**Pre-condition to re-open:** a survivorship-corrected cross-sectional study of
student fund performance is published. None exists.

---

## R6 — Reading `docs/benchmark/kimi/` while writing this

**Rejected — it would have destroyed the point.**

Kimi's parallel research was being written to the adjacent folder during this
study. Reading it would have made this document derivative and the two
non-independent, removing the entire value of having commissioned both.

Mirrored the comparator-first filenames only, so the two can be diffed cell by
cell. Divergences between them are the interesting output.

**Pre-condition to re-open:** n/a — both are now written. Future parallel studies
should hold the same rule.

---

## R7 — Leading with any Room outcome number at current sample sizes

**Rejected — we cannot support it.**

At n = 150, the 95% CI on a 37% rate is ±7.7 points, and the instrument's own
run-to-run flip rate is ~12% on a 4-of-32 estimate whose CI is **[1%, 24%]**. We do
not currently know whether the Room is near-deterministic or flips a quarter of its
verdicts.

**Pre-condition to re-open:** the n thresholds in `06`, plus a narrowed noise-floor
interval (`07` §7 item 4). Until then, outcome numbers are internal-only and
teaching-only per `08`.

---

Back to [`README.md`](README.md).
